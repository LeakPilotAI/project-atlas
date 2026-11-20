"""Actual V5 PowerShell ownership block, all process/native queries mocked."""

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "command",
        "parent",
        "missing_role",
        "extra_process",
        "duplicate_rich",
        "duplicate_classic",
        "classic_projection",
        "bad_pid",
        "empty_command",
        "query_error",
    ],
)
def test_full_command_parent_and_complete_roster_are_required(tmp_path, fault):
    source = (ROOT / "scripts/acceptance_harness_v5/metadata_preflight.ps1").read_text()
    block = source[
        source.index("    $filter=") : source.index("    $result.accepted=$true")
    ]
    needle = "[Diagnostics.Process]::GetProcessById($candidate.ProcessId)"
    assert block.count(needle) == 1
    block = block.replace(needle, "(Get-FixtureProcess $candidate.ProcessId)")
    created = 134000000000000000
    rich = [
        {
            "pid": 20,
            "parent_pid": 10,
            "created": created,
            "image": "d:/fixture/root.exe",
            "command_line": "exact root command",
        },
        {
            "pid": 30,
            "parent_pid": 20,
            "created": created + 100,
            "image": "d:/fixture/python.exe",
            "command_line": "exact worker command",
        },
    ]
    classic = [{k: v[k] for k in ("pid", "created", "image")} for v in rich]
    if fault == "duplicate_rich":
        rich.append(dict(rich[0]))
    elif fault == "duplicate_classic":
        classic[1] = dict(classic[0])
    elif fault == "classic_projection":
        rich[1]["created"] += 10
    elif fault == "bad_pid":
        rich[1]["pid"] = [30]
    elif fault == "empty_command":
        rich[1]["command_line"] = ""
    code = r"""
$ErrorActionPreference='Stop'
$result=[ordered]@{}
function Get-CimInstance {
    param($ClassName,$Filter)
    if($ClassName -ne 'Win32_Process'){throw 'NO_REAL_QUERIES_PERMITTED'}
    if($env:V5_FAULT -eq 'query_error'){throw 'SYNTHETIC_QUERY_UNAVAILABLE'}
    [pscustomobject]@{ProcessId=20;ParentProcessId=10;CommandLine='exact root command'}
    if($env:V5_FAULT -ne 'missing_role'){
        $cmd=if($env:V5_FAULT -eq 'command'){'different command'}else{'exact worker command'}
        $parent=if($env:V5_FAULT -eq 'parent'){99}else{20}
        [pscustomobject]@{ProcessId=30;ParentProcessId=$parent;CommandLine=$cmd}
    }
    if($env:V5_FAULT -eq 'extra_process'){[pscustomobject]@{ProcessId=99;ParentProcessId=30;CommandLine='matching worker text'}}
}
function Get-FixtureProcess {
    param($Id)
    $value=if($Id -eq 20){134000000000000000L}else{134000000000000100L}
    $image=if($Id -eq 20){'d:/fixture/root.exe'}else{'d:/fixture/python.exe'}
    $p=[pscustomobject]@{Id=$Id;StartTime=[datetime]::FromFileTimeUtc($value);MainModule=[pscustomobject]@{FileName=$image}}
    $p|Add-Member -MemberType ScriptMethod -Name Dispose -Value {}
    $p
}
try{& ([scriptblock]::Create($env:V5_BLOCK));$result.accepted=$true}
catch{$result.accepted=$false;$result.error=$_.Exception.Message}
$result|ConvertTo-Json -Depth 8 -Compress
"""
    env = dict(
        os.environ,
        V5_FAULT=fault,
        V5_BLOCK=block,
        ATLAS_V5_RICH_CLAIMS=json.dumps(rich),
        ATLAS_AUTH_HELPER_CLAIMS=json.dumps(classic),
        TEMP=str(tmp_path),
        TMP=str(tmp_path),
        PSModuleAnalysisCachePath=str(tmp_path / "module.cache"),
    )
    ps = (
        Path(os.environ["SystemRoot"])
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    result = subprocess.run(
        [str(ps), "-NoProfile", "-NonInteractive", "-Command", code],
        env=env,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    data = json.loads(result.stdout)
    assert data["accepted"] is (fault == "none"), data
