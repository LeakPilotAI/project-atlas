import json
from pathlib import Path
from app.services.v6_maturity_sequence_run_lengths import _runs,maturity_sequence_run_length_diagnostics


def add(p:Path,row):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8") as f:f.write(json.dumps(row)+"\n")

def member(p,day,regime,i):add(p,{"event":"membership","trade_id":f"{day}-{regime}-{i}","entry_timestamp":f"2026-09-{day:02d}T12:00:00+00:00","challengers":["trend_regime"],"pre_entry_snapshot":{"regime":regime}})
def snap(p,day,hour,closed):add(p,{"event":"v6_forward_evidence_snapshot","timestamp":f"2026-09-{day:02d}T{hour:02d}:00:00+00:00","evidence":{"forward":{"trend_regime":{"closed":closed}}}})


def test_runs_groups_consecutive_outcomes():
    assert _runs([])==[]
    assert _runs(["PERSISTED","PERSISTED","REVERSED","REVERSED","PERSISTED"])==[
        {"outcome":"PERSISTED","length":2},{"outcome":"REVERSED","length":2},{"outcome":"PERSISTED","length":1}
    ]


def test_maturity_run_length_reports_current_and_previous_runs(tmp_path):
    h=tmp_path/"h.jsonl";m=tmp_path/"m.jsonl"
    for i in range(10):member(m,10,"TREND_UP",i)
    snap(h,10,13,0);snap(h,10,14,1);snap(h,10,15,2);snap(h,10,16,3)
    r=maturity_sequence_run_length_diagnostics(membership_path=m,history_path=h);c=r["candidates"]["trend_regime"]
    assert c["observation_count"]==4;assert c["confirmation_check_count"]==2
    d=c["dimensions"]["forward_sample"]
    assert d["sequence"]==["PERSISTED","PERSISTED"]
    assert d["run_count"]==1;assert d["current_run_length"]==2;assert d["current_run_outcome"]=="PERSISTED"
    assert d["previous_run_outcome"] is None;assert d["previous_run_length"]==0;assert d["run_boundary_present"] is False


def test_maturity_run_length_preserves_safety_and_fail_closed(tmp_path):
    r=maturity_sequence_run_length_diagnostics(membership_path=tmp_path/"m",history_path=tmp_path/"h")
    assert r["candidates"]=={};assert r["duplicate_refreshes_skipped"]==0
    assert r["automatic_scoring"] is False;assert r["weighted_scoring"] is False;assert r["readiness_percentage"] is None
    assert r["automatic_promotion"] is False;assert r["trading_readiness"]=="NOT_READY";assert r["live_capital_allowed"] is False;assert r["automatic_real_money_execution"] is False
