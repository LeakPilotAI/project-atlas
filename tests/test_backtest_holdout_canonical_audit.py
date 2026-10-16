import app.backtest.holdout_canonical_audit as mod


def test_plan_is_gated_and_isolated(tmp_path):
    result=mod.run(root=tmp_path,manifest=tmp_path/"stage.json",execute=False)
    assert result["status"]=="HOLDOUT_CANONICAL_AUDIT_PLANNED"
    assert result["canonical_output_count"]==0
    assert result["source_audit"] is None
    assert result["ready_for_locked_baseline_batch"] is False
    assert result["holdout_evaluation_allowed"] is False
    assert result["development_evidence_mutated"] is False
    assert result["threshold_retuning_allowed"] is False
    assert result["same_window_optimization_allowed"] is False
    assert result["live_capital_allowed"] is False
    assert "canonical-holdout-2025-h2" in result["canonical_root"]


def test_execute_requires_and_surfaces_green_audit(tmp_path,monkeypatch):
    seen={}
    def fake_canonical(**kwargs):
        seen.update(kwargs)
        return {"status":"ASSEMBLED_CANONICAL_PIT_DATASETS","normalized_outputs":3}
    def fake_audit(root,symbols,timeframe):
        assert tuple(symbols)==("BTC","ETH","SOL")
        assert timeframe=="5m"
        return {"ready_for_locked_baseline_batch":True,"audit_id":"abc123","datasets":[]}
    monkeypatch.setattr(mod,"run_canonical_batch",fake_canonical)
    monkeypatch.setattr(mod,"audit_representative_bundle",fake_audit)
    result=mod.run(root=tmp_path,manifest=tmp_path/"stage.json",execute=True)
    assert result["status"]=="HOLDOUT_CANONICAL_AUDIT_EXECUTED"
    assert result["canonical_output_count"]==3
    assert result["ready_for_locked_baseline_batch"] is True
    assert result["holdout_evaluation_allowed"] is True
    assert "holdout-2025-h2-funded" in str(seen["funded_root"])
    assert "holdout-2025-h2-oi" in str(seen["oi_root"])
    assert "holdout-2025-h2-volume24h" in str(seen["volume_root"])
    assert "holdout-2025-h2-htf" in str(seen["htf_root"])
