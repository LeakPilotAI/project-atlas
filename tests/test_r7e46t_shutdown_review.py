"""Independent adversarial lifecycle review; every lifecycle callback is synthetic."""
import json

import pytest
from test_r7e46s_complete_shutdown import MODULE, container, run_ps


@pytest.mark.parametrize("case", [
    "completed_identity_replaced", "first_service_restarts", "absent_service_appears",
    "successful_cli_still_running", "final_backend_changes", "interrupted_stop",
])
def test_independent_shutdown_races(tmp_path, case):
    payload = json.dumps({"postgres": container(tmp_path, "postgres", "a"),
                          "redis": container(tmp_path, "redis", "b")}).replace("'", "''")
    source = rf"""
$ErrorActionPreference='Stop'
Import-Module '{MODULE}' -Force
$Root='{tmp_path}';$case='{case}';$script:data=ConvertFrom-Json '{payload}'
$script:calls=@();$script:intents=@();$script:stoppedRedis=$false
if($case -ceq 'absent_service_appears'){{$script:data.postgres=$null}}
$prior=$null
if($case -ceq 'completed_identity_replaced'){{
 $prior=[pscustomobject]@{{state='COMPLETE';root=$Root;pending_ids=@();services=@(
  @{{name='atlas-postgres';id=('c'*64)}},@{{name='atlas-redis';id=('b'*64)}})}}
}}
$status={{if($case -ceq 'final_backend_changes' -and $script:stoppedRedis){{return @{{state='AMBIGUOUS'}}}};return @{{state='STOPPED'}}}}
$inspect={{param($Target)
 foreach($service in @('postgres','redis')){{$row=$script:data.$service
  if($row -and ($Target -ceq "atlas-$service" -or $Target -ceq $row.Id)){{return $row}}
 }}
 if($Target -cin @('atlas-postgres','atlas-redis')){{return $null}}
 throw 'Unknown ID'
}}
$stop={{param($Id)
 $script:calls+=,$Id
 if($Id -cnotin $script:intents){{throw 'intent not durable'}}
 if($case -ceq 'interrupted_stop'){{throw 'simulated controller interruption'}}
 if($case -ceq 'successful_cli_still_running' -and $Id -ceq ('a'*64)){{return @{{ok=$true;pending=$false}}}}
 foreach($service in @('postgres','redis')){{$row=$script:data.$service;if($row -and $row.Id -ceq $Id){{$row.State.Running=$false;$row.State.Status='exited'}}}}
 if($Id -ceq ('b'*64)){{
  $script:stoppedRedis=$true
  if($case -ceq 'first_service_restarts'){{$script:data.postgres.State.Running=$true;$script:data.postgres.State.Status='running'}}
  if($case -ceq 'absent_service_appears'){{$script:data.postgres=ConvertFrom-Json ('{payload}');$script:data.postgres=$script:data.postgres.postgres}}
 }}
 return @{{ok=$true;pending=$false}}
}}
$observe={{param($Value) $script:intents=@($Value.pending_ids)}}
$result=Invoke-AtlasCompleteShutdownPolicy -Root $Root -BackendStatus $status -BackendStop {{throw 'backend already stopped'}} -Inspect $inspect -ContainerStop $stop -PriorReceipt $prior -Observe $observe
$retry=$null
if($case -ceq 'successful_cli_still_running'){{
 $before=$script:calls.Count
 $retryPrior=[pscustomobject]@{{state=$result.state;root=$Root;services=$result.services;pending_ids=$result.pending_ids}}
 $retry=Invoke-AtlasCompleteShutdownPolicy -Root $Root -BackendStatus $status -BackendStop {{throw 'unexpected'}} -Inspect $inspect -ContainerStop $stop -PriorReceipt $retryPrior -Observe $observe
 if($script:calls.Count -ne $before){{throw 'accepted-but-unconfirmed stop replayed'}}
}}
@{{result=$result;retry=$retry;calls=$script:calls}}|ConvertTo-Json -Depth 9 -Compress
"""
    data = json.loads(run_ps(tmp_path, source))
    (tmp_path / "audit-evidence.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    assert data["result"]["state"] != "COMPLETE", data
    if case == "completed_identity_replaced":
        assert not data["calls"]
    if case == "successful_cli_still_running":
        assert "a" * 64 in data["result"]["pending_ids"]
    if case == "final_backend_changes":
        assert data["result"]["backend_state"] == "AMBIGUOUS"
    if case == "interrupted_stop":
        assert "a" * 64 in data["result"]["pending_ids"]


@pytest.mark.parametrize("exited", ['"true"', '1', 'null'])
def test_receipt_rejects_non_boolean_exit_evidence(tmp_path, exited):
    path = tmp_path / "logs/runtime"
    path.mkdir(parents=True)
    receipt = {"schema_version": 1, "root": str(tmp_path), "state": "COMPLETE",
               "backend_state": "STOPPED", "pending_ids": [], "services": [
                   {"name": "atlas-postgres", "id": "a" * 64, "state": "exited"},
                   {"name": "atlas-redis", "id": "b" * 64, "state": "exited"}],
               "owned_cli": [{"exited": json.loads(exited)}]}
    target = path / "atlas-complete-shutdown.json"
    target.write_text(json.dumps(receipt), encoding="utf-8")
    original = target.read_bytes()
    output = run_ps(tmp_path, rf"""
$ErrorActionPreference='Stop';Import-Module '{MODULE}' -Force
$rejected=$false;try{{Assert-AtlasCompleteReceipt '{tmp_path}'}}catch{{$rejected=$true}}
@{{rejected=$rejected}}|ConvertTo-Json -Compress
""")
    assert json.loads(output)["rejected"]
    assert target.read_bytes() == original

@pytest.mark.parametrize("initial,final", [("running", "running"), ("STOPPED", "running"),
                                          ("stopping", "stopping")])
def test_preflight_cannot_switch_backend_session(tmp_path, initial, final):
    payload = json.dumps({"postgres": container(tmp_path, "postgres", "a"),
                          "redis": container(tmp_path, "redis", "b")}).replace("'", "''")
    output = run_ps(tmp_path, rf"""
$ErrorActionPreference='Stop';Import-Module '{MODULE}' -Force
$Root='{tmp_path}';$data=ConvertFrom-Json '{payload}';$script:reads=0;$script:stops=0
$status={{$script:reads++;if($script:reads -eq 1){{return @{{state='{initial}';run_id='a670a59a-e41b-450f-9371-38208c0fc88d'}}}};return @{{state='{final}';run_id='b670a59a-e41b-450f-9371-38208c0fc88d'}}}}
$inspect={{param($Target)if($Target -ceq 'atlas-postgres'){{return $data.postgres}};return $data.redis}}
$stop={{param($Expected)$script:stops++;throw 'must not stop a changed session'}}
$result=Invoke-AtlasCompleteShutdownPolicy -Root $Root -BackendStatus $status -BackendStop $stop -Inspect $inspect -ContainerStop {{throw 'must not stop dependencies'}}
@{{state=$result.state;stops=$script:stops}}|ConvertTo-Json -Compress
""")
    assert json.loads(output) == {"state": "BLOCKED", "stops": 0}


@pytest.mark.parametrize("case", ["valid", "string_bool", "oneoff", "missing_oneoff",
                                   "bad_id", "contradictory", "unknown_state"])
def test_restoration_parser_rejects_ambiguous_ownership(tmp_path, case):
    from test_r7e46s_complete_shutdown import ROOT

    data = container(tmp_path, "postgres", "a")
    if case == "string_bool":
        data["State"]["Running"] = "false"
    if case == "oneoff":
        data["Config"]["Labels"]["com.docker.compose.oneoff"] = "True"
    if case == "missing_oneoff":
        del data["Config"]["Labels"]["com.docker.compose.oneoff"]
    if case == "bad_id":
        data["Id"] = "short"
    if case == "contradictory":
        data["State"]["Status"] = "exited"
    if case == "unknown_state":
        data["State"]["Status"] = "restarting"
    data["State"]["Health"] = {"Status": "healthy"}
    payload = json.dumps(data).replace("'", "''")
    output = run_ps(tmp_path, rf"""
$ErrorActionPreference='Stop'
Import-Module '{ROOT / "scripts/windows/Atlas-ContainerOwnership.psm1"}' -Force
$accepted=$false;try{{$result=ConvertFrom-AtlasContainerInspection 'atlas-postgres' 'postgres' '{tmp_path}' '{payload}';$accepted=$true}}catch{{$result=$null}}
@{{accepted=$accepted}}|ConvertTo-Json -Compress
""")
    assert json.loads(output)["accepted"] is (case == "valid")
