from app.services.e26_attribution import build_e26_attribution, CURRENT_MODEL


def _row(side="LONG", net=-1.0, model=CURRENT_MODEL, reason="SETUP_STOP",
         exit_price=98.5, stop=99.0, risk=1.0, score=72, symbol="BTC",
         vol=0.2, momentum=0.1, trend=0.2, mfe=0.3, mae=1.0):
    return {"strategy":"perp_setup_auto_v2_resting_limit","side":side,"net_pnl_r":net,
            "exit_reason":reason,"actual_exit_price":exit_price,"initial_stop":stop,
            "risk_price":risk,"signal_score":score,"symbol":symbol,
            "entry_timestamp":"2026-10-01T12:00:00+00:00","mfe_r":mfe,"mae_r":mae,
            "features":{"paper_execution_model_version":model,"volatility_pct":vol,
                        "momentum_pct":momentum,"trend_pct":trend}}


def test_stop_tail_separates_model_side_and_overshoot_bucket():
    rows=[_row(), _row(side="SHORT", model="legacy", stop=101, exit_price=107, net=-7)]
    report=build_e26_attribution(rows)
    tail=report["stop_tail_attribution"]
    cohorts={x["cohort"]:x for x in tail["by_execution_model_side"]}
    buckets={x["cohort"]:x for x in tail["by_overshoot_bucket"]}
    assert cohorts[f"{CURRENT_MODEL}|LONG"]["sample_size"] == 1
    assert cohorts["legacy|SHORT"]["sample_size"] == 1
    assert buckets["0.25-1.00R"]["sample_size"] == 1
    assert buckets[">5.00R"]["sample_size"] == 1


def test_stop_tail_reports_negative_r_contribution_without_rewriting():
    rows=[_row(net=-1.5), _row(reason="SETUP_TP1", net=3, exit_price=102),
          _row(side="SHORT", stop=101, exit_price=104, net=-4)]
    report=build_e26_attribution(rows)
    tail=report["stop_tail_attribution"]
    assert tail["all_negative_r"] == -5.5
    assert sum(x["sample_size"] for x in tail["by_overshoot_bucket"]) == 2
    assert report["counterfactual_fills_rewritten"] is False


def test_current_long_is_execution_model_scoped_and_read_only():
    rows=[_row(net=-1), _row(net=2, reason="SETUP_TP1", exit_price=102, mfe=2),
          _row(model="legacy", net=99), _row(side="SHORT", net=99)]
    before=[dict(r) for r in rows]
    report=build_e26_attribution(rows)
    assert report["current_adaptive_long"]["overall"]["sample_size"] == 2
    assert report["current_adaptive_long"]["overall"]["total_r"] == 1.0
    assert rows == before
    assert report["strategy_action"] is None
    assert report["threshold_change"] is None
    assert report["promotion_allowed"] is False
    assert report["live_capital_allowed"] is False
    assert report["automatic_real_money_execution"] is False
