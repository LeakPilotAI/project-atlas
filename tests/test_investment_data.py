"""Phase 2 investment data — mocked providers only. No live Yahoo in CI."""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.investment.bars import OhlcvBar
from app.investment.enums import AssetType, DataQuality
from app.investment.freshness import FreshnessRules, classify_freshness
from app.investment.history import append_bars, load_bars
from app.investment.ingest import InvestmentIngest
from app.investment.quality_report import summarize_snapshots
from app.investment.snapshot import persist_snapshot
from app.investment.universe import (
    InvestmentUniverse,
    UniverseEntry,
    load_example_universe,
    load_universe,
)
from app.investment.validate import validate_ohlc, validate_share_consistency
from app.investment.yahoo_fundamentals import YahooFundamentalProvider, YahooValuationProvider
from app.investment.yahoo_price import YahooPriceProvider, dataframe_to_bars
from app.investment.yfinance_client import ProviderCallError, is_usable_info, normalize_fast_info, wrap_provider_error


class FakeRow(dict):
    pass


class FakeDF:
    def __init__(self, rows, empty=False):
        self._rows = rows
        self.empty = empty

    def iterrows(self):
        for idx, data in self._rows:
            yield idx, FakeRow(data)


class FakeClient:
    def __init__(self, info=None, history=None, fail=False, fail_code="PROVIDER_ERROR"):
        self._info = info or {}
        self._history = history
        self._fail = fail
        self._fail_code = fail_code
        self.history_kwargs = None

    async def info(self, symbol: str):
        if self._fail:
            raise ProviderCallError(self._fail_code, "boom", symbol, retryable=True)
        return dict(self._info)

    async def history(self, symbol: str, **kwargs):
        self.history_kwargs = dict(kwargs)
        if self._fail:
            raise ProviderCallError(self._fail_code, "boom", symbol, retryable=True)
        if self._history is None:
            return FakeDF([], empty=True)
        return self._history


def test_universe_from_file_not_hardcoded(tmp_path):
    p = tmp_path / "universe.json"
    p.write_text(
        '{"assets":[{"symbol":"ZZZ","name":"Test","asset_type":"ETF","active":true}]}',
        encoding="utf-8",
    )
    u = load_universe(p)
    assert u.symbols() == ["ZZZ"]
    assert u.get("zzz").asset_type is AssetType.ETF
    empty = load_universe(tmp_path / "missing.json")
    assert len(empty) == 0


def test_example_universe_has_major_group_without_scoring_tickers():
    u = load_example_universe()
    types = {e.asset_type for e in u}
    assert AssetType.STOCK in types
    assert AssetType.ETF in types
    assert AssetType.INDEX in types
    assert AssetType.SECTOR_ETF in types
    majors = {e.symbol for e in u.by_group("major")}
    assert "NVDA" in majors and "MSFT" in majors and "SPY" in majors
    from app.investment import scoring as scoring_mod
    from app.investment import moves as moves_mod

    src = Path(inspect.getfile(scoring_mod)).read_text(encoding="utf-8")
    src_m = Path(inspect.getfile(moves_mod)).read_text(encoding="utf-8")
    for ticker in ("MSFT", "AAPL", "NVDA"):
        assert f'"{ticker}"' not in src
        assert f'"{ticker}"' not in src_m


def test_freshness_kinds_differ():
    now = datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc)
    recent = now - timedelta(minutes=5)
    day_old = now - timedelta(hours=20)
    month_old = now - timedelta(days=20)
    assert classify_freshness(recent, kind="price", now=now) is DataQuality.FRESH
    assert classify_freshness(day_old, kind="price", now=now) is DataQuality.STALE
    assert classify_freshness(day_old, kind="fundamental", now=now) is DataQuality.FRESH
    assert classify_freshness(month_old, kind="valuation", now=now) is DataQuality.STALE
    assert classify_freshness(None, kind="price") is DataQuality.UNKNOWN
    future = now + timedelta(hours=2)
    assert classify_freshness(future, kind="price", now=now) is DataQuality.UNKNOWN


def test_freshness_rules_are_configurable():
    now = datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc)
    ts = now - timedelta(minutes=30)
    tight = FreshnessRules(price=60)
    wide = FreshnessRules(price=3600)
    assert classify_freshness(ts, kind="price", now=now, rules=tight) is DataQuality.STALE
    assert classify_freshness(ts, kind="price", now=now, rules=wide) is DataQuality.FRESH


