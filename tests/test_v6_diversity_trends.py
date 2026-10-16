import json
from pathlib import Path
from app.services.v6_diversity_trends import diversity_trends

def add(p:Path,row):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8") as f:f.write(json.dumps(row)+"\n")

def snapshot(p,day):
    add(p,{"event":"v6_forward_evidence_snapshot","timestamp":f"2026-09-{day:02d}T23:00:00+00:00","evidence":{"forward":{"trend_regime":{"closed":100+day}}}})

def member(p,day,regime,i):
    add(p,{"event":"membership","trade_id":f"{day}-{regime}-{i}","entry_timestamp":f"2026-09-{day:02d}T12:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":regime}})

def test_trend_broadens_using_only_memberships_known_by_each_snapshot(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl"
    for i in range(10):member(m,1,"TREND_UP",i)
    snapshot(h,1)
    for i in range(10):member(m,2,"TREND_DOWN",i)
    snapshot(h,2)
    for i in range(10):member(m,3,"TREND_UP",10+i)
    snapshot(h,3)
    r=diversity_trends(membership_path=m,history_path=h);c=r["candidates"]["trend_regime"]
    assert c["trend"]=="BROADENING"
    assert c["series"][0]["membership_count"]==10
    assert c["series"][-1]["membership_count"]==30
    assert c["series"][0]["diversity_established"] is False
    assert c["series"][-1]["diversity_established"] is True
    assert r["retrospective_reclassification"] is False
    assert r["live_capital_allowed"] is False

def test_insufficient_history_fails_closed(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl";snapshot(h,1);snapshot(h,2)
    c=diversity_trends(membership_path=m,history_path=h)["candidates"]["trend_regime"]
    assert c["longitudinal_evidence_sufficient"] is False
    assert c["trend"]=="INSUFFICIENT_LONGITUDINAL_EVIDENCE"

def test_future_memberships_do_not_leak_into_old_snapshots(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl"
    snapshot(h,1);snapshot(h,2);snapshot(h,3)
    for i in range(20):member(m,4,"TREND_UP",i)
    c=diversity_trends(membership_path=m,history_path=h)["candidates"]["trend_regime"]
    assert all(p["membership_count"]==0 for p in c["series"])
    assert c["trend"]=="MIXED_OR_CONCENTRATED"
