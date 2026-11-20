"""Provider-shaped fixtures through normalization, retained SQLite, ASGI and HTML."""
import asyncio
import copy
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from app.investment.offline_research import ResearchInputRefused, equity_session

from scripts.observation_runtime.market_replay import (
    ReplayStore,
    create_replay_app,
    normalize_chart,
    normalize_quote,
)


def fixture(ts, symbol="SPY"):
    return {"chart": {"error": None, "result": [{"meta": {"symbol": symbol,
            "currency": "USD", "dataGranularity": "1m"}, "timestamp": [int(ts.timestamp())],
            "indicators": {"quote": [{"open": [100], "high": [102], "low": [99],
                                      "close": [101], "volume": [120]}]}}]}}


@pytest.mark.parametrize("stamp,session", [
    ("2026-10-20T12:00:00+00:00", "PRE_MARKET"),
    ("2026-10-20T14:00:00+00:00", "REGULAR"),
    ("2026-10-20T21:00:00+00:00", "AFTER_HOURS"),
    ("2026-11-27T18:00:00+00:00", "AFTER_HOURS"),
    ("2026-11-02T14:30:00+00:00", "REGULAR"),
])
def test_full_pipeline_restart_api_html(tmp_path, stamp, session):
    ts = datetime.fromisoformat(stamp)
    now = ts + timedelta(seconds=70)
    path = tmp_path / "isolated.db"
    with sqlite3.connect(path) as connection:
        store = ReplayStore(connection)
        assert store.ingest(fixture(ts), observed_at=now, asset_class="US_ETF") == 1
        assert store.ingest(fixture(ts), observed_at=now + timedelta(seconds=2), asset_class="US_ETF") == 0
    with sqlite3.connect(path) as connection:
        store = ReplayStore(connection)
        app = create_replay_app(store, symbols=["SPY", "MISSING"], clock=lambda: now)

        async def exercise():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
                result = (await client.get("/api/market-data")).json()
                row = next(r for r in result["rows"] if r["symbol"] == "SPY")
                assert (row["status"], row["session"], row["price"]) == ("FRESH", session, 101)
                assert result["network_authorized"] is False
                page = await client.get("/")
                assert "Synthetic fixtures only" in page.text
                assert f"<td>{session}</td>" in page.text
                assert "<td>UNAVAILABLE</td>" in page.text
                assert page.headers["cache-control"] == "no-store"
                assert (await client.post("/api/market-data")).status_code == 405
        asyncio.run(exercise())


@pytest.mark.parametrize("mutation", ["future", "partial", "missing", "null", "ohlc", "duplicate", "currency", "interval"])
def test_invalid_batch_no_write(mutation):
    ts = datetime(2026, 10, 20, 14, tzinfo=UTC)
    payload = fixture(ts)
    result = payload["chart"]["result"][0]
    now = ts + timedelta(seconds=70)
    if mutation == "future":
        result["timestamp"][0] += 120
    elif mutation == "partial":
        now = ts + timedelta(seconds=59)
    elif mutation == "missing":
        del result["timestamp"]
    elif mutation == "null":
        result["indicators"]["quote"][0]["close"] = [None]
    elif mutation == "ohlc":
        result["indicators"]["quote"][0]["high"] = [90]
    elif mutation == "duplicate":
        result["timestamp"] *= 2
        for key in result["indicators"]["quote"][0]:
            result["indicators"]["quote"][0][key] *= 2
    elif mutation == "currency":
        result["meta"]["currency"] = "EUR"
    else:
        result["meta"]["dataGranularity"] = "1d"
    with sqlite3.connect(":memory:") as connection:
        store = ReplayStore(connection)
        with pytest.raises(ResearchInputRefused):
            store.ingest(payload, observed_at=now, asset_class="US_ETF")
        assert connection.execute("SELECT count(*) FROM replay_bars").fetchone()[0] == 0


def test_conflict_rollback_stale_and_integrity():
    ts = datetime(2026, 10, 20, 14, tzinfo=UTC)
    now = ts + timedelta(seconds=70)
    with sqlite3.connect(":memory:") as connection:
        store = ReplayStore(connection)
        store.ingest(fixture(ts), observed_at=now, asset_class="US_EQUITY")
        changed = copy.deepcopy(fixture(ts))
        changed["chart"]["result"][0]["indicators"]["quote"][0]["close"] = [100]
        with pytest.raises(ResearchInputRefused, match="Conflicting"):
            store.ingest(changed, observed_at=now, asset_class="US_EQUITY")
        stale = store.snapshot(["SPY"], now=now + timedelta(minutes=4))["rows"][0]
        assert stale["price"] is None and stale["reference_close"] == 101
        connection.execute("UPDATE replay_bars SET body=replace(body,'101.0','102.0')")
        with pytest.raises(ResearchInputRefused, match="integrity"):
            store.snapshot(["SPY"], now=now)


