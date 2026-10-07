import json
from pathlib import Path
from app.services.v6_maturity_transitions import maturity_change_history


def add(p:Path,row):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8") as f:f.write(json.dumps(row)+"\n")

def member(p,day,regime,i):add(p,{"event":"membership","trade_id":f"{day}-{regime}-{i}","entry_timestamp":f"2026-09-{day:02d}T12:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":regime}})
def snap(p,day,hour,closed):add(p,{"event":"v6_forward_evidence_snapshot","timestamp":f"2026-09-{day:02d}T{hour:02d}:00:00+00:00","evidence":{"forward":{"trend_regime":{"closed":closed}}}})


def test_maturity_transitions_follow_retained_new_evidence_only(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl"
    for i in range(10):member(m,10,"TREND_UP",i)
    snap(h,10,13,0);snap(h,10,14,0);snap(h,10,15,1);snap(h,10,16,2)
    r=maturity_change_history(membership_path=m,history_path=h);c=r["candidates"]["trend_regime"]
    assert c["observation_count"]==3;assert c["transition_count"]==2;assert r["duplicate_refreshes_skipped"]==1
    assert c["transitions"][0]["dimensions"]["forward_sample"]["transition"]=="MISSING->PRESENT"
    assert c["transitions"][1]["dimensions"]["forward_sample"]["transition"]=="PRESENT->PRESENT"
    assert c["transitions"][1]["dimensions"]["confirmation_depth"]["transition"]=="MISSING->PRESENT"


def test_maturity_transition_output_preserves_all_dimensions_and_safety_locks(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl"
    for i in range(10):member(m,10,"TREND_UP",i)
    snap(h,10,13,1);snap(h,10,14,2)
    r=maturity_change_history(membership_path=m,history_path=h);t=r["candidates"]["trend_regime"]["latest_transition"]
    assert set(t["dimensions"])==set(r["dimensions"])
    assert r["mode"]=="DESCRIPTIVE_MATURITY_NEW_EVIDENCE_TRANSITIONS"
    assert r["automatic_scoring"] is False;assert r["weighted_scoring"] is False;assert r["readiness_percentage"] is None
    assert r["automatic_promotion"] is False;assert r["live_capital_allowed"] is False;assert r["automatic_real_money_execution"] is False


def test_maturity_transitions_missing_files_fail_closed(tmp_path):
    r=maturity_change_history(membership_path=tmp_path/"m",history_path=tmp_path/"h")
    assert r["candidates"]=={};assert r["duplicate_refreshes_skipped"]==0
    assert r["trading_readiness"]=="NOT_READY";assert r["live_capital_allowed"] is False
