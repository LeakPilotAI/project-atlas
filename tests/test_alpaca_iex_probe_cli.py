"""Safe bounded IEX probe CLI reporting, without provider access."""
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "observation_runtime" / "alpaca_iex_probe.py"


def test_probe_cli_rejects_invalid_duration_without_connecting():
    p = subprocess.run([sys.executable, str(SCRIPT), "--seconds", "0"],
                       capture_output=True, text=True, timeout=10, check=False)
    assert p.returncode == 1
    assert json.loads(p.stdout) == {"status": "REFUSED", "reason": "IEX_CONFIGURATION_OR_DATA_UNAVAILABLE"}


def test_probe_cli_rejects_duplicate_symbols_without_connecting():
    p = subprocess.run([sys.executable, str(SCRIPT), "--seconds", "1",
                        "--symbols", "MSFT", "MSFT"],
                       capture_output=True, text=True, timeout=10, check=False)
    assert p.returncode == 1
    assert json.loads(p.stdout)["status"] == "REFUSED"
