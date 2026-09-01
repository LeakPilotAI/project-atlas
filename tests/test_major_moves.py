"""Phase 7 — equity move intelligence. Isolated from Hyperliquid gates."""

from datetime import date, timedelta
from pathlib import Path

from app.investment.alerts import AlertStore, commit_move, should_emit_move
from app.investment.bars import OhlcvBar
from app.investment.cause import infer_cause
from app.investment.enums import (
    CauseCategory,
    EvidenceQuality,
    MoveClassification,
    ThesisState,
)
from app.investment.models import MeasuredValue
from app.investment.move_store import MOVE_EVENTS_PATH, append_move_event, append_move_outcome
from app.investment.moves import (
    apply_thesis_safety,
    atr,
    classify_from_score,
    consecutive_down_days,
    gap_magnitude,
    is_actionable_dislocation,
    relative_volume,
    score_move,
)
from app.investment.relative import period_return, relative_report
from app.investment.review_levels import build_review_levels
from app.investment.tape import public_payload, set_rows
from app.investment.thesis_trend import apply_deterioration, detect_deterioration
from app.investment.universe import UniverseEntry, load_example_universe
from app.services.funnel_research import EXT_LOCK, RR_LOCK, RSI_LONG_LOCK, RSI_SHORT_LOCK
from app.investment.allocation import build_plan, maximum_recommended_allocation
from app.investment.enums import InvestmentAlertState, RiskTolerance
from app.investment.models import HoldingInput, PortfolioInput
from app.investment.research_models import ResearchRecord
from app.investment.drawdown import DrawdownReport


def _bars(closes, volumes=None, opens=None, start="2024-01-02") -> list:
    d = date.fromisoformat(start)
    out = []
    for i, c in enumerate(closes):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        vol = None if volumes is None else volumes[i]
        o = (opens[i] if opens is not None else c)
        out.append(
            OhlcvBar(
                session_date=d.isoformat(),
                open=float(o),
                high=float(c) * 1.01,
                low=float(c) * 0.99,
                close=float(c),
                volume=vol,
            )
        )
        d += timedelta(days=1)
    return out


def test_gates_untouched() -> None:
    assert RSI_LONG_LOCK == 28.0
    assert RSI_SHORT_LOCK == 72.0
    assert EXT_LOCK == 1.4
    assert RR_LOCK == 1.8


def test_atr_normalized_and_missing_volume() -> None:
    bars = _bars([100 + i * 0.1 for i in range(40)] + [90])
    a = atr(bars)
    assert a is not None and a > 0
    assert relative_volume(bars) is None  # volumes missing — not fake 0
    scored = score_move(symbol="ZZZ", bars=bars)
    assert scored.rel_volume is None
    assert scored.score is not None
    assert "relative volume UNKNOWN" in " ".join(scored.notes)


def test_relative_volume_when_present() -> None:
    closes = [100] * 25
    vols = [1_000_000] * 24 + [3_000_000]
    bars = _bars(closes, volumes=vols)
    rv = relative_volume(bars)
    assert rv is not None
    assert 2.5 < rv < 3.5


def test_relative_weakness_idiosyncratic_vs_market() -> None:
    asset_idio = _bars([100] * 10 + [91])
    spy_quiet = _bars([100] * 10 + [99])
    sector_quiet = _bars([100] * 10 + [98])
    idio = relative_report(
        symbol="AAA",
        asset_bars=asset_idio,
        spy_bars=spy_quiet,
        qqq_bars=spy_quiet,
        sector_bars=sector_quiet,
        spy_symbol="SPY",
        qqq_symbol="QQQ",
        sector_symbol="SOXX",
    )
    assert idio.asset_1d is not None and idio.asset_1d < -0.08
    assert idio.vs_spy_1d is not None and idio.vs_spy_1d < -0.07

    spy_crash = _bars([100] * 10 + [92])
    market = relative_report(
        symbol="AAA",
        asset_bars=asset_idio,
        spy_bars=spy_crash,
        qqq_bars=spy_crash,
        sector_bars=spy_crash,
        spy_symbol="SPY",
        qqq_symbol="QQQ",
        sector_symbol="SOXX",
    )
    assert abs(market.vs_spy_1d) < abs(idio.vs_spy_1d)


