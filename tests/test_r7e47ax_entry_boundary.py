"""R7E47AX: offline entry point capability checks."""
import json
import subprocess
import sys

from pathlib import Path

ENTRY = (
    Path(__file__).resolve().parents[1]
    / "scripts/observation_runtime/observation_entry.py"
)


def invoke(*args):
    return subprocess.run(
        [sys.executable, "-m", "scripts.observation_runtime.observation_entry", *args],
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_synthetic_once():
    result = invoke("--synthetic-once")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["mode"] == "SYNTHETIC_OFFLINE"
    assert data["observations"] == 1
    assert data["budget_remaining"] == 0
    assert data["session_closed"] is True
    assert data["final_event"] == "GRACEFUL_SHUTDOWN"
    assert data["network_enabled"] is False
    assert data["trading_enabled"] is False


def test_status_remains_offline():
    result = invoke("--status")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["network_enabled"] is False
    assert data["production_backend_enabled"] is False


def test_forbidden_operations():
    for flag in ("--live", "--trade", "--paper", "--discord"):
        result = invoke(flag)
        assert result.returncode != 0
        assert "unrecognized arguments" in result.stderr


def test_mutually_exclusive_operations():
    result = invoke("--status", "--synthetic-once")
    assert result.returncode != 0
