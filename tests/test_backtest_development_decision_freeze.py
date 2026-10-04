import json
from pathlib import Path

import pytest

from app.backtest.development_decision_freeze import run


def _baseline(path:Path,*,expectancy=-0.1,total_r=-10.0,trades=100,holdout=False,retune=False):
    payload={
        "status":"LOCKED_DEVELOPMENT_BASELINE_COMPLETE",
        "source_audit_id":"audit",
        "thresholds":{"rsi_long_max":28.0},
        "aggregate":{"expectancy_r":expectancy,"total_r":total_r,"trade_count":trades},
        "runs":[],
        "holdout_data_touched":holdout,
        "threshold_retuning_allowed":retune,
    }
    path.write_text(json.dumps(payload),encoding="utf-8")


def test_negative_development_is_frozen_without_retuning(tmp_path):
    baseline=tmp_path/"baseline.json";output=tmp_path/"freeze.json"
    _baseline(baseline)
    result=run(baseline_summary=baseline,output=output)
    assert result["development_result"]=="FAILED_NEGATIVE"
    assert result["development_edge_positive"] is False
    assert result["parameters_frozen"] is True
    assert result["same_window_optimization_allowed"] is False
    assert result["holdout_data_touched"] is False
    assert output.is_file()


def test_positive_development_can_be_recorded_but_not_retuned(tmp_path):
    baseline=tmp_path/"baseline.json";output=tmp_path/"freeze.json"
    _baseline(baseline,expectancy=0.1,total_r=10.0,trades=100)
    result=run(baseline_summary=baseline,output=output)
    assert result["development_result"]=="POSITIVE"
    assert result["threshold_retuning_allowed"] is False
    assert result["same_window_optimization_allowed"] is False


def test_freeze_rejects_holdout_contamination(tmp_path):
    baseline=tmp_path/"baseline.json";output=tmp_path/"freeze.json"
    _baseline(baseline,holdout=True)
    with pytest.raises(RuntimeError,match="holdout"):
        run(baseline_summary=baseline,output=output)
