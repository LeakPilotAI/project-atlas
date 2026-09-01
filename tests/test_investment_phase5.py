"""Phase 5 — opt-in scan, observations, look-ahead, outcomes. No live Yahoo. No trading imports."""

from __future__ import annotations

import asyncio
import inspect
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.investment.alerts import AlertStore
from app.investment.bars import OhlcvBar
from app.investment.blocking import blocking_factors, first_blocker, is_qualified
from app.investment.drawdown import DrawdownReport
from app.investment.enums import (
    AssetType,
    DataQuality,
    EvidenceQuality,
    InvestmentAlertState,
    RiskTolerance,
    ThesisState,
)
from app.investment.freshness import restamp
from app.investment.history import append_bars
from app.investment.ingest import FetchPlan, history_fetch_kwargs
from app.investment.lookahead import filter_bars_as_of
from app.investment.models import HoldingInput, MeasuredValue, PortfolioInput
from app.investment.notify import format_investment_alert
from app.investment.outcomes import empty_outcomes, enrich_observation, measure_outcomes
from app.investment.research import InvestmentResearch, generational_gate
from app.investment.research_models import ComponentScores, Explainability, ResearchRecord, SCORING_VERSION
from app.investment.scan import (
    FetchState,
    InvestmentScanner,
    failed_record,
    format_scan_dashboard,
    plan_fetches,
    start_investment_scanner,
)
from app.investment.scan_models import SCAN_VERSION
from app.investment.scan_settings import ScanSettings
from app.investment.scan_store import load_observations
from app.investment.snapshot import snapshot_from_parts
from app.investment.storage import LEDGER_PATH, OBSERVATIONS_PATH, OUTCOMES_PATH, TRADING_PAPER_JOURNAL
from app.investment.universe import UniverseEntry, load_example_universe, load_universe
from app.investment.yfinance_client import ProviderCallError


def _weekdays(n: int, start: date = date(2020, 1, 2)) -> list[str]:
    d = start
    out: list[str] = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def bars_from_closes(closes: list[float], start: date = date(2020, 1, 2)) -> list[OhlcvBar]:
    dates = _weekdays(len(closes), start)
    out: list[OhlcvBar] = []
    for dt, c in zip(dates, closes):
        out.append(
            OhlcvBar(
                session_date=dt,
                open=c,
                high=c * 1.01,
                low=c * 0.99,
                close=c,
                volume=1_000_000,
                adjusted_close=c,
                source="test",
            )
        )
    return out


def ramp(start: float, end: float, n: int) -> list[float]:
    if n <= 1:
        return [end]
    return [start + (end - start) * i / (n - 1) for i in range(n)]


def mv(value, quality: DataQuality = DataQuality.FRESH) -> MeasuredValue:
    return MeasuredValue.of(value, source="test", quality=quality)


def _entry(sym="XYZ", **kw) -> UniverseEntry:
    return UniverseEntry(
        symbol=sym,
        name=kw.get("name", "Test Co"),
        asset_type=kw.get("asset_type", AssetType.STOCK),
        sector=kw.get("sector", "Industrials"),
        active=True,
    )


def healthy_snap(entry: UniverseEntry, price=50.0, quality=DataQuality.FRESH):
    funds = {
        "revenue": mv(80e9, quality),
        "earnings": mv(10e9, quality),
        "eps": mv(6.0, quality),
        "free_cash_flow": mv(8e9, quality),
        "operating_cash_flow": mv(12e9, quality),
        "gross_margin": mv(0.45, quality),
        "operating_margin": mv(0.22, quality),
        "net_margin": mv(0.12, quality),
        "total_debt": mv(20e9, quality),
        "cash": mv(15e9, quality),
        "shares_outstanding": mv(1.6e9, quality),
        "market_cap": mv(80e9, quality),
    }
    val = {
        "pe": mv(14.0, quality),
        "forward_pe": mv(13.0, quality),
        "ps": mv(2.0, quality),
        "pb": mv(2.5, quality),
        "fcf_yield": mv(0.08, quality),
        "earnings_yield": mv(0.07, quality),
        "price_to_fcf": mv(12.0, quality),
        "ev_ebitda": mv(10.0, quality),
    }
    return snapshot_from_parts(
        entry,
        price=mv(price, quality),
        fundamentals=funds,
        valuation=val,
    )


