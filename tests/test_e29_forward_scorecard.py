from pathlib import Path
from app.services import e29_forward_scorecard as s


def _open(tid,m=1,t=1,sym="BTC",ts=None):
    ts=ts or s.FREEZE_START_UTC
    return {"event":"open","trade_type":"PAPER","trade_id":tid,"symbol":sym,"side":"LONG",
      "strategy":s.BASELINE_STRATEGY,"entry_timestamp":ts,"signal_score":75,
      "features":{"momentum_pct":m,"trend_pct":t,"volatility_pct":0.3,
      "paper_execution_model_version":s.BASELINE_EXECUTION_MODEL}}


def _close(o,r=1):
    return {**o,"event":"close","exit_timestamp":"9999-01-01T00:00:00+00:00",
      "net_pnl_r":r,"mfe_r":max(r,0),"mae_r":max(-r,0),"exit_reason":"TP" if r>0 else "SETUP_STOP",
      "actual_exit_price":100,"initial_stop":99,"risk_price":1,"slippage_bps":2}


def test_e29_membership_is_append_only_and_close_cannot_reclassify(tmp_path):
    p=tmp_path/"m.jsonl"; o=_open("x",9,9)
    a,n=s.sync_membership([o],p); assert n==1 and a["x"]["challenger_member"] is True
    poisoned=_close({**o,"features":{**o["features"],"momentum_pct":-999,"trend_pct":-999}},-10)
    b,n2=s.sync_membership([o,poisoned],p)
    assert n2==0 and b["x"]["challenger_member"] is True
    assert len(p.read_text().strip().splitlines())==1


def test_e29_pre_freeze_open_never_enters_membership(tmp_path):
    p=tmp_path/"m.jsonl"; o=_open("old",9,9,ts="2026-01-01T00:00:00+00:00")
    m,n=s.sync_membership([o],p); assert n==0 and m=={}


def test_e29_small_lucky_sample_is_not_ready_or_promotable(tmp_path):
    p=tmp_path/"m.jsonl"; o=_open("lucky",9,9); rows=[o,_close(o,100)]
    r=s.e29_forward_scorecard(rows=rows,membership_path=p)
    assert r["status"]=="NOT_READY"
    assert r["challenger"]["expectancy_r_after_recorded_costs"]==100
    assert r["promotion_allowed"] is False
    assert not all(r["minimum_evidence_gates"].values())


def test_e29_scorecard_separates_baseline_and_challenger(tmp_path):
    p=tmp_path/"m.jsonl"; good=_open("good",9,9); bad=_open("bad",-9,-9)
    r=s.e29_forward_scorecard(rows=[good,bad,_close(good,1),_close(bad,-1)],membership_path=p)
    assert r["baseline"]["closed_trades"]==2
    assert r["challenger"]["closed_trades"]==1
    assert r["membership_classified_from_close"] is False
    assert r["thresholds_mutable"] is False
    assert r["live_capital_allowed"] is False