"""Run actual PowerShell policy with synthetic metadata and fake lifecycle I/O."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/windows/Atlas-CompleteShutdown.psm1"
MANAGER = ROOT / "scripts/windows/Atlas-Background.ps1"


def run_ps(tmp_path, source):
    executable = shutil.which("powershell.exe")
    if not executable:
        pytest.skip("Requires Windows PowerShell")
    script = tmp_path / "isolated.ps1"
    script.write_text(source, encoding="utf-8-sig")
    result = subprocess.run([executable, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                             "Bypass", "-File", str(script)], capture_output=True,
                            encoding="utf-8", errors="replace", timeout=25,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def container(root, service, identity):
    return {"Id": identity * 64, "Name": f"/atlas-{service}", "Config": {"Labels": {
        "com.docker.compose.project": "atlas", "com.docker.compose.service": service,
        "com.docker.compose.project.working_dir": str(root),
        "com.docker.compose.project.config_files": str(root / "docker-compose.yml"),
        "com.docker.compose.oneoff": "False"}}, "State": {"Running": True, "Status": "running"}}


@pytest.mark.parametrize("case", [
    "normal", "stopped", "missing", "one_missing", "wrong_project", "wrong_root",
    "extra_config", "mixed_projects", "oneoff", "bad_id", "string_bool", "backend_timeout",
    "backend_changed", "wrong_ack", "docker_partial", "replace_after_drain", "uncertain",
])
def test_shutdown_policy(tmp_path, case):
    data = {"postgres": container(tmp_path, "postgres", "a"),
            "redis": container(tmp_path, "redis", "b")}
    if case == "stopped":
        for row in data.values():
            row["State"] = {"Running": False, "Status": "exited"}
    if case == "missing":
        data = {"postgres": None, "redis": None}
    if case == "one_missing":
        data["postgres"] = None
    labels = data["redis"]["Config"]["Labels"] if data["redis"] else {}
    if case == "wrong_project":
        labels["com.docker.compose.project"] = "foreign-project"
    if case == "wrong_root":
        labels["com.docker.compose.project.working_dir"] += "-foreign"
    if case == "extra_config":
        labels["com.docker.compose.project.config_files"] += ",foreign.yml"
    if case == "mixed_projects":
        labels["com.docker.compose.project"] = "projectatlas"
    if case == "oneoff":
        labels["com.docker.compose.oneoff"] = "True"
    if case == "bad_id":
        data["redis"]["Id"] = "short"
    if case == "string_bool":
        data["redis"]["State"]["Running"] = "false"
    payload = json.dumps(data).replace("'", "''")
    module = str(MODULE).replace("'", "''")
    root = str(tmp_path).replace("'", "''")
    source = rf"""
$ErrorActionPreference='Stop'
Import-Module '{module}' -Force
$Root='{root}';$case='{case}';$script:data=ConvertFrom-Json '{payload}'
$script:atlasPolicyNow=0.0;$script:stopCalls=@();$script:backendStops=0;$script:inspections=@();$script:lastIntent=@()
$run='a670a59a-e41b-450f-9371-38208c0fc88d'
$status={{
 if($case -cin @('stopped','missing','one_missing')){{return @{{state='STOPPED'}}}}
 if($script:backendStops -eq 0){{return @{{state='running';run_id=$run}}}}
 if($case -ceq 'backend_timeout'){{return @{{state='stopping';run_id=$run}}}}
 if($case -ceq 'backend_changed'){{return @{{state='stopping';run_id='b670a59a-e41b-450f-9371-38208c0fc88d'}}}}
 if($case -ceq 'replace_after_drain'){{$script:data.redis.Id='c'*64}}
 return @{{state='STOPPED'}}
}}
$backendStop={{param($Expected) $script:backendStops++;if($Expected -cne $run){{throw 'wrong expected run'}}
 return @{{state='stopping';run_id=$(if($case -ceq 'wrong_ack'){{'wrong'}}else{{$run}})}}}}