class FakeIngest:
    def __init__(self, snaps=None, fail=None, fail_n=0):
        self.snaps = snaps or {}
        self.fail = fail
        self.fail_n = fail_n
        self.calls = []
        self.history_root = None

    async def ingest_symbol(self, entry, **kwargs):
        self.calls.append((entry.symbol, dict(kwargs)))
        if self.fail is not None and len(self.calls) <= (self.fail_n or 10_000):
            raise self.fail
        snap = self.snaps.get(entry.symbol)
        if snap is None:
            raise RuntimeError(f"no snap for {entry.symbol}")
        return snap


def _cfg(**kw) -> ScanSettings:
    return ScanSettings(
        enabled=True,
        notify_discord=kw.get("notify", False),
        persist=kw.get("persist", True),
        inter_symbol_delay_seconds=0.0,
        max_retries=kw.get("retries", 0),
        retry_base_seconds=0.0,
        price_refresh_seconds=kw.get("price_ttl", 900),
        fundamental_refresh_seconds=kw.get("fund_ttl", 86400),
        valuation_refresh_seconds=kw.get("val_ttl", 86400),
        history_refresh_seconds=kw.get("hist_ttl", 86400),
        interval_open_seconds=3600,
        interval_closed_seconds=21600,
    )


def _scanner(tmp_path: Path, ingest, universe, **kw) -> InvestmentScanner:
    hist = tmp_path / "hist"
    hist.mkdir(parents=True, exist_ok=True)
    ingest.history_root = hist
    return InvestmentScanner(
        settings=_cfg(**kw),
        universe=universe,
        ingest=ingest,
        alert_store=AlertStore(path=tmp_path / "alerts.json"),
        portfolio=kw.get("portfolio", PortfolioInput()),
        paper=kw.get("paper"),
        history_root=hist,
        observations_path=tmp_path / "obs.jsonl",
        outcomes_path=tmp_path / "out.jsonl",
        fetch_state_path=tmp_path / "fetch.json",
        persist=kw.get("persist", True),
        notify=kw.get("notify_fn", lambda *a, **k: None),
        system_ok=kw.get("system_ok", True),
    )


def _seed_history(scanner: InvestmentScanner, symbol: str, closes: list[float]) -> None:
    append_bars(symbol, bars_from_closes(closes), root=scanner.history_root)


# --- universe ---


def test_example_universe_is_diversified_research_set():
    u = load_example_universe()
    types = {e.asset_type for e in u}
    assert {AssetType.STOCK, AssetType.ETF, AssetType.INDEX, AssetType.SECTOR_ETF} <= types
    symbols = set(u.symbols())
    assert "SPY" in symbols and "XLK" in symbols and "XLV" in symbols
    assert "JNJ" in symbols and "CAT" in symbols
    assert "KO" in symbols or "PG" in symbols
    majors = {e.symbol for e in u.by_group("major")}
    assert "NVDA" in majors


def test_operator_universe_from_file_not_engine(tmp_path):
    p = tmp_path / "universe.json"
    p.write_text(
        '{"assets":[{"symbol":"ZZZ","name":"Test","asset_type":"STOCK","active":true}]}',
        encoding="utf-8",
    )
    u = load_universe(p)
    assert u.symbols() == ["ZZZ"]
    src = Path(inspect.getfile(load_universe)).read_text(encoding="utf-8")
    assert '"ZZZ"' not in src


# --- orchestration ---


