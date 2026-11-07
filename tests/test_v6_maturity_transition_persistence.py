import json
from pathlib import Path
from app.services.v6_maturity_transition_persistence import maturity_transition_persistence


def add(p:Path,row):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8") as f:f.write(json.dumps(row)+"\n")

def member(p,day,regime,i):add(p,{"event":"membership","trade_id":f"{day}-{regime}-{i}","entry_timestamp":f"2026-09-{day:02d}T12:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":regime}})
def snap(p,day,hour,closed):add(p,{"event":"v6_forward_evidence_snapshot","timestamp":f"2026-09-{day:02d}T{hour:02d}:00:00+00:00","evidence":{"forward":{"trend_regime":{"closed":closed}}}})


def test_maturity_persistence_classifies_per_dimension_next_observation(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl"
    for i in range(10):member(m,10,"TREND_UP",i)
    snap(h,10,13,0);snap(h,10,14,1);snap(h,10,15,2)
    r=maturity_transition_persistence(membership_path=m,history_path=h);c=r["candidates"]["trend_regime"]
    assert c["observation_count"]==3;assert c["confirmation_check_count"]==1
    d=c["latest_check"]["dimensions"]
    assert d["forward_sample"]["transition"]=="MISSING->PRESENT"
    assert d["forward_sample"]["outcome"]=="PERSISTED"
    assert d["confirmation_depth"]["outcome"]=="CHANGED_AGAIN"
    assert set(d)==set(r["dimensions"])


def test_maturity_persistence_preserves_safety_and_duplicate_resistance(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl"
    for i in range(10):member(m,10,"TREND_UP",i)
    # Two unchanged refreshes (closed=1 and closed=2) are intentionally duplicates.
    # The retained-history engine counts each skipped refresh, so this fixture has two.
    snap(h,10,13,1);snap(h,10,14,1);snap(h,10,15,2);snap(h,10,16,2)
    r=maturity_transition_persistence(membership_path=m,history_path=h);c=r["candidates"]["trend_regime"]
    assert r["duplicate_refreshes_skipped"]==2
    assert c["observation_count"]==2;assert c["confirmation_check_count"]==0
    assert c["duplicate_refresh_resistant"] is True;assert c["new_evidence_only"] is True;assert c["production_promoted"] is False
    assert r["automatic_scoring"] is False;assert r["weighted_scoring"] is False;assert r["readiness_percentage"] is None
    assert r["automatic_promotion"] is False;assert r["live_capital_allowed"] is False;assert r["automatic_real_money_execution"] is False


def test_maturity_persistence_missing_files_fail_closed(tmp_path):
    r=maturity_transition_persistence(membership_path=tmp_path/"m",history_path=tmp_path/"h")
    assert r["candidates"]=={};assert r["duplicate_refreshes_skipped"]==0
    assert r["trading_readiness"]=="NOT_READY";assert r["live_capital_allowed"] is False