$inspect={{param($Target)
 $script:inspections+=,$Target
 foreach($service in @('postgres','redis')){{
  $row=$script:data.$service
  if($row -and ($Target -ceq "atlas-$service" -or $Target -ceq $row.Id)){{return $row}}
 }}
 if($Target -cin @('atlas-postgres','atlas-redis')){{return $null}}
 throw 'Unknown ID; never inspect unrelated resources'
}}
$stop={{param($Id)
 if($Id -cnotin @(('a'*64),('b'*64))){{throw 'unrelated container targeted'}}
 if($Id -cnotin $script:lastIntent){{throw 'durable stop intent missing'}}
 $script:stopCalls+=,$Id
 if($case -ceq 'uncertain' -and $Id -ceq ('a'*64)){{return @{{ok=$false;pending=$true}}}}
 if($case -ceq 'docker_partial' -and $Id -ceq ('a'*64)){{return @{{ok=$false;pending=$false}}}}
 foreach($service in @('postgres','redis')){{if($script:data.$service -and $script:data.$service.Id -ceq $Id){{
  $script:data.$service.State.Running=$false;$script:data.$service.State.Status='exited'
 }}}}
 return @{{ok=$true;pending=$false}}
}}
$pause={{$script:atlasPolicyNow+=1}};$clock={{return $script:atlasPolicyNow}}
$observe={{param($Value) $script:lastIntent=@($Value.pending_ids)}}
$result=Invoke-AtlasCompleteShutdownPolicy -Root $Root -BackendStatus $status -BackendStop $backendStop -Inspect $inspect -ContainerStop $stop -Pause $pause -Clock $clock -BackendTimeoutSeconds 3 -Observe $observe
$retry=$null;$resolved=$null
if($case -ceq 'uncertain'){{
 $prior=[pscustomobject]@{{state=$result.state;root=$Root;services=$result.services;pending_ids=$result.pending_ids}}
 $count=$script:stopCalls.Count
 $retry=Invoke-AtlasCompleteShutdownPolicy -Root $Root -BackendStatus $status -BackendStop $backendStop -Inspect $inspect -ContainerStop $stop -Pause $pause -Clock $clock -PriorReceipt $prior -Observe $observe
 if($script:stopCalls.Count -ne $count){{throw 'uncertain stop was replayed'}}
 $script:data.postgres.State.Running=$false;$script:data.postgres.State.Status='exited'
 $resolved=Invoke-AtlasCompleteShutdownPolicy -Root $Root -BackendStatus $status -BackendStop $backendStop -Inspect $inspect -ContainerStop $stop -Pause $pause -Clock $clock -PriorReceipt $prior -Observe $observe
}}
@{{result=$result;retry=$retry;resolved=$resolved;backend_stops=$script:backendStops;docker_stops=$script:stopCalls;inspections=$script:inspections}}|ConvertTo-Json -Depth 9 -Compress
"""
    result = json.loads(run_ps(tmp_path, source))
    (tmp_path / "evidence.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    if case in {"normal", "stopped", "missing", "one_missing"}:
        assert result["result"]["state"] == "COMPLETE", result
    elif case == "uncertain":
        assert result["result"]["state"] == "INCOMPLETE", result
        assert result["retry"]["state"] == "INCOMPLETE"
        assert result["resolved"]["state"] == "COMPLETE"
    elif case == "docker_partial":
        assert result["result"]["state"] == "INCOMPLETE", result
        assert len(result["docker_stops"]) == 2
    else:
        assert result["result"]["state"] == "BLOCKED", result
        assert not result["docker_stops"]
    if case in {"stopped", "missing"}:
        assert result["backend_stops"] == 0
        assert not result["docker_stops"]
    assert set(result["inspections"]) <= {"atlas-postgres", "atlas-redis", "a" * 64, "b" * 64}


def test_named_gate_is_reentrant_and_excludes_other_controller(tmp_path):
    module = str(MODULE).replace("'", "''")
    child = tmp_path / "competing.ps1"
    child.write_text(rf"""Import-Module '{module}' -Force
try{{$gate=Enter-AtlasLifecycleGate '{tmp_path}';Exit-AtlasLifecycleGate $gate;exit 9}}catch{{exit 0}}
""", encoding="utf-8-sig")
    result = run_ps(tmp_path, rf"""
