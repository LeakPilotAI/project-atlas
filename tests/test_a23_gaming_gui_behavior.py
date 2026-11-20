"""Execute real GUI functions against temporary managers; never launch Atlas."""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTROLS = ROOT / "scripts/windows/Atlas-Background-Controls.ps1"
UI = ROOT / "scripts/windows/Atlas-Background-Ui.psm1"


def literal(path):
    return str(path).replace("'", "''")


def run_fixture(tmp_path, body):
    fixture = tmp_path / "fixture.ps1"
    fixture.write_text(body, encoding="utf-8-sig")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(fixture)],
        capture_output=True, text=True, timeout=35, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def setup():
    return rf"""$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Import-Module '{literal(UI)}' -Force
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile(
    '{literal(CONTROLS)}', [ref]$tokens, [ref]$errors)
if ($errors.Count) {{ throw 'GUI parse failed' }}
foreach ($node in $ast.FindAll({{
    param($n)
    $n -is [Management.Automation.Language.FunctionDefinitionAst]
}}, $true)) {{ Invoke-Expression $node.Extent.Text }}
$startButton = [pscustomobject]@{{ Enabled = $false }}
$gamingButton = [pscustomobject]@{{ Enabled = $false }}
$stopButton = [pscustomobject]@{{ Enabled = $false }}
$statusButton = [pscustomobject]@{{ Enabled = $true }}
function Set-StatusMessage($Message, $Color) {{ $script:lastMessage = $Message }}
$script:activeManager = $null
"""


@pytest.mark.parametrize("state,enabled,stop", [
    ("STOPPED", True, False), ("running", False, True),
    ("starting", False, False), ("stopping", False, False),
    ("AMBIGUOUS", False, False), ("stop_timeout", False, False),
])
def test_only_explicit_stopped_enables_both_start_buttons(tmp_path, state, enabled, stop):
    result = run_fixture(tmp_path, setup() + f"""
Apply-AtlasStatus ([pscustomobject]@{{state='{state}';message='fixture'}})
@{{ normal=$startButton.Enabled; gaming=$gamingButton.Enabled;
   stop=$stopButton.Enabled; status=$statusButton.Enabled }} | ConvertTo-Json
""")
    assert result == {"normal": enabled, "gaming": enabled, "stop": stop, "status": True}


def test_actual_initialization_is_passive_and_fail_closed(tmp_path):
    # Execute initialization only: no ShowDialog, timer, callbacks, or manager action.
    text = CONTROLS.read_text(encoding="utf-8-sig")
    prefix = text.split("function Set-StatusMessage", 1)[0]
    result = run_fixture(tmp_path, "Set-StrictMode -Version Latest\n" +
                         f"$PSScriptRoot = '{literal(CONTROLS.parent)}'\n" + prefix + """
try {
    @{ normal=$startButton.Enabled; gaming=$gamingButton.Enabled;
       stop=$stopButton.Enabled; status=$statusButton.Enabled;
       caption=$status.Text } | ConvertTo-Json
} finally { $statusTip.Dispose(); $form.Dispose() }
""")
    assert result == {"normal": False, "gaming": False, "stop": False,
                      "status": True, "caption": "Status not checked - click Atlas Status."}


