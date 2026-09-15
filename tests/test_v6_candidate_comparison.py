from app.services.v6_candidate_comparison import compare_report

def _p(closed=120,bexp=0.05,cexp=0.2,ci=(0.05,0.35),cdd=8.0,bdd=10.0):
    return {"marker":{"cohort":"v6_forward_only","started_at":"2026-09-15T12:00:00+00:00"},"baseline":{"n":closed,"expectancy":bexp,"max_drawdown_r":bdd,"uncertainty":{"expectancy_ci95":[-0.02,0.12]}},"challengers":{"trend_regime":{"opened":closed,"closed":closed,"open":0,"metrics":{"n":closed,"expectancy":cexp,"max_drawdown_r":cdd,"profit_factor":1.2},"uncertainty":{"expectancy_ci95":list(ci)}}}}

def test_forward_candidate_can_be_research_nomination_only_after_strict_evidence():
    r=compare_report(_p());c=r["candidates"]["trend_regime"]
    assert c["sample_sufficient"] is True
    assert c["positive_lower_expectancy_ci95"] is True
    assert c["beats_contemporaneous_baseline_expectancy"] is True
    assert c["research_nomination"] is True
    assert r["research_nominations"]==["trend_regime"]
    assert c["promoted"] is False
    assert r["trading_readiness"]=="NOT_READY"
    assert r["live_capital_allowed"] is False

def test_small_forward_sample_cannot_be_nominated():
    r=compare_report(_p(closed=40));assert r["candidates"]["trend_regime"]["research_nomination"] is False;assert r["research_nominations"]==[]

def test_nonpositive_ci_or_failure_to_beat_baseline_blocks_nomination():
    a=compare_report(_p(ci=(-0.1,0.3)));assert a["research_nominations"]==[]
    b=compare_report(_p(bexp=0.25,cexp=0.2));assert b["research_nominations"]==[]

def test_comparison_is_forward_only_and_never_uses_shadow_or_promotes():
    r=compare_report(_p())
    assert r["retrospective_substitution"] is False
    assert r["shadow_population_used"] is False
    assert r["membership_frozen_at_open"] is True
    assert r["automatic_promotion"] is False
    assert r["production_strategy_modified"] is False
    assert r["automatic_real_money_execution"] is False
