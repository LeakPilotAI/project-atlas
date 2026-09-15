import json
from app.services.v6_research_status import research_status
from app.services.command_center_summary import build_command_center_summary


def test_lightweight_status_reads_durable_cutoff_without_recompute(tmp_path):
    marker=tmp_path/"marker.json"; members=tmp_path/"members.jsonl"
    marker.write_text(json.dumps({"cohort":"v6_forward_only","started_at":"2026-09-15T12:00:00+00:00"}),encoding="utf-8")
    members.write_text(json.dumps({"event":"membership","trade_id":"a","challengers":["trend_regime","quality_85"]})+"\n",encoding="utf-8")
    r=research_status(marker_path=marker,membership_path=members)
    assert r["heavy_retrospective_recompute"] is False
    assert r["prospective"]["initialized"] is True
    assert r["prospective"]["unique_memberships"]==1
    assert r["prospective"]["by_challenger"]["quality_85"]==1
    assert r["trading_readiness"]=="NOT_READY"
    assert r["live_capital_allowed"] is False


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
