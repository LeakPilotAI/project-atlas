from app.investment.quality_dips_v2 import (
    MIN_TARGET_UPSIDE_PCT,
    POLICY_METADATA,
    PatientCapitalState,
    UpsideWindow,
    patient_state,
    required_entry_price,
    upside_pct,
    valuation_window,
)


def _state(**overrides):
    values = dict(
        thesis_intact=True,
        value_trap=False,
        quality_score=85,
        valuation_score=85,
        fundamentals_score=85,
        drawdown_percentile=90,
        conservative_upside_pct=42,
        base_upside_pct=50,
        evidence_quality="HIGH",
    )
    values.update(overrides)
    return patient_state(**values)


def test_upside_math_and_entry_price_work_backwards_from_value():
    assert upside_pct(100, 129) == 29.0
    assert required_entry_price(129, 29) == 100.0
    assert required_entry_price(150, 50) == 100.0


def test_valuation_window_keeps_scenarios_separate():
    result = valuation_window(UpsideWindow(100, 129, 140, 150))
    assert result == {
        "conservative_upside_pct": 29.0,
        "base_upside_pct": 40.0,
        "optimistic_upside_pct": 50.0,
    }


def test_patience_gate_waits_below_29_percent_conservative_upside():
    state, reasons = _state(conservative_upside_pct=28.99)
    assert state == PatientCapitalState.WATCH
    assert any("29%" in reason for reason in reasons)


def test_broken_thesis_overrides_apparent_discount():
    state, _ = _state(thesis_intact=False, conservative_upside_pct=80)
    assert state == PatientCapitalState.THESIS_BROKEN


def test_value_trap_never_becomes_generational_from_price_decline_alone():
    state, _ = _state(
        value_trap=True,
        quality_score=100,
        valuation_score=100,
        fundamentals_score=100,
        drawdown_percentile=100,
        conservative_upside_pct=100,
    )
    assert state == PatientCapitalState.WATCH


def test_deep_value_requires_stronger_stack_than_plain_accumulation():
    state, _ = _state()
    assert state == PatientCapitalState.DEEP_VALUE
    accumulation, _ = _state(
        quality_score=75,
        valuation_score=75,
        fundamentals_score=75,
        drawdown_percentile=70,
        conservative_upside_pct=30,
        base_upside_pct=35,
    )
    assert accumulation == PatientCapitalState.ACCUMULATION


def test_generational_is_rare_and_requires_50_percent_conservative_upside():
    state, _ = _state(
        quality_score=95,
        valuation_score=95,
        fundamentals_score=95,
        drawdown_percentile=97,
        conservative_upside_pct=50,
        base_upside_pct=60,
    )
    assert state == PatientCapitalState.GENERATIONAL
    not_yet, _ = _state(
        quality_score=95,
        valuation_score=95,
        fundamentals_score=95,
        drawdown_percentile=97,
        conservative_upside_pct=49.99,
        base_upside_pct=60,
    )
    assert not_yet == PatientCapitalState.DEEP_VALUE


def test_v2_is_research_only_not_production_or_live_execution():
    assert MIN_TARGET_UPSIDE_PCT == 29.0
    assert POLICY_METADATA["wired_to_production"] is False
    assert POLICY_METADATA["execution"] == "MANUAL_ONLY"
    assert POLICY_METADATA["live_capital_allowed"] is False
    assert POLICY_METADATA["automatic_real_money_execution"] is False
    assert POLICY_METADATA["guaranteed_return"] is False
