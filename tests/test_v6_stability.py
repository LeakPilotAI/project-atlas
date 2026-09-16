import json
from app.services.v6_stability import stability_report

def _row(ts,closed=120,exp=0.15,ci_ok=True):
    return {"event":"v6_forward_evidence_snapshot","timestamp":ts,"evidence":{"forward":{"trend_regime":{"closed":closed,"expectancy":exp,"uncertainty_supports_positive_edge":ci_ok}}}}
def _write(path,rows):path.write_text("\n".join(json.dumps(r) for r in rows)+"\n",encoding="utf-8")

def test_three_separated_qualifying_snapshots_enable_human_review_only(tmp_path):
    path=tmp_path/"history.jsonl"; _write(path,[_row("2026-09-15T00:00:00+00:00"),_row("2026-09-15T06:00:00+00:00"),_row("2026-09-15T12:00:00+00:00")])
    r=stability_report(path=path); c=r["candidates"]["trend_regime"]
    assert c["qualifying_snapshot_count"]==3
    assert c["human_review_eligible"] is True
    assert c["production_promoted"] is False
    assert r["human_review_eligible"]==["trend_regime"]
    assert r["trading_readiness"]=="NOT_READY"
    assert r["live_capital_allowed"] is False
    assert r["automatic_real_money_execution"] is False

def test_close_spacing_does_not_count_as_independent_snapshots(tmp_path):
    path=tmp_path/"history.jsonl"; _write(path,[_row("2026-09-15T00:00:00+00:00"),_row("2026-09-15T01:00:00+00:00"),_row("2026-09-15T02:00:00+00:00")])
    c=stability_report(path=path)["candidates"]["trend_regime"]
    assert c["qualifying_snapshot_count"]==1
    assert c["human_review_eligible"] is False

def test_low_sample_or_nonpositive_ci_never_qualifies(tmp_path):
    path=tmp_path/"history.jsonl"; _write(path,[_row("2026-09-15T00:00:00+00:00",closed=99),_row("2026-09-15T06:00:00+00:00",ci_ok=False),_row("2026-09-15T12:00:00+00:00",exp=-0.1)])
    c=stability_report(path=path)["candidates"]["trend_regime"]
    assert c["qualifying_snapshot_count"]==0
    assert c["human_review_eligible"] is False
