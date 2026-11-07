import json
from app.services.v6_evidence_sufficiency_gaps import evidence_sufficiency_gaps


def _write_memberships(path,count,name="trend_regime"):
    rows=[]
    for i in range(count):
        rows.append({"event":"membership","trade_id":f"t{i}","entry_timestamp":f"2026-09-{10+i//10:02d}T12:00:00+00:00","challengers":[name],"pre_entry_snapshot":{"regime":"TREND_UP"}})
    path.write_text("".join(json.dumps(r)+"\n" for r in rows),encoding="utf-8")


def _write_snapshot(path,closed=5):
    row={"event":"v6_forward_evidence_snapshot","timestamp":"2026-09-16T23:00:00+00:00","evidence":{"forward":{"trend_regime":{"closed":closed}}}}
    path.write_text(json.dumps(row)+"\n",encoding="utf-8")


def test_reports_window_membership_gaps_and_confirmation_gap(tmp_path):
    members=tmp_path/"members.jsonl";history=tmp_path/"history.jsonl";_write_memberships(members,15);_write_snapshot(history)
    r=evidence_sufficiency_gaps(membership_path=members,history_path=history);c=r["candidates"]["trend_regime"]
    assert c["observation_count"]==1;assert c["minimum_observations_required"]==3;assert c["confirmation_observation_gap"]==2;assert c["confirmation_layer_sufficient"] is False
    assert c["windows"]["3"]["required_memberships"]==10;assert c["windows"]["3"]["membership_gap"]>=0
    assert c["windows"]["7"]["required_memberships"]==20;assert c["windows"]["14"]["required_memberships"]==30
    assert all(w["membership_gap"]==max(0,w["required_memberships"]-w["current_memberships"]) for w in c["windows"].values())
    assert r["readiness_score"] is None;assert r["automatic_scoring"] is False;assert r["best_window_selection"] is False
    assert r["trading_readiness"]=="NOT_READY";assert r["live_capital_allowed"] is False;assert r["automatic_real_money_execution"] is False


def test_missing_files_fail_closed(tmp_path):
    r=evidence_sufficiency_gaps(membership_path=tmp_path/"members.jsonl",history_path=tmp_path/"history.jsonl")
    assert r["candidates"]=={};assert r["readiness_score"] is None;assert r["automatic_scoring"] is False;assert r["automatic_promotion"] is False;assert r["live_capital_allowed"] is False
