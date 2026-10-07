from app.services.day_trading_cohort_diagnostics import build_day_trading_cohort_diagnostics


def test_cohorts_preserve_strategy_side_regime_and_native_r():
    rows = [
        {"strategy":"legacy","side":"LONG","regime_normalized":"TREND_UP","net_pnl_r":1.0,"exit_reason":"TP1","features":{"paper_execution_model_version":"v1"}},
        {"strategy":"legacy","side":"SHORT","regime_normalized":"TREND_DOWN","net_pnl_r":-0.5,"exit_reason":"STOP","features":{"paper_execution_model_version":"v1"}},
        {"strategy":"current","side":"SHORT","regime_normalized":"UNKNOWN","net_pnl_r":-1.0,"exit_reason":"SETUP_STOP","features":{"paper_execution_model_version":"v2"}},
    ]
    report = build_day_trading_cohort_diagnostics(rows)
    strategies = {x["cohort"]: x for x in report["by_strategy"]}
    assert report["overall"] == {"sample_size":3,"total_r":-0.5,"expectancy_r":-0.1667,"win_rate":0.3333}
    assert strategies["legacy"]["sample_size"] == 2
    assert strategies["legacy"]["expectancy_r"] == 0.25
    assert strategies["current"]["expectancy_r"] == -1.0


def test_cohorts_are_diagnostic_only_and_unknown_metadata_is_not_inferred():
    rows = [{"net_pnl_r":0.25}]
    report = build_day_trading_cohort_diagnostics(rows)
    assert report["by_strategy"][0]["cohort"] == "UNKNOWN"
    assert report["by_regime"][0]["cohort"] == "UNKNOWN"
    assert report["interpretation_only"] is True
    assert report["strategy_action"] is None
    assert report["threshold_change"] is None
    assert report["sizing_change"] is None
    assert report["execution_change"] is None
    assert report["promotion_allowed"] is False
    assert report["historical_evidence_rewritten"] is False
    assert report["live_capital_allowed"] is False
    assert report["automatic_real_money_execution"] is False


def test_cohort_partition_does_not_change_input_rows():
    rows = [{"strategy":"a","net_pnl_r":1.0},{"strategy":"b","net_pnl_r":-1.0}]
    before = [dict(row) for row in rows]
    report = build_day_trading_cohort_diagnostics(rows)
    assert rows == before
    assert sum(x["sample_size"] for x in report["by_strategy"]) == report["overall"]["sample_size"]