def test_drawdown_percentile_and_down_days_and_gap() -> None:
    up = list(range(80, 120))
    bars = _bars(up + [100])
    scored = score_move(symbol="ZZZ", bars=bars)
    assert scored.drawdown is not None
    downs = _bars([10, 9, 8, 7])
    assert consecutive_down_days(downs) == 3
    gapped = _bars([10, 9], opens=[10, 8])
    g = gap_magnitude(gapped)
    assert g is not None and g < -0.05


def test_major_universe_from_file_not_scoring() -> None:
    u = load_example_universe()
    assert any(e.symbol == "NVDA" and "major" in e.groups for e in u)
    assert u.sector_etf_for(u.get("NVDA")) == "SOXX"
    assert u.spy_symbol() == "SPY"


def test_thesis_broken_blocks_accumulation() -> None:
    move = score_move(symbol="ZZZ", bars=_bars([100] * 30 + [70]))
    cls = apply_thesis_safety(
        move, thesis=ThesisState.BROKEN, evidence=EvidenceQuality.HIGH
    )
    assert cls is MoveClassification.FUNDAMENTAL_BREAKDOWN
    assert not is_actionable_dislocation(cls, thesis=ThesisState.BROKEN, evidence=EvidenceQuality.HIGH)


def test_healthy_dip_vs_broken() -> None:
    bars = _bars([100] * 30 + [80], volumes=[1e6] * 30 + [4e6])
    spy = _bars([100] * 31)
    rel = relative_report(symbol="AAA", asset_bars=bars, spy_bars=spy, spy_symbol="SPY")
    move = score_move(symbol="AAA", bars=bars, relative=rel)
    healthy = apply_thesis_safety(move, thesis=ThesisState.INTACT, evidence=EvidenceQuality.HIGH)
    broken = apply_thesis_safety(move, thesis=ThesisState.BROKEN, evidence=EvidenceQuality.HIGH)
    assert broken is MoveClassification.FUNDAMENTAL_BREAKDOWN
    if healthy in (MoveClassification.MAJOR_DISLOCATION, MoveClassification.EXTREME_DISLOCATION):
        assert is_actionable_dislocation(healthy, thesis=ThesisState.INTACT, evidence=EvidenceQuality.HIGH)


def test_thesis_deterioration() -> None:
    prior = {
        "earnings": MeasuredValue.of(10, source="t"),
        "free_cash_flow": MeasuredValue.of(8, source="t"),
    }
    cur = {
        "earnings": MeasuredValue.of(2, source="t"),
        "free_cash_flow": MeasuredValue.of(-1, source="t"),
    }
    bad, notes = detect_deterioration(cur, prior)
    assert bad is True
    assert apply_deterioration(ThesisState.INTACT, True) is ThesisState.UNDER_PRESSURE
    none, _ = detect_deterioration(cur, None)
    assert none is False


def test_cause_unknown_without_sourced_headline() -> None:
    rec = infer_cause(headlines=[{"title": "something fell"}])
    assert rec.category is CauseCategory.UNKNOWN
    rec2 = infer_cause(
        headlines=[
            {
                "title": "Company misses earnings badly",
                "source": "Reuters",
                "timestamp": "2026-09-01T14:00:00+00:00",
            }
        ]
    )
    assert rec2.category is CauseCategory.EARNINGS
    assert rec2.headline
    assert rec2.source == "Reuters"


def test_market_wide_structural_cause_not_invented_headline() -> None:
    asset = _bars([100] * 10 + [91])
    spy = _bars([100] * 10 + [92])
    rel = relative_report(symbol="AAA", asset_bars=asset, spy_bars=spy, spy_symbol="SPY")
    rec = infer_cause(headlines=[], relative=rel)
    assert rec.headline is None
    assert rec.category in (CauseCategory.MARKET_WIDE, CauseCategory.UNKNOWN)


def test_review_levels_not_tp() -> None:
    lv = build_review_levels(price=100.0, atr=3.0, thesis=ThesisState.INTACT)
    assert lv.recovery and lv.fair_value and lv.overvaluation and lv.thesis_review
    assert lv.recovery > 100
    assert "not automatic" in lv.disclaimer.lower() or "not automatic" in "".join(lv.reasons.values()).lower() or "reassess" in lv.disclaimer.lower()
    assert "take profit" not in lv.disclaimer.lower()


