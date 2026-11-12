"""Real isolated Windows self-Job prerequisite (NO accounts/providers/orders).

The native self-assignment is executed in a NEW selected Python subprocess,
never in the pytest or Desktop Commander command process. This is a native
feasibility test and does not establish financial operating authority.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    SOURCE as R17_SOURCE,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_native_original_self_job import (
    NativeOriginalSelfJob,
)

SELECTED_IMAGE = (
    Path("D:/AtlasRuntime/releases") / R17_SOURCE / "python/python.exe"
)


def test_original_self_job_is_not_an_order_start_or_financial_issuer():
    assert not hasattr(NativeOriginalSelfJob, "place_order")
    assert not hasattr(NativeOriginalSelfJob, "submit_order")
    assert not hasattr(NativeOriginalSelfJob, "start")
    assert not hasattr(NativeOriginalSelfJob, "issue_financial_lease")
    assert not hasattr(NativeOriginalSelfJob, "create_account")
    assert not hasattr(NativeOriginalSelfJob, "close")


@pytest.mark.skipif(
    sys.platform != "win32" or not SELECTED_IMAGE.is_file(),
    reason="Requires real Windows selected native R17 Python image",
)
def test_actual_selected_python_can_own_its_original_job_without_account_writes():
    before = inspect_two_lane_native_roots()
    assert before["native_root_total"] == 12
    assert before["all_twelve_distinct_and_empty"] is True
    child_code = (
        "from scripts.observation_runtime.personal_native_original_self_job "
        "import create_original_self_job;"
        "o=create_original_self_job();"
        "assert o.verify() is True;"
        "print('ORIGINAL_SELF_OWNED_WINDOWS_JOB_PASS',flush=True);"
        "print('FINANCIAL_AUTHORITY_FALSE',flush=True);"
        "print('PAPER_START_FALSE',flush=True)"
    )
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.run(
        [str(SELECTED_IMAGE), "-B", "-c", child_code],
        cwd=Path(__file__).resolve().parents[1],
        env=env, text=True, capture_output=True,
        timeout=12, check=False,
        creationflags=getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0),
    )
    assert process.returncode == 0, "ISOLATED_NATIVE_SELF_JOB_FAILED"
    assert process.stdout.splitlines() == [
        "ORIGINAL_SELF_OWNED_WINDOWS_JOB_PASS",
        "FINANCIAL_AUTHORITY_FALSE",
        "PAPER_START_FALSE",
    ]
    assert not process.stderr.strip()
    assert inspect_two_lane_native_roots() == before