@pytest.mark.parametrize("action,prior,mode", [
    ("GamingStart", "", "ok"), ("GamingStart", "false", "ok"),
    ("GamingStart", "sentinel", "ok"), ("Start", "false", "ok"),
    ("Status", "false", "ok"), ("Stop", "false", "ok"),
    ("GamingStart", "false", "throw"), ("GamingStart", "false", "malformed"),
])
def test_real_encoded_child_dispatch_and_completion(tmp_path, action, prior, mode):
    manager = tmp_path / "Mock Manager's.ps1"
    manager.write_text(f"""
param([ValidateSet('Start','Status','Stop')][string]$Action, [switch]$Json)
$ErrorActionPreference = 'Stop'
if ('{mode}' -eq 'throw') {{ throw 'INJECTED_MANAGER_FAILURE' }}
if ('{mode}' -eq 'malformed') {{ Write-Output 'not-json'; return }}
$state = switch ($Action) {{ 'Start' {{ 'starting' }} 'Stop' {{ 'stopping' }} default {{ 'STOPPED' }} }}
@{{state=$state;message='fixture'; received_action=$Action;
   gaming=$env:ATLAS_GAMING_MODE; json_switch=[bool]$Json}} | ConvertTo-Json -Compress
""", encoding="utf-8-sig")
    result = run_fixture(tmp_path, setup() + rf"""
$Manager = '{literal(manager)}'
$Root = '{literal(tmp_path)}'
$PowerShell = Join-Path $PSHOME 'powershell.exe'
[Environment]::SetEnvironmentVariable('ATLAS_GAMING_MODE','{prior}','Process')
Apply-AtlasStatus ([pscustomobject]@{{state='STOPPED';message='fixture'}})
Start-BackgroundManager '{action}'
$active = $script:activeManager
if (-not $active) {{ throw $script:lastMessage }}
$during = @{{normal=$startButton.Enabled; gaming=$gamingButton.Enabled;
             stop=$stopButton.Enabled; status=$statusButton.Enabled}}
$deadline = (Get-Date).AddSeconds(15)
do {{
    $files = Read-AtlasManagerCompletionFiles $active.output_path $active.error_path $active.exit_code_path
    if ($active.process.HasExited -and $files.state -eq 'ready') {{ break }}
    Start-Sleep -Milliseconds 25
}} while ((Get-Date) -lt $deadline)
if ($files.state -ne 'ready') {{ throw 'mock child completion timed out' }}
$completion = ConvertFrom-AtlasManagerCompletion $active.action $files.output $files.error_output $files.exit_code
Poll-BackgroundManager
@{{action=$active.action; success=$completion.success; response=$completion.result;
   error=$completion.error; during=$during; normal=$startButton.Enabled;
   gaming=$gamingButton.Enabled; stop=$stopButton.Enabled; status=$statusButton.Enabled;
   parent_mode=$env:ATLAS_GAMING_MODE; message=$script:lastMessage}} | ConvertTo-Json -Depth 6
""")
    assert result["action"] == ("Start" if action == "GamingStart" else action)
    assert result["during"] == dict.fromkeys(["normal", "gaming", "stop", "status"], False)
    assert (result["parent_mode"] or "") == prior
    assert result["status"] is True
    if mode == "ok":
        assert result["success"] is True
        assert result["response"]["received_action"] == result["action"]
        assert result["response"]["json_switch"] is True
        assert (result["response"]["gaming"] or "") == (
            "true" if action == "GamingStart" else prior)
        assert result["normal"] is (action == "Status")
        assert result["gaming"] is (action == "Status")
    else:
        assert result["success"] is False
        assert ("INJECTED_MANAGER_FAILURE" if mode == "throw" else "malformed JSON") in result["error"]
        assert result["normal"] is False
        assert result["gaming"] is False
    assert result["stop"] is False


def test_idle_poll_never_invokes_a_manager(tmp_path):
    result = run_fixture(tmp_path, setup() + """
function Start-Process { throw 'idle poll attempted a process launch' }
1..5 | ForEach-Object { Poll-BackgroundManager }
@{active=($null -ne $script:activeManager); gaming=$gamingButton.Enabled} | ConvertTo-Json
""")
    assert result == {"active": False, "gaming": False}


def test_launch_failure_disables_actions_until_manual_recheck(tmp_path):
    result = run_fixture(tmp_path, setup() + """
$Manager='fixture'; $Root='fixture'; $PowerShell='fixture'
function Start-Process { throw 'INJECTED_PROCESS_CREATION_FAILURE' }
Apply-AtlasStatus ([pscustomobject]@{state='STOPPED';message='fixture'})
Start-BackgroundManager 'GamingStart'
@{normal=$startButton.Enabled; gaming=$gamingButton.Enabled;
  stop=$stopButton.Enabled; status=$statusButton.Enabled;
  active=($null -ne $script:activeManager); message=$script:lastMessage} | ConvertTo-Json
""")
    assert result["normal"] is False
    assert result["gaming"] is False
    assert result["stop"] is False
    assert result["status"] is True
    assert result["active"] is False
    assert "INJECTED_PROCESS_CREATION_FAILURE" in result["message"]


def test_active_request_rejects_duplicate_launch(tmp_path):
    result = run_fixture(tmp_path, setup() + """
function Start-Process { throw 'duplicate process launch attempted' }
$script:activeManager=@{action='Start'}
Start-BackgroundManager 'GamingStart'
@{action=$script:activeManager.action} | ConvertTo-Json
""")
    assert result == {"action": "Start"}