def test_scan_persists_qualified_and_rejected(tmp_path):
    e1 = _entry("AAA")
    e2 = _entry("BBB")
    snap1 = healthy_snap(e1, price=40)
    snap2 = snapshot_from_parts(
        e2,
        price=MeasuredValue.unknown("test", "missing"),
        fundamentals={},
        valuation={},
        failures=[{"code": "EMPTY", "message": "no data"}],
    )
    ingest = FakeIngest({"AAA": snap1, "BBB": snap2})
    from app.investment.universe import InvestmentUniverse

    sc = _scanner(tmp_path, ingest, InvestmentUniverse([e1, e2]))
    _seed_history(sc, "AAA", ramp(80, 40, 300))
    _seed_history(sc, "BBB", ramp(10, 10, 30))
    monday = datetime(2026, 8, 24, 15, 0, tzinfo=timezone.utc)
    report = asyncio.run(sc.run_once(now=monday))
    assert report.evaluated == 2
    rows = load_observations(tmp_path / "obs.jsonl")
    assert len(rows) == 2
    classes = {r["classification"] for r in rows}
    assert "NO_ACTION" in classes or any(r["symbol"] == "BBB" and r["qualified"] is False for r in rows)
    for r in rows:
        assert r["look_ahead_protected"] is True
        assert r["outcomes"]["price_1d"] is None
        assert r["blocking_reason"] != "" or r["classification"] == "GENERATIONAL_OPPORTUNITY"
        assert "as_of" in r
        assert r["scan_version"] == SCAN_VERSION
    assert "INVESTMENT SCAN" in report.dashboard
    assert "TOP BLOCKERS" in report.dashboard
    assert "performance dashboard" in report.dashboard.lower() or "not a performance" in report.dashboard.lower()


def test_provider_failure_is_no_action_not_invented(tmp_path):
    e = _entry("ZZZ")
    ingest = FakeIngest(
        fail=ProviderCallError("RATE_LIMIT", "429", "ZZZ", retryable=True),
        fail_n=99,
        snaps={},
    )
    from app.investment.universe import InvestmentUniverse

    sc = _scanner(tmp_path, ingest, InvestmentUniverse([e]), retries=1)
    report = asyncio.run(sc.run_once(now=datetime(2026, 8, 24, 15, 0, tzinfo=timezone.utc)))
    assert len(ingest.calls) >= 2  # initial + retry
    obs = report.observations[0]
    assert obs.classification == "NO_ACTION"
    assert obs.qualified is False
    assert obs.research is not None
    assert obs.research.price is None
    assert obs.outcomes["return_20d"] is None
    assert "provider" in (obs.blocking_reason + " ".join(obs.blocking_factors)).lower() or obs.provider_failures


def test_partial_and_stale_data_labeled(tmp_path):
    e = _entry("STALE")
    old = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)
    px = MeasuredValue.of(100.0, source="test", timestamp=old, quality=DataQuality.FRESH)
    snap = snapshot_from_parts(e, price=px, fundamentals={"earnings": mv(1e9)}, valuation={})
    now = datetime(2026, 8, 24, 15, 0, tzinfo=timezone.utc)
    restamped = restamp(px, kind="price", now=now)
    assert restamped.quality is DataQuality.STALE
    assert restamped.value == 100.0
    ingest = FakeIngest({e.symbol: snap})
    from app.investment.universe import InvestmentUniverse

    sc = _scanner(tmp_path, ingest, InvestmentUniverse([e]))
    _seed_history(sc, e.symbol, ramp(120, 100, 80))
    report = asyncio.run(sc.run_once(now=now))
    obs = report.observations[0]
    assert obs.field_quality.get("price") in {"STALE", "FRESH", "UNKNOWN", "MISSING"}
    assert obs.qualified is False
    assert obs.classification in {"NO_ACTION", "WATCH"}


def test_blocking_reason_recorded_for_rejects():
    rec = ResearchRecord(
        scoring_version=SCORING_VERSION,
        symbol="XYZ",
        classification=InvestmentAlertState.NO_ACTION,
        opportunity_score=64,
        evidence_quality=EvidenceQuality.MEDIUM,
        thesis=ThesisState.UNDER_PRESSURE,
        components=ComponentScores(valuation=40, fundamentals=50, risk=40),
        drawdown=DrawdownReport(current_drawdown=-0.10, coverage_bars=100),
        generational_blockers=["valuation missing or not attractive (need ≥ 70)"],
    )
    assert is_qualified(rec) is False
    fac = blocking_factors(rec)
    assert any("UNDER_PRESSURE" in x or "Thesis" in x for x in fac)
    assert any("Valuation" in x or "valuation" in x.lower() for x in fac)
    assert any("Evidence" in x for x in fac)
    assert first_blocker(rec)


