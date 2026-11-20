"""R7E44A: fail-closed missing-manifest audit, exclusively temporary fixtures."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "scripts/windows/Atlas-Background.ps1"
OWNERSHIP = ROOT / "scripts/windows/Atlas-ProcessOwnership.psm1"


def run(tmp_path, script):
    path = tmp_path / "audit.ps1"
    path.write_text(script, encoding="utf-8-sig")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(path)],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout


def test_retained_owner_missing_manifest_never_recovers_or_changes_records(tmp_path):
    run(tmp_path, rf"""
$ErrorActionPreference='Stop'
$Root='D:\Work\Project Atlas'
$RuntimeDir='{str(tmp_path).replace("'", "''")}'
$OwnerPath=Join-Path $RuntimeDir 'atlas-background-owner.json'
$RuntimePath=Join-Path $RuntimeDir 'runtime.json'
$StopPath=Join-Path $RuntimeDir 'stop.json'
$RecoveryLockPath=Join-Path $RuntimeDir 'recovery.lock'
$LockPath=Join-Path $RuntimeDir 'start.lock'
$StopLockPath=Join-Path $RuntimeDir 'stop.lock'
@{{schema_version=1;root=$Root;run_id='867a9b46-e377-4018-b42f-010a71332caa';
  state='stop_timeout';pid=31552;created_utc='2026-10-14T07:41:51.2012980Z';
  command_line='fixture'}} | ConvertTo-Json | Set-Content $OwnerPath
@{{run_id='9a2b6955-04ca-4dbe-a48a-d045ed11417e'}} | ConvertTo-Json | Set-Content $StopPath
$ownerBefore=[IO.File]::ReadAllText($OwnerPath)
$stopBefore=[IO.File]::ReadAllText($StopPath)
function Read-JsonFile($Path) {{
    if (Test-Path -LiteralPath $Path) {{ Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json }}
}}
function Get-AtlasApiProcesses {{ throw 'missing manifest must fail before process query' }}
function Get-ApiListeners {{ throw 'missing manifest must fail before listener query' }}
function New-ExclusiveJsonFile {{ throw 'recovery must not start' }}
function Move-AtlasDeadSessionMetadata {{ throw 'archive must not start' }}
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile(
 '{str(MANAGER).replace("'", "''")}',[ref]$tokens,[ref]$errors)
if ($errors.Count) {{ throw 'parser error' }}
foreach ($name in @('Get-VerifiedState','Assert-CleanStart')) {{
 $definition=$ast.Find({{param($n)
   $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name
 }},$true)
 Invoke-Expression $definition.Extent.Text
}}
$state=Get-VerifiedState
if ($state.state -cne 'AMBIGUOUS' -or $state.message -notmatch 'Runtime manifest does not confirm') {{ throw 'wrong state' }}
$blocked=$false
try {{ Assert-CleanStart }} catch {{
 if ($_.Exception.Message -notmatch 'Refusing startup') {{ throw }}
 $blocked=$true
}}
if (-not $blocked) {{ throw 'start allowed' }}
if ([IO.File]::ReadAllText($OwnerPath) -cne $ownerBefore -or
    [IO.File]::ReadAllText($StopPath) -cne $stopBefore) {{ throw 'records changed' }}
if (Test-Path $RuntimePath) {{ throw 'runtime manufactured' }}
if (Test-Path $RecoveryLockPath) {{ throw 'lock created' }}
'PASS'
""")


def test_existing_dead_session_contract_rejects_missing_or_conflicting_runtime(tmp_path):
    run(tmp_path, rf"""
$ErrorActionPreference='Stop'
Import-Module '{str(OWNERSHIP).replace("'", "''")}' -Force
$owner=[pscustomobject]@{{root='D:\Atlas';run_id='867a9b46-e377-4018-b42f-010a71332caa';pid=31552}}
$runtime=[pscustomobject]@{{run_id=$owner.run_id;pid=31552}}
if (Test-AtlasDeadSession $owner $null 'D:\Atlas' @() @() @() $false) {{ throw 'missing manifest accepted' }}
$runtime.run_id='9a2b6955-04ca-4dbe-a48a-d045ed11417e'
if (Test-AtlasDeadSession $owner $runtime 'D:\Atlas' @() @() @() $false) {{ throw 'different run accepted' }}
$runtime.run_id=$owner.run_id
if (Test-AtlasDeadSession $owner $runtime 'D:\Atlas' @(31552) @() @() $false) {{ throw 'live PID accepted' }}
if (Test-AtlasDeadSession $owner $runtime 'D:\Atlas' @() @(100) @() $false) {{ throw 'API accepted' }}
if (Test-AtlasDeadSession $owner $runtime 'D:\Atlas' @() @() @(100) $false) {{ throw 'listener accepted' }}
if (Test-AtlasDeadSession $owner $runtime 'D:\Atlas' @() @() @() $true) {{ throw 'lock accepted' }}
if (-not (Test-AtlasDeadSession $owner $runtime 'D:\Atlas' @() @() @() $false)) {{ throw 'valid dead fixture rejected' }}
$path=Join-Path '{str(tmp_path).replace("'", "''")}' 'archive'
try {{
 Move-AtlasDeadSessionMetadata 'unused-owner' 'unused-runtime' $path $owner $null 'D:\Atlas' @() @() @() $false
 throw 'archive accepted missing manifest'
}} catch {{ if ($_.Exception.Message -notmatch 'not proven dead and unambiguous') {{ throw }} }}
if (Test-Path $path) {{ throw 'archive created for missing manifest' }}
'PASS'
""")
