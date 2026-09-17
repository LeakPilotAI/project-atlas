import json
from app.services.v6_maturity_sequence_run_boundaries import maturity_sequence_run_boundary_diagnostics


def _write_fixture(tmp_path):
    members=tmp_path/"members.jsonl";history=tmp_path/"history.jsonl"
    rows=[
        {"event":"membership","trade_id":"t1","entry_timestamp":"2026-09-15T01:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":"TREND_UP"}},
        {"event":"membership","trade_id":"t2","entry_timestamp":"2026-09-15T02:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":"TREND_UP"}},
        {"event":"membership","trade_id":"t3","entry_timestamp":"2026-09-15T03:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":"TREND_UP"}},
        {"event":"membership","trade_id":"t4","entry_timestamp":"2026-09-15T04:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":"TREND_UP"}},
        {"event":"membership","trade_id":"t5","entry_timestamp":"2026-09-15T05:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":"TREND_UP"}},
    ]
    members.write_text("\n".join(json.dumps(x) for x in rows)+"\n",encoding="utf-8")
    snaps=[]
    for i,count in enumerate([1,2,3,4,5],start=1):
        snaps.append({"event":"v6_forward_evidence_snapshot","timestamp":f"2026-09-15T0{i}:30:00+00:00","evidence":{"forward":{"trend_regime":{"closed":count,"expectancy":0.1,"uncertainty_supports_positive_edge":False}},"shadow_paper":{"prospective_nomination_count":1}}})
    history.write_text("\n".join(json.dumps(x) for x in snaps)+"\n",encoding="utf-8")
    return members,history


def test_run_boundary_diagnostics_shape_and_safety(tmp_path):
    members,history=_write_fixture(tmp_path)
    r=maturity_sequence_run_boundary_diagnostics(membership_path=members,history_path=history)
    assert r["mode"]=="DESCRIPTIVE_MATURITY_RUN_BOUNDARY_TRANSITIONS"
    assert r["automatic_scoring"] is False;assert r["weighted_scoring"] is False;assert r["readiness_percentage"] is None
    assert r["live_capital_allowed"] is False;assert r["automatic_real_money_execution"] is False
    c=r["candidates"]["trend_regime"];assert c["minimum_observations_required"]==3;assert c["duplicate_refresh_resistant"] is True;assert c["new_evidence_only"] is True;assert c["production_promoted"] is False
    for dim in r["dimensions"]:
        d=c["dimensions"][dim]
        assert d["boundary_count"]==max(0,d["run_count"]-1)
        assert len(d["boundaries"])==d["boundary_count"]
        if d["boundaries"]:
            assert d["latest_boundary"]==d["boundaries"][-1]
            for b in d["boundaries"]:
                assert set(b)=={"boundary_index","from_outcome","from_length","to_outcome","to_length","transition"}


def test_run_boundary_missing_files_fail_closed(tmp_path):
    r=maturity_sequence_run_boundary_diagnostics(membership_path=tmp_path/"members.jsonl",history_path=tmp_path/"history.jsonl")
    assert r["candidates"]=={}
    assert r["duplicate_refreshes_skipped"]==0
    assert r["trading_readiness"]=="NOT_READY"
