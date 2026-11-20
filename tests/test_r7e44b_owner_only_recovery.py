"""Owner-only recovery primitives: temporary paths, no live manager invocation."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT / "tests/fixtures/r7e44b_owner_only_recovery.ps1"


@pytest.mark.parametrize("scenario", [
    "success", "owner_changed", "stop_changed", "runtime_present",
    "start_lock_present", "outside_archive", "destination_exists", "lock_changed",
])
def test_owner_only_recovery_preserves_scope_and_fail_closed(tmp_path, scenario):
    fixture = tmp_path / "fixture.ps1"
    fixture.write_text(rf"""
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$Root='{str(tmp_path).replace("'", "''")}'
$RuntimeDir=Join-Path $Root 'runtime'
$OwnerPath=Join-Path $RuntimeDir 'atlas-background-owner.json'
$StopPath=Join-Path $RuntimeDir 'stop.json'
$RuntimePath=Join-Path $RuntimeDir 'runtime.json'
$LockPath=Join-Path $RuntimeDir 'start.lock'
$StopLockPath=Join-Path $RuntimeDir 'stop.lock'
$ExpectedRun='867a9b46-e377-4018-b42f-010a71332caa'
$archive=Join-Path $RuntimeDir 'stale-sessions\fixture'
[void][IO.Directory]::CreateDirectory($archive)
@{{schema_version=1;root=$Root;run_id=$ExpectedRun;state='stop_timeout';pid=31552;launcher_pid=24880}} |
 ConvertTo-Json | Set-Content $OwnerPath
@{{run_id='9a2b6955-04ca-4dbe-a48a-d045ed11417e'}} | ConvertTo-Json | Set-Content $StopPath
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile(
 '{str(RECOVERY).replace("'", "''")}',[ref]$tokens,[ref]$errors)
if($errors.Count) {{ throw 'recovery parse failed' }}
foreach($name in @('Get-BytesHash','Assert-RecordSet','Move-OnlyStaleOwner')) {{
 $definition=$ast.Find({{param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name}},$true)
 Invoke-Expression $definition.Extent.Text
}}
function Read-JsonFile($Path) {{ Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json }}
function Assert-RecoveryLock {{ if('{scenario}' -eq 'lock_changed') {{ throw 'lock changed' }} }}
$ExpectedOwnerHash=Get-BytesHash $OwnerPath
$ExpectedStopHash=Get-BytesHash $StopPath
$originalStop=[IO.File]::ReadAllBytes($StopPath)
$target=Join-Path $archive 'atlas-background-owner.json'
switch('{scenario}') {{
 'owner_changed' {{ Add-Content $OwnerPath 'changed' }}
 'stop_changed' {{ Add-Content $StopPath 'changed' }}
 'runtime_present' {{ [IO.File]::WriteAllText($RuntimePath,'unexpected') }}
 'start_lock_present' {{ [IO.File]::WriteAllText($LockPath,'unexpected') }}
 'outside_archive' {{ $target=Join-Path $Root 'atlas-background-owner.json' }}
 'destination_exists' {{ [IO.File]::WriteAllText($target,'existing evidence') }}
}}
$ownerBefore=Get-BytesHash $OwnerPath
$stopBefore=Get-BytesHash $StopPath
$failed=$false
try {{ Move-OnlyStaleOwner $target }} catch {{ $failed=$true }}
if('{scenario}' -eq 'success') {{
 if($failed) {{ throw 'approved fixture failed' }}
 Assert-RecordSet $true
 if((Get-BytesHash $target) -cne $ExpectedOwnerHash) {{ throw 'archive bytes changed' }}
}} else {{
 if(-not $failed) {{ throw 'unsafe archive accepted' }}
 if((Get-BytesHash $OwnerPath) -cne $ownerBefore) {{ throw 'owner changed on failure' }}
 if('{scenario}' -eq 'destination_exists' -and [IO.File]::ReadAllText($target) -cne 'existing evidence') {{ throw 'destination overwritten' }}
}}
if((Get-BytesHash $StopPath) -cne $stopBefore) {{ throw 'stop request mutated' }}
'PASS'
""", encoding="utf-8-sig")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(fixture)],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout
