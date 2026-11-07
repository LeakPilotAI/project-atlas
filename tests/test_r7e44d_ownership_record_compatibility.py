"""Equivalent record forms must retain identical strict identity decisions."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/windows/Atlas-ProcessOwnership.psm1"
MANAGER = ROOT / "scripts/windows/Atlas-Background.ps1"


@pytest.mark.parametrize("scenario", [
    "valid", "owner_start_fallback", "missing_root", "missing_run", "missing_pid",
    "missing_created", "missing_launcher_pid", "missing_launcher_created",
    "missing_launcher_executable", "missing_launcher_command", "wrong_run",
    "wrong_runtime_pid", "api_pid_reused", "launcher_pid_reused", "wrong_api_executable",
    "wrong_launcher_executable", "wrong_launcher_command", "foreign_api_command",
    "foreign_api_pid", "wrong_parent", "malformed_pid", "malformed_created",
    "missing_runtime_pid", "missing_runtime_run", "runtime_skew", "null_owner",
    "null_runtime", "null_api", "missing_launcher", "wrong_root",
])
def test_shared_verifier_and_cleanup_accept_only_equivalent_valid_records(tmp_path, scenario):
    fixture = tmp_path / "records.ps1"
    fixture.write_text(rf"""
$ErrorActionPreference='Stop'
Import-Module '{str(MODULE).replace("'", "''")}' -Force
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile(
 '{str(MANAGER).replace("'", "''")}',[ref]$tokens,[ref]$errors)
if($errors.Count) {{ throw 'manager parse failed' }}
$definition=$ast.Find({{param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-VerifiedApiIdentity'}},$true)
Invoke-Expression $definition.Extent.Text
$Root='D:\Atlas'; $VenvPy='D:\Atlas\backend\.venv\Scripts\python.exe'
$VenvBasePy='C:\Python312\python.exe'; $RuntimePath='fixture-not-a-real-path'
$run='689b6423-8620-441b-bc6f-0b1e98527440'
$created=([datetime]'2026-10-16T08:28:47.7447190Z').ToUniversalTime()
$launcherCreated=$created.AddMilliseconds(-35)
$apiCommand='"C:\Python312\python.exe" -m uvicorn app.main:app --log-config "D:\Atlas\deploy\logging.json"'
$launcherCommand='"D:\Atlas\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --log-config "D:\Atlas\deploy\logging.json"'
$checks=0
foreach($ownerType in @('hashtable','persisted','ordered')) {{
 foreach($runtimeType in @('hashtable','persisted')) {{
  $ownerMap=@{{root=$Root;run_id=$run;pid=15876;created_utc=$created.ToString('o');started_utc=$created.ToString('o');
    executable=$VenvBasePy;command_line=$apiCommand;launcher_pid=27960;
    launcher_created_utc=$launcherCreated.ToString('o');launcher_executable=$VenvPy;launcher_command_line=$launcherCommand}}
  $runtimeMap=@{{run_id=$run;pid=15876;started_utc=$created.ToString('o')}}
  $script:fixtureApi=[pscustomobject]@{{ProcessId=15876;ParentProcessId=27960;ExecutablePath=$VenvBasePy;CommandLine=$apiCommand;CreationDate=$created}}
  $script:fixtureLauncher=[pscustomobject]@{{ProcessId=27960;ExecutablePath=$VenvPy;CommandLine=$launcherCommand;CreationDate=$launcherCreated}}
  switch('{scenario}') {{
   'owner_start_fallback' {{ $runtimeMap.Remove('started_utc'); $ownerMap.started_utc=$created.AddSeconds(-60).ToString('o') }}
   'missing_root' {{$ownerMap.Remove('root')}}
   'missing_run' {{$ownerMap.Remove('run_id')}}
   'missing_pid' {{$ownerMap.Remove('pid')}}
   'missing_created' {{$ownerMap.Remove('created_utc')}}
   'missing_launcher_pid' {{$ownerMap.Remove('launcher_pid')}}
   'missing_launcher_created' {{$ownerMap.Remove('launcher_created_utc')}}
   'missing_launcher_executable' {{$ownerMap.Remove('launcher_executable')}}
   'missing_launcher_command' {{$ownerMap.Remove('launcher_command_line')}}
   'wrong_run' {{$runtimeMap.run_id='867a9b46-e377-4018-b42f-010a71332caa'}}
   'wrong_runtime_pid' {{$runtimeMap.pid=99999}}
   'api_pid_reused' {{$script:fixtureApi.CreationDate=$created.AddSeconds(1)}}
   'launcher_pid_reused' {{$script:fixtureLauncher.CreationDate=$launcherCreated.AddSeconds(1)}}
   'wrong_api_executable' {{$script:fixtureApi.ExecutablePath='C:\Foreign\python.exe'}}
   'wrong_launcher_executable' {{$script:fixtureLauncher.ExecutablePath='C:\Foreign\python.exe'}}
   'wrong_launcher_command' {{$script:fixtureLauncher.CommandLine=$launcherCommand+' --foreign'}}
   'foreign_api_command' {{$script:fixtureApi.CommandLine='"C:\Python312\python.exe" -m uvicorn app.main:app --log-config "D:\Other\logging.json"'}}
   'foreign_api_pid' {{$script:fixtureApi.ProcessId=99999}}
   'wrong_parent' {{$script:fixtureApi.ParentProcessId=99999}}
   'malformed_pid' {{$ownerMap.pid='not-a-pid'}}
   'malformed_created' {{$ownerMap.created_utc='not-a-time'}}
   'missing_runtime_pid' {{$runtimeMap.Remove('pid')}}
   'missing_runtime_run' {{$runtimeMap.Remove('run_id')}}
   'runtime_skew' {{$runtimeMap.started_utc=$created.AddSeconds(-60).ToString('o')}}
   'missing_launcher' {{$script:fixtureLauncher=$null}}
   'wrong_root' {{$ownerMap.root='D:\Other'}}
  }}
  $owner=if($ownerType -eq 'persisted') {{$ownerMap|ConvertTo-Json|ConvertFrom-Json}}
    elseif($ownerType -eq 'ordered') {{$ordered=[ordered]@{{}};foreach($key in $ownerMap.Keys){{$ordered[$key]=$ownerMap[$key]}};$ordered}}
    else {{$ownerMap}}
  $script:fixtureRuntime=if($runtimeType -eq 'persisted') {{$runtimeMap|ConvertTo-Json|ConvertFrom-Json}} else {{$runtimeMap}}
  if('{scenario}' -eq 'null_owner') {{$owner=$null}}
  if('{scenario}' -eq 'null_runtime') {{$script:fixtureRuntime=$null}}
  if('{scenario}' -eq 'null_api') {{$script:fixtureApi=$null}}
  function Read-JsonFile($Path) {{return $script:fixtureRuntime}}
  function Get-AtlasApiProcesses {{return @($script:fixtureApi)}}
  function Get-ApiListeners {{return @(15876)}}
  function Get-CimProcess([int]$ProcessId) {{
   if($ProcessId -ne 27960) {{throw 'unexpected process query'}}
   return $script:fixtureLauncher
  }}
  $expected='{scenario}' -in @('valid','owner_start_fallback')
  $beforeOwner=$owner|ConvertTo-Json -Compress
  $beforeRuntime=$script:fixtureRuntime|ConvertTo-Json -Compress
  foreach($entry in @('shared','cleanup')) {{
   $accepted=$false
   try {{
    $accepted=if($entry -eq 'shared') {{
     Test-AtlasApiProcessOwnership $owner $script:fixtureRuntime $script:fixtureApi $script:fixtureLauncher $VenvPy $Root $VenvBasePy
    }} else {{Test-VerifiedApiIdentity $owner}}
   }} catch {{
    # Malformed fields may raise the existing fail-closed conversion error.
    if($expected) {{throw}}
   }}
   if([bool]$accepted -ne $expected) {{throw "Wrong decision: {scenario} / $ownerType / $runtimeType / $entry"}}
   $checks++
  }}
  if(($owner|ConvertTo-Json -Compress) -cne $beforeOwner -or
     ($script:fixtureRuntime|ConvertTo-Json -Compress) -cne $beforeRuntime) {{throw 'Record mutated'}}
 }}
}}
"PASS: $checks fixture decisions"
""", encoding="utf-8-sig")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(fixture)],
        capture_output=True, text=True, timeout=25, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: 12 fixture decisions" in result.stdout
