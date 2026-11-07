import app.backtest.holdout_funding_merge_batch as mod


def test_plan_is_isolated_and_nonexecuting(tmp_path,monkeypatch):
    monkeypatch.setattr(mod,"run_funding_batch",lambda **kwargs: (_ for _ in ()).throw(AssertionError("funding must not run in plan mode")))
    monkeypatch.setattr(mod,"run_merge_batch",lambda **kwargs: (_ for _ in ()).throw(AssertionError("merge must not run in plan mode")))
    result=mod.run(root=tmp_path,manifest=tmp_path/"stage.json",execute=False)
    assert result["status"]=="HOLDOUT_FUNDING_MERGE_PLANNED"
    assert result["research_window"]=="holdout-2025-h2"
    assert result["funding_normalized_output_count"]==0
    assert result["funded_output_count"]==0
    assert result["development_evidence_mutated"] is False
    assert result["threshold_retuning_allowed"] is False
    assert result["holdout_evaluation_allowed_before_source_audit_green"] is False
    assert result["interpolation_used"] is False
    assert result["forward_fill_used"] is False


def test_execute_runs_funding_then_exact_merge(tmp_path,monkeypatch):
    calls=[]
    def fake_funding(**kwargs):
        calls.append("funding")
        return {"normalized_outputs":[{"symbol":"BTC"},{"symbol":"ETH"},{"symbol":"SOL"}],"status":"ACQUIRED_FIRST_PARTY_FUNDING","exact_event_timestamps":True}
    def fake_merge(**kwargs):
        calls.append("merge")
        return {"normalized_outputs":[{"symbol":"BTC"},{"symbol":"ETH"},{"symbol":"SOL"}],"status":"MERGED_FIRST_PARTY_FUNDING_INTO_5M_BARS"}
    monkeypatch.setattr(mod,"run_funding_batch",fake_funding)
    monkeypatch.setattr(mod,"run_merge_batch",fake_merge)
    result=mod.run(root=tmp_path,manifest=tmp_path/"stage.json",execute=True)
    assert calls==["funding","merge"]
    assert result["status"]=="HOLDOUT_FUNDING_MERGE_EXECUTED"
    assert result["funding_normalized_output_count"]==3
    assert result["funded_output_count"]==3
    assert result["exact_event_timestamps"] is True
    assert result["current_state_backfill_used"] is False
    assert result["live_capital_allowed"] is False
    assert result["automatic_real_money_execution"] is False
