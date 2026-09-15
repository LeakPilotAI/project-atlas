import json
from app.services.v6_research_status import research_status
from app.services.command_center_summary import build_command_center_summary


def test_lightweight_status_reads_durable_cutoff_without_recompute(tmp_path):
    marker=tmp_path/"marker.json"; members=tmp_path/"members.jsonl"; cache=tmp_path/"cache.json"
    marker.write_text(json.dumps({"cohort":"v6_forward_only","started_at":"2026-09-15T12:00:00+00:00"}),encoding="utf-8")
    members.write_text(json.dumps({"event":"membership","trade_id":"a","challengers":["trend_regime","quality_85"]})+"\n",encoding="utf-8")
    r=research_status(marker_path=marker,membership_path=members,scorecard_cache_path=cache)
    assert r["heavy_retrospective_recompute"] is False
    assert r["prospective"]["initialized"] is True
    assert r["prospective"]["unique_memberships"]==1
    assert r["prospective"]["by_challenger"]["quality_85"]==1
    assert r["readiness_progress"]["source"]=="DURABLE_MEMBERSHIP_ONLY"
    assert r["trading_readiness"]=="NOT_READY"
    assert r["live_capital_allowed"] is False


def test_lightweight_status_surfaces_cached_scorecard_progress(tmp_path):
    marker=tmp_path/"marker.json"; members=tmp_path/"members.jsonl"; cache=tmp_path/"cache.json"
    marker.write_text(json.dumps({"cohort":"v6_forward_only","started_at":"2026-09-15T12:00:00+00:00"}),encoding="utf-8")
    members.write_text(json.dumps({"event":"membership","trade_id":"a","challengers":["trend_regime"]})+"\n",encoding="utf-8")
    cache.write_text(json.dumps({"forward_evidence":{"trend_regime":{"closed":25,"positive_expectancy":True,"uncertainty_supports_positive_edge":False}},"exit_replay":{"path_coverage":0.35,"coverage_sufficient":False},"shadow_paper":{"prospective_nomination_count":2,"populations_pooled":False},"research_evidence_ready":False}),encoding="utf-8")
    r=research_status(marker_path=marker,membership_path=members,scorecard_cache_path=cache); p=r["readiness_progress"]
    assert p["source"]=="CACHED_SCORECARD"
    assert p["forward"]["trend_regime"]["closed"]==25
    assert p["forward"]["trend_regime"]["closed_progress"]==0.25
    assert p["exit_replay"]["coverage_progress"]==0.5
    assert p["shadow_paper"]["prospective_nomination_count"]==2
    assert p["trading_readiness"]=="NOT_READY"


def test_command_center_keeps_research_distinct_from_domains():
    status={"domain":"V6_RESEARCH","trading_readiness":"NOT_READY","live_capital_allowed":False}
    out=build_command_center_summary({"running":True,"setups":[],"plans":[]},[],[],v6_status=status)
    assert out["research"] is status
    assert out["research_guardrails"]["research_is_trading_readiness"] is False
    assert out["research_guardrails"]["automatic_promotion"] is False
    assert out["research_guardrails"]["live_capital_allowed"] is False
    assert out["execution"]=="NO_ORDER_ACTIONS"
    assert out["perps"]["execution"]=="MANUAL_ONLY"
    assert out["investments"]["execution"]=="MANUAL_ONLY"
