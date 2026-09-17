import app.backtest.holdout_volume_htf_batch as mod


def test_plan_is_holdout_isolated_and_does_not_run_htf(tmp_path,monkeypatch):
    seen={}
    def fake_volume(**kwargs):
        seen.update(kwargs)
        return {"object_count":21,"normalized_output_count":0,"status":"PLANNED_NOT_DOWNLOADED","pit_rolling_volume_context_complete":False}
    def fail_htf(**kwargs):
        raise AssertionError("HTF must not derive in plan mode")
    monkeypatch.setattr(mod,"run_volume_batch",fake_volume)
    monkeypatch.setattr(mod,"run_htf_batch",fail_htf)
    result=mod.run(root=tmp_path,manifest=tmp_path/"stage.json",execute=False)
    assert result["status"]=="HOLDOUT_VOLUME_HTF_PLANNED"
    assert result["research_window"]=="holdout-2025-h2"
    assert result["volume_object_count"]==21
    assert result["volume_normalized_output_count"]==0
    assert result["htf_normalized_output_count"]==0
    assert result["development_evidence_mutated"] is False
    assert result["threshold_retuning_allowed"] is False
    assert result["holdout_evaluation_allowed_before_source_audit_green"] is False
    assert result["current_state_backfill_used"] is False
    assert seen["start_utc"]=="2025-07-01T00:00:00Z"
    assert seen["end_utc"]=="2026-01-01T00:00:00Z"
    assert "holdout-2025-h2-volume24h" in str(seen["raw_root"])


def test_execute_reports_three_volume_and_three_htf_outputs(tmp_path,monkeypatch):
    def fake_volume(**kwargs):
        return {"object_count":21,"normalized_output_count":3,"status":"ACQUIRED_AND_DERIVED_ROLLING_VOLUME","pit_rolling_volume_context_complete":True}
    def fake_htf(**kwargs):
        assert "holdout-2025-h2-candles" in str(kwargs["candle_root"])
        return {"normalized_output_count":3,"status":"DERIVED_COMPLETED_1H_HTF_CONTEXT","completed_hourly_only":True}
    monkeypatch.setattr(mod,"run_volume_batch",fake_volume)
    monkeypatch.setattr(mod,"run_htf_batch",fake_htf)
    result=mod.run(root=tmp_path,manifest=tmp_path/"stage.json",execute=True)
    assert result["status"]=="HOLDOUT_VOLUME_HTF_EXECUTED"
    assert result["volume_normalized_output_count"]==3
    assert result["pit_rolling_volume_context_complete"] is True
    assert result["htf_normalized_output_count"]==3
    assert result["completed_hourly_only"] is True
    assert result["live_capital_allowed"] is False
    assert result["automatic_real_money_execution"] is False
