"""Deterministic actual-adapter/policy checks with synthetic Docker replies only."""
import json
import re

import pytest
from test_r7e46s_complete_shutdown import MANAGER, MODULE, ROOT, container, run_ps


@pytest.mark.parametrize("case", [
    "missing", "null", "empty", "SIGTERM", "SIGINT", "numeric_signal", "array_signal",
    "boolean_signal", "object_signal", "unsafe_signal", "missing_project", "missing_service",
    "missing_root", "missing_config", "missing_oneoff", "full_id_mismatch", "unavailable",
])
def test_actual_inspection_adapter_and_policy_fail_closed(tmp_path, case):
    data = {"postgres": container(tmp_path, "postgres", "a"),
            "redis": container(tmp_path, "redis", "b")}
    for row in data.values():
        row["State"] = {"Running": False, "Status": "exited"}
    values = {"null": None, "empty": "", "SIGTERM": "SIGTERM", "SIGINT": "SIGINT",
              "numeric_signal": 15, "array_signal": ["SIGTERM"], "boolean_signal": False,
              "object_signal": {"value": "SIGTERM"}, "unsafe_signal": "SIGKILL"}
    if case in values:
        data["redis"]["Config"]["StopSignal"] = values[case]
    label = {"missing_project": "project", "missing_service": "service", "missing_root": "project.working_dir",
             "missing_config": "project.config_files", "missing_oneoff": "oneoff"}.get(case)
    if label:
        del data["redis"]["Config"]["Labels"]["com.docker.compose." + label]
    payload = json.dumps(data).replace("'", "''")
    entry = ROOT / "scripts/windows/Atlas-CompleteShutdown.ps1"
    result = json.loads(run_ps(tmp_path, rf"""
$ErrorActionPreference='Stop';Import-Module '{MODULE}' -Force
$Root='{tmp_path}';$script:fixture=ConvertFrom-Json '{payload}';$script:commands=@();$script:stopCalls=0
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile('{entry}',[ref]$tokens,[ref]$errors)
if($errors.Count){{throw 'parse error'}}
$node=$ast.Find({{param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -ceq 'Get-CompleteContainer'}},$true)
Invoke-Expression $node.Extent.Text
function Invoke-AtlasDockerCommand([string[]]$Arguments){{
 if($Arguments[0] -cne 'inspect' -or $Arguments[1] -cne '--type' -or $Arguments[2] -cne 'container'){{throw 'Unexpected command'}}
 $target=$Arguments[-1];$script:commands+=,$target
 if('{case}' -ceq 'unavailable'){{return @{{ok=$false;pending=$false;error='Engine unavailable';output=''}}}}
 $row=$null
 if($target -cin @('atlas-postgres',('a'*64))){{$row=$script:fixture.postgres}}
 elseif($target -cin @('atlas-redis',('b'*64))){{$row=$script:fixture.redis}}
 else{{throw 'Unrelated target'}}
 $copy=$row|ConvertTo-Json -Depth 8|ConvertFrom-Json
 if('{case}' -ceq 'full_id_mismatch' -and $target -ceq ('a'*64)){{$copy.Id='c'*64}}
 return @{{ok=$true;pending=$false;error='';output=($copy|ConvertTo-Json -Depth 8)}}
}}
$result=Invoke-AtlasCompleteShutdownPolicy -Root $Root -BackendStatus {{return @{{state='STOPPED'}}}} -BackendStop {{throw 'Backend must remain stopped'}} -Inspect {{param($Id)Get-CompleteContainer $Id}} -ContainerStop {{param($Id)$script:stopCalls++;throw 'Already exited'}}
@{{result=$result;commands=$script:commands;stops=$script:stopCalls}}|ConvertTo-Json -Depth 9 -Compress
"""))
    (tmp_path / "evidence.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    assert result["stops"] == 0
    assert set(result["commands"]) <= {"atlas-postgres", "atlas-redis", "a" * 64, "b" * 64}
    assert result["result"]["state"] == ("COMPLETE" if case in {"missing", "null", "empty", "SIGTERM", "SIGINT"} else "BLOCKED")


def test_optional_template_projection_is_null_safe_and_required_fields_unchanged():
    text = (ROOT / "scripts/windows/Atlas-CompleteShutdown.ps1").read_text(encoding="utf-8")
    assert '{{json (index .Config "StopSignal")}}' in text
    assert '{{json .Config.StopSignal}}' not in text
    for field in ['{{json .Id}}', '{{json .Name}}', '{{json .State.Running}}', '{{json .State.Status}}']:
        assert field in text
    for label in ["project", "service", "project.working_dir", "project.config_files", "oneoff"]:
        assert f'index .Config.Labels "com.docker.compose.{label}"' in text
    assert 'Assert-AtlasCompleteReceipt $Root' in MANAGER.read_text(encoding="utf-8")

@pytest.mark.parametrize("signal,accepted", [("SIGTERM", True), (15, False), (["SIGTERM"], False)])
def test_dictionary_optional_signal_cannot_bypass_validation(tmp_path, signal, accepted):
    data = container(tmp_path, "redis", "b")
    data["State"] = {"Running": False, "Status": "exited"}
    payload = json.dumps(data).replace("'", "''")
    raw = json.dumps({"signal": signal}).replace("'", "''")
    output = run_ps(tmp_path, rf"""
$ErrorActionPreference='Stop';Import-Module '{MODULE}' -Force
$row=ConvertFrom-Json '{payload}';$signal=(ConvertFrom-Json '{raw}').signal
$row.Config=@{{Labels=$row.Config.Labels;StopSignal=$signal}}
$accepted=$false;try{{$identity=ConvertTo-AtlasShutdownIdentity $row 'atlas-redis' 'redis' '{tmp_path}';$accepted=$true}}catch{{$identity=$null}}
@{{accepted=$accepted}}|ConvertTo-Json -Compress
""")
    assert json.loads(output)["accepted"] is accepted


def test_projection_produces_complete_json_framing():
    # Every action emits one JSON value. Replacing those actions with null tests
    # literal JSON framing independently of Docker and of metadata field values.
    source = (ROOT / "scripts/windows/Atlas-CompleteShutdown.ps1").read_text(encoding="utf-8")
    template = re.search(r"(?m)^    \$format='(.*)'$", source).group(1)
    framing = re.sub(r"\{\{.*?\}\}", "null", template)
    shape = json.loads(framing)
    assert set(shape) == {"Id", "Name", "Config", "State"}
    assert set(shape["Config"]) == {"StopSignal", "Labels"}
    assert set(shape["State"]) == {"Running", "Status"}
    assert len(shape["Config"]["Labels"]) == 5
