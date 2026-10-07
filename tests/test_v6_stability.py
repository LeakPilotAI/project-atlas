import json
from app.services.v6_stability import stability_report

def _row(ts,closed=120,exp=0.15,ci_ok=True,candidate_dd=8.0,baseline_dd=10.0):
    return {"event":"v6_forward_evidence_snapshot","timestamp":ts,"evidence":{"forward":{"trend_regime":{"closed":closed,"expectancy":exp,"uncertainty_supports_positive_edge":ci_ok}},"risk_comparison":{"baseline":{"closed":max(120,closed),"max_drawdown_r":baseline_dd},"candidates":{"trend_regime":{"closed":closed,"max_drawdown_r":candidate_dd}}}}}
def _write(path,rows):path.write_text("\n".join(json.dumps(r) for r in rows)+"\n",encoding="utf-8")

def test_three_separated_snapshots_with_new_closes_enable_human_review_only(tmp_path):
    path=tmp_path/"history.jsonl"; _write(path,[_row("2026-09-15T00:00:00+00:00",120),_row("2026-09-15T06:00:00+00:00",121),_row("2026-09-15T12:00:00+00:00",122)])
    r=stability_report(path=path); c=r["candidates"]["trend_regime"]
    assert c["qualifying_snapshot_count"]==3
    assert c["independence_established"] is True
    assert c["contemporaneous_risk_stable"] is True
    assert c["human_review_eligible"] is True
    assert c["production_promoted"] is False
    assert r["human_review_eligible"]==["trend_regime"]
    assert r["trading_readiness"]=="NOT_READY"
    assert r["live_capital_allowed"] is False
    assert r["automatic_real_money_execution"] is False

def test_repeated_refreshes_over_unchanged_closes_do_not_create_stability(tmp_path):
    path=tmp_path/"history.jsonl"; _write(path,[_row("2026-09-15T00:00:00+00:00",120),_row("2026-09-15T06:00:00+00:00",120),_row("2026-09-15T12:00:00+00:00",120)])
    c=stability_report(path=path)["candidates"]["trend_regime"]
    assert c["raw_qualifying_snapshot_count"]==3
    assert c["qualifying_snapshot_count"]==1
    assert c["rejected_unchanged_evidence"]==2
    assert c["independence_established"] is False
    assert c["human_review_eligible"] is False

def test_new_closes_without_time_separation_remain_dependent(tmp_path):
    path=tmp_path/"history.jsonl"; _write(path,[_row("2026-09-15T00:00:00+00:00",120),_row("2026-09-15T01:00:00+00:00",121),_row("2026-09-15T02:00:00+00:00",122)])
    c=stability_report(path=path)["candidates"]["trend_regime"]
    assert c["qualifying_snapshot_count"]==1
    assert c["rejected_temporal_dependence"]==2
    assert c["human_review_eligible"] is False

def test_low_sample_or_nonpositive_ci_never_qualifies(tmp_path):
    path=tmp_path/"history.jsonl"; _write(path,[_row("2026-09-15T00:00:00+00:00",closed=99),_row("2026-09-15T06:00:00+00:00",closed=120,ci_ok=False),_row("2026-09-15T12:00:00+00:00",closed=121,exp=-0.1)])
    c=stability_report(path=path)["candidates"]["trend_regime"]
    assert c["qualifying_snapshot_count"]==0
    assert c["human_review_eligible"] is False
