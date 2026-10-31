from pathlib import Path

from app.backtest.holdout_build_plan import START_UTC,END_UTC,WINDOW,build_plan,run


def test_holdout_build_plan_is_isolated_and_ordered(tmp_path:Path):
    payload=build_plan(tmp_path)
    assert payload["research_window"]==WINDOW
    assert payload["start_utc"]==START_UTC
    assert payload["end_utc"]==END_UTC
    assert payload["development_evidence_mutated"] is False
    assert payload["threshold_retuning_allowed"] is False
    assert payload["same_window_optimization_allowed"] is False
    assert payload["holdout_evaluation_allowed_before_source_audit_green"] is False
    assert payload["live_capital_allowed"] is False
    assert payload["automatic_real_money_execution"] is False
    assert [x["stage"] for x in payload["stages"]]==[
        "candles","oi","rolling_volume","htf","funding","funding_merge","canonical","source_audit"
    ]
    assert payload["stages"][-1]["status"]=="GATE"
    for path in payload["paths"].values():
        assert "holdout-2025-h2" in path
        assert "dev-2024-h2" not in path


def test_holdout_build_plan_persists(tmp_path:Path):
    output=tmp_path/"plan.json"
    payload=run(root=tmp_path,output=output)
    assert output.is_file()
    assert payload["status"]=="HOLDOUT_DATA_BUILD_PLAN_READY"
