"""Selected R14 Python interpreter owner session; disposable financial lanes.

Selected native interpreter loads native app/services and Windows signal source,
while the test helper supplies a fake accepted owner with only temp SQLite.
This pytest wrapper does NOT start or select any operational Atlas session.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
R14 = Path("D:/AtlasRuntime/releases/7ff9d3dba2eabe110f843c13efac49464805de2a")
NATIVE_PYTHON = R14 / "python/python.exe"
SCENARIO = ROOT / "tests/fixtures/atlas_r14_selected_native_owner_smoke.py"
SELECTED_RECORD = Path("D:/AtlasRuntime/selection/r0013.json")
R14_SHA = "6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31"
PASS_TOKENS = (
    "SELECTED_R14_NATIVE_OWNER_AND_DURABLE_TWO_LANE_STOP_PASS",
    "SELECTED_R14_NATIVE_OWNER_EXPIRY_DURABLE_STOP_PASS",
    "SELECTED_R14_NATIVE_OWNER_UNKNOWN_STOP_LATCHED_NO_RETRY_PASS",
    "R14_NATIVE_OWNER_SUPERVISED_DISPOSABLE_ACCEPTANCE_3_OF_3",
    "NO_FINANCIAL_PROVIDER_ACCOUNT_OR_LIVE_PAPER_ORDERS",
)


@pytest.mark.skipif(sys.platform != "win32", reason="Native R14 Windows event integration")
def test_installed_python_financial_owner_run_and_stop_under_exact_selected_r14():
    before = hashlib.sha256(SELECTED_RECORD.read_bytes()).hexdigest()
    assert before == R14_SHA
    assert NATIVE_PYTHON.is_file()
    assert SCENARIO.is_file()
    assert not (SELECTED_RECORD.parent/"r0014.json").exists()
    # Exclude the workspace root from PYTHONPATH. The selected R14 root and
    # backend must win all production imports, checked again inside child.
    env = {**os.environ,
           "PYTHONPATH": ";".join((str(R14), str(R14/"backend"), str(ROOT/"tests"))),
           "PYTHONDONTWRITEBYTECODE":"1"}
    result = subprocess.run(
        [str(NATIVE_PYTHON),"-B","-u",str(SCENARIO)],
        env=env,cwd=R14,capture_output=True,text=True,timeout=25)
    assert result.returncode==0,(result.stdout+result.stderr)[-1800:]
    for token in PASS_TOKENS:
        assert result.stdout.count(token)==1
    assert hashlib.sha256(SELECTED_RECORD.read_bytes()).hexdigest()==before
    assert not (SELECTED_RECORD.parent/"r0014.json").exists()
    assert not (SELECTED_RECORD.parent/"r0014.pending").exists()
