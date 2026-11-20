import json
import os
import subprocess
import sys

import pytest
from scripts.observation_runtime.disposable_v3_incremental_demo import run_incremental_demo


@pytest.mark.parametrize("scenario,expected", [
    ("take_profit", ["WAIT", "ENTER", "MARK", "EXIT"]),
    ("stop_loss", ["WAIT", "ENTER", "EXIT", "WAIT"]),
    ("gap_down", ["WAIT", "ENTER", "EXIT", "WAIT"]),
    ("no_entry", ["WAIT", "WAIT", "WAIT", "WAIT"]),
])
def test_incremental_scenario(scenario, expected):
    result = run_incremental_demo(scenario=scenario)
    assert result["actions"] == expected
    assert result["completed_ticks"] == 4
    assert result["cash_reconciled"] is True
    assert result["recovery_status"] == "CLEAN"
    assert result["forward_trading_authorized"] is False
    assert result["open_positions"] == 0


def test_incremental_demo_cli_one_json_line():
    env = {**os.environ, "PYTHONPATH": "backend;."}
    process = subprocess.run([sys.executable, "-m",
        "scripts.observation_runtime.disposable_v3_incremental_demo",
        "--scenario", "take_profit"], capture_output=True, text=True,
        check=True, timeout=15, env=env)
    assert process.stderr == ""
    assert len(process.stdout.splitlines()) == 1
    assert json.loads(process.stdout)["completed_ticks"] == 4
