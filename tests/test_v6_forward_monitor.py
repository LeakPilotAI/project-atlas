import json
from app.services.v6_forward_monitor import append_snapshot, monitor_status

def _report(closed,expectancy=0.1,coverage=0.5,noms=1):
    return {"forward_evidence":{"trend_regime":{"opened":closed,"closed":closed,"open":0,"expectancy":expectancy,"expectancy_ci95":[-0.1,0.3],"sample_sufficient":closed>=100,"positive_expectancy":expectancy>0,"uncertainty_supports_positive_edge":False,"research_evidence_ready":False}},"exit_replay":{"path_coverage":coverage,"coverage_sufficient":coverage>=0.7,"uses_final_mfe_to_trigger":False},"shadow_paper":{"prospective_nomination_count":noms,"populations_pooled":False},"research_evidence_ready":False,"trading_readiness":"NOT_READY","live_capital_allowed":False}

def test_monitor_appends_history_and_computes_deltas(tmp_path):
    path=tmp_path/"history.jsonl"
    a=append_snapshot(_report(20,0.1,0.4,1),path=path,timestamp="2026-09-15T12:00:00+00:00")
    b=append_snapshot(_report(27,0.15,0.5,3),path=path,timestamp="2026-09-15T13:00:00+00:00")
    lines=path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines)==2
    assert a["deltas"]["forward"]["trend_regime"]["closed_delta"]==20
    assert b["deltas"]["forward"]["trend_regime"]["closed_delta"]==7
    assert b["deltas"]["forward"]["trend_regime"]["expectancy_delta"]==0.05
    assert b["deltas"]["exit_replay_path_coverage_delta"]==0.1
    assert b["deltas"]["nomination_count_delta"]==2
    assert b["automatic_promotion"] is False
    assert b["automatic_real_money_execution"] is False

def test_monitor_status_is_read_only_and_fail_closed(tmp_path):
    path=tmp_path/"history.jsonl"
    assert monitor_status(path=path)["snapshot_count"]==0
    append_snapshot(_report(5),path=path)
    r=monitor_status(path=path)
    assert r["snapshot_count"]==1
    assert r["append_only"] is True
    assert r["trading_readiness"]=="NOT_READY"
    assert r["live_capital_allowed"] is False
