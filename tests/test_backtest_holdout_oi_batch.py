from pathlib import Path

import app.backtest.holdout_oi_batch as mod


def test_holdout_oi_plan_is_isolated(tmp_path,monkeypatch):
    seen={}
    def fake_run(**kwargs):
        seen.update(kwargs)
        return {"object_count":552,"normalized_output_count":0,"status":"PLANNED_NOT_DOWNLOADED","pit_oi_context_complete":False}
    monkeypatch.setattr(mod,"run_oi_batch",fake_run)
    result=mod.run(root=tmp_path,manifest=tmp_path/"stage.json",execute=False)
    assert result["status"]=="HOLDOUT_OI_BATCH_PLANNED"
    assert result["research_window"]=="holdout-2025-h2"
    assert result["object_count"]==552
    assert result["normalized_output_count"]==0
    assert result["development_evidence_mutated"] is False
    assert result["threshold_retuning_allowed"] is False
    assert result["holdout_evaluation_allowed_before_source_audit_green"] is False
    assert seen["start_utc"]=="2025-07-01T00:00:00Z"
    assert seen["end_utc"]=="2026-01-01T00:00:00Z"
    assert "holdout-2025-h2-oi" in str(seen["raw_root"])
    assert "holdout-2025-h2-oi" in str(seen["output_root"])


def test_holdout_oi_execute_reports_normalized_outputs(tmp_path,monkeypatch):
    def fake_run(**kwargs):
        return {"object_count":552,"normalized_output_count":3,"status":"ACQUIRED_AND_NORMALIZED_OI_ROLLING_VOLUME_STILL_REQUIRED","pit_oi_context_complete":True}
    monkeypatch.setattr(mod,"run_oi_batch",fake_run)
    result=mod.run(root=tmp_path,manifest=tmp_path/"stage.json",execute=True)
    assert result["status"]=="HOLDOUT_OI_BATCH_EXECUTED"
    assert result["normalized_output_count"]==3
    assert result["pit_oi_context_complete"] is True
    assert result["live_capital_allowed"] is False
    assert result["automatic_real_money_execution"] is False