$ErrorActionPreference='Stop';Import-Module '{module}' -Force
$outer=Enter-AtlasLifecycleGate '{tmp_path}'
try {{
 Import-Module '{module}' -Force
 $inner=Enter-AtlasLifecycleGate '{tmp_path}'
 Exit-AtlasLifecycleGate $inner
 & powershell.exe -NoProfile -NonInteractive -File '{child}'
 if($LASTEXITCODE -ne 0){{throw 'competing controller was admitted'}}
}} finally {{Exit-AtlasLifecycleGate $outer}}
$again=Enter-AtlasLifecycleGate '{tmp_path}';Exit-AtlasLifecycleGate $again
'PASS'
""")
    assert "PASS" in result


@pytest.mark.parametrize("case", ["alive", "gone", "reused", "missing_identity"])
def test_prior_cli_ownership_never_kills_or_replays(tmp_path, case):
    result = run_ps(tmp_path, rf"""
$ErrorActionPreference='Stop';Import-Module '{MODULE}' -Force
$receipt=@{{state='INCOMPLETE';owned_cli=@(@{{pid=12345;created_utc='old';executable='docker.exe';command_line='fixture';exited=$false}})}}
if('{case}' -ceq 'missing_identity'){{$receipt.owned_cli[0].command_line=''}}
$lookup={{param($Id) if('{case}' -ceq 'gone'){{return $null}};return @{{created_utc=$(if('{case}' -ceq 'reused'){{'new'}}else{{'old'}})}}}}
$rejected=$false;try{{Assert-AtlasPriorCliExited $receipt $lookup}}catch{{$rejected=$true}}
@{{rejected=$rejected}}|ConvertTo-Json -Compress
""")
    assert json.loads(result)["rejected"] is (case in {"alive", "missing_identity"})


def test_explicit_opt_in_and_no_destructive_lifecycle_commands():
    script = (ROOT / "scripts/windows/Atlas-CompleteShutdown.ps1").read_text(encoding="utf-8")
    assert "if (-not $Complete)" in script
    assert "@('stop','--time','-1',$Id)" in script
    assert "Stop-Process" not in script and ".Kill(" not in script
    assert "compose down" not in script and "prune" not in script
    assert "-ExpectedRunId $Expected" in script
    assert "Assert-AtlasPriorCliExited $prior" in script
    assert "--type','container'" in script
    manager = MANAGER.read_text(encoding="utf-8")
    assert "& docker start $postgres.id $redis.id" in manager
    assert "Assert-AtlasCompleteReceipt $Root" in manager


@pytest.mark.parametrize("endpoint,passed", [
    ("npipe:////./pipe/dockerDesktopLinuxEngine", True),
    ("npipe:////./pipe/docker_engine", True),
    ("tcp://foreign.example:2375", False), ("ssh://foreign.example", False), ("", False),
])
def test_docker_endpoint_is_local_and_explicit(tmp_path, endpoint, passed):
    result = run_ps(tmp_path, rf"""
$ErrorActionPreference='Stop';Import-Module '{MODULE}' -Force
$env:DOCKER_HOST=$null
$accepted=$false;try{{[void](Confirm-AtlasLocalDockerEndpoint '{endpoint}');$accepted=$true}}catch{{}}
@{{accepted=$accepted}}|ConvertTo-Json -Compress
""")
    assert json.loads(result)["accepted"] is passed


@pytest.mark.parametrize("state,rejected", [("COMPLETE", False), ("INCOMPLETE", True),
                                          ("IN_PROGRESS", True), ("BLOCKED", True)])
def test_incomplete_receipt_blocks_start_without_erasing_evidence(tmp_path, state, rejected):
    result = run_ps(tmp_path, rf"""
$ErrorActionPreference='Stop';Import-Module '{MODULE}' -Force
$root='{tmp_path}';[void](New-Item -ItemType Directory -Force (Join-Path $root 'logs/runtime'))
$path=Join-Path $root 'logs/runtime/atlas-complete-shutdown.json'
@{{schema_version=1;root=$root;state='{state}';backend_state='STOPPED';pending_ids=@();owned_cli=@();services=@(@{{name='atlas-postgres';id=('a'*64);state='exited'}},@{{name='atlas-redis';id=('b'*64);state='exited'}})}}|ConvertTo-Json -Depth 5|Set-Content $path
$before=[IO.File]::ReadAllBytes($path)
$rejected=$false;try{{Assert-AtlasCompleteReceipt $root}}catch{{$rejected=$true}}
if([Convert]::ToBase64String($before) -cne [Convert]::ToBase64String([IO.File]::ReadAllBytes($path))){{throw 'receipt modified'}}
@{{rejected=$rejected}}|ConvertTo-Json -Compress
""")
    assert json.loads(result)["rejected"] is rejected


@pytest.mark.parametrize("bad_id", [False, True])
def test_actual_dependency_restoration_starts_only_verified_ids_and_restores_environment(tmp_path, bad_id):
    (tmp_path / "docker-compose.yml").write_text("services: {}", encoding="utf-8")
    result = run_ps(tmp_path, rf"""
