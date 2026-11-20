"""Offline ownership regressions: mocked queries, no Atlas/selector/provider launch.

These exercise existing checks. They do not repair an unproven historical
ancestry or authorize a process merely because its command resembles Atlas.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PS = (
    Path(os.environ.get("SystemRoot", "C:/Windows"))
    / "System32/WindowsPowerShell/v1.0/powershell.exe"
)


def powershell(code, tmp_path, **environment):
    if not PS.is_file():
        pytest.skip("Windows PowerShell unavailable; offline parser tests not executed")
    env = dict(
        os.environ,
        **environment,
        TEMP=str(tmp_path),
        TMP=str(tmp_path),
        PSModuleAnalysisCachePath=str(tmp_path / "module.cache"),
    )
    result = subprocess.run(
        [str(PS), "-NoProfile", "-NonInteractive", "-Command", code],
        env=env,
        capture_output=True,
        timeout=12,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert not result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "approved_helper",
        "undeclared_wrapper",
        "unexpected_child",
        "missing_helper_claim",
        "image",
        "stale_creation",
        "pid_reuse",
        "wrong_pid",
        "nested_pid",
        "missing_image",
        "empty_claims",
        "query_error",
    ],
)
def test_actual_metadata_guard_with_mocked_processes(tmp_path, fault):
    source = (REPO / "scripts/acceptance_harness_v3/metadata_preflight.ps1").read_text()
    # Execute the actual ownership block only; no service/shortcut/registry
    # queries and no production observation. Replace only the native observer.
    block = source[
        source.index("    $filter=") : source.index("    $result.accepted=$true")
    ]
    needle = "[Diagnostics.Process]::GetProcessById($candidate.ProcessId)"
    assert block.count(needle) == 1
    block = block.replace(needle, "(Get-FixtureProcess $candidate.ProcessId)")
    code = r"""
$ErrorActionPreference='Stop'
$result=[ordered]@{}
$created=[datetime]::Parse('2026-01-02T03:04:05Z').ToUniversalTime()
$identity=@{pid=101;created=$created.ToFileTimeUtc();image='D:\synthetic\python.exe'}
$claims=@($identity)
$rows=@([pscustomobject]@{ProcessId=101;ExecutablePath=$identity.image;CommandLine='synthetic supervisor'})
$kind=$env:FIXTURE_FAULT
if($kind -eq 'approved_helper'){
    $claims+=@{pid=102;created=$created.ToFileTimeUtc();image=$identity.image}
    $rows+=[pscustomobject]@{ProcessId=102;ExecutablePath=$identity.image;CommandLine='synthetic approved helper'}
}
if($kind -in @('undeclared_wrapper','unexpected_child','missing_helper_claim')){
    # Even an identical command must not make an unclaimed process owned.
    $rows+=[pscustomobject]@{ProcessId=103;ExecutablePath=$identity.image;CommandLine='synthetic supervisor';ParentProcessId=101}
}
if($kind -eq 'wrong_pid'){$identity.pid=104}
if($kind -eq 'nested_pid'){$identity.pid=@(101)}
if($kind -eq 'missing_image'){$identity.Remove('image')}
$env:ATLAS_AUTH_HELPER_CLAIMS=ConvertTo-Json -InputObject $claims -Compress
if($kind -eq 'empty_claims'){$env:ATLAS_AUTH_HELPER_CLAIMS='[]'}
function Get-CimInstance {
    param($ClassName,$Filter)
    if($ClassName -ne 'Win32_Process'){throw 'UNEXPECTED_REAL_QUERY'}
    if($kind -eq 'query_error'){throw 'SYNTHETIC_ENUMERATION_FAILED'}
    return $rows
}
function Get-FixtureProcess {
    param($ProcessId)
    $time=$created
    if($kind -in @('stale_creation','pid_reuse')){$time=$time.AddSeconds(1)}
    $image='D:\synthetic\python.exe'
    if($kind -eq 'image'){$image='D:\unexpected\python.exe'}
    $p=[pscustomobject]@{Id=$ProcessId;StartTime=$time;MainModule=[pscustomobject]@{FileName=$image}}
    $p|Add-Member -MemberType ScriptMethod -Name Dispose -Value {$script:disposed++}
    return $p
}
$disposed=0
try {
    & ([scriptblock]::Create($env:FIXTURE_GUARD))
    $result.accepted=$true
}catch{$result.accepted=$false;$result.error=$_.Exception.Message}
$result.disposed=$disposed
$result|ConvertTo-Json -Depth 8 -Compress
"""
    observed = powershell(code, tmp_path, FIXTURE_FAULT=fault, FIXTURE_GUARD=block)
    assert observed["accepted"] is (fault in {"none", "approved_helper"}), observed
    if fault in {
        "undeclared_wrapper",
        "unexpected_child",
        "missing_helper_claim",
        "wrong_pid",
    }:
        assert observed["error"] == "EXISTING_ATLAS_PROCESS_REQUIRES_OWNERSHIP_REVIEW"
    if fault in {"image", "stale_creation", "pid_reuse"}:
        assert observed["error"] == "DIAGNOSTIC_HELPER_OWNERSHIP_MISMATCH"
        assert observed["disposed"] == 1
    if fault in {"none", "approved_helper"}:
        assert observed["disposed"] == (2 if fault == "approved_helper" else 1)


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "command",
        "parent",
        "image",
        "creation",
        "pid_reuse",
        "missing_parent",
        "missing_command",
        "account",
        "missing_row",
        "duplicate_row",
    ],
)
def test_existing_fixture_command_context_never_grants_ownership(tmp_path, fault):
    # The existing observer verifies command/parent/account only with a retained
    # live Process. The PowerShell test process is the sole retained fixture;
    # every CIM/owner query is mocked in the module session state.
    code = r"""