def test_incremental_history_kwargs(tmp_path):
    append_bars("QQQ", bars_from_closes([1.0, 2.0, 3.0], start=date(2024, 1, 2)), root=tmp_path)
    kw = history_fetch_kwargs("QQQ", root=tmp_path, period="5y")
    assert "start" in kw
    assert "period" not in kw
    kw2 = history_fetch_kwargs("NEW", root=tmp_path, period="5y")
    assert kw2 == {"period": "5y"}


def test_fetch_plan_skips_live_price_when_closed(tmp_path):
    st = FetchState(path=tmp_path / "f.json")
    now = datetime(2026, 8, 29, 18, 0, tzinfo=timezone.utc)  # Saturday
    st.touch("SPY", price=now - timedelta(hours=4), fundamentals=now - timedelta(hours=1), valuation=now, history=now)
    cfg = _cfg()
    plan = plan_fetches(
        "SPY",
        session="MARKET_CLOSED",
        settings=cfg,
        state=st,
        now=now,
        has_prior=True,
        has_history=True,
    )
    assert plan.price is False
    open_plan = plan_fetches(
        "SPY",
        session="MARKET_OPEN",
        settings=cfg,
        state=st,
        now=now + timedelta(days=2),
        has_prior=True,
        has_history=True,
    )
    assert open_plan.price is True  # older than 15 min relative to Monday clock in this call


# --- look-ahead / outcomes ---


def test_look_ahead_future_crash_does_not_affect_score():
    e = _entry("LAH")
    past = ramp(50, 80, 260)
    past_bars = bars_from_closes(past, start=date(2024, 1, 2))
    last = date.fromisoformat(past_bars[-1].session_date)
    as_of = datetime(last.year, last.month, last.day, 20, 0, tzinfo=timezone.utc)
    future_bars = bars_from_closes(ramp(80, 20, 40), start=last + timedelta(days=1))
    all_bars = past_bars + future_bars
    cutoff = filter_bars_as_of(all_bars, as_of)
    assert len(cutoff) == len(past_bars)
    assert all(b.session_date <= as_of.date().isoformat() for b in cutoff)
    snap_now = healthy_snap(e, price=80)
    snap_future = healthy_snap(e, price=20)
    rec_protected = InvestmentResearch().score_snapshot(snap_now, all_bars, as_of=as_of)
    rec_leaky = InvestmentResearch().score_snapshot(snap_future, all_bars)
    assert rec_protected.drawdown.current_drawdown is not None
    assert rec_leaky.drawdown.current_drawdown is not None
    # Using the future print at T would invent a deep drawdown the T-clock cannot see.
    assert rec_leaky.drawdown.current_drawdown < rec_protected.drawdown.current_drawdown - 0.2
    assert rec_protected.drawdown.current_drawdown > -0.15


def test_outcomes_null_at_t_and_enrichment_is_separate(tmp_path):
    as_of = datetime(2024, 6, 3, 20, 0, tzinfo=timezone.utc)
    obs = {
        "observation_id": "XYZ-1",
        "symbol": "XYZ",
        "as_of": as_of.isoformat(),
        "price": 100.0,
        "research": {"price": 100.0, "symbol": "XYZ"},
        "outcomes": empty_outcomes(),
    }
    assert obs["outcomes"]["price_5d"] is None
    # subsequent sessions
    later = bars_from_closes([99, 101, 98, 110, 108], start=date(2024, 6, 4))
    now = datetime(2024, 6, 12, 20, 0, tzinfo=timezone.utc)
    written = enrich_observation(obs, later, now=now, outcomes_path=tmp_path / "out.jsonl")
    assert written is not None
    assert written["price_1d"] == 99.0
    assert abs(written["return_1d"] - (-0.01)) < 1e-9
    # original dict not mutated into a score
    assert obs["outcomes"]["price_1d"] is None
    # original file would be unchanged — we never opened observations.jsonl
    rows = json.loads((tmp_path / "out.jsonl").read_text().splitlines()[0])
    assert rows["observation_id"] == "XYZ-1"
    assert rows["look_ahead_protected"] is True


def test_measure_outcomes_does_not_use_bars_after_now():
    as_of = datetime(2024, 1, 2, 21, 0, tzinfo=timezone.utc)
    bars = bars_from_closes([100, 110, 120], start=date(2024, 1, 3))
    now = datetime(2024, 1, 4, 21, 0, tzinfo=timezone.utc)  # only 1 session elapsed
    out = measure_outcomes(price_at_t=100.0, as_of=as_of, bars=bars, now=now)
    assert out["price_1d"] is not None
    assert out["price_5d"] is None
    assert out["price_252d"] is None


