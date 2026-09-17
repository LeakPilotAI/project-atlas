from app.investment.quality_dips_v2_position_monitor import (
    PositionMonitorInput,
    PositionResearchState,
    evaluate_position,
)


def _base_current():
    return {
        "thesis": "INTACT",
        "evidence_quality": "HIGH",
        "quality_score": 90,
        "fundamentals_score": 90,
        "trend": {
            "short_term": "MIXED",
            "intermediate_term": "UP",
            "long_term": "UP",
            "momentum": "STRONG",
            "relative_strength": "STRONG",
        },
    }


def _entry():
    return {
        "entry_level": "L2",
        "entry_timestamp": "2026-09-17T00:00:00+00:00",
        "quality_score": 90,
        "fundamentals_score": 90,
    }


def test_intact_position_defaults_to_hold():
    out = evaluate_position(PositionMonitorInput("MSFT", 100, 112, _entry(), _base_current()))
    assert out["state"] == PositionResearchState.HOLD.value
    assert out["pnl_pct"] == 12.0
    assert out["price_alone_breaks_thesis"] is False


def test_bearish_trend_is_hold_watch_not_thesis_broken():
    cur = _base_current()
    cur["trend"] = {
        "short_term": "DOWN",
        "intermediate_term": "BEARISH",
        "long_term": "DOWN",
        "momentum": "WEAK",
        "relative_strength": "WEAK",
    }
    out = evaluate_position(PositionMonitorInput("MSFT", 100, 72, _entry(), cur))
    assert out["state"] == PositionResearchState.HOLD_WATCH.value
    assert out["price_alone_breaks_thesis"] is False


def test_explicit_thesis_failure_wins():
    cur = _base_current()
    cur["thesis"] = "BROKEN"
    out = evaluate_position(PositionMonitorInput("MSFT", 100, 140, _entry(), cur))
    assert out["state"] == PositionResearchState.THESIS_BROKEN.value


def test_value_trap_blocks_adding():
    cur = _base_current()
    cur["value_trap"] = True
    out = evaluate_position(PositionMonitorInput("MSFT", 100, 80, _entry(), cur))
    assert out["state"] == PositionResearchState.STOP_ADDING.value


def test_material_fundamental_deterioration_triggers_exit_review():
    cur = _base_current()
    cur["fundamentals_score"] = 70
    out = evaluate_position(PositionMonitorInput("MSFT", 100, 105, _entry(), cur))
    assert out["state"] == PositionResearchState.EXIT_REVIEW.value
    assert out["fundamentals_delta"] == -20.0


def test_explicit_add_eligible_state():
    cur = _base_current()
    cur["add_eligible"] = True
    out = evaluate_position(PositionMonitorInput("MSFT", 100, 92, _entry(), cur))
    assert out["state"] == PositionResearchState.ADD_ELIGIBLE.value


def test_invalid_price_fails_to_hold_watch():
    out = evaluate_position(PositionMonitorInput("MSFT", 0, 92, _entry(), _base_current()))
    assert out["state"] == PositionResearchState.HOLD_WATCH.value


def test_manual_only_contract():
    out = evaluate_position(PositionMonitorInput("MSFT", 100, 110, _entry(), _base_current()))
    assert out["execution"] == "MANUAL_ONLY"
    assert out["live_capital_allowed"] is False
    assert out["automatic_real_money_execution"] is False