$ErrorActionPreference='Stop';Import-Module '{MODULE}' -Force
$Root='{tmp_path}';$RuntimeDir=$Root;$ComposePath=Join-Path $Root 'docker-compose.yml'
$script:called=@();$script:postgres=@{{id=$(if(${str(bad_id).lower()}){{'bad'}}else{{'a'*64}});project='atlas';running=$false;health='healthy'}}
$script:redis=@{{id=('b'*64);project='atlas';running=$false;health='healthy'}}
function Get-AtlasLocalDockerEndpoint {{return 'npipe:////./pipe/dockerDesktopLinuxEngine'}}
function Get-AtlasContainer($Name,$Service) {{if($Service -eq 'postgres'){{return $script:postgres}}else{{return $script:redis}}}}
function docker {{
 $script:called+=,@($args);$global:LASTEXITCODE=0
 if($args[0] -ceq 'start'){{$script:postgres.running=$true;$script:redis.running=$true}}
}}
$env:DOCKER_HOST='prior-host';$env:DOCKER_CONTEXT='prior-context'
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile('{MANAGER}',[ref]$tokens,[ref]$errors)
$node=$ast.Find({{param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -ceq 'Start-AtlasDependencies'}},$true)
Invoke-Expression $node.Extent.Text
$failed=$false;try{{Start-AtlasDependencies}}catch{{$failed=$true}}
@{{failed=$failed;called=$script:called;host_restored=($env:DOCKER_HOST -ceq 'prior-host');context_restored=($env:DOCKER_CONTEXT -ceq 'prior-context')}}|ConvertTo-Json -Depth 6 -Compress
""")
    data = json.loads(result)
    assert data["failed"] is bad_id
    assert data["host_restored"] and data["context_restored"]
    expected = [["info"]] if bad_id else [["info"], ["start", "a" * 64, "b" * 64]]
    assert data["called"] == expected


@pytest.mark.parametrize("case", ["valid", "missing_opt_in", "wrong_run", "reused_pid", "wrong_executable"])
def test_complete_stop_controller_preserves_actual_identity_checks(tmp_path, case):
    result = run_ps(tmp_path, rf"""
$ErrorActionPreference='Stop'
$ManagerPath=Join-Path $PSScriptRoot 'Atlas-Background.ps1'
$StopLockPath='fixture';$PowerShellPath='fixture-powershell.exe'
$owner=@{{run_id='a670a59a-e41b-450f-9371-38208c0fc88d';state='stopping'}}
$complete=Join-Path $PSScriptRoot 'Atlas-CompleteShutdown.ps1'
$command='fixture-powershell.exe -NoProfile -File "'+$complete+'" -Complete'
if('{case}' -ceq 'missing_opt_in'){{$command=$command.Replace(' -Complete','')}}
$script:lock=@{{pid=12345;run_id=$owner.run_id;phase='requesting';command_line=$command;created_utc='created';executable=$PowerShellPath}}
if('{case}' -ceq 'wrong_run'){{$script:lock.run_id='different'}}
$script:current=@{{pid=12345;command_line=$command;created_utc='created';executable=$PowerShellPath}}
if('{case}' -ceq 'reused_pid'){{$script:current.created_utc='later'}}
if('{case}' -ceq 'wrong_executable'){{$script:current.executable='foreign.exe'}}
function Read-JsonFile($Path){{return $script:lock}}
function Get-ProcessIdentity($Id){{return $script:current}}
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile('{MANAGER}',[ref]$tokens,[ref]$errors)
$identity=$ast.Find({{param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -ceq 'Test-IdentityRecord'}},$true)
Invoke-Expression $identity.Extent.Text
$clause=$ast.Find({{param($n)$n -is [Management.Automation.Language.IfStatementAst] -and $n.Clauses[0].Item1.Extent.Text -ceq '$owner.state -eq "stopping"'}},$true)
Invoke-Expression ('function Test-Controller {{'+$clause.Extent.Text+';return @{{state="PASS"}}}}')
Test-Controller|ConvertTo-Json -Compress
""")
    assert json.loads(result)["state"] == ("PASS" if case == "valid" else "AMBIGUOUS")


def test_actual_receipt_writer_preserves_previous_versions(tmp_path):
    entry = ROOT / "scripts/windows/Atlas-CompleteShutdown.ps1"
    result = run_ps(tmp_path, rf"""
