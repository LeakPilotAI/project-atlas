from app.services.v6_readiness_scorecard import build_scorecard


def _prospective(closed=120, expectancy=0.2, ci=(0.05,0.35)):
    return {"marker":{"started_at":"2026-09-15T12:00:00+00:00"},"challengers":{"trend_regime":{"opened":closed,"closed":closed,"open":0,"metrics":{"expectancy":expectancy},"uncertainty":{"expectancy_ci95":ci}}}}

def _replay(closed=100,path=80):
    return {"closed_with_open":closed,"uses_final_mfe_to_trigger":False,"candidates":{"capture_0_5r":{"path_eligible":path}}}

def _shadow(pooled=False):
    return {"populations_pooled":pooled,"prospective_nominations":[{"interaction":"trend","prospective_validation_required":True}]}


def test_scorecard_can_mark_research_evidence_ready_but_never_trading_ready():
    r=build_scorecard(prospective=_prospective(),exit_replay=_replay(),shadow_paper=_shadow())
    assert r["research_evidence_ready"] is True
    assert r["research_candidates"]==["trend_regime"]
    assert r["trading_readiness"]=="NOT_READY"
    assert r["live_capital_allowed"] is False
    assert r["automatic_promotion"] is False
    assert r["automatic_real_money_execution"] is False


def test_scorecard_fails_closed_without_forward_sample_or_positive_ci():
    r=build_scorecard(prospective=_prospective(closed=20,expectancy=0.2,ci=(-0.1,0.4)),exit_replay=_replay(),shadow_paper=_shadow())
    assert r["research_evidence_ready"] is False
    x=r["forward_evidence"]["trend_regime"]
    assert x["sample_sufficient"] is False
    assert x["uncertainty_supports_positive_edge"] is False


def test_scorecard_requires_point_in_time_replay_coverage():
    r=build_scorecard(prospective=_prospective(),exit_replay=_replay(closed=100,path=20),shadow_paper=_shadow())
    assert r["exit_replay"]["coverage_sufficient"] is False
    assert r["research_evidence_ready"] is False


def test_scorecard_rejects_pooled_shadow_paper_state():
    r=build_scorecard(prospective=_prospective(),exit_replay=_replay(),shadow_paper=_shadow(pooled=True))
    assert r["shadow_paper"]["populations_pooled"] is True
    assert r["research_evidence_ready"] is False
    assert r["production_strategy_modified"] is False
