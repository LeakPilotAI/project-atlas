from app.services.challenger_exit_replay import replay_exit_candidates


def _open(tid="x"):
    return {"event":"open","trade_id":tid,"trade_type":"PAPER","side":"LONG","actual_entry_price":100.0,"risk_price":10.0,"fees_bps":0.0,"slippage_bps":0.0}

def _mark(tid, ts, mark, *, mfe=99.0):
    return {"event":"mark","trade_id":tid,"trade_type":"PAPER","timestamp":ts,"mark":mark,"mfe_r":mfe}

def _close(tid="x", pnl=-1.0):
    return {"event":"close","trade_id":tid,"trade_type":"PAPER","net_pnl_r":pnl,"R_multiple":pnl,"mfe_r":9.0,"mae_r":1.0}


def test_replay_uses_mark_path_not_final_mfe():
    rows=[_open(),_mark("x","2026-09-15T00:01:00+00:00",104.0,mfe=9.0),_close()]
    r=replay_exit_candidates(rows)
    assert r["uses_final_mfe_to_trigger"] is False
    assert r["candidates"]["capture_0_5r"]["triggered"] == 0
    assert r["candidates"]["capture_1_0r"]["triggered"] == 0


def test_replay_triggers_only_after_observed_threshold():
    rows=[_open(),_mark("x","2026-09-15T00:01:00+00:00",104.0),_mark("x","2026-09-15T00:02:00+00:00",106.0),_close()]
    r=replay_exit_candidates(rows)
    assert r["candidates"]["capture_0_5r"]["triggered"] == 1
    assert r["candidates"]["capture_0_5r"]["metrics"]["total_r"] == 0.5
    assert r["candidates"]["capture_1_0r"]["triggered"] == 0
    assert r["production_strategy_modified"] is False
    assert r["live_capital_allowed"] is False


def test_short_direction_is_replayed_correctly():
    o=_open(); o["side"]="SHORT"
    rows=[o,_mark("x","2026-09-15T00:01:00+00:00",94.0),_close()]
    r=replay_exit_candidates(rows)
    assert r["candidates"]["capture_0_5r"]["triggered"] == 1


def test_costs_reduce_candidate_result_in_r():
    o=_open(); o["fees_bps"]=2.0; o["slippage_bps"]=1.0
    rows=[o,_mark("x","2026-09-15T00:01:00+00:00",106.0),_close()]
    r=replay_exit_candidates(rows)
    value=r["candidates"]["capture_0_5r"]["metrics"]["total_r"]
    assert 0.49 < value < 0.5


def test_missing_mark_path_cannot_manufacture_exit_from_close_mfe():
    r=replay_exit_candidates([_open(),_close(pnl=2.0)])
    assert r["candidates"]["capture_0_5r"]["path_eligible"] == 0
    assert r["candidates"]["capture_0_5r"]["triggered"] == 0
    assert r["candidates"]["capture_0_5r"]["metrics"]["total_r"] == 2.0