@pytest.mark.parametrize("stamp", ["2026-11-26T14:00:00+00:00", "2026-10-24T14:00:00+00:00"])
def test_holiday_weekend_refused(stamp):
    ts = datetime.fromisoformat(stamp)
    assert equity_session(ts) == "CLOSED"
    with pytest.raises(ResearchInputRefused):
        normalize_chart(fixture(ts), observed_at=ts + timedelta(minutes=2), asset_class="US_ETF")


def test_transaction_rolls_back_new_bar_before_conflict():
    ts = datetime(2026, 10, 20, 14, tzinfo=UTC)
    now = ts + timedelta(minutes=3)
    with sqlite3.connect(":memory:") as connection:
        store = ReplayStore(connection)
        store.ingest(fixture(ts + timedelta(minutes=1)), observed_at=now, asset_class="US_ETF")
        payload = fixture(ts)
        result = payload["chart"]["result"][0]
        result["timestamp"].append(int((ts + timedelta(minutes=1)).timestamp()))
        for key, values in result["indicators"]["quote"][0].items():
            values.append(100 if key == "close" else values[0])
        with pytest.raises(ResearchInputRefused, match="Conflicting"):
            store.ingest(payload, observed_at=now, asset_class="US_ETF")
        assert connection.execute("SELECT count(*) FROM replay_bars").fetchone()[0] == 1


def test_commit_failure_not_acknowledged():
    class BrokenConnection(sqlite3.Connection):
        fail = False

        def __exit__(self, *args):
            if self.fail:
                self.rollback()
                raise OSError("synthetic storage commit failure")
            return super().__exit__(*args)

    with sqlite3.connect(":memory:", factory=BrokenConnection) as connection:
        store = ReplayStore(connection)
        connection.fail = True
        ts = datetime(2026, 10, 20, 14, tzinfo=UTC)
        with pytest.raises(OSError, match="commit failure"):
            store.ingest(fixture(ts), observed_at=ts + timedelta(minutes=2), asset_class="US_ETF")
        assert connection.execute("SELECT count(*) FROM replay_bars").fetchone()[0] == 0
        connection.fail = False


def test_gap_diagnostics_do_not_impute_or_claim_open_coverage():
    ts = datetime(2026, 10, 20, 14, tzinfo=UTC)
    now = ts + timedelta(minutes=4)
    with sqlite3.connect(":memory:") as connection:
        store = ReplayStore(connection)
        for offset in (0, 2):
            store.ingest(fixture(ts + timedelta(minutes=offset)), observed_at=now, asset_class="US_ETF")
        row = store.snapshot(["SPY"], now=now)["rows"][0]
        assert row["coverage"]["status"] == "GAPS"
        assert row["coverage"]["missing_minutes"] == 1
        assert row["coverage"]["observed_bars"] == 2
        assert row["price"] == 101
        assert "NOT_FULL_SESSION" in row["coverage"]["scope"]


def test_retained_key_substitution_refused():
    ts = datetime(2026, 10, 20, 14, tzinfo=UTC)
    now = ts + timedelta(minutes=2)
    with sqlite3.connect(":memory:") as connection:
        store = ReplayStore(connection)
        store.ingest(fixture(ts), observed_at=now, asset_class="US_ETF")
        connection.execute("UPDATE replay_bars SET symbol='QQQ'")
        with pytest.raises(ResearchInputRefused, match="identity"):
            store.snapshot(["QQQ"], now=now)


def test_replay_cannot_display_observation_before_receipt():
    ts = datetime(2026, 10, 20, 14, tzinfo=UTC)
    with sqlite3.connect(":memory:") as connection:
        store = ReplayStore(connection)
        store.ingest(fixture(ts), observed_at=ts + timedelta(minutes=3), asset_class="US_ETF")
        row = store.snapshot(["SPY"], now=ts + timedelta(minutes=2))["rows"][0]
        assert row["status"] == "NOT_YET_OBSERVED"
        assert row["price"] is None and row["reference_close"] is None


def quote_fixture(ts):
    return {"quoteResponse": {"error": None, "result": [{"symbol": "SPY", "currency": "USD",
            "exchangeDataDelayedBy": 0, **{p + k: v for p in ("preMarket", "regularMarket", "postMarket")
                                         for k, v in (("Time", int(ts.timestamp())), ("Price", 103))}}]}}