def test_buy_ladder_reserve_and_caps() -> None:
    rec = ResearchRecord(
        symbol="ZZZ",
        price=50.0,
        classification=InvestmentAlertState.DEEP_VALUE,
        opportunity_score=80,
        evidence_quality=EvidenceQuality.HIGH,
        thesis=ThesisState.INTACT,
        drawdown=DrawdownReport(current_drawdown=-0.25),
    )
    port = PortfolioInput(
        portfolio_value=100_000,
        available_cash=10_000,
        minimum_cash_reserve=4_000,
        maximum_position_percent=10.0,
        maximum_sector_exposure_percent=25.0,
        risk_tolerance=RiskTolerance.MODERATE,
        provided=True,
        holdings=[HoldingInput(symbol="ZZZ", shares=0, sector="Technology")],
        allow_fractional_shares=False,
    )
    cap, notes, err = maximum_recommended_allocation(rec, port, mark=50.0)
    assert err == ""
    assert float(cap) <= 6000  # cash 10k - reserve 4k
    plan = build_plan(rec, port)
    assert plan.is_actionable() or plan.blocked_reason
    if plan.is_actionable():
        spent = sum(t.dollar_amount or 0 for t in plan.tiers)
        assert spent + (plan.remaining_reserve or 0) <= port.available_cash + 0.1


def test_broken_thesis_no_ladder() -> None:
    rec = ResearchRecord(
        symbol="ZZZ",
        price=50.0,
        classification=InvestmentAlertState.DEEP_VALUE,
        opportunity_score=90,
        evidence_quality=EvidenceQuality.HIGH,
        thesis=ThesisState.BROKEN,
    )
    port = PortfolioInput(
        portfolio_value=100_000,
        available_cash=20_000,
        minimum_cash_reserve=2_000,
        maximum_position_percent=10.0,
        provided=True,
    )
    plan = build_plan(rec, port)
    assert not plan.is_actionable()
    assert "THESIS BROKEN" in plan.blocked_reason


def test_alert_dedup_same_move_class() -> None:
    store = AlertStore(persist=False)
    d1 = should_emit_move(store, "AAA", MoveClassification.MAJOR_DISLOCATION)
    assert d1.emit is True
    commit_move(store, "AAA", MoveClassification.MAJOR_DISLOCATION)
    d2 = should_emit_move(store, "AAA", MoveClassification.MAJOR_DISLOCATION)
    assert d2.emit is False
    d3 = should_emit_move(store, "AAA", MoveClassification.EXTREME_DISLOCATION)
    assert d3.emit is True


def test_empty_majors_tape_shows_nearest() -> None:
    set_rows(
        [
            {"symbol": "AAA", "move_score": 67, "classification": "NORMAL_PULLBACK"},
            {"symbol": "BBB", "move_score": 61, "classification": "NORMAL"},
            {"symbol": "CCC", "move_score": 58, "classification": "NORMAL"},
        ]
    )
    p = public_payload()
    assert p["quiet"] is True
    assert "No major dislocations" in p["headline"]
    assert p["nearest"][0]["symbol"] == "AAA"
    assert p["rows"]


def test_outcome_separation(tmp_path) -> None:
    ev = tmp_path / "events.jsonl"
    oc = tmp_path / "outcomes.jsonl"
    row = append_move_event({"symbol": "AAA", "price": 1}, path=ev)
    assert row.get("outcomes") is None
    append_move_outcome(row["event_id"], {"return_1d": 0.01}, path=oc)
    raw = ev.read_text(encoding="utf-8")
    assert "return_1d" not in raw
    assert oc.read_text(encoding="utf-8").find("return_1d") >= 0


def test_trading_isolation_paths() -> None:
    from app.investment.storage import assert_storage_separated, LEDGER_PATH, TRADING_PAPER_JOURNAL

    assert_storage_separated()
    assert LEDGER_PATH.resolve() != TRADING_PAPER_JOURNAL.resolve()
    from app.investment.moves import score_move as sm
    src = Path(sm.__code__.co_filename).read_text(encoding="utf-8")
    assert "rsi_long" not in src
    assert "perp_micro" not in src


def test_classify_score_bands() -> None:
    assert classify_from_score(None) is MoveClassification.UNKNOWN
    assert classify_from_score(92) is MoveClassification.EXTREME_DISLOCATION
    assert classify_from_score(82) is MoveClassification.MAJOR_DISLOCATION
    assert classify_from_score(10) is MoveClassification.NORMAL
