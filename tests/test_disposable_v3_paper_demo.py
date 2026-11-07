"""Isolated CLI demonstration must remain synthetic and cleanup-only."""
import json
import os
import subprocess
import sys

from scripts.observation_runtime.disposable_v3_paper_demo import run_demo


def test_demo_reconciles_strategy_and_refuses_authority():
    result = run_demo()
    assert result["actions"] == ["WAIT", "ENTER", "MARK", "EXIT"]
    assert result["cash_reconciled"] is True
    assert result["data_source"] == "SYNTHETIC"
    assert result["evidence_class"] == "TEST_DATA"
    assert result["forward_trading_authorized"] is False
    assert result["live_order_authorized"] is False
    assert result["provider_authenticated"] is False
    assert result["research_provenance_attested"] is False


def test_demo_cli_is_single_json_output():
    env = {**os.environ, "PYTHONPATH": "backend;."}
    process = subprocess.run(
        [sys.executable, "-m", "scripts.observation_runtime.disposable_v3_paper_demo"],
        capture_output=True, text=True, check=True, env=env, timeout=15)
    assert process.stderr == ""
    lines = process.stdout.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["cash_reconciled"] is True