@pytest.mark.parametrize("hour,session", [(12, "PRE_MARKET"), (14, "REGULAR"), (21, "AFTER_HOURS")])
def test_quote_normalization_session_and_persistence(hour, session):
    ts = datetime(2026, 10, 20, hour, tzinfo=UTC)
    now = ts + timedelta(seconds=10)
    with sqlite3.connect(":memory:") as connection:
        store = ReplayStore(connection)
        assert store.ingest_quote(quote_fixture(ts), observed_at=now, asset_class="US_ETF") == 1
        assert store.ingest_quote(quote_fixture(ts), observed_at=now, asset_class="US_ETF") == 0
        row = store.quote_snapshot(["SPY"], now=now)[0]
        assert (row["session"], row["status"], row["price"]) == (session, "FRESH", 103)
        assert store.quote_snapshot(["SPY"], now=now + timedelta(seconds=31))[0]["price"] is None


@pytest.mark.parametrize("mutation", ["missing_session", "future", "naive", "delay", "boolean", "currency"])
def test_quote_refuses_invalid_or_fallback_evidence(mutation):
    ts = datetime(2026, 10, 20, 12, tzinfo=UTC)
    payload = quote_fixture(ts)
    row = payload["quoteResponse"]["result"][0]
    now = ts + timedelta(seconds=5)
    if mutation == "missing_session":
        del row["preMarketTime"]
    elif mutation == "future":
        row["preMarketTime"] += 10
    elif mutation == "naive":
        now = now.replace(tzinfo=None)
    elif mutation == "delay":
        del row["exchangeDataDelayedBy"]
    elif mutation == "boolean":
        row["preMarketPrice"] = True
    else:
        row["currency"] = "EUR"
    with pytest.raises(ResearchInputRefused):
        normalize_quote(payload, observed_at=now, asset_class="US_ETF")


def test_delayed_quote_never_current_and_older_quote_never_overrides():
    ts = datetime(2026, 10, 20, 14, tzinfo=UTC)
    now = ts + timedelta(seconds=20)
    with sqlite3.connect(":memory:") as connection:
        store = ReplayStore(connection)
        delayed = quote_fixture(ts)
        delayed["quoteResponse"]["result"][0]["exchangeDataDelayedBy"] = 900
        store.ingest_quote(delayed, observed_at=now, asset_class="US_ETF")
        store.ingest_quote(quote_fixture(ts - timedelta(seconds=10)), observed_at=now, asset_class="US_ETF")
        row = store.quote_snapshot(["SPY"], now=now)[0]
        assert row["status"] == "DELAYED" and row["price"] is None
        assert row["reference_price"] == 103
        assert row["timestamp"] == ts.isoformat()


def test_quotes_and_bars_are_separate_in_actual_api_and_dashboard():
    ts = datetime(2026, 10, 20, 14, tzinfo=UTC)
    now = ts + timedelta(seconds=70)
    with sqlite3.connect(":memory:") as connection:
        store = ReplayStore(connection)
        store.ingest(fixture(ts), observed_at=now, asset_class="US_ETF")
        store.ingest_quote(quote_fixture(now - timedelta(seconds=2)), observed_at=now, asset_class="US_ETF")
        app = create_replay_app(store, symbols=["SPY"], clock=lambda: now)
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
                response = (await client.get("/api/market-data")).json()
                assert response["rows"][0]["price"] == 101
                assert response["quote_rows"][0]["price"] == 103
                assert "Timestamped quote references" in (await client.get("/")).text
        asyncio.run(check())


def test_historical_api_is_bounded_sorted_and_universe_scoped():
    ts = datetime(2026, 10, 20, 14, tzinfo=UTC)
    now = ts + timedelta(minutes=5)
    with sqlite3.connect(":memory:") as connection:
        store = ReplayStore(connection)
        for offset in (2, 0, 3):
            store.ingest(fixture(ts + timedelta(minutes=offset)), observed_at=now, asset_class="US_ETF")
        app = create_replay_app(store, symbols=["SPY"], clock=lambda: now)
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
                response = await client.get("/api/market-data/history", params={"symbol": "SPY", "limit": 2})
                data = response.json()
                assert data["more_retained_rows"] is True
                assert [r["timestamp"] for r in data["rows"]] == [(ts + timedelta(minutes=i)).isoformat() for i in (2, 3)]
                assert all("price" not in r for r in data["rows"])
                assert (await client.get("/api/market-data/history", params={"symbol": "SPY", "limit": 1001})).status_code == 422
                assert (await client.get("/api/market-data/history", params={"symbol": "QQQ"})).status_code == 404
        asyncio.run(check())