$ErrorActionPreference='Stop'
Import-Module $env:FIXTURE_MODULE
$m=Get-Module 'Atlas-NativeIdentity-Observation'
$p=[Diagnostics.Process]::GetCurrentProcess()
try {
    $expected=@{pid=$p.Id;created_utc=$p.StartTime.ToUniversalTime().ToString('o');
        executable=$p.MainModule.FileName;command_line='synthetic supervisor';parent_pid=100;account_sid='SYNTHETIC-SID'}
    $row=[pscustomobject]@{ProcessId=$p.Id;CreationDate=$p.StartTime;ExecutablePath=$expected.executable;
        CommandLine=$expected.command_line;ParentProcessId=100}
    $kind=$env:FIXTURE_FAULT
    if($kind -eq 'command'){$row.CommandLine='synthetic unexpected command'}
    if($kind -eq 'parent'){$row.ParentProcessId=999}
    if($kind -eq 'image'){$row.ExecutablePath='D:\unexpected\python.exe'}
    if($kind -in @('creation','pid_reuse')){$row.CreationDate=$row.CreationDate.AddSeconds(1)}
    if($kind -eq 'missing_parent'){$expected.Remove('parent_pid')}
    if($kind -eq 'missing_command'){$expected.Remove('command_line')}
    & $m {
        param($value,$fault)
        $script:fixtureRow=$value;$script:fixtureFault=$fault
        function script:Get-CimInstance {
            param($ClassName,$Filter,$OperationTimeoutSec,$ErrorAction)
            if($ClassName -ne 'Win32_Process'){throw 'UNEXPECTED_REAL_QUERY'}
            if($script:fixtureFault -eq 'missing_row'){return}
            $script:fixtureRow
            if($script:fixtureFault -eq 'duplicate_row'){$script:fixtureRow}
        }
        function script:Invoke-CimMethod {
            param($InputObject,$MethodName,$OperationTimeoutSec,$ErrorAction)
            if($MethodName -ne 'GetOwnerSid'){throw 'UNEXPECTED_REAL_METHOD'}
            $sid=if($script:fixtureFault -eq 'account'){'UNEXPECTED-SID'}else{'SYNTHETIC-SID'}
            [pscustomobject]@{ReturnValue=0;Sid=$sid}
        }
    } $row $kind
    try{$observed=Get-AtlasFixtureCommandObservation $p $expected;$accepted=$true}
    catch{$observed=$null;$accepted=$false;$errorText=$_.Exception.Message}
    @{accepted=$accepted;observation=$observed;error=$errorText}|ConvertTo-Json -Depth 8 -Compress
}finally{$p.Dispose()}
"""
    observed = powershell(
        code,
        tmp_path,
        FIXTURE_FAULT=fault,
        FIXTURE_MODULE=str(
            REPO / "scripts/windows/Atlas-NativeIdentity-Observation.psm1"
        ),
    )
    assert observed["accepted"] is (fault == "none"), observed
    if fault == "none":
        for flag in (
            "ownership_independently_verified",
            "startup_authorized",
            "shutdown_authorized",
            "production_authorized",
        ):
            assert observed["observation"][flag] is False
        assert observed["observation"]["command_line_verified"] is True
