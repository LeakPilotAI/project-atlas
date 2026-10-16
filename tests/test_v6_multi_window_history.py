import json
from pathlib import Path
from app.services.v6_multi_window_history import multi_window_consistency_history


def add(p:Path,row):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8") as f:f.write(json.dumps(row)+"\n")

def member(p,day,regime,i):add(p,{"event":"membership","trade_id":f"{day}-{regime}-{i}","entry_timestamp":f"2026-09-{day:02d}T12:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":regime}})
def snap(p,day,hour,closed):add(p,{"event":"v6_forward_evidence_snapshot","timestamp":f"2026-09-{day:02d}T{hour:02d}:00:00+00:00","evidence":{"forward":{"trend_regime":{"closed":closed}}}})


def test_duplicate_refresh_does_not_create_false_history(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl"
    for i in range(10):member(m,10,"TREND_UP",i)
    snap(h,10,13,10);snap(h,10,14,10);snap(h,10,15,10)
    r=multi_window_consistency_history(membership_path=m,history_path=h);c=r["candidates"]["trend_regime"]
    assert c["observation_count"]==1;assert r["duplicate_refreshes_skipped"]==2;assert c["new_evidence_required"] is True


def test_new_forward_closed_evidence_creates_observation(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl"
    for i in range(10):member(m,10,"TREND_UP",i)
    snap(h,10,13,10);snap(h,10,14,11)
    c=multi_window_consistency_history(membership_path=m,history_path=h)["candidates"]["trend_regime"]
    assert c["observation_count"]==2;assert [p["forward_closed"] for p in c["series"]]==[10,11]


def test_history_preserves_all_windows_and_disagreement(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl"
    for d in (1,2,3):
        for regime in ("TREND_UP","TREND_DOWN"):
            for i in range(6):member(m,d,regime,i)
    for d in (10,11,12):
        for i in range(8):member(m,d,"TREND_UP",100+i)
    snap(h,12,23,150)
    p=multi_window_consistency_history(membership_path=m,history_path=h)["candidates"]["trend_regime"]["latest"]
    assert set(p["windows"])=={"3","7","14"};assert p["windows"]["3"]["comparison"]=="RECENT_CONCENTRATION";assert p["windows"]["14"]["comparison"]=="DIVERSITY_PERSISTS";assert p["window_disagreement"] is True


def test_missing_files_fail_closed(tmp_path):
    r=multi_window_consistency_history(membership_path=tmp_path/"m",history_path=tmp_path/"h")
    assert r["snapshot_count"]==0;assert r["candidates"]=={};assert r["live_capital_allowed"] is False;assert r["automatic_real_money_execution"] is False