def test_ohlc_validation_flags_impossible_and_missing():
    bad = validate_ohlc(session_date="2024-01-01", open_=10, high=9, low=11, close=10, volume=-1)
    codes = {i.code for i in bad}
    assert "IMPOSSIBLE_OHLC" in codes
    assert "NEGATIVE_VOLUME" in codes
    miss = validate_ohlc(session_date=None, open_=None, high=1, low=1, close=1)
    assert any(i.code == "MISSING_OHLC" for i in miss)
    assert any(i.code == "INVALID_DATE" for i in miss)
    zero = validate_ohlc(session_date="2024-01-01", open_=0, high=1, low=0, close=1)
    assert any(i.code == "SUSPICIOUS_ZERO" for i in zero)


def test_share_consistency_flagged_not_repaired():
    issues = validate_share_consistency(shares=100, market_cap=1e12, price=10)
    assert any(i.code == "INCONSISTENT_SHARES" for i in issues)
    ok = validate_share_consistency(shares=1_000_000, market_cap=10_000_000, price=10)
    assert ok == []


def test_price_normalization_and_source_timestamp():
    ts = 1_700_000_000
    client = FakeClient(info={"regularMarketPrice": 12.5, "regularMarketTime": ts})
    p = YahooPriceProvider(client)

    async def _run():
        mv = await p.get_price("ZZZ")
        assert mv.value == 12.5
        assert mv.source == "yfinance"
        assert mv.timestamp is not None
        assert mv.retrieved_at is not None
        assert mv.effective_timestamp is not None
        assert mv.effective_timestamp.year == 2023
        assert mv.quality in (DataQuality.FRESH, DataQuality.STALE)
        assert mv.availability is True
        d = mv.as_dict()
        assert d["source"] == "yfinance"
        assert d["retrieved_at"]
        assert d["effective_timestamp"]
        assert d["quality"] in {"FRESH", "STALE"}

    asyncio.run(_run())


def test_missing_price_is_missing_not_zero():
    p = YahooPriceProvider(FakeClient(info={"regularMarketPrice": None}))

    async def _run():
        mv = await p.get_price("NONE")
        assert mv.value is None
        assert mv.quality is DataQuality.MISSING
        assert mv.availability is False

    asyncio.run(_run())


def test_provider_failure_no_crash_no_fake_number():
    p = YahooPriceProvider(FakeClient(fail=True))

    async def _run():
        mv = await p.get_price("ERR")
        assert mv.value is None
        assert mv.quality is DataQuality.MISSING
        assert p.last_failure is not None
        assert p.last_failure.code == "PROVIDER_ERROR"

    asyncio.run(_run())


def test_ohlcv_normalization_from_dataframe():
    df = FakeDF(
        [
            (
                datetime(2024, 1, 2, tzinfo=timezone.utc),
                {"Open": 10, "High": 11, "Low": 9.5, "Close": 10.5, "Volume": 1000, "Adj Close": 10.4},
            )
        ]
    )
    bars = dataframe_to_bars(df, source="yfinance", retrieved_at=datetime.now(timezone.utc))
    assert len(bars) == 1
    assert bars[0].session_date == "2024-01-02"
    assert bars[0].close == 10.5
    assert bars[0].source == "yfinance"
    assert bars[0].retrieved_at is not None
    assert bars[0].effective_timestamp is not None


def test_history_date_range_forwarded():
    client = FakeClient(history=FakeDF([], empty=True))
    p = YahooPriceProvider(client)

    async def _run():
        await p.get_daily_ohlcv("ZZZ", start="2024-01-01", end="2024-02-01")
        assert client.history_kwargs["start"] == "2024-01-01"
        assert client.history_kwargs["end"] == "2024-02-01"
        assert client.history_kwargs["interval"] == "1d"

    asyncio.run(_run())


def test_history_dedup(tmp_path):
    b = OhlcvBar(session_date="2024-01-02", open=1, high=2, low=0.5, close=1.5, volume=10, source="t")
    r1 = append_bars("AAA", [b, b], root=tmp_path)
    r2 = append_bars("AAA", [b], root=tmp_path)
    assert r1["written"] == 1
    assert r1["skipped_duplicate"] >= 1
    assert r2["written"] == 0
    assert len(load_bars("AAA", root=tmp_path)) == 1


def test_conflicting_ohlc_stored_not_repaired(tmp_path):
    b = OhlcvBar(session_date="2024-01-03", open=10, high=9, low=11, close=10, volume=1, source="t")
    r = append_bars("BBB", [b], root=tmp_path)
    assert r["written"] == 1
    assert r["flagged"] == 1
    loaded = load_bars("BBB", root=tmp_path)
    assert loaded[0].high == 9
    assert loaded[0].low == 11
    assert "IMPOSSIBLE_OHLC" in loaded[0].issues


