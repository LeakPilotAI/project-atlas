from pathlib import Path

from app.backtest import holdout_candle_batch as mod


def test_holdout_candle_batch_plan_uses_separate_holdout_roots(tmp_path,monkeypatch):
    seen={}
    def fake_run_batch(**kwargs):
        seen.update(kwargs)
        return {"batch_status":"PLANNED_NOT_DOWNLOADED","objects":[{"x":1}],"normalized_outputs":[]}
    monkeypatch.setattr(mod,"run_batch",fake_run_batch)
    result=mod.run(root=tmp_path,manifest=tmp_path/"plan.json",execute=False)
    assert seen["start_utc"]=="2025-07-01T00:00:00Z"
    assert seen["end_utc"]=="2026-01-01T00:00:00Z"
    assert "holdout-2025-h2-candles" in str(seen["raw_root"])
    assert "holdout-2025-h2-candles" in str(seen["output_root"])
    assert result["development_evidence_mutated"] is False
    assert result["threshold_retuning_allowed"] is False
    assert result["holdout_evaluation_allowed_before_source_audit_green"] is False
    assert result["status"]=="HOLDOUT_CANDLE_BATCH_PLANNED"


def test_holdout_candle_batch_execute_records_outputs(tmp_path,monkeypatch):
    def fake_run_batch(**kwargs):
        return {"batch_status":"ACQUIRED_AND_NORMALIZED_CANDLES_CONTEXT_STILL_REQUIRED","objects":[{}]*36,"normalized_outputs":[{}]*6}
    monkeypatch.setattr(mod,"run_batch",fake_run_batch)
    result=mod.run(root=tmp_path,manifest=tmp_path/"run.json",execute=True)
    assert result["object_count"]==36
    assert result["normalized_output_count"]==6
    assert result["status"]=="HOLDOUT_CANDLE_BATCH_EXECUTED"
