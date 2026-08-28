"""Phase 3 research/scoring — deterministic. No live Yahoo. No trading-engine imports."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from app.investment.bars import OhlcvBar
from app.investment.drawdown import analyze_drawdown, coverage_label, return_volatility
from app.investment.enums import (
    AssetType,
    DataQuality,
    EvidenceQuality,
    InvestmentAlertState,
    ThesisState,
)
from app.investment.models import MeasuredValue
from app.investment.research import (
    InvestmentResearch,
    assess_evidence,
    assess_thesis,
    classify_opportunity,
    format_research_text,
    generational_gate,
)
from app.investment.research_models import SCORING_VERSION, ResearchRecord
from app.investment.research_store import append_research, load_research
from app.investment.scoring import (
    CORRELATION_GROUPS,
    combine_components,
    score_valuation,
)
from app.investment.snapshot import snapshot_from_parts
from app.investment.universe import UniverseEntry


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


def healthy_funds() -> dict:
    return {
        "revenue": mv(80e9),
        "earnings": mv(15e9),
        "eps": mv(6.0),
        "free_cash_flow": mv(12e9),
        "operating_cash_flow": mv(18e9),
        "gross_margin": mv(0.68),
        "operating_margin": mv(0.24),
        "net_margin": mv(0.18),
        "total_debt": mv(20e9),
        "cash": mv(25e9),
        "shares_outstanding": mv(2.4e9),
        "market_cap": mv(400e9),
    }


def collapsed_funds() -> dict:
    return {
        "revenue": mv(40e9),
        "earnings": mv(-8e9),
        "eps": mv(-3.0),
        "free_cash_flow": mv(-6e9),
        "operating_cash_flow": mv(-2e9),
        "gross_margin": mv(0.20),
        "operating_margin": mv(-0.05),
        "net_margin": mv(-0.20),
        "total_debt": mv(90e9),
        "cash": mv(4e9),
        "shares_outstanding": mv(2.4e9),
        "market_cap": mv(80e9),
    }


def cheap_val() -> dict:
    return {
        "pe": mv(12.0),
        "forward_pe": mv(11.0),
        "ps": mv(1.4),
        "pb": mv(1.8),
        "ev_ebitda": mv(9.0),
        "fcf_yield": mv(0.07),
        "earnings_yield": mv(1 / 12.0),
        "price_to_fcf": mv(1 / 0.07),
    }


def rich_val() -> dict:
    return {
        "pe": mv(28.0),
        "ps": mv(6.0),
        "pb": mv(8.0),
        "fcf_yield": mv(0.012),
    }


def make_snap(
    symbol: str = "ZZZ",
    price: float = 60.0,
    funds=None,
    val=None,
    asset_type: AssetType = AssetType.STOCK,
    failures=None,
    quality: DataQuality = DataQuality.FRESH,
):
    entry = UniverseEntry(
        symbol=symbol,
        name="Test Co",
        asset_type=asset_type,
        sector="Health Care",
    )
    return snapshot_from_parts(
        entry,
        price=mv(price, quality=quality),
        fundamentals=funds if funds is not None else healthy_funds(),
        valuation=val if val is not None else cheap_val(),
        failures=failures or [],
    )


def peak_then_last(n_up: int, peak: float, last: float) -> list[OhlcvBar]:
    return bars_from_closes(ramp(peak * 0.5, peak, n_up) + [last])


def test_drawdown_from_highest_available():
    bars = bars_from_closes([10, 20, 40, 80, 100, 68])
    dd = analyze_drawdown(bars)
    assert dd.high_available == 100
    assert dd.current_drawdown == pytest.approx(-0.32)
    assert dd.coverage_bars == 6
    assert "insufficient" in dd.coverage_label


def test_drawdown_52w_window():
    closes = ramp(50, 100, 200) + ramp(100, 80, 60)  # last ~80, high 100 in window
    bars = bars_from_closes(closes)
    dd = analyze_drawdown(bars)
    assert dd.coverage_bars == 260
    assert dd.high_52w is not None
    assert dd.drawdown_52w == pytest.approx(dd.current_drawdown, abs=1e-9)
    assert dd.current_drawdown == pytest.approx(-0.20, abs=0.02)


def test_historical_max_drawdown_and_percentile():
    # Long grind up, mid crash to 50, recover to 90, then last 70. High=100 path.
    up = ramp(40, 100, 180)
    crash = ramp(100, 50, 20)
    rec = ramp(50, 90, 80)
    last = [70]
    bars = bars_from_closes(up + crash + rec + last)
    dd = analyze_drawdown(bars)
    assert dd.max_drawdown is not None and dd.max_drawdown <= -0.49
    assert dd.current_drawdown == pytest.approx(-0.30, abs=0.02)
    assert dd.drawdown_percentile is not None
    assert 0 <= dd.drawdown_percentile <= 100


def test_insufficient_history_percentile_unknown():
    bars = peak_then_last(25, 100, 60)
    dd = analyze_drawdown(bars)
    assert dd.coverage_bars < 60
    assert dd.drawdown_percentile is None
    assert any("UNKNOWN" in n for n in dd.notes)
    assert "insufficient" in coverage_label(dd.coverage_bars)


def test_current_quote_overrides_last_close_for_current_dd():
    bars = bars_from_closes([100, 100, 100, 90])
    dd = analyze_drawdown(bars, current_price=70)
    assert dd.current_drawdown == pytest.approx(-0.30)


def test_volatility_none_if_too_short():
    assert return_volatility(bars_from_closes([1, 2, 3])) is None
    v = return_volatility(bars_from_closes(ramp(100, 110, 80)))
    assert v is not None and v > 0


def test_valuation_missing_is_unknown_not_invented():
    score, notes = score_valuation({})
    assert score is None
    assert any("UNKNOWN" in n or "missing" in n for n in notes)


def test_valuation_does_not_treat_low_pe_as_proven_undervalue():
    _, notes = score_valuation({"pe": mv(9.0)})
    assert any("not automatically undervaluation" in n for n in notes)


def test_correlated_pe_and_earnings_yield_not_double_counted():
    pe_only, _ = score_valuation({"pe": mv(15.0)})
    both, notes = score_valuation({"pe": mv(15.0), "earnings_yield": mv(1 / 15.0)})
    assert pe_only is not None and both is not None
    assert abs(pe_only - both) <= 8
    assert "earnings_multiple" in CORRELATION_GROUPS
    assert any("averaged" in n for n in notes)


def test_fcf_yield_and_price_to_fcf_grouped():
    y = 0.05
    a, _ = score_valuation({"fcf_yield": mv(y)})
    b, notes = score_valuation({"fcf_yield": mv(y), "price_to_fcf": mv(1 / y)})
    assert a is not None and b is not None
    assert abs(a - b) <= 8
    assert any("cashflow_multiple" in n for n in notes)


def test_fundamental_quality_healthy_vs_collapsed():
    eng = InvestmentResearch()
    bars = peak_then_last(300, 100, 80)
    healthy = eng.score_snapshot(make_snap(price=80, funds=healthy_funds(), val=cheap_val()), bars)
    dead = eng.score_snapshot(make_snap(price=80, funds=collapsed_funds(), val={"pe": mv(-4.0)}), bars)
    assert healthy.components.fundamentals is not None and healthy.components.fundamentals >= 70
    assert dead.components.fundamentals is not None and dead.components.fundamentals <= 40
    assert healthy.thesis in (ThesisState.STRONG, ThesisState.INTACT)
    assert dead.thesis in (ThesisState.BROKEN, ThesisState.DAMAGED)


def test_thesis_unknown_without_enough_fields():
    state, notes, _ = assess_thesis({"market_cap": mv(1e9)}, asset_type=AssetType.STOCK)
    assert state is ThesisState.UNKNOWN
    assert any("too few" in n for n in notes)


def test_thesis_unknown_for_thin_etf():
    state, _, _ = assess_thesis({"market_cap": mv(1e12), "shares_outstanding": mv(1e9)}, asset_type=AssetType.ETF)
    assert state is ThesisState.UNKNOWN


def test_risk_splits_market_fundamental_data():
    rec = InvestmentResearch().score_snapshot(
        make_snap(price=70, funds=healthy_funds(), val=cheap_val()),
        peak_then_last(300, 100, 70),
    )
    assert rec.market_risk
    assert rec.fundamental_risk or rec.thesis in (ThesisState.STRONG, ThesisState.INTACT)
    assert rec.data_risk
    assert rec.components.risk is not None


def test_evidence_reduced_when_fundamentals_missing():
    bars = peak_then_last(300, 100, 80)
    full = make_snap(price=80)
    thin = make_snap(price=80, funds={"market_cap": mv(1e9)}, val={"pe": mv(18.0)})
    ev_full, _, _ = assess_evidence(full, analyze_drawdown(bars))
    ev_thin, _, missing = assess_evidence(thin, analyze_drawdown(bars))
    rank = {
        EvidenceQuality.HIGH: 4,
        EvidenceQuality.MEDIUM: 3,
        EvidenceQuality.LOW: 2,
        EvidenceQuality.INSUFFICIENT: 1,
        EvidenceQuality.UNKNOWN: 0,
    }
    assert rank[ev_thin] < rank[ev_full]
    assert "revenue" in missing or "free_cash_flow" in missing


def test_evidence_reduced_when_conflicting():
    bars = peak_then_last(300, 100, 80)
    funds = healthy_funds()
    funds["revenue"] = mv(80e9, quality=DataQuality.CONFLICTING)
    rec = InvestmentResearch().score_snapshot(make_snap(price=80, funds=funds), bars)
    assert rec.evidence_quality in (EvidenceQuality.LOW, EvidenceQuality.INSUFFICIENT)
    assert any("conflict" in n.lower() for n in rec.explain.data_quality_notes + rec.data_risk)


def test_insufficient_history_marks_percentile_unknown_on_record():
    rec = InvestmentResearch().score_snapshot(
        make_snap(price=60),
        peak_then_last(30, 100, 60),
    )
    assert rec.drawdown.drawdown_percentile is None
    assert rec.classification is not InvestmentAlertState.GENERATIONAL_OPPORTUNITY


def test_price_down_50_fundamentals_collapse_is_thesis_broken():
    rec = InvestmentResearch().score_snapshot(
        make_snap(price=50, funds=collapsed_funds(), val={"pe": mv(-8.0), "ps": mv(1.0)}),
        peak_then_last(400, 100, 50),
    )
    assert rec.thesis is ThesisState.BROKEN
    assert rec.classification is InvestmentAlertState.THESIS_BROKEN
    assert rec.classification is not InvestmentAlertState.GENERATIONAL_OPPORTUNITY
    assert rec.classification is not InvestmentAlertState.ACCUMULATION
    assert rec.classification is not InvestmentAlertState.DEEP_VALUE
    with pytest.raises(RuntimeError, match="not probabilities"):
        rec.as_probability_claim()


def test_price_down_40_healthy_is_accumulation_or_deep_value():
    rec = InvestmentResearch().score_snapshot(
        make_snap(price=60, funds=healthy_funds(), val=cheap_val()),
        peak_then_last(400, 100, 60),
    )
    assert rec.thesis in (ThesisState.STRONG, ThesisState.INTACT)
    assert rec.evidence_quality in (EvidenceQuality.HIGH, EvidenceQuality.MEDIUM)
    assert rec.classification in (
        InvestmentAlertState.ACCUMULATION,
        InvestmentAlertState.DEEP_VALUE,
    )
    assert rec.classification is not InvestmentAlertState.GENERATIONAL_OPPORTUNITY
    assert rec.classification is not InvestmentAlertState.THESIS_BROKEN


def test_price_down_10_healthy_is_not_generational():
    rec = InvestmentResearch().score_snapshot(
        make_snap(price=90, funds=healthy_funds(), val=cheap_val()),
        peak_then_last(400, 100, 90),
    )
    assert rec.drawdown.current_drawdown == pytest.approx(-0.10, abs=0.005)
    assert rec.classification is not InvestmentAlertState.GENERATIONAL_OPPORTUNITY
    assert rec.classification is not InvestmentAlertState.DEEP_VALUE
    assert rec.classification is not InvestmentAlertState.ACCUMULATION
    assert rec.classification in (
        InvestmentAlertState.WATCH,
        InvestmentAlertState.NO_ACTION,
    )


def test_generational_requires_independent_pillars():
    # Large drawdown + collapsed funds must not pass the gate.
    rec = InvestmentResearch().score_snapshot(
        make_snap(price=50, funds=collapsed_funds(), val=cheap_val()),
        peak_then_last(500, 100, 50),
    )
    ok, blockers = generational_gate(
        thesis=rec.thesis,
        evidence=rec.evidence_quality,
        dd=rec.drawdown,
        valuation_score=rec.components.valuation,
        fundamentals_score=rec.components.fundamentals,
        balance_sheet_score=rec.components.balance_sheet,
        cash_flow_score=rec.components.cash_flow,
        risk_score=rec.components.risk,
        opportunity_score=rec.opportunity_score,
    )
    assert ok is False
    assert blockers
    assert rec.classification is InvestmentAlertState.THESIS_BROKEN


def test_generational_can_pass_when_all_pillars_hold():
    rec = InvestmentResearch().score_snapshot(
        make_snap(price=50, funds=healthy_funds(), val=cheap_val()),
        peak_then_last(500, 100, 50),
    )
    assert rec.drawdown.current_drawdown == pytest.approx(-0.50, abs=0.005)
    assert rec.thesis in (ThesisState.STRONG, ThesisState.INTACT)
    assert rec.classification is InvestmentAlertState.GENERATIONAL_OPPORTUNITY
    assert rec.generational_blockers == []


def test_score_is_integer_and_versioned():
    rec = InvestmentResearch().score_snapshot(
        make_snap(price=80),
        peak_then_last(300, 100, 80),
    )
    assert rec.scoring_version == SCORING_VERSION
    assert rec.scoring_version == InvestmentResearch.version
    if rec.opportunity_score is not None:
        assert rec.opportunity_score == int(rec.opportunity_score)
        assert 0 <= rec.opportunity_score <= 100


def test_missing_components_are_none_not_zero():
    rec = InvestmentResearch().score_snapshot(
        make_snap(price=80, funds=healthy_funds(), val={}),
        peak_then_last(300, 100, 80),
    )
    assert rec.components.growth is None
    assert rec.components.valuation is None
    assert rec.opportunity_score is None or rec.opportunity_score > 0


def test_combine_omits_missing_instead_of_zeroing():
    from app.investment.research_models import ComponentScores

    a = combine_components(ComponentScores(valuation=80, fundamentals=80, drawdown=50))
    b = combine_components(ComponentScores(valuation=80, fundamentals=80, drawdown=50, growth=0))
    assert a is not None and b is not None
    assert b < a  # stuffing a fake 0 growth would drag the score — we only do that if present


def test_explainability_sections_present():
    rec = InvestmentResearch().score_snapshot(
        make_snap(price=60),
        peak_then_last(300, 100, 60),
    )
    text = format_research_text(rec)
    for heading in (
        "WHY THIS ASSET?",
        "WHY IS IT INTERESTING?",
        "WHY NOW?",
        "WHAT SUPPORTS THE THESIS?",
        "WHAT WEAKENS THE THESIS?",
        "WHAT DATA IS MISSING?",
        "WHAT COULD INVALIDATE THE THESIS?",
        "RISKS:",
        "DATA QUALITY:",
        "not a probability",
    ):
        assert heading in text
    opp = rec.to_opportunity(make_snap().asset)
    assert opp.scoring_version == SCORING_VERSION
    assert opp.why_now


def test_historical_opportunity_storage_appends(tmp_path: Path):
    p = tmp_path / "opportunities.jsonl"
    eng = InvestmentResearch()
    r1 = eng.score_snapshot(make_snap(symbol="AAA", price=80), peak_then_last(300, 100, 80))
    r2 = eng.score_snapshot(make_snap(symbol="AAA", price=60), peak_then_last(300, 100, 60))
    append_research(r1, path=p)
    append_research(r2, path=p)
    rows = load_research(p)
    assert len(rows) == 2
    assert rows[0]["price"] == 80
    assert rows[1]["price"] == 60
    assert rows[0]["scoring_version"] == SCORING_VERSION
    assert rows[0]["symbol"] == "AAA"
    assert "input_snapshot" in rows[0]
    assert "components" in rows[0]


def test_research_does_not_import_trading_stack():
    import inspect
    import re

    import app.investment.research as research_mod
    import app.investment.scoring as scoring_mod

    for mod in (research_mod, scoring_mod):
        src = Path(inspect.getfile(mod)).read_text(encoding="utf-8")
        assert "perp_micro" not in src
        assert "paper_journal" not in src
        assert not re.search(r"\bRSI\b", src)
        assert "from app.services" not in src
        assert "app.adapters" not in src


def test_classify_watch_floor():
    dd = analyze_drawdown(peak_then_last(300, 100, 95))
    state = classify_opportunity(
        thesis=ThesisState.INTACT,
        evidence=EvidenceQuality.MEDIUM,
        dd=dd,
        valuation_score=50,
        fundamentals_score=70,
        opportunity_score=42,
        generational_ok=False,
    )
    assert state is InvestmentAlertState.WATCH