def test_fundamentals_missing_and_present():
    info = {
        "totalRevenue": 1e9,
        "freeCashflow": 1e8,
        "sharesOutstanding": 5_000_000,
        "marketCap": 2e9,
    }
    f = YahooFundamentalProvider(FakeClient(info=info))

    async def _run():
        all_m = await f.get_all("ZZZ")
        assert all_m["revenue"].value == 1e9
        assert all_m["revenue"].source == "yfinance"
        assert all_m["revenue"].timestamp is not None
        assert all_m["revenue"].retrieved_at is not None
        assert all_m["revenue"].effective_timestamp is not None
        assert all_m["eps"].quality is DataQuality.MISSING
        assert all_m["eps"].value is None

    asyncio.run(_run())


def test_valuation_does_not_invent_yield():
    v = YahooValuationProvider(FakeClient(info={"trailingPE": 18.2, "marketCap": 1e9}))

    async def _run():
        all_m = await v.get_all("ZZZ")
        assert all_m["pe"].value == 18.2
        assert all_m["pe"].source == "yfinance"
        assert all_m["pe"].retrieved_at is not None
        assert all_m["fcf_yield"].quality is DataQuality.MISSING
        assert all_m["earnings_yield"].quality is DataQuality.MISSING
        assert all_m["price_to_fcf"].quality is DataQuality.MISSING
        assert all_m["fcf_yield"].value is None

    asyncio.run(_run())


def test_valuation_derived_only_with_both_inputs():
    v = YahooValuationProvider(
        FakeClient(info={"marketCap": 1e9, "freeCashflow": 1e8, "netIncomeToCommon": 5e7, "trailingPE": 20})
    )

    async def _run():
        all_m = await v.get_all("ZZZ")
        assert abs(all_m["fcf_yield"].value - 0.1) < 1e-9
        assert abs(all_m["price_to_fcf"].value - 10) < 1e-9
        assert abs(all_m["earnings_yield"].value - 0.05) < 1e-9

    asyncio.run(_run())


def test_snapshot_and_quality_report(tmp_path):
    entry = UniverseEntry(symbol="ZZZ", name="Test ETF", asset_type=AssetType.ETF)
    funds = YahooFundamentalProvider(FakeClient(info={"marketCap": 1e9, "totalRevenue": 1e8, "sharesOutstanding": 1e6}))
    val = YahooValuationProvider(FakeClient(info={"trailingPE": 20.0}))
    hist = FakeDF(
        [
            (
                datetime(2024, 6, 1, tzinfo=timezone.utc),
                {"Open": 10, "High": 11, "Low": 9, "Close": 10.5, "Volume": 100},
            )
        ]
    )
    price_h = YahooPriceProvider(
        FakeClient(info={"regularMarketPrice": 100.0, "regularMarketTime": 1_700_000_000}, history=hist)
    )

    async def _run():
        ing = InvestmentIngest(
            universe=InvestmentUniverse([entry]),
            price=price_h,
            fundamentals=funds,
            valuation=val,
            history_root=tmp_path / "hist",
            snapshot_path=tmp_path / "snaps.jsonl",
            persist=True,
        )
        snaps = await ing.ingest_universe()
        assert len(snaps) == 1
        s = snaps[0]
        assert s.asset.symbol == "ZZZ"
        assert s.price.value == 100.0
        assert s.price.retrieved_at is not None
        assert s.price.effective_timestamp is not None
        assert "revenue" in s.fundamentals
        assert "pe" in s.valuation
        text = summarize_snapshots(snaps)
        assert "Assets requested" in text
        assert "Price:" in text
        assert "Fundamentals:" in text
        assert "Valuation:" in text
        assert "Provider errors" in text
        assert (tmp_path / "snaps.jsonl").exists()
        assert (tmp_path / "hist" / "ZZZ.jsonl").exists()

    asyncio.run(_run())


def test_inactive_universe_entries_skipped(tmp_path):
    active = UniverseEntry(symbol="ON", name="On", asset_type=AssetType.ETF, active=True)
    off = UniverseEntry(symbol="OFF", name="Off", asset_type=AssetType.ETF, active=False)
    price = YahooPriceProvider(FakeClient(info={"regularMarketPrice": 1.0, "regularMarketTime": 1_700_000_000}))
    funds = YahooFundamentalProvider(FakeClient(info={}))
    val = YahooValuationProvider(FakeClient(info={}))

    async def _run():
        ing = InvestmentIngest(
            universe=InvestmentUniverse([active, off]),
            price=price,
            fundamentals=funds,
            valuation=val,
            history_root=tmp_path,
            persist=False,
        )
        snaps = await ing.ingest_universe()
        assert [s.asset.symbol for s in snaps] == ["ON"]

    asyncio.run(_run())


