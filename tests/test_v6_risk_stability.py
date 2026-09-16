import json
from app.services.v6_forward_monitor import append_snapshot
from app.services.v6_stability import stability_report

def _report():return {"forward_evidence":{"trend_regime":{"opened":130,"closed":120,"open":10,"expectancy":0.2,"expectancy_ci95":[0.05,0.35],"sample_sufficient":True,"positive_expectancy":True,"uncertainty_supports_positive_edge":True,"research_evidence_ready":True}},"exit_replay":{},"shadow_paper":{}}
def _comparison(candidate_dd=8.0,baseline_dd=10.0):return {"cutoff":"2026-09-15T00:00:00+00:00","baseline":{"closed":120,"metrics":{"expectancy":0.05,"max_drawdown_r":baseline_dd}},"candidates":{"trend_regime":{"closed":120,"metrics":{"expectancy":0.2,"max_drawdown_r":candidate_dd},"expectancy_delta_vs_baseline":0.15,"max_drawdown_delta_vs_baseline":candidate_dd-baseline_dd,"research_nomination":True}}}
def test_snapshot_persists_contemporaneous_risk_and_stability_passes(tmp_path):
    path=tmp_path/"history.jsonl"
    for ts in ("2026-09-15T00:00:00+00:00","2026-09-15T06:00:00+00:00","2026-09-15T12:00:00+00:00"):append_snapshot(_report(),path=path,timestamp=ts,comparison=_comparison())
    rows=[json.loads(x) for x in path.read_text().splitlines()]; risk=rows[-1]["evidence"]["risk_comparison"]
    assert risk["baseline"]["max_drawdown_r"]==10.0
    assert risk["candidates"]["trend_regime"]["max_drawdown_r"]==8.0
    c=stability_report(path=path)["candidates"]["trend_regime"]
    assert c["contemporaneous_risk_stable"] is True
    assert c["human_review_eligible"] is True

def test_material_drawdown_deterioration_blocks_human_review(tmp_path):
    path=tmp_path/"history.jsonl"
    for ts in ("2026-09-15T00:00:00+00:00","2026-09-15T06:00:00+00:00","2026-09-15T12:00:00+00:00"):append_snapshot(_report(),path=path,timestamp=ts,comparison=_comparison(candidate_dd=12.0,baseline_dd=10.0))
    c=stability_report(path=path)["candidates"]["trend_regime"]
    assert c["contemporaneous_risk_stable"] is False
    assert c["human_review_eligible"] is False

def test_old_snapshots_without_risk_data_fail_closed_for_review(tmp_path):
    path=tmp_path/"history.jsonl"; rows=[]
    for ts in ("2026-09-15T00:00:00+00:00","2026-09-15T06:00:00+00:00","2026-09-15T12:00:00+00:00"):rows.append({"event":"v6_forward_evidence_snapshot","timestamp":ts,"evidence":{"forward":{"trend_regime":{"closed":120,"expectancy":0.2,"uncertainty_supports_positive_edge":True}}}})
    path.write_text("\n".join(json.dumps(r) for r in rows)+"\n")
    c=stability_report(path=path)["candidates"]["trend_regime"]
    assert c["contemporaneous_risk_stable"] is False
    assert c["human_review_eligible"] is False
