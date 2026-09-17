from pathlib import Path

from app.backtest.holdout_prepare_plan import build_plan


def test_holdout_plan_is_untouched_and_locked(tmp_path:Path):
    result=build_plan(root=tmp_path)
    assert result["status"]=="HOLDOUT_PREPARATION_PLAN_READY"
    assert result["research_window"]=="holdout-2025-h2"
    assert result["start_utc"]=="2025-07-01T00:00:00Z"
    assert result["end_utc"]=="2026-01-01T00:00:00Z"
    assert result["symbols"]==["BTC","ETH","SOL"]
    assert result["development_evidence_mutated"] is False
    assert result["threshold_retuning_allowed"] is False
    assert result["same_window_optimization_allowed"] is False
    assert result["holdout_evaluation_allowed_before_source_audit_green"] is False
    assert result["live_capital_allowed"] is False
    assert result["automatic_real_money_execution"] is False


def test_holdout_plan_uses_separate_paths(tmp_path:Path):
    result=build_plan(root=tmp_path)
    for value in result["paths"].values():
        assert "holdout-2025-h2" in value
        assert "dev-2024-h2" not in value
