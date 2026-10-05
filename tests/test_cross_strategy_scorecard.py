from app.services.cross_strategy_scorecard import build_cross_strategy_scorecard


def test_cross_strategy_scorecard_preserves_native_units_and_no_universal_metric():
    day = [
        {"net_pnl_r": 1.0, "result": "TP", "exit_timestamp": "2026-10-05T10:00:00+00:00"},
        {"net_pnl_r": -0.5, "result": "STOP", "exit_timestamp": "2026-10-05T11:00:00+00:00"},
    ]
    investment = {
        "paper_policy_version": "QUALITY_DIPS_PAPER_V1",
        "summary": {"open_lots": 1, "closed_lots": 2},
        "closed_lots": [
            {"realized_return_pct": 10.0, "realized_pnl": 10.0},
            {"realized_return_pct": -4.0, "realized_pnl": -4.0},
        ],
        "timeline": [{"event": "close_lot", "timestamp": "2026-10-05T12:00:00+00:00"}],
    }
    prediction = {
        "engine_version": "prediction-paper-reprice-v1",
        "summary": {
            "open_positions": 0,
            "closed_trades": 2,
            "net_pnl_dollars": 6.0,
            "win_rate": 0.5,
            "expired_unclosed_trades": 0,
        },
        "events": [{"event": "close", "timestamp": "2026-10-05T13:00:00+00:00"}],
    }

    report = build_cross_strategy_scorecard(
        day_rows=day,
        investment_snapshot=investment,
        prediction_snapshot=prediction,
    )
    lanes = {row["lane"]: row for row in report["lanes"]}

    assert lanes["DAY_TRADING"]["expectancy"] == 0.25
    assert lanes["DAY_TRADING"]["expectancy_unit"] == "R_PER_CLOSED_TRADE"
    assert lanes["INVESTMENT_QUALITY_DIPS_V1"]["expectancy"] == 3.0
    assert lanes["INVESTMENT_QUALITY_DIPS_V1"]["expectancy_unit"] == "MEAN_REALIZED_RETURN_PCT_PER_CLOSED_LOT"
    assert lanes["PREDICTION"]["expectancy"] == 3.0
    assert lanes["PREDICTION"]["expectancy_unit"] == "NET_DOLLARS_PER_CLOSED_REPRICING_TRADE"
    assert report["comparison_rules"]["universal_win_rate"] is None
    assert report["comparison_rules"]["universal_expectancy"] is None
    assert report["comparison_rules"]["pool_lane_pnl"] is False
    assert report["live_capital_allowed"] is False
    assert report["automatic_real_money_execution"] is False


def test_cross_strategy_scorecard_keeps_missing_samples_unavailable_not_zero():
    report = build_cross_strategy_scorecard(
        day_rows=[],
        investment_snapshot={
            "paper_policy_version": "QUALITY_DIPS_PAPER_V1",
            "summary": {"open_lots": 0, "closed_lots": 0},
            "closed_lots": [],
            "timeline": [],
        },
        prediction_snapshot={
            "engine_version": "prediction-paper-reprice-v1",
            "summary": {"open_positions": 0, "closed_trades": 0, "net_pnl_dollars": 0.0},
            "events": [],
        },
    )
    for lane in report["lanes"]:
        assert lane["sample_size"] == 0
        assert lane["expectancy"] is None
        assert lane["win_rate"] is None
        assert lane["realized_status"] == "NO_CLOSED_SAMPLE"
    assert report["comparison_rules"]["missing_metrics_are_zero"] is False
