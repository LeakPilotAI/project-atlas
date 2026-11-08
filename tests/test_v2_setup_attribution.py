from app.services.v2_setup_attribution import build_v2_setup_attribution


def _row(side="LONG", score=75, net=1.0, model="m1", reason="SETUP_TP1",
         mfe=1.8, mae=0.2, entry=100.0, stop=99.0, exit_price=101.8):
    return {
        "strategy":"perp_setup_auto_v2_resting_limit","side":side,"signal_score":score,
        "net_pnl_r":net,"exit_reason":reason,"mfe_r":mfe,"mae_r":mae,
        "actual_entry_price":entry,"initial_stop":stop,"actual_exit_price":exit_price,
        "risk_price":1.0,"features":{"paper_execution_model_version":model},
    }


def test_version_and_side_are_not_pooled():
    rows=[_row("LONG",net=1,model="old"),_row("SHORT",net=-2,model="old"),
          _row("SHORT",net=0.5,model="current"),{"strategy":"rsi_extension_v1","net_pnl_r":99}]
    report=build_v2_setup_attribution(rows)
    cohorts={x["cohort"]:x for x in report["by_execution_model_and_side"]}
    assert report["overall"]["sample_size"] == 3
    assert cohorts["old|SHORT"]["expectancy_r"] == -2.0
    assert cohorts["current|SHORT"]["expectancy_r"] == 0.5


def test_setup_stop_overshoot_uses_recorded_geometry_only():
    long=_row("LONG",net=-1.5,reason="SETUP_STOP",entry=100,stop=99,exit_price=98.5)
    short=_row("SHORT",net=-2.0,reason="SETUP_STOP",entry=100,stop=101,exit_price=103)
    report=build_v2_setup_attribution([long,short])
    assert report["setup_stop_overshoot"]["long"]["average_r_beyond_initial_stop"] == 0.5
    assert report["setup_stop_overshoot"]["short"]["average_r_beyond_initial_stop"] == 2.0
    assert report["setup_stop_overshoot"]["all"]["sample_size"] == 2


def test_attribution_is_read_only_and_does_not_infer_causality():
    rows=[_row()]
    before=[dict(rows[0])]
    report=build_v2_setup_attribution(rows)
    assert rows == before
    assert report["selection_execution_exit_not_causally_resolved"] is True
    assert report["unknown_metadata_backfilled"] is False
    assert report["strategy_action"] is None
    assert report["threshold_change"] is None
    assert report["sizing_change"] is None
    assert report["execution_change"] is None
    assert report["promotion_allowed"] is False
    assert report["historical_evidence_rewritten"] is False
    assert report["live_capital_allowed"] is False
    assert report["automatic_real_money_execution"] is False