def test_historical_read_preserves_receipt_vintage():
    ts = datetime(2026, 10, 20, 14, tzinfo=UTC)
    with sqlite3.connect(":memory:") as connection:
        store = ReplayStore(connection)
        store.ingest(fixture(ts), observed_at=ts + timedelta(minutes=5), asset_class="US_ETF")
        assert store.history("SPY", now=ts + timedelta(minutes=3))["rows"] == []
        assert len(store.history("SPY", now=ts + timedelta(minutes=5))["rows"]) == 1


def test_historical_read_refuses_corrupt_older_bar():
    ts = datetime(2026, 10, 20, 14, tzinfo=UTC)
    now = ts + timedelta(minutes=5)
    with sqlite3.connect(":memory:") as connection:
        store = ReplayStore(connection)
        for offset in (0, 2):
            store.ingest(fixture(ts + timedelta(minutes=offset)), observed_at=now, asset_class="US_ETF")
        connection.execute("UPDATE replay_bars SET digest='invalid' WHERE event_time=?", (ts.isoformat(),))
        with pytest.raises(ResearchInputRefused, match="integrity"):
            store.history("SPY", now=now)


def test_current_api_matches_actual_frontend_contract_fixture():
    ts = datetime(2026, 10, 20, 12, tzinfo=UTC)
    now = ts + timedelta(seconds=70)
    expected = json.loads((Path(__file__).parent / "fixtures/market-replay-v1/api.json").read_bytes())
    with sqlite3.connect(":memory:") as connection:
        store = ReplayStore(connection)
        store.ingest(fixture(ts), observed_at=now, asset_class="US_ETF")
        store.ingest_quote(quote_fixture(now - timedelta(seconds=2)), observed_at=now, asset_class="US_ETF")
        app = create_replay_app(store, symbols=["SPY", "MISSING"], clock=lambda: now)
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
                response = await client.get("/api/market-data")
                assert response.headers["cache-control"] == "no-store"
                assert response.json() == expected
        asyncio.run(check())


@pytest.mark.parametrize('surface',['bar','quote'])
def test_winter_after_hours_crosses_utc_midnight_same_exchange_date(surface):
    now = datetime(2026, 11, 3, 0, 0, 10, tzinfo=UTC)
    with sqlite3.connect(":memory:") as connection:
        store=ReplayStore(connection)
        if surface=='bar':
            store.ingest(fixture(now.replace(second=0)-timedelta(minutes=1)),observed_at=now,asset_class='US_ETF')
            row=store.snapshot(['SPY'],now=now)['rows'][0]
        else:
            store.ingest_quote(quote_fixture(now-timedelta(seconds=15)),observed_at=now,asset_class='US_ETF')
            row=store.quote_snapshot(['SPY'],now=now)[0]
        assert row['session']=='AFTER_HOURS'
        assert row['status']=='FRESH'
        assert row['price'] is not None


def test_coverage_uses_exchange_day_across_utc_midnight():
    ts=datetime(2026,11,2,23,58,tzinfo=UTC)
    now=ts+timedelta(minutes=4,seconds=10)
    with sqlite3.connect(':memory:') as connection:
        store=ReplayStore(connection)
        for offset in (0,2,3):
            store.ingest(fixture(ts+timedelta(minutes=offset)),observed_at=now,asset_class='US_ETF')
        coverage=store.snapshot(['SPY'],now=now)['rows'][0]['coverage']
        assert coverage['observed_bars']==3
        assert coverage['missing_minutes']==1
        assert coverage['status']=='GAPS'


def test_current_coverage_reads_index_bounded_exchange_day_only():
    now=datetime(2026,10,20,14,2,tzinfo=UTC)
    with sqlite3.connect(':memory:') as connection:
        store=ReplayStore(connection)
        old=datetime(2026,10,19,14,tzinfo=UTC)
        store.ingest(fixture(old),observed_at=now,asset_class='US_ETF')
        store.ingest(fixture(now-timedelta(minutes=1)),observed_at=now,asset_class='US_ETF')
        connection.execute("UPDATE replay_bars SET digest='invalid' WHERE event_time=?",(old.isoformat(),))
        coverage=store.snapshot(['SPY'],now=now)['rows'][0]['coverage']
        assert coverage['observed_bars']==1
        plan=connection.execute('EXPLAIN QUERY PLAN SELECT body,digest,event_time FROM replay_bars '
            'WHERE symbol=? AND event_time>=? AND event_time<=? ORDER BY event_time DESC LIMIT 10001',
            ('SPY','2026-10-20T04:00:00+00:00',now.isoformat())).fetchall()
        assert any('SEARCH' in row[3] and 'INDEX' in row[3] for row in plan)
        with pytest.raises(ResearchInputRefused,match='integrity'):store.history('SPY',now=now)
