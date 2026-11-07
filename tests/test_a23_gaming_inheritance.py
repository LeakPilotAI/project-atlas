"""Real child-process inheritance through isolated manager launch statements."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "scripts/windows/Atlas-Background.ps1"
LAUNCHER = ROOT / "scripts/windows/Atlas-Background-Gaming.ps1"


def ps(value):
    return str(value).replace("'", "''")


@pytest.mark.parametrize("gaming,scan,expected", [
    ("true", 60, 180), ("true", 300, 300), ("false", 60, 60),
])
def test_manager_start_worker_api_settings_inherit(tmp_path, gaming, scan, expected):
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import sys,json;sys.path.insert(0," + repr(str(ROOT / "backend")) + ");"
        "from app.core.config import get_settings; s=get_settings();"
        "print(json.dumps(dict(gaming=s.atlas_gaming_mode,"
        "discovery=s.effective_perp_micro_scan_seconds,"
        "manage=s.perp_micro_manage_seconds)))", encoding="utf-8",
    )
    worker = tmp_path / "worker.ps1"
    worker.write_text(rf"""
param($Action, $RunId)
$ErrorActionPreference = 'Stop'
if ($Action -ne 'Worker' -or -not $RunId) {{ throw 'invalid worker dispatch' }}
$Root = '{ps(tmp_path)}'; $Backend = $Root; $VenvPy = '{ps(sys.executable)}'
$loggingConfig = 'fixture.json'; $stdout = Join-Path $Root 'api.out'
$stderr = Join-Path $Root 'api.err'
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile('{ps(MANAGER)}',[ref]$tokens,[ref]$errors)
if ($errors.Count) {{ throw 'manager parse failed' }}
$launch = @($ast.FindAll({{
    param($n)
    $n -is [Management.Automation.Language.AssignmentStatementAst] -and
    $n.Left.Extent.Text -eq '$api' -and $n.Right.Extent.Text -match 'Start-Process'
}}, $true))
if ($launch.Count -ne 1) {{ throw 'unexpected API launch statement count' }}
function Start-Process {{
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle,
          $RedirectStandardOutput, $RedirectStandardError, [switch]$PassThru)
    if ($ArgumentList[2] -cne 'app.main:app' -or $WindowStyle -cne 'Hidden') {{
        throw 'unexpected API dispatch contract'
    }}
    # Replace only the executable workload: Python reads settings, never imports main.
    Microsoft.PowerShell.Management\Start-Process -FilePath $FilePath `
        -ArgumentList '"{ps(probe)}"' -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden -RedirectStandardOutput $RedirectStandardOutput `
        -RedirectStandardError $RedirectStandardError -Wait -PassThru
}}
Invoke-Expression $launch[0].Extent.Text
if ($api.ExitCode -ne 0) {{ throw (Get-Content $stderr -Raw) }}
""", encoding="utf-8-sig")
    fixture = tmp_path / "start.ps1"
    fixture.write_text(rf"""
$ErrorActionPreference = 'Stop'
$Root='{ps(tmp_path)}'; $RuntimeDir=$Root; $LockPath=Join-Path $Root 'fixture.lock'
Import-Module '{ps(ROOT / "scripts/windows/Atlas-CompleteShutdown.psm1")}' -Force
$ManagerPath='{ps(worker)}'; $PowerShellPath=Join-Path $PSHOME 'powershell.exe'
$env:ATLAS_GAMING_MODE='{gaming}'; $env:PERP_MICRO_SCAN_SECONDS='{scan}'
$env:PERP_MICRO_MANAGE_SECONDS='8'
function Assert-CleanStart {{ }}
function New-ExclusiveJsonFile($Value,$Path) {{ }}
function Remove-OwnedFile($Path,$RunId) {{ }}
function Get-ProcessIdentity($ProcessId) {{
    return @{{executable='fixture';command_line='fixture';created_utc='fixture'}}
}}
function Write-Status($Value) {{ }}
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile('{ps(MANAGER)}',[ref]$tokens,[ref]$errors)
$branch=@($ast.EndBlock.Statements | Where-Object {{
    $_ -is [Management.Automation.Language.IfStatementAst] -and
    $_.Clauses[0].Item1.Extent.Text -ceq '$Action -eq "Start"'
}})
if ($branch.Count -ne 1) {{ throw 'unexpected Start branch count' }}
& ([scriptblock]::Create($branch[0].Clauses[0].Item2.Extent.Text.Trim('{{','}}')))
$deadline=(Get-Date).AddSeconds(15)
while (-not (Test-Path (Join-Path $Root 'api.out'))) {{
    if ((Get-Date) -gt $deadline) {{ throw 'worker did not launch settings probe' }}
    Start-Sleep -Milliseconds 25
}}
do {{
    try {{
        $result=Get-Content (Join-Path $Root 'api.out') -Raw | ConvertFrom-Json
        if ($result) {{ break }}
    }} catch {{ }}
    if ((Get-Date) -gt $deadline) {{ throw 'probe did not complete' }}
    Start-Sleep -Milliseconds 25
}} while ($true)
$result | ConvertTo-Json
""", encoding="utf-8-sig")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(fixture)],
        capture_output=True, text=True, timeout=35, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {
        "gaming": gaming == "true", "discovery": expected, "manage": 8,
    }


@pytest.mark.parametrize("prior,fail", [("", False), ("false", False), ("sentinel", True)])
def test_cli_launcher_restores_environment_after_manager_outcome(tmp_path, prior, fail):
    # Copy only the opt-in launcher; its fixed sibling manager is an inert fixture.
    launcher = tmp_path / LAUNCHER.name
    launcher.write_bytes(LAUNCHER.read_bytes())
    (tmp_path / MANAGER.name).write_text(
        "param($Action)\n"
        "if ($Action -ne 'Start' -or $env:ATLAS_GAMING_MODE -ne 'true') { throw 'bad dispatch' }\n"
        + rf"""
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile('{ps(MANAGER)}',[ref]$tokens,[ref]$errors)
$definition=$ast.Find({{
    param($n)
    $n -is [Management.Automation.Language.FunctionDefinitionAst] -and
    $n.Name -eq 'Test-StartCommandLine'
}}, $true)
Invoke-Expression $definition.Extent.Text
$ManagerPath=$PSCommandPath
$own=Get-CimInstance Win32_Process -Filter "ProcessId=$PID"
if (-not (Test-StartCommandLine $own.CommandLine)) {{ throw 'start ownership rejected' }}
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'ownership-accepted'), 'yes')
"""
        + ("throw 'INJECTED_FAILURE'\n" if fail else ""), encoding="utf-8-sig",
    )
    script = rf"""
$ErrorActionPreference='Stop'
[Environment]::SetEnvironmentVariable('ATLAS_GAMING_MODE','{prior}','Process')
$failed=$false
try {{ & '{ps(launcher)}' -Action Start }} catch {{ $failed=$true }}
@{{failed=$failed; prior=$env:ATLAS_GAMING_MODE}} | ConvertTo-Json
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["failed"] is fail
    assert (data["prior"] or "") == prior
    assert (tmp_path / "ownership-accepted").read_text() == "yes"