$ErrorActionPreference='Stop'
$Root='{tmp_path}';$audit=Join-Path $Root 'audit';[void](New-Item -ItemType Directory $audit)
$receiptPath=Join-Path $Root 'active.json';$operation=[guid]::NewGuid().ToString();$script:ownedCli=@()
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile('{entry}',[ref]$tokens,[ref]$errors)
$node=$ast.Find({{param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -ceq 'Save-CompleteReceipt'}},$true)
Invoke-Expression $node.Extent.Text
$value=@{{state='IN_PROGRESS';backend_state='STOPPED';services=@();pending_ids=@();errors=@()}}
Save-CompleteReceipt $value
$first=[IO.File]::ReadAllBytes($receiptPath)
$value.state='COMPLETE';Save-CompleteReceipt $value
$old=@(Get-ChildItem $audit -Filter 'receipt-before-*.json')
if($old.Count -ne 1 -or [Convert]::ToBase64String([IO.File]::ReadAllBytes($old[0].FullName)) -cne [Convert]::ToBase64String($first)){{throw 'prior evidence lost'}}
@{{state=(Get-Content $receiptPath -Raw|ConvertFrom-Json).state;backups=$old.Count}}|ConvertTo-Json -Compress
""")
    assert json.loads(result) == {"state": "COMPLETE", "backups": 1}


def test_native_adapter_quoting_and_exit_status_use_only_fake_cli(tmp_path):
    entry = ROOT / "scripts/windows/Atlas-CompleteShutdown.ps1"
    result = run_ps(tmp_path, rf"""
$ErrorActionPreference='Stop'
$fake=Join-Path '{tmp_path}' 'fake-docker.exe'
Add-Type -TypeDefinition 'using System; public class FakeAtlasDocker {{public static void Main(string[] args) {{ foreach(string arg in args) Console.WriteLine(arg); }}}}' -OutputAssembly $fake -OutputType ConsoleApplication
$audit='{tmp_path}';$operation=[guid]::NewGuid().ToString();$script:commandNumber=0;$script:ownedCli=@();$script:DockerPath=$fake
$script:DockerEndpoint='npipe:////./pipe/dockerDesktopLinuxEngine';$DockerTimeoutSeconds=3
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile('{entry}',[ref]$tokens,[ref]$errors)
$node=$ast.Find({{param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -ceq 'Invoke-AtlasDockerCommand'}},$true)
Invoke-Expression $node.Extent.Text
foreach($name in @('format','nativeFormat')){{
 $assignment=$ast.Find({{param($n)$n -is [Management.Automation.Language.AssignmentStatementAst] -and $n.Left -is [Management.Automation.Language.VariableExpressionAst] -and $n.Left.VariablePath.UserPath -ceq $name}},$true)
 Invoke-Expression $assignment.Extent.Text
}}
$reply=Invoke-AtlasDockerCommand @('inspect','--type','container','--format',$nativeFormat,('a'*64))
$lines=@($reply.output.TrimEnd().Split("`n")|ForEach-Object {{$_.TrimEnd("`r")}})
@{{ok=$reply.ok;exit_code=$reply.exit_code;args=$lines;expected_format=$format;exited=$script:ownedCli[0].exited}}|ConvertTo-Json -Depth 5 -Compress
""")
    data = json.loads(result)
    assert data["ok"] and data["exit_code"] == 0 and data["exited"], data
    assert data["args"] == ["--host", "npipe:////./pipe/dockerDesktopLinuxEngine", "inspect",
                            "--type", "container", "--format", data["expected_format"], "a" * 64]
