import json
from pathlib import Path
from app.services.v6_transition_persistence import transition_persistence_diagnostics


def add(p:Path,row):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8") as f:f.write(json.dumps(row)+"\n")
def member(p,day,regime,i):add(p,{"event":"membership","trade_id":f"{day}-{regime}-{i}","entry_timestamp":f"2026-09-{day:02d}T12:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":regime}})
def snap(p,day,closed):add(p,{"event":"v6_forward_evidence_snapshot","timestamp":f"2026-09-{day:02d}T23:00:00+00:00","evidence":{"forward":{"trend_regime":{"closed":closed}}}})


def test_requires_three_qualifying_observations(tmp_path):
    h=tmp_path/"h";m=tmp_path/"m"
    for i in range(10):member(m,10,"TREND_UP",i)
    snap(h,10,10);snap(h,11,11)
    c=transition_persistence_diagnostics(membership_path=m,history_path=h)["candidates"]["trend_regime"]
    assert c["observation_count"]==2;assert c["confirmation_check_count"]==0;assert c["minimum_observations_required"]==3


def test_persistence_check_preserves_all_windows(tmp_path):
    h=tmp_path/"h";m=tmp_path/"m"
    for d in (1,2,3):
        for regime in ("TREND_UP","TREND_DOWN"):
            for i in range(10):member(m,d,regime,i)
    snap(h,3,60)
    for d in (10,11,12):
        for i in range(10):member(m,d,"TREND_UP",100+i)
    snap(h,12,90);snap(h,13,91)
    c=transition_persistence_diagnostics(membership_path=m,history_path=h)["candidates"]["trend_regime"]
    assert c["confirmation_check_count"]==1;check=c["latest_check"]
    assert set(check["windows"])=={"3","7","14"}
    assert all(v["outcome"] in {"PERSISTED","REVERSED","CHANGED_AGAIN","BECAME_INSUFFICIENT"} for v in check["windows"].values())
    assert check["disagreement_outcome"] in {"PERSISTED","REVERSED","CHANGED_AGAIN"}


def test_duplicate_refreshes_cannot_create_confirmation(tmp_path):
    h=tmp_path/"h";m=tmp_path/"m"
    for i in range(10):member(m,10,"TREND_UP",i)
    snap(h,10,10);snap(h,11,11);snap(h,12,11)
    r=transition_persistence_diagnostics(membership_path=m,history_path=h);c=r["candidates"]["trend_regime"]
    assert c["observation_count"]==2;assert c["confirmation_check_count"]==0;assert r["duplicate_refreshes_skipped"]==1


def test_missing_data_fails_closed_and_live_locked(tmp_path):
    r=transition_persistence_diagnostics(membership_path=tmp_path/"m",history_path=tmp_path/"h")
    assert r["candidates"]=={};assert r["automatic_scoring"] is False;assert r["automatic_promotion"] is False;assert r["live_capital_allowed"] is False;assert r["automatic_real_money_execution"] is False
