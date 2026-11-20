import json
import subprocess
import sys
from pathlib import Path

from scripts.observation_runtime.observation_entry import capabilities


ENTRY = (
    Path(__file__).resolve().parents[1]
    / "scripts/observation_runtime/observation_entry.py"
)


def test_capabilities_are_deny_by_default():
    state = capabilities()
    assert state["profile"] == "OBSERVATION_ONLY"
    assert state["mode"] == "OFFLINE"
    assert state["session_started"] is False

    for key, value in state.items():
        if key.endswith("_enabled"):
            assert value is False


def test_status_subprocess():
    result = subprocess.run(
        [sys.executable, str(ENTRY), "--status"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert json.loads(result.stdout) == capabilities()


def test_unknown_operation_refused():
    result = subprocess.run(
        [sys.executable, str(ENTRY), "--live"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "unrecognized arguments" in result.stderr