def test_rate_limit_error_is_structured():
    err = ProviderCallError("RATE_LIMIT", "429", "ZZZ", retryable=True)
    assert err.failure.retryable is True
    assert err.failure.code == "RATE_LIMIT"
    assert err.failure.symbol == "ZZZ"


def test_stub_yahoo_info_is_not_usable():
    assert is_usable_info({}) is False
    assert is_usable_info({"trailingPegRatio": None}) is False
    assert is_usable_info({"regularMarketPrice": 12.5}) is True
    mapped = normalize_fast_info({"lastPrice": 10.0, "marketCap": 1e9, "shares": 1e6})
    assert mapped["regularMarketPrice"] == 10.0
    assert mapped["marketCap"] == 1e9
    assert mapped["sharesOutstanding"] == 1e6


def test_error_classification_from_exceptions():
    assert wrap_provider_error(TimeoutError("timed out"), "ZZZ").failure.code == "TIMEOUT"
    assert wrap_provider_error(RuntimeError("HTTP 429 rate limit"), "ZZZ").failure.code == "RATE_LIMIT"
    assert wrap_provider_error(RuntimeError("Symbol may be delisted"), "NOPE").failure.code == "MISSING_TICKER"
    assert wrap_provider_error(RuntimeError("empty payload"), "ZZZ").failure.code == "EMPTY"
    assert wrap_provider_error(RuntimeError("boom"), "ZZZ").failure.code == "PROVIDER_ERROR"


def test_rate_limit_and_timeout_do_not_invent_prices():
    p = YahooPriceProvider(FakeClient(fail=True, fail_code="RATE_LIMIT"))
    t = YahooPriceProvider(FakeClient(fail=True, fail_code="TIMEOUT"))

    async def _run():
        a = await p.get_price("ZZZ")
        b = await t.get_price("ZZZ")
        assert a.value is None and a.quality is DataQuality.MISSING
        assert p.last_failure.code == "RATE_LIMIT"
        assert b.value is None and b.quality is DataQuality.MISSING
        assert t.last_failure.code == "TIMEOUT"

    asyncio.run(_run())


def test_empty_history_is_empty_not_fabricated():
    p = YahooPriceProvider(FakeClient(history=FakeDF([], empty=True)))

    async def _run():
        bars = await p.get_daily_ohlcv("ZZZ")
        assert bars == []

    asyncio.run(_run())


def test_missing_ticker_failure_is_structured():
    p = YahooPriceProvider(FakeClient(fail=True, fail_code="MISSING_TICKER"))

    async def _run():
        mv = await p.get_price("NOPE")
        assert mv.value is None
        assert mv.quality is DataQuality.MISSING
        assert p.last_failure.code == "MISSING_TICKER"

    asyncio.run(_run())


def test_persist_snapshot_appends(tmp_path):
    entry = UniverseEntry(symbol="ZZZ", name="Test", asset_type=AssetType.STOCK)
    price = YahooPriceProvider(FakeClient(info={"regularMarketPrice": 5.0, "regularMarketTime": 1_700_000_000}))
    funds = YahooFundamentalProvider(FakeClient(info={}))
    val = YahooValuationProvider(FakeClient(info={}))

    async def _run():
        ing = InvestmentIngest(
            universe=InvestmentUniverse([entry]),
            price=price,
            fundamentals=funds,
            valuation=val,
            history_root=tmp_path,
            snapshot_path=tmp_path / "snaps.jsonl",
            persist=True,
        )
        snaps = await ing.ingest_universe()
        persist_snapshot(snaps[0], path=tmp_path / "snaps.jsonl")
        lines = (tmp_path / "snaps.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    asyncio.run(_run())


def test_quality_report_counts_provider_errors(tmp_path):
    entry = UniverseEntry(symbol="ERR", name="Err", asset_type=AssetType.STOCK)
    price = YahooPriceProvider(FakeClient(fail=True, fail_code="RATE_LIMIT"))
    funds = YahooFundamentalProvider(FakeClient(fail=True, fail_code="RATE_LIMIT"))
    val = YahooValuationProvider(FakeClient(fail=True, fail_code="RATE_LIMIT"))

    async def _run():
        ing = InvestmentIngest(
            universe=InvestmentUniverse([entry]),
            price=price,
            fundamentals=funds,
            valuation=val,
            history_root=tmp_path,
            persist=False,
        )
        snaps = await ing.ingest_universe()
        assert snaps[0].price.value is None
        assert snaps[0].failures
        text = summarize_snapshots(snaps)
        assert "Provider errors" in text
        assert "Missing" in text

    asyncio.run(_run())
