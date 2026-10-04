from app.services.paper_attribution import attribute_trade, build_scorecards


def _row(**overrides):
    row = {
        "event": "close",
        "trade_id": "t1",
        "trade_type": "PAPER",
        "symbol": "BTC",
        "side": "LONG",
        "strategy": "rsi_extension_v1",
        "entry_timestamp": "2026-10-01T14:00:00+00:00",
        "exit_timestamp": "2026-10-01T14:10:00+00:00",
        "gross_pnl_r": -1.0,
        "net_pnl_r": -1.05,
        "R_multiple": -1.0,
        "mfe_r": 0.1,
        "mae_r": 1.0,
        "holding_time_sec": 600,
        "regime_normalized": "RANGE",
        "features": {"paper_execution_model_version": "paper-v1"},
        "result": "LOSS",
    }
    row.update(overrides)
    return row


def test_signal_failure_pattern_is_observational_not_causal():
    out = attribute_trade(_row())
    assert out["primary"] == "SIGNAL_FAILURE_PATTERN"
    assert "DIRECTION_OR_SIGNAL_FAILURE_PATTERN" in out["observations"]
    assert out["causation_established"] is False


def test_positive_excursion_loser_is_exit_capture_pattern():
    out = attribute_trade(_row(mfe_r=0.8, mae_r=1.0))
    assert out["primary"] == "EXIT_CAPTURE_PATTERN"
    assert "POSITIVE_EXCURSION_NOT_CAPTURED" in out["observations"]


def test_cost_drag_can_flip_nonnegative_gross():
    out = attribute_trade(_row(gross_pnl_r=0.02, net_pnl_r=-0.03, R_multiple=0.02))
    assert out["primary"] == "COST_DRAG"
    assert out["cost_r"] == 0.05


def test_unresolved_is_allowed_when_path_does_not_support_cause():
    out = attribute_trade(_row(mfe_r=None, mae_r=None, gross_pnl_r=-0.2, net_pnl_r=-0.25))
    assert out["primary"] == "UNRESOLVED_NEGATIVE_EDGE"
    assert out["unknown"] is True


def test_nonperformance_records_are_excluded():
    out = attribute_trade(_row(result="SESSION_ROLL", net_pnl_r=0.0))
    assert out["eligible"] is False
    assert out["primary"] == "NON_PERFORMANCE_RECORD"


def test_scorecards_separate_strategy_version_and_regime():
    rows = [
        _row(trade_id="a", regime_normalized="RANGE"),
        _row(
            trade_id="b",
            side="SHORT",
            regime_normalized="TREND_DOWN",
            gross_pnl_r=1.0,
            net_pnl_r=0.95,
            R_multiple=1.0,
            mfe_r=1.2,
            mae_r=0.1,
            result="WIN",
        ),
    ]
    out = build_scorecards(rows)
    assert out["closed_performance_records"] == 2
    assert len(out["by_strategy_version"]) == 1
    assert set(out["by_regime"]) == {"RANGE", "TREND_DOWN"}
    assert len(out["by_strategy_version_regime"]) == 2
    assert out["interpretation"]["thresholds_modified"] is False
    assert out["live_capital_allowed"] is False
    assert out["automatic_real_money_execution"] is False
