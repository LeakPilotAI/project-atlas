import json
from pathlib import Path
from app.services.v6_fixed_window_diversity import fixed_window_diversity,multi_window_diversity

def add(p:Path,row):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8") as f:f.write(json.dumps(row)+"\n")
def member(p,day,regime,i):add(p,{"event":"membership","trade_id":f"{day}-{regime}-{i}","entry_timestamp":f"2026-09-{day:02d}T12:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":regime}})
def snap(p,day):add(p,{"event":"v6_forward_evidence_snapshot","timestamp":f"2026-09-{day:02d}T23:00:00+00:00","evidence":{"forward":{"trend_regime":{"closed":150}}}})

def test_recent_concentration_detected_when_cumulative_history_is_diverse(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl"
    for d in (1,2,3):
        for regime in ("TREND_UP","TREND_DOWN"):
            for i in range(10):member(m,d,regime,i)
    for d in (10,11,12):
        for i in range(10):member(m,d,"TREND_UP",100+i)
    snap(h,12);c=fixed_window_diversity(membership_path=m,history_path=h,window_days=7)["candidates"]["trend_regime"]
    assert c["cumulative"]["diversity_established"] is True;assert c["recent_window"]["diversity_established"] is False;assert c["recent_window_evidence_sufficient"] is True;assert c["comparison"]=="RECENT_CONCENTRATION"

def test_recent_window_fails_closed_when_sample_is_small(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl"
    for i in range(5):member(m,12,"TREND_UP",i)
    snap(h,12);c=fixed_window_diversity(membership_path=m,history_path=h)["candidates"]["trend_regime"]
    assert c["recent_window_evidence_sufficient"] is False;assert c["comparison"]=="INSUFFICIENT_RECENT_WINDOW_EVIDENCE"

def test_future_memberships_are_excluded(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl";snap(h,12)
    for i in range(25):member(m,13,"TREND_UP",i)
    c=fixed_window_diversity(membership_path=m,history_path=h)["candidates"]["trend_regime"]
    assert c["recent_window"]["membership_count"]==0;assert c["cumulative"]["membership_count"]==0

def test_multi_window_reports_all_predeclared_windows_without_selection(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl"
    for d in (1,2,3):
        for regime in ("TREND_UP","TREND_DOWN"):
            for i in range(6):member(m,d,regime,i)
    for d in (10,11,12):
        for i in range(8):member(m,d,"TREND_UP",100+i)
    snap(h,12);r=multi_window_diversity(membership_path=m,history_path=h);c=r["candidates"]["trend_regime"]
    assert [x["days"] for x in r["predeclared_windows"]]==[3,7,14]
    assert [x["minimum_memberships"] for x in r["predeclared_windows"]]==[10,20,30]
    assert set(c["windows"])=={"3","7","14"};assert r["all_windows_reported"] is True;assert r["best_window_selection"] is False;assert c["selected_best_window"] is None
    assert c["windows"]["3"]["comparison"]=="RECENT_CONCENTRATION";assert c["windows"]["7"]["comparison"]=="RECENT_CONCENTRATION";assert c["windows"]["14"]["comparison"]=="DIVERSITY_PERSISTS";assert c["window_disagreement"] is True

def test_multi_window_insufficient_windows_remain_visible(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl"
    for i in range(11):member(m,12,"TREND_UP",i)
    snap(h,12);c=multi_window_diversity(membership_path=m,history_path=h)["candidates"]["trend_regime"]
    assert c["windows"]["3"]["recent_window_evidence_sufficient"] is True
    assert c["windows"]["7"]["comparison"]=="INSUFFICIENT_RECENT_WINDOW_EVIDENCE"
    assert c["windows"]["14"]["comparison"]=="INSUFFICIENT_RECENT_WINDOW_EVIDENCE"
