from app.services import e28_challenger_workbench as w


def _open(tid,momentum,trend,score=72.0,vol=0.3,ts="2026-10-01T00:00:00+00:00"):
    return {"event":"open","trade_type":"PAPER","trade_id":tid,"symbol":"BTC","side":"LONG",
            "strategy":w.BASELINE_STRATEGY,"entry_timestamp":ts,"signal_score":score,
            "features":{"momentum_pct":momentum,"trend_pct":trend,"volatility_pct":vol,
                        "paper_execution_model_version":w.BASELINE_EXECUTION_MODEL}}


def test_e28_threshold_derivation_is_open_only_and_outcome_blind():
    rows=[_open("a",0.1,0.2),_open("b",0.3,0.4),_open("c",0.5,0.6)]
    rows += [{"event":"close","trade_id":"a","pnl_r":999,"mfe_r":99,"mae_r":0,"exit_reason":"MAGIC"}]
    a=w.derive_outcome_blind_rule(rows)
    b=w.derive_outcome_blind_rule(rows[:-1])
    assert a==b
    assert a["thresholds"]=={"momentum_pct_min":0.3,"trend_pct_min":0.4}


def test_e28_membership_is_decidable_from_registered_open_snapshot_only():
    thresholds={"momentum_pct_min":0.3,"trend_pct_min":0.4}
    assert w.qualifies({"signal_score":70,"momentum_pct":0.3,"trend_pct":0.4,"volatility_pct":0.2},thresholds)
    assert not w.qualifies({"signal_score":70,"momentum_pct":0.29,"trend_pct":0.4,"volatility_pct":0.2},thresholds)
    assert not w.qualifies({"signal_score":70,"momentum_pct":0.4,"trend_pct":0.5,"volatility_pct":None},thresholds)


def test_e28_post_freeze_and_incompatible_rows_cannot_enter_derivation():
    rows=[_open("good",0.2,0.3)]
    rows.append(_open("future",9,9,ts="9999-12-31T00:00:00+00:00"))
    wrong=_open("wrong",9,9); wrong["features"]["paper_execution_model_version"]="legacy"; rows.append(wrong)
    d=w.derive_outcome_blind_rule(rows)
    assert d["derivation_open_count"]==1
    assert d["thresholds"]=={"momentum_pct_min":0.2,"trend_pct_min":0.3}


def test_e28_report_freezes_forward_boundary_without_strategy_authority():
    r=w.e28_workbench(rows=[_open("a",0.2,0.3),_open("b",0.4,0.5)])
    assert r["challenger_version"]=="perp-setup-v2-long-selection-v1"
    assert r["forward_membership"]["historical_rows_count_as_prospective"] is False
    assert r["forward_membership"]["membership_decidable_from_open_snapshot_only"] is True
    assert r["leakage_controls"]["pnl_optimization"] is False
    assert r["e27_acceptance_gate_unchanged"] is True
    assert r["production_strategy_modified"] is False
    assert r["live_capital_allowed"] is False
    assert r["automatic_real_money_execution"] is False