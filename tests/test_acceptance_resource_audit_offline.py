"""Real PowerShell parser/JSON path, with every CIM query replaced by fixtures."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from scripts.observation_runtime.installed_acceptance_cleanup import socket_cleanup

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/windows/Atlas-Acceptance-Resource-Audit.ps1"
)


@pytest.mark.parametrize(
    "kind", ["empty", "zero", "missing", "throw", "partial", "bad_claims"]
)
def test_real_powershell_capture_keeps_zero_missing_and_query_failure_distinct(
    tmp_path, kind
):
    ps = (
        Path(os.environ.get("SystemRoot", "C:/Windows"))
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    if not ps.is_file():
        found = shutil.which("pwsh")
        if not found:
            pytest.skip("PowerShell unavailable; no native query attempted")
        ps = Path(found)
    env = dict(
        os.environ,
        ATLAS_AUDIT_SCRIPT=str(SCRIPT),
        ATLAS_AUDIT_FIXTURE_KIND=kind,
        ATLAS_AUTH_HELPER_CLAIMS=json.dumps(
            [{"pid": 1234, "created": 123456789, "image": "d:/synthetic/python.exe"}]
        ),
        PSModuleAnalysisCachePath=str(tmp_path / "module.cache"),
        TEMP=str(tmp_path),
        TMP=str(tmp_path),
    )
    if kind == "bad_claims":
        env["ATLAS_AUTH_HELPER_CLAIMS"] = '[{"pid":[1234],"created":1,"image":"x"}]'
    code = r"""
$ErrorActionPreference='Stop'
function Get-CimInstance {
    param([Parameter(Position=0)]$ClassName,$Namespace,$Filter)
    if($ClassName -eq 'Win32_Process'){return}
    if($ClassName -ne 'MSFT_NetTCPConnection'){throw 'UNEXPECTED_QUERY'}
    if($env:ATLAS_AUDIT_FIXTURE_KIND -eq 'throw'){throw 'SYNTHETIC_CIM_DENIED'}
    if($env:ATLAS_AUDIT_FIXTURE_KIND -eq 'empty' -or $env:ATLAS_AUDIT_FIXTURE_KIND -eq 'bad_claims'){return}
    $item=[pscustomobject]@{LocalAddress='127.0.0.1';LocalPort=42001;RemoteAddress='0.0.0.0';RemotePort=0;State=2}
    if($env:ATLAS_AUDIT_FIXTURE_KIND -ne 'missing'){$item|Add-Member -NotePropertyName OwningProcess -NotePropertyValue 0}
    $item
    if($env:ATLAS_AUDIT_FIXTURE_KIND -eq 'partial'){throw 'SYNTHETIC_PARTIAL_ENUMERATION'}
}
& $env:ATLAS_AUDIT_SCRIPT -OwnedPort 42001 -OwnedAddress '127.0.0.1'
exit $LASTEXITCODE
"""
    before = time.perf_counter_ns()
    result = subprocess.run(
        [str(ps), "-NoProfile", "-NonInteractive", "-Command", code],
        env=env,
        capture_output=True,
        check=False,
        timeout=12,
    )
    (tmp_path / "captured.json").write_bytes(result.stdout)
    assert not result.stderr, result.stderr.decode(errors="replace")
    observed = json.loads(result.stdout)
    decision = socket_cleanup(
        observed, address="127.0.0.1", port=42001, stopped_ns=before
    )
    if kind == "empty":
        assert (
            result.returncode == 0 and observed["rows"] == [] and decision["accepted"]
        ), observed
    elif kind in ("zero", "missing"):
        assert (
            result.returncode == 0
            and len(observed["rows"]) == 1
            and not decision["accepted"]
        ), observed
        row = observed["rows"][0]
        assert (
            row["family"] == 4
            and row["local_address"] == "127.0.0.1"
            and row["local_port"] == 42001
        )
        assert row["state"] == 2 and row["protocol"] == "TCP"
        assert row["owner_pid"] == 0 if kind == "zero" else row["owner_pid"] is None
        assert row["owner_present"] is (kind == "zero")
    else:
        assert result.returncode == 2 and observed["error"] and not decision["accepted"]
        assert decision["enumeration_error"] is not None
