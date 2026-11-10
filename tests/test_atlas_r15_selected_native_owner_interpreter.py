"""Selected R15 actual native Python owner + disposable Stop/restart.

Runs ONE isolated child at a time; no FinancialPaper account or market source.
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    selected_code,
)

ROOT=Path(__file__).resolve().parents[1]
RELEASE=Path("D:/AtlasRuntime/releases/2c79a8d846d6b33669008114732ae5896153812a")
SCRIPT=ROOT/"tests/fixtures/atlas_r15_selected_native_owner_smoke.py"
SELECTED=Path("D:/AtlasRuntime/selection/r0014.json")
SHA="b729ff718fc41d90942400db15fc17e1bcf0cac6ae9ccf18e0492e9c6c4f2eb2"
PASS=(
    "SELECTED_R15_NATIVE_OWNER_DURABLE_EXPIRY_STOP_PASS",
    "SELECTED_R15_NATIVE_OWNER_REAL_WINDOWS_STOP_SIGNAL_PASS",
    "SELECTED_R15_NATIVE_OWNER_UNKNOWN_STOP_REFUSED_NO_RETRY_PASS",
    "R15_SELECTED_NATIVE_DISPOSABLE_OWNER_THREE_SCENARIOS_PASS",
    "NO_REAL_FINANCIAL_ACCOUNT_PROVIDER_OR_ORDER",
)


@pytest.mark.skipif(sys.platform!="win32",reason="Native R15 Windows Stop")
def test_actual_installed_r15_owner_runs_and_durably_stops_three_scenarios():
    assert selected_code()["revision"]==14
    assert hashlib.sha256(SELECTED.read_bytes()).hexdigest()==SHA
    assert SCRIPT.is_file() and (RELEASE/"python/python.exe").is_file()
    env={**os.environ,
         "PYTHONPATH":";".join((str(RELEASE),str(RELEASE/"backend"),
                              str(ROOT/"tests"))),
         "PYTHONDONTWRITEBYTECODE":"1"}
    result=subprocess.run(
        [str(RELEASE/"python/python.exe"),"-B","-u",str(SCRIPT)],
        cwd=RELEASE,env=env,capture_output=True,text=True,timeout=40,
    )
    assert result.returncode==0,(result.stdout+result.stderr)[-2500:]
    for token in PASS:
        assert result.stdout.count(token)==1
    assert hashlib.sha256(SELECTED.read_bytes()).hexdigest()==SHA
