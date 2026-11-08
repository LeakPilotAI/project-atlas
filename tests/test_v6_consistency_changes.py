import json
from pathlib import Path
from app.services.v6_consistency_changes import consistency_change_diagnostics


def add(p:Path,row):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8") as f:f.write(json.dumps(row)+"\n")
def member(p,day,regime,i):add(p,{"event":"membership","trade_id":f"{day}-{regime}-{i}","entry_timestamp":f"2026-09-{day:02d}T12:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":regime}})
def snap(p,day,hour,closed):add(p,{"event":"v6_forward_evidence_snapshot","timestamp":f"2026-09-{day:02d}T{hour:02d}:00:00+00:00","evidence":{"forward":{"trend_regime":{"closed":closed}}}})


def test_change_diagnostics_ignore_duplicate_refreshes(tmp_path):
    h=tmp_path/"h";m=tmp_path/"m"
    for i in range(10):member(m,10,"TREND_UP",i)
    snap(h,10,13,10);snap(h,10,14,10);snap(h,10,15,10)
    r=consistency_change_diagnostics(membership_path=m,history_path=h);c=r["candidates"]["trend_regime"]
    assert c["observation_count"]==1;assert c["transition_count"]==0;assert r["duplicate_refreshes_skipped"]==2


def test_change_diagnostics_report_window_and_disagreement_transitions(tmp_path):
    h=tmp_path/"h";m=tmp_path/"m"
    for d in (1,2,3):
        for regime in ("TREND_UP","TREND_DOWN"):
            for i in range(10):member(m,d,regime,i)
    snap(h,3,23,60)
    for d in (10,11,12):
        for i in range(10):member(m,d,"TREND_UP",100+i)
    snap(h,12,23,90)
    c=consistency_change_diagnostics(membership_path=m,history_path=h)["candidates"]["trend_regime"]
    assert c["transition_count"]==1;t=c["latest_transition"]
    assert set(t["windows"])=={"3","7","14"};assert t["windows"]["3"]["comparison_changed"] is True;assert t["disagreement_transition"] in {"ENTERED","LEFT","PERSISTED","ABSENT"}
    assert c["new_evidence_only"] is True


def test_change_diagnostics_fail_closed_and_never_unlock_live(tmp_path):
    r=consistency_change_diagnostics(membership_path=tmp_path/"m",history_path=tmp_path/"h")
    assert r["candidates"]=={};assert r["automatic_scoring"] is False;assert r["automatic_promotion"] is False;assert r["live_capital_allowed"] is False;assert r["automatic_real_money_execution"] is False
