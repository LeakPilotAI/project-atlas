import json
from app.services.v6_maturity_sequence_run_boundary_recurrence import _recurrence,maturity_sequence_run_boundary_recurrence_diagnostics


def _write_fixture(tmp_path):
    members=tmp_path/"members.jsonl";history=tmp_path/"history.jsonl"
    rows=[{"event":"membership","trade_id":f"t{i}","entry_timestamp":f"2026-09-15T0{i}:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":"TREND_UP"}} for i in range(1,6)]
    members.write_text("\n".join(json.dumps(x) for x in rows)+"\n",encoding="utf-8")
    snaps=[{"event":"v6_forward_evidence_snapshot","timestamp":f"2026-09-15T0{i}:30:00+00:00","evidence":{"forward":{"trend_regime":{"closed":i,"expectancy":0.1,"uncertainty_supports_positive_edge":False}},"shadow_paper":{"prospective_nomination_count":1}}} for i in range(1,6)]
    history.write_text("\n".join(json.dumps(x) for x in snaps)+"\n",encoding="utf-8")
    return members,history


def test_recurrence_groups_exact_transition_forms_and_preserves_lengths():
    boundaries=[
        {"boundary_index":1,"from_outcome":"PERSISTED","from_length":2,"to_outcome":"REVERSED","to_length":1,"transition":"PERSISTED->REVERSED"},
        {"boundary_index":2,"from_outcome":"REVERSED","from_length":1,"to_outcome":"PERSISTED","to_length":3,"transition":"REVERSED->PERSISTED"},
        {"boundary_index":3,"from_outcome":"PERSISTED","from_length":3,"to_outcome":"REVERSED","to_length":2,"transition":"PERSISTED->REVERSED"},
    ]
    rows=_recurrence(boundaries)
    assert [r["transition"] for r in rows]==["PERSISTED->REVERSED","REVERSED->PERSISTED"]
    first=rows[0];assert first["count"]==2;assert first["from_outcome"]=="PERSISTED";assert first["to_outcome"]=="REVERSED"
    assert first["occurrences"]==[{"boundary_index":1,"from_length":2,"to_length":1},{"boundary_index":3,"from_length":3,"to_length":2}]
    assert first["latest_occurrence"]=={"boundary_index":3,"from_length":3,"to_length":2}


def test_boundary_recurrence_shape_and_safety(tmp_path):
    members,history=_write_fixture(tmp_path);r=maturity_sequence_run_boundary_recurrence_diagnostics(membership_path=members,history_path=history)
    assert r["mode"]=="DESCRIPTIVE_MATURITY_RUN_BOUNDARY_RECURRENCE"
    assert r["automatic_scoring"] is False;assert r["weighted_scoring"] is False;assert r["readiness_percentage"] is None
    assert r["live_capital_allowed"] is False;assert r["automatic_real_money_execution"] is False
    c=r["candidates"]["trend_regime"];assert c["minimum_observations_required"]==3;assert c["duplicate_refresh_resistant"] is True;assert c["new_evidence_only"] is True;assert c["production_promoted"] is False
    for dim in r["dimensions"]:
        d=c["dimensions"][dim];assert d["distinct_transition_count"]==len(d["recurrences"])
        assert sum(x["count"] for x in d["recurrences"])==d["boundary_count"]


def test_boundary_recurrence_missing_files_fail_closed(tmp_path):
    r=maturity_sequence_run_boundary_recurrence_diagnostics(membership_path=tmp_path/"members.jsonl",history_path=tmp_path/"history.jsonl")
    assert r["candidates"]=={};assert r["duplicate_refreshes_skipped"]==0;assert r["trading_readiness"]=="NOT_READY"
