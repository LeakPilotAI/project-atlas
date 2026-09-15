import json
from app.services.v6_evidence_trends import evidence_trends

def _row(ts,closed,exp,ci_ok=False,sample=False,coverage=0.2,noms=0):
    return {"event":"v6_forward_evidence_snapshot","timestamp":ts,"evidence":{"forward":{"trend_regime":{"closed":closed,"expectancy":exp,"expectancy_ci95":[0.01,0.2] if ci_ok else [-0.1,0.2],"sample_sufficient":sample,"positive_expectancy":exp>0,"uncertainty_supports_positive_edge":ci_ok,"research_evidence_ready":False}},"exit_replay":{"path_coverage":coverage},"shadow_paper":{"prospective_nomination_count":noms}}}

def test_trends_preserve_order_and_compute_growth_transitions(tmp_path):
    path=tmp_path/"history.jsonl"
    rows=[_row("2026-09-15T12:00:00+00:00",20,0.05),_row("2026-09-15T13:00:00+00:00",100,0.12,True,True,0.75,2)]
    path.write_text("\n".join(json.dumps(x) for x in rows)+"\n",encoding="utf-8")
    r=evidence_trends(path=path); s=r["summary"]["trend_regime"]
    assert r["snapshot_count"]==2
    assert [x["closed"] for x in r["series"]["trend_regime"]]==[20,100]
    assert s["closed_growth"]==80
    assert s["expectancy_change"]==0.07
    assert s["positive_ci_transitions"]==1
    assert s["sample_sufficiency_transitions"]==1
    assert r["history_rewritten"] is False
    assert r["normal_command_center_recompute"] is False
    assert r["trading_readiness"]=="NOT_READY"
    assert r["live_capital_allowed"] is False

def test_trends_empty_history_fails_closed(tmp_path):
    r=evidence_trends(path=tmp_path/"missing.jsonl")
    assert r["snapshot_count"]==0
    assert r["series"]=={}
    assert r["automatic_promotion"] is False
    assert r["automatic_real_money_execution"] is False