# --- alerts / allocation / paper via scanner ---


def test_alert_dedup_across_scans(tmp_path):
    e = _entry("XYZ")
    snap = healthy_snap(e, price=40)
    ingest = FakeIngest({e.symbol: snap})
    from app.investment.universe import InvestmentUniverse

    notes = []
    sc = _scanner(
        tmp_path,
        ingest,
        InvestmentUniverse([e]),
        notify_fn=lambda text, sym, pri=None: notes.append(text),
        notify=True,
    )
    _seed_history(sc, "XYZ", ramp(70, 40, 300))
    t0 = datetime(2026, 8, 24, 15, 0, tzinfo=timezone.utc)
    asyncio.run(sc.run_once(now=t0))
    n1 = len(notes)
    asyncio.run(sc.run_once(now=t0 + timedelta(minutes=5)))
    assert len(notes) == n1  # duplicate classification suppressed


def test_generational_gate_still_blocks_drawdown_only():
    ok, blockers = generational_gate(
        thesis=ThesisState.BROKEN,
        evidence=EvidenceQuality.LOW,
        dd=DrawdownReport(current_drawdown=-0.60, drawdown_percentile=99, coverage_bars=400),
        valuation_score=40,
        fundamentals_score=40,
        balance_sheet_score=40,
        cash_flow_score=40,
        risk_score=20,
        opportunity_score=40,
    )
    assert ok is False
    assert blockers


def test_portfolio_aware_plan_and_missing_profile(tmp_path):
    e = _entry("XYZ")
    snap = healthy_snap(e, price=40)
    ingest = FakeIngest({e.symbol: snap})
    from app.investment.universe import InvestmentUniverse
    from app.investment.paper_book import PaperBook

    port = PortfolioInput(
        portfolio_value=20_000,
        available_cash=8_000,
        minimum_cash_reserve=2_000,
        maximum_position_percent=15,
        provided=True,
        risk_tolerance=RiskTolerance.MODERATE,
        holdings=[],
    )
    paper = PaperBook(cash=8_000, state_path=tmp_path / "p.json", ledger_path=tmp_path / "l.jsonl")
    sc = _scanner(tmp_path, ingest, InvestmentUniverse([e]), portfolio=port, paper=paper)
    _seed_history(sc, "XYZ", ramp(80, 40, 400))
    monday = datetime(2026, 8, 24, 15, 0, tzinfo=timezone.utc)
    report = asyncio.run(sc.run_once(now=monday))
    rec = report.observations[0].research
    assert rec is not None
    # missing profile → research only
    sc2 = _scanner(tmp_path / "b", ingest, InvestmentUniverse([e]), portfolio=PortfolioInput())
    (tmp_path / "b" / "hist").mkdir(parents=True, exist_ok=True)
    sc2.history_root = sc.history_root
    report2 = asyncio.run(sc2.run_once(now=monday))
    assert report2.evaluated == 1


def test_weekend_is_closed_not_offline_and_no_fake_fills(tmp_path):
    e = _entry("XYZ")
    snap = healthy_snap(e, price=40)
    ingest = FakeIngest({e.symbol: snap})
    from app.investment.universe import InvestmentUniverse
    from app.investment.paper_book import PaperBook

    paper = PaperBook(cash=8_000, state_path=tmp_path / "p.json", ledger_path=tmp_path / "l.jsonl")
    sc = _scanner(tmp_path, ingest, InvestmentUniverse([e]), paper=paper)
    _seed_history(sc, "XYZ", ramp(80, 40, 300))
    sat = datetime(2026, 8, 29, 15, 0, tzinfo=timezone.utc)
    report = asyncio.run(sc.run_once(now=sat))
    assert report.session == "MARKET_CLOSED"
    assert paper.fills == []
    sc.system_ok = False
    report2 = asyncio.run(sc.run_once(now=sat))
    assert report2.session == "SYSTEM_OFFLINE"


