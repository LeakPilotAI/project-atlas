"""Market reliability contracts; all clocks, providers and journals are isolated."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.adapters import hyperliquid as hl
from app.adapters import hyperliquid_cache as cache
from app.core.market_freshness import fresh_observation, positive_price
from app.investment import market_hours as calendar
from app.services.perp_setup_paper_mirror import PerpSetupPaperMirror

NOW = datetime(2026, 10, 16, 14, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("stamp,expected", [
    (None, False), ("", False), ("broken", False), (True, False),
    ("2026-10-16T14:00:00", False),
    ((NOW + timedelta(microseconds=1)).isoformat(), False),
    ((NOW - timedelta(seconds=30, microseconds=1)).isoformat(), False),
    ((NOW - timedelta(seconds=30)).isoformat(), True),
    (NOW.isoformat(), True), ("2026-10-16T09:00:00-05:00", True),
])
def test_authoritative_timestamp_boundaries(stamp, expected):
    assert fresh_observation(stamp, now=NOW) is expected


@pytest.mark.parametrize("price", [None, 0, -1, True, "nan", "inf", float("-inf")])
def test_nonfinite_or_invalid_price_rejected(price):
    assert not positive_price(price)


@pytest.mark.parametrize("evidence", [
    {}, {"updated_at": NOW.isoformat()}, {"mark_timestamp": None},
    {"mark_timestamp": "invalid"}, {"mark_timestamp": "2026-10-16T14:00:00"},
    {"mark_timestamp": (NOW + timedelta(seconds=1)).isoformat()},
    {"mark_timestamp": NOW.isoformat(),
     "price_timestamp": (NOW - timedelta(seconds=1)).isoformat()},
])
def test_paper_rejects_missing_future_invalid_and_conflicting_timestamps(monkeypatch, evidence):
    import app.core.market_freshness as freshness

    original = freshness.fresh_observation
    monkeypatch.setattr(freshness, "fresh_observation",
                        lambda value, **kw: original(value, now=NOW, **kw))
    assert not PerpSetupPaperMirror._fresh_mark_timestamp(evidence)


@pytest.mark.parametrize("age,expected", [(0, True), (30, True), (30.000001, False), (-0.001, False)])
def test_paper_exact_age_boundary(monkeypatch, age, expected):
    import app.core.market_freshness as freshness

    original = freshness.fresh_observation
    monkeypatch.setattr(freshness, "fresh_observation",
                        lambda value, **kw: original(value, now=NOW, **kw))
    stamp = (NOW - timedelta(seconds=age)).isoformat()
    assert PerpSetupPaperMirror._fresh_mark_timestamp({"mark_timestamp": stamp}) is expected


def rest(price="200"):
    return [{"universe": [{"name": "BTC"}]},
            [{"markPx": price, "dayNtlVlm": "10", "openInterest": "2", "funding": "-0.01"}]]


@pytest.fixture
def adapter_clock(monkeypatch):
    clock = [NOW]
    monkeypatch.setattr(hl, "datetime", SimpleNamespace(now=lambda zone: clock[0]))
    monkeypatch.setattr(hl, "fresh_observation",
                        lambda stamp, **kw: fresh_observation(stamp, now=clock[0], **kw))
    return clock


@pytest.mark.parametrize("ws_time", [None, NOW - timedelta(seconds=31), NOW + timedelta(seconds=1), NOW])
def test_untimestamped_ws_never_overrides_rest(adapter_clock, ws_time):
    adapter = hl.HyperliquidAdapter()
    adapter._mids["BTC"] = 100.0
    if ws_time:
        adapter._mid_received_at["BTC"] = ws_time

    async def provider(body):
        return rest()

    adapter._post = provider
    ticker = asyncio.run(adapter.get_all_tickers())[0]
    assert ticker.price == 200.0
    assert ticker.timestamp == NOW.isoformat()
    assert ticker.timestamp_basis == "REST_REQUEST_START"
    assert ticker.price_source == "REST_MARK"


def test_slow_rest_response_is_not_restamped(adapter_clock):
    adapter = hl.HyperliquidAdapter()

    async def provider(body):
        adapter_clock[0] += timedelta(seconds=31)
        return rest()

    adapter._post = provider
    with pytest.raises(ValueError, match="expired"):
        asyncio.run(adapter.get_all_tickers())


def test_conflicting_rest_observations_same_timestamp_fail_closed(adapter_clock):
    adapter = hl.HyperliquidAdapter()
    payload = [rest()]

    async def provider(body):
        return payload[0]

    adapter._post = provider
    asyncio.run(adapter.get_all_tickers())
    payload[0] = rest("201")
    with pytest.raises(ValueError, match="Conflicting"):
        asyncio.run(adapter.get_all_tickers())


@pytest.mark.asyncio
async def test_concurrent_older_response_cannot_supersede_newer(adapter_clock):
    adapter = hl.HyperliquidAdapter()
    waiting, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def provider(body):
        nonlocal calls
        calls += 1
        if calls == 1:
            waiting.set()
            await release.wait()
            return rest("100")
        return rest("200")

    adapter._post = provider
    old = asyncio.create_task(adapter.get_all_tickers())
    await waiting.wait()
    adapter_clock[0] += timedelta(seconds=1)
    assert (await adapter.get_all_tickers())[0].price == 200
    release.set()
    with pytest.raises(ValueError, match="Out-of-order"):
        await old
    assert adapter._last_rest_prices == {"BTC": 200}


@pytest.mark.asyncio
async def test_ws_disconnect_clears_receipts_before_reconnect_backoff(monkeypatch, adapter_clock):
    adapter = hl.HyperliquidAdapter()
    adapter._mids["BTC"] = 100
    adapter._mid_received_at["BTC"] = NOW
    adapter._ws_running = True
    attempted = []
    monkeypatch.setattr(adapter, "_consume_request", attempted.append)

    def broken_connect(*args, **kwargs):
        raise OSError("isolated disconnect")

    async def backoff(seconds):
        assert adapter.get_mid("BTC") is None
        assert not adapter._mids and not adapter._mid_received_at
        adapter._ws_running = False

    monkeypatch.setattr(hl, "websockets", SimpleNamespace(connect=broken_connect))
    monkeypatch.setattr(hl.asyncio, "sleep", backoff)
    await adapter._mids_loop()
    assert attempted == ["WEBSOCKET_CONNECT"]


@pytest.mark.asyncio
async def test_expired_cache_and_failed_feeds_produce_no_prices(monkeypatch):
    monkeypatch.setattr(cache, "_lock", asyncio.Lock())
    monkeypatch.setattr(cache, "_tickers", [{"symbol": "BTC", "price": 100,
                                            "timestamp": "2020-01-01T00:00:00Z"}])
    monkeypatch.setattr(cache, "_tickers_ts", 0)
    monkeypatch.setattr(cache, "_backoff_until", 0)

    async def unavailable():
        return []

    monkeypatch.setattr(cache, "_fetch_via_adapter", unavailable)
    monkeypatch.setattr(cache, "_fetch_direct", unavailable)
    assert await cache.get_tickers_cached(force=True) == []


@pytest.mark.parametrize("stamp,expected", [
    ("2026-07-03T15:00:00Z", "MARKET_CLOSED"),
    ("2027-06-18T15:00:00Z", "MARKET_CLOSED"),
    ("2028-01-01T15:00:00Z", "MARKET_CLOSED"),
    ("2027-12-31T15:00:00Z", "MARKET_OPEN"),
    ("2026-11-27T17:59:59Z", "MARKET_OPEN"),
    ("2026-11-27T18:00:00Z", "MARKET_CLOSED"),
    ("2026-12-24T18:00:00Z", "MARKET_CLOSED"),
    ("2028-07-03T17:00:00Z", "MARKET_CLOSED"),
    ("2029-01-02T15:00:00Z", "SYSTEM_OFFLINE"),
])
def test_calendar_holidays_early_closes_and_horizon(stamp, expected):
    assert calendar.session_status(datetime.fromisoformat(stamp)) == expected


@pytest.mark.parametrize("now,opening", [
    ("2026-03-06T22:00:00Z", "2026-03-09T13:30:00+00:00"),
    ("2026-10-30T22:00:00Z", "2026-11-02T14:30:00+00:00"),
    ("2026-07-02T22:00:00Z", "2026-07-06T13:30:00+00:00"),
    ("2026-11-25T22:00:00Z", "2026-11-27T14:30:00+00:00"),
])
def test_next_open_handles_weekends_holidays_and_dst(now, opening):
    assert calendar.next_session_open(datetime.fromisoformat(now)).isoformat() == opening


@pytest.mark.parametrize("seconds_before,expected", [(180, 180), (30, 60), (1, 60)])
def test_wake_at_open_with_existing_minimum_rate(seconds_before, expected):
    now = NOW.replace(hour=13, minute=30) - timedelta(seconds=seconds_before)
    assert calendar.next_scan_delay(now, open_seconds=900, closed_seconds=21600) == expected


@pytest.mark.asyncio
async def test_real_scanner_loop_uses_calendar_wakeup(monkeypatch):
    from app.investment import scan

    fake = SimpleNamespace(_running=True, system_ok=True)
    fake._cfg = lambda: SimpleNamespace(interval_open_seconds=900, interval_closed_seconds=21600)
    delays = []

    async def run_once():
        pass

    async def sleep(delay):
        delays.append(delay)
        fake._running = False

    fake.run_once = run_once
    monkeypatch.setattr(scan, "_now", lambda: NOW.replace(hour=13, minute=27))
    monkeypatch.setattr(scan.asyncio, "sleep", sleep)
    await scan.InvestmentScanner._loop(fake)
    assert delays == [180]


def test_opening_pass_refreshes_preopen_price_without_extra_fundamentals():
    from app.investment.scan import FetchState, plan_fetches
    from app.investment.scan_settings import ScanSettings

    state = FetchState(path=None)
    preopen = NOW.replace(hour=13, minute=29)
    state.touch("TEST", price=preopen, history=preopen, fundamentals=preopen, valuation=preopen)
    plan = plan_fetches("TEST", session="MARKET_OPEN", settings=ScanSettings(), state=state,
                       now=NOW.replace(hour=13, minute=30), has_prior=True, has_history=True)
    assert plan.price is True
    assert not plan.fundamentals and not plan.valuation and not plan.history


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,closes", [("fresh", 1), ("missing", 0), ("future", 0), ("stale", 0)])
async def test_open_position_outside_discovery_uses_independent_quote_evidence(
    monkeypatch, tmp_path, kind, closes,
):
    import app.services.perp_setup_paper_mirror as mirror_module

    class Journal:
        marked = 0
        closed = 0

        def list_open(self):
            return [{"trade_id": "isolated", "source": mirror_module.SOURCE, "symbol": "BTC",
                     "side": "LONG", "actual_entry_price": 100, "stop_price": 95,
                     "working_stop": 95, "tp1_price": 105, "working_target": 105}]

        def update_excursion(self, *args):
            self.marked += 1

        async def close_trade(self, *args, **kwargs):
            self.closed += 1

    journal = Journal()
    monkeypatch.setattr(mirror_module, "paper_journal", journal)
    mirror = PerpSetupPaperMirror(pending_path=tmp_path / "pending.jsonl")
    mirror._seeded = True
    current = datetime.now(timezone.utc)
    stamp = {"fresh": current, "missing": None, "future": current + timedelta(seconds=60),
             "stale": current - timedelta(seconds=31)}[kind]
    result = await mirror.sync([], {"BTC": 106}, price_timestamps={"BTC": stamp})
    assert journal.closed == closes
    assert journal.marked == closes
    assert result["closed"] == closes


@pytest.mark.parametrize("kind,expected", [("fresh", "HEALTHY"), ("stale", "STALE"),
                                          ("future", "UNAVAILABLE"), ("missing", "UNAVAILABLE")])
def test_manual_snapshot_rechecks_price_age_without_refetch(monkeypatch, kind, expected):
    import app.services.perp_manual_service as manual

    clock = [datetime.now(timezone.utc)]
    monkeypatch.setattr(manual, "fresh_observation",
                        lambda value, **kw: fresh_observation(value, now=clock[0], **kw))
    service = manual.PerpManualService()
    stamp = {"fresh": clock[0], "stale": clock[0] - timedelta(seconds=31),
             "future": clock[0] + timedelta(seconds=1), "missing": None}[kind]
    service.last_snapshot = {"markets": [{"symbol": "BTC", "price": 100,
                                          "timestamp": stamp.isoformat() if stamp else None}]}
    assert service.snapshot()["data_freshness"]["status"] == expected
    if kind == "fresh":
        clock[0] += timedelta(seconds=31)
        assert service.snapshot()["data_freshness"]["status"] == "STALE"

@pytest.mark.asyncio
@pytest.mark.parametrize("market_price,market_stamp", [
    (None, "fresh"),
    (0.0, "fresh"),
    (None, "stale"),
])
async def test_authoritative_market_price_cannot_fall_back_to_setup(
    monkeypatch, market_price, market_stamp, tmp_path
):
    from app.services.perp_setup_paper_mirror import PerpSetupPaperMirror
    from datetime import datetime, timedelta, timezone

    mirror = PerpSetupPaperMirror()
    now = datetime.now(timezone.utc)
    stamp = now if market_stamp == "fresh" else now - timedelta(minutes=5)

    setup = {
        "symbol": "BTC",
        "price": 100.0,
        "mark": 100.0,
        "mark_timestamp": now.isoformat(),
        "price_timestamp": now.isoformat(),
    }

    calls = []

    def record_arm(*args, **kwargs):
        calls.append((args, kwargs))
        return True

    monkeypatch.setattr(mirror, "_seed", lambda: None)
    monkeypatch.setattr(mirror, "_arm", record_arm)

    price_map = {} if market_price is None else {"BTC": market_price}

    await mirror.sync(
        [setup],
        price_map,
        price_timestamps={"BTC": stamp.isoformat()},
    )

    assert calls == [], "Setup-carried price must never authorize arming."
