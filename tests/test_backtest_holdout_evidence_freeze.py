import json
from pathlib import Path
import pytest
from app.backtest.holdout_evidence_freeze import build,run


def _summary():
    return {"status":"UNTOUCHED_HOLDOUT_EVALUATION_COMPLETE","source_audit_green":True,"source_audit_id":"audit","parameters_frozen":True,"threshold_retuning_allowed":False,"same_window_optimization_allowed":False,"production_strategy_modified":False,"live_capital_allowed":False,"research_window":"holdout-2025-h2","development_result":"FAILED_NEGATIVE","thresholds":{"x":1},"aggregate":{"trade_count":546,"total_r":-26.72350715657114,"expectancy_r":-0.048944152301412344},"runs":[{"symbol":"BTC","run_id":"b","metrics":{}},{"symbol":"ETH","run_id":"e","metrics":{}},{"symbol":"SOL","run_id":"s","metrics":{}}]}


def test_negative_holdout_freezes_without_retuning():
    p=build(_summary())
    assert p["status"]=="HOLDOUT_EVIDENCE_FROZEN"
    assert p["holdout_result"]=="FAILED_NEGATIVE"
    assert p["stable_positive_edge_established"] is False
    assert p["next_cycle_must_be_isolated"] is True
    assert p["threshold_retuning_allowed"] is False
    assert p["live_capital_allowed"] is False


def test_freeze_fails_closed_on_safety_violation():
    for key,value in [("source_audit_green",False),("parameters_frozen",False),("threshold_retuning_allowed",True),("production_strategy_modified",True),("live_capital_allowed",True)]:
        s=_summary();s[key]=value
        with pytest.raises(RuntimeError):build(s)


def test_freeze_is_idempotent_and_hashes_source(tmp_path:Path):
    summary=tmp_path/"summary.json";summary.write_text(json.dumps(_summary(),sort_keys=True),encoding="utf-8")
    output=tmp_path/"freeze.json";a=run(summary_path=summary,output=output);b=run(summary_path=summary,output=output)
    assert a==b
    assert len(a["holdout_summary_sha256"])==64