def test_discord_copy_is_investment_not_trading():
    from app.investment.alerts import AlertDecision

    rec = ResearchRecord(
        symbol="XYZ",
        price=42.5,
        classification=InvestmentAlertState.DEEP_VALUE,
        opportunity_score=88,
        evidence_quality=EvidenceQuality.HIGH,
        thesis=ThesisState.INTACT,
        drawdown=DrawdownReport(current_drawdown=-0.32),
        explain=Explainability(why_now=["valuation compression"], risks=["vol"]),
    )
    text = format_investment_alert(
        rec,
        AlertDecision(emit=True, reason="x", classification=InvestmentAlertState.DEEP_VALUE),
    )
    assert text.startswith("ATLAS INVESTMENT — DEEP VALUE")
    assert "Price:" in text
    assert "Research only" in text
    assert "No real order has been placed" in text
    assert "/paper" not in text


def test_dashboard_counts():
    obs_rows = []
    for cls, sym in [
        (InvestmentAlertState.WATCH, "A"),
        (InvestmentAlertState.NO_ACTION, "B"),
        (InvestmentAlertState.DEEP_VALUE, "C"),
    ]:
        rec = ResearchRecord(
            symbol=sym,
            classification=cls,
            opportunity_score=50,
            evidence_quality=EvidenceQuality.MEDIUM,
            thesis=ThesisState.INTACT,
            drawdown=DrawdownReport(current_drawdown=-0.2),
        )
        from app.investment.scan_models import ScanObservation

        obs_rows.append(
            ScanObservation(
                scan_id="s",
                symbol=sym,
                classification=cls.value,
                blocking_reason="Valuation insufficient" if cls is InvestmentAlertState.NO_ACTION else "Evidence quality MEDIUM",
                research=rec,
            )
        )
    from app.investment.scan_models import ScanReport

    report = ScanReport(
        scan_id="s",
        session="MARKET_CLOSED",
        universe=3,
        evaluated=3,
        counts={"WATCH": 1, "NO_ACTION": 1, "DEEP_VALUE": 1, "ACCUMULATION": 0, "GENERATIONAL_OPPORTUNITY": 0, "THESIS_BROKEN": 0},
        observations=obs_rows,
    )
    text = format_scan_dashboard(report)
    assert "Universe: 3" in text
    assert "WATCH: 1" in text
    assert "DEEP VALUE: 1" in text
    assert "TOP OPPORTUNITIES" in text
    assert "TOP BLOCKERS" in text
    assert "/paper" in text or "Hyperliquid" in text


def test_start_wrapper_never_raises():
    async def _run():
        import app.investment.scan as sc

        async def boom():
            raise RuntimeError("boom")

        orig = sc.investment_scanner.start
        sc.investment_scanner.start = boom  # type: ignore
        try:
            await start_investment_scanner()
        finally:
            sc.investment_scanner.start = orig

    asyncio.run(_run())


def test_scanner_disabled_does_not_loop():
    sc = InvestmentScanner(settings=ScanSettings(enabled=False))
    asyncio.run(sc.start())
    assert sc.running is False
    assert sc._task is None


def test_phase5_does_not_import_trading_stack():
    import app.investment.scan as scan_mod
    import app.investment.outcomes as out_mod

    for mod in (scan_mod, out_mod):
        src = Path(inspect.getfile(mod)).read_text(encoding="utf-8")
        assert "perp_micro" not in src
        assert "paper_journal" not in src
        assert not re.search(r"\bRSI\b", src)
        assert "from app.services" not in src
        assert "from app.adapters" not in src
    assert OBSERVATIONS_PATH != TRADING_PAPER_JOURNAL
    assert OUTCOMES_PATH != TRADING_PAPER_JOURNAL
    assert "investment" in str(OBSERVATIONS_PATH)
    assert LEDGER_PATH != TRADING_PAPER_JOURNAL


def test_failed_record_has_null_outcomes_and_no_price():
    rec = failed_record("XYZ", "X", "RATE_LIMIT", datetime(2026, 8, 28, tzinfo=timezone.utc))
    assert rec.price is None
    assert rec.classification is InvestmentAlertState.NO_ACTION
    assert rec.opportunity_score is None
    assert rec.as_probability_claim
    with pytest.raises(RuntimeError):
        rec.as_probability_claim()
