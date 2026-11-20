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


def test_stop_loss_scenario_exits_and_reconciles():
    result = run_demo(scenario="stop_loss")
    assert result["actions"] == ["WAIT", "ENTER", "EXIT", "WAIT"]
    assert result["net_realized_pnl"] < 0
    assert result["cash_reconciled"] is True
    assert result["forward_trading_authorized"] is False

def test_no_entry_scenario_never_mutates_position():
    result = run_demo(scenario="no_entry")
    assert result["actions"] == ["WAIT"] * 4
    assert result["net_realized_pnl"] == 0
    assert result["cash_reconciled"] is True
    assert result["live_order_authorized"] is False

def test_unknown_scenario_refused():
    import pytest
    with pytest.raises(ValueError, match="SCENARIO_UNKNOWN"):
        run_demo(scenario="unsupported")

def test_cli_explicit_stop_loss_scenario():
    env = {**os.environ, "PYTHONPATH": "backend;."}
    process = subprocess.run(
        [sys.executable, "-m", "scripts.observation_runtime.disposable_v3_paper_demo",
         "--scenario", "stop_loss"], capture_output=True, text=True, check=True,
        env=env, timeout=15)
    result = json.loads(process.stdout)
    assert result["scenario"] == "stop_loss"
    assert result["net_realized_pnl"] < 0


def test_gap_down_exits_at_worse_bid_not_stop_threshold():
    ordinary = run_demo(scenario="stop_loss")
    gap = run_demo(scenario="gap_down")
    assert gap["actions"] == ["WAIT", "ENTER", "EXIT", "WAIT"]
    assert gap["net_realized_pnl"] < ordinary["net_realized_pnl"] < 0
    assert gap["cash_reconciled"] is True
    assert gap["forward_trading_authorized"] is False

def test_gap_down_cli_reconciles_without_forward_authority():
    env = {**os.environ, "PYTHONPATH": "backend;."}
    process = subprocess.run(
        [sys.executable, "-m", "scripts.observation_runtime.disposable_v3_paper_demo",
         "--scenario", "gap_down"], capture_output=True, text=True, check=True,
        env=env, timeout=15)
    result = json.loads(process.stdout)
    assert result["scenario"] == "gap_down"
    assert result["net_realized_pnl"] < 0
    assert result["live_order_authorized"] is False
