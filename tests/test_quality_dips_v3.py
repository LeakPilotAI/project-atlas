from app.investment.quality_dips_v3 import LEVEL_MARGINS, build_v3_entry_plan, robust_fair_value


def base(**overrides):
    args = dict(
        symbol="TEST", current_price=110.0,
        normalization={"conservative": 100.0, "base": 140.0, "optimistic": 180.0},
        quality_score=82, fundamentals_score=80, valuation_score=72,
        drawdown_percentile=80, evidence_quality="HIGH",
        thesis_intact=True, value_trap=False,
    )
    args.update(overrides)
    return build_v3_entry_plan(**args)


def test_robust_anchor_uses_complete_distribution_not_low_target():
    assert robust_fair_value({"conservative": 100, "base": 140, "optimistic": 180}) == 140
    assert robust_fair_value({"conservative": 100, "base": 140}) is None


def test_v3_ladder_uses_explicit_margin_of_safety():
    out = base()
    assert out["entry_ladder"]["ready"] is True
    assert [x["limit_price"] for x in out["entry_ladder"]["levels"]] == [119.0, 112.0, 105.0, 98.0]
    assert out["patient_state"] == "ACCUMULATION"
    assert out["execution"] == "MANUAL_ONLY"
    assert out["automatic_real_money_execution"] is False


def test_v3_fails_closed_on_weak_or_missing_evidence():
    assert base(evidence_quality="LOW")["patient_state"] == "WATCH"
    assert base(thesis_intact=False)["patient_state"] == "WATCH"
    assert base(value_trap=True)["patient_state"] == "WATCH"
    assert base(normalization={"conservative": 100, "base": 140})["entry_ladder"]["ready"] is False


def test_v3_deep_value_requires_stronger_stack():
    out = base(current_price=100, quality_score=88, fundamentals_score=84, valuation_score=78, drawdown_percentile=85)
    assert out["patient_state"] == "DEEP_VALUE"


def test_v3_generational_is_rare():
    out = base(current_price=90, quality_score=94, fundamentals_score=92, valuation_score=90, drawdown_percentile=96)
    assert out["patient_state"] == "GENERATIONAL"


def test_v3_zero_signal_is_valid():
    out = base(current_price=130)
    assert out["patient_state"] == "WATCH"
    assert out["blockers"] == []


def test_v3_policy_is_not_a_guarantee():
    out = base()
    assert out["policy"]["guaranteed_undervaluation"] is False
    assert out["policy"]["guaranteed_return"] is False
    assert LEVEL_MARGINS == {"L1": .15, "L2": .20, "L3": .25, "L4": .30}
