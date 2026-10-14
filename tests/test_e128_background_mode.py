import asyncio
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "scripts" / "windows" / "Atlas-Background.ps1"
CONTROLS = ROOT / "scripts" / "windows" / "Atlas-Background-Controls.ps1"
INSTALLER = ROOT / "scripts" / "windows" / "Install-AtlasBackgroundShortcut.ps1"
CONTAINER_MODULE = ROOT / "scripts" / "windows" / "Atlas-ContainerOwnership.psm1"
OWNERSHIP_MODULE = ROOT / "scripts" / "windows" / "Atlas-ProcessOwnership.psm1"
UI_MODULE = ROOT / "scripts" / "windows" / "Atlas-Background-Ui.psm1"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_e128_background_owner_requires_pid_process_identity_and_unique_run_id():
    text = _text(MANAGER)
    assert "function Test-IdentityRecord" in text
    assert "current.executable -ieq $ExpectedExecutable" in text
    assert "current.command_line -ceq [string]$Record.command_line" in text
    assert "current.created_utc -ceq [string]$Record.created_utc" in text
    assert "[string]$runtime.run_id -cne [string]$owner.run_id" in text
    assert "Test-AtlasApiProcessOwnership" in text
    assert "launcher_pid" in text
    assert "atlas-background-recovery.lock" in text
    assert "refusing to infer ownership" in text.lower()


def test_e128_background_duplicate_or_stale_starts_fail_closed():
    text = _text(MANAGER)
    assert "function Assert-CleanStart" in text
    assert "[System.IO.FileMode]::CreateNew" in text
    assert "Another start owns the lifecycle lock, or a stale lock exists" in text
    assert "runtime manifest exists without a background owner" in text
    assert "Port 8000 is occupied by an unowned process" in text


def test_e128_worker_verifies_gui_encoded_start_command_line():
    manager_path = str(MANAGER).replace("'", "''")
    output = _run_ownership_powershell(rf"""
$sourcePath = '{manager_path}'
$ManagerPath = 'D:\Atlas\scripts\windows\Atlas-Background.ps1'
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $sourcePath, [ref]$tokens, [ref]$parseErrors
)
if ($parseErrors.Count -gt 0) {{ throw 'Could not parse the production background manager.' }}
$definition = $ast.Find({{
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Test-StartCommandLine'
}}, $true)
if (-not $definition) {{ throw 'Test-StartCommandLine was not found.' }}
Invoke-Expression $definition.Extent.Text
$wrapper = "& '$ManagerPath' -Action 'Start' -Json"
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($wrapper))
$guiCommandLine = '"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -EncodedCommand ' + $encoded
if (-not (Test-StartCommandLine $guiCommandLine)) {{
    throw 'The encoded GUI manager invocation was not recognized as the verified Start action.'
}}
$directCommandLine = '"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -File "' +
    $ManagerPath + '" -Action Start -Json'
if (-not (Test-StartCommandLine $directCommandLine)) {{
    throw 'The direct manager Start invocation was not recognized.'
}}
$wrongManager = "& 'D:\Other\Atlas-Background.ps1' -Action 'Start' -Json"
$wrongEncoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($wrongManager))
if (Test-StartCommandLine ('powershell.exe -EncodedCommand ' + $wrongEncoded)) {{
    throw 'A different manager path was accepted.'
}}
$wrongAction = "& '$ManagerPath' -Action 'Status' -Json"
$wrongActionEncoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($wrongAction))
if (Test-StartCommandLine ('powershell.exe -EncodedCommand ' + $wrongActionEncoded)) {{
    throw 'A non-Start action was accepted.'
}}
if (Test-StartCommandLine 'powershell.exe -EncodedCommand not-valid-base64') {{
    throw 'A malformed encoded command was accepted.'
}}
Write-Output 'PASS'
""")
    assert "PASS" in output


def test_e128_unverified_dead_start_lock_stays_ambiguous_and_is_preserved(tmp_path):
    runtime_dir = str(tmp_path).replace("'", "''")
    manager_path = str(MANAGER).replace("'", "''")
    output = _run_ownership_powershell(rf"""
$runtimeDir = '{runtime_dir}'
$sourcePath = '{manager_path}'
$Root = 'D:\Atlas'
$RecoveryLockPath = Join-Path $runtimeDir 'atlas-background-recovery.lock'
$OwnerPath = Join-Path $runtimeDir 'atlas-background-owner.json'
$LockPath = Join-Path $runtimeDir 'atlas-background-start.lock'
$StopLockPath = Join-Path $runtimeDir 'atlas-background-stop.lock'
$RuntimePath = Join-Path $runtimeDir 'runtime.json'
$PowerShellPath = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$ManagerPath = 'D:\Atlas\scripts\windows\Atlas-Background.ps1'
$lock = [ordered]@{{
    pid=34684
    run_id='f201c0f7-1db5-4d89-968b-1a38217f4c9c'
    root=$Root
    phase='launching'
    executable=$PowerShellPath
    created_utc='2026-10-14T06:53:38.8267140Z'
    command_line='"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -EncodedCommand fixture'
}}
$lock | ConvertTo-Json | Set-Content -LiteralPath $LockPath
$before = (Get-FileHash -LiteralPath $LockPath -Algorithm SHA256).Hash
function Read-JsonFile([string]$Path) {{
    return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json)
}}
function Test-IdentityRecord($Record, [string]$ExpectedExecutable, [string]$RequiredCommand) {{
    return $false
}}
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $sourcePath, [ref]$tokens, [ref]$parseErrors
)
if ($parseErrors.Count -gt 0) {{ throw 'Could not parse the production background manager.' }}
$definition = $ast.Find({{
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Get-VerifiedState'
}}, $true)
if (-not $definition) {{ throw 'Get-VerifiedState was not found in the production manager.' }}
Invoke-Expression $definition.Extent.Text
$state = Get-VerifiedState
if ($state.state -ne 'AMBIGUOUS' -or $state.message -notmatch 'start lock is stale') {{
    throw "Unverified stale lock was not reported as ambiguous: $($state | ConvertTo-Json -Compress)"
}}
if (-not (Test-Path -LiteralPath $LockPath -PathType Leaf) -or
    (Get-FileHash -LiteralPath $LockPath -Algorithm SHA256).Hash -ne $before) {{
    throw 'Status modified or removed the unverified stale start lock.'
}}
Write-Output 'PASS'
""")
    assert "PASS" in output


def test_e128_verified_live_api_recovers_false_stop_timeout_state(tmp_path):
    runtime_dir = str(tmp_path).replace("'", "''")
    manager_path = str(MANAGER).replace("'", "''")
    output = _run_ownership_powershell(rf"""
$runtimeDir = '{runtime_dir}'
$sourcePath = '{manager_path}'
$Root = 'D:\Atlas'
$OwnerPath = Join-Path $runtimeDir 'atlas-background-owner.json'
$RuntimePath = Join-Path $runtimeDir 'runtime.json'
$LockPath = Join-Path $runtimeDir 'atlas-background-start.lock'
$StopLockPath = Join-Path $runtimeDir 'atlas-background-stop.lock'
$RecoveryLockPath = Join-Path $runtimeDir 'atlas-background-recovery.lock'
$VenvPy = 'D:\Atlas\backend\.venv\Scripts\python.exe'
$ManagerPath = 'D:\Atlas\scripts\windows\Atlas-Background.ps1'
$PowerShellPath = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$run = '867a9b46-e377-4018-b42f-010a71332caa'
$owner = [pscustomobject]@{{
    schema_version=1; root=$Root; run_id=$run; pid=31552; state='stop_timeout'
    created_utc='2026-10-14T07:41:51.2012980Z'
    started_utc='2026-10-14T07:41:55.418405+00:00'
    executable='C:\Python312\python.exe'
    command_line='"C:\Python312\python.exe" -m uvicorn app.main:app'
    launcher_pid=24880; launcher_created_utc='2026-10-14T07:41:51.1660240Z'
    launcher_executable=$VenvPy
    launcher_command_line='"D:\Atlas\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app'
    last_error='The API PID identity could not be verified; cleanup: Atlas PID identity changed before shutdown; no process was signalled.'
}}
$runtime = [pscustomobject]@{{
    pid=31552; run_id=$run; started_utc='2026-10-14T07:41:55.418405+00:00'
}}
$owner | ConvertTo-Json | Set-Content -LiteralPath $OwnerPath
$runtime | ConvertTo-Json | Set-Content -LiteralPath $RuntimePath
function Read-JsonFile([string]$Path) {{ Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json }}
function Get-AtlasApiProcesses {{ return ,@([pscustomobject]@{{ProcessId=31552;ParentProcessId=24880;ExecutablePath='C:\Python312\python.exe';CommandLine='"C:\Python312\python.exe" -m uvicorn app.main:app';CreationDate=[datetime]::Parse('2026-10-14T07:41:51.2012980Z')}}) }}
function Get-ApiListeners {{ return ,@(31552) }}
function Get-CimProcess([int]$ProcessId) {{ return [pscustomobject]@{{ProcessId=24880;ParentProcessId=28384;ExecutablePath=$VenvPy;CommandLine=$owner.launcher_command_line;CreationDate=[datetime]::Parse('2026-10-14T07:41:51.1660240Z')}} }}
function Test-AtlasApiProcessOwnership($OwnerRecord,$RuntimeRecord,$ApiProcess,$OwnerProcess,[string]$ExpectedExecutable,[string]$ExpectedRoot,[string]$ExpectedBaseExecutable) {{ return $true }}
$tokens=$null; $parseErrors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($sourcePath,[ref]$tokens,[ref]$parseErrors)
if($parseErrors.Count -gt 0) {{ throw 'Production manager did not parse.' }}
$definition=$ast.Find({{param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-VerifiedState'}},$true)
if(-not $definition) {{ throw 'Get-VerifiedState was not found.' }}
Invoke-Expression $definition.Extent.Text
$state=Get-VerifiedState
if($state.state -ne 'running' -or $state.owner.state -ne 'running') {{
    throw "Verified API did not report RUNNING: $($state | ConvertTo-Json -Compress)"
}}
if((Read-JsonFile $OwnerPath).state -ne 'stop_timeout') {{
    throw 'Status unexpectedly mutated persisted ownership metadata.'
}}
Write-Output 'PASS'
""")
    assert "PASS" in output


def test_e128_background_stop_uses_graceful_run_id_handshake_without_forced_fallback():
    text = _text(MANAGER)
    assert "Write-JsonAtomic @{run_id=[string]$Owner.run_id} $StopPath" in text
    assert "Start-Sleep -Milliseconds 500" in text
    assert "Test-VerifiedApiIdentity $Owner" in text
    assert "Stop-Process" not in text
    assert "No forced termination was attempted" in text
    assert "docker stop" not in text
    assert "Atlas-Stop.ps1" not in text


def test_e128_background_stop_timeout_reports_intervention_and_retains_ownership():
    text = _text(MANAGER)
    assert '$TimeoutSeconds = 30' in text
    assert '$owner.state = "stop_timeout"' in text
    assert "operator intervention is required" in text.lower()
    assert "process and runtime ownership were retained" in text
    assert "Review the Atlas logs and PAPER reconciliation" in text


def test_e128_empty_port_query_is_free_but_actual_query_failure_is_not():
    text = _text(MANAGER)
    query = text.split("function Get-ApiListeners {", 1)[1].split("\nfunction ", 1)[0]
    assert "Get-NetTCPConnection -State Listen -ErrorAction Stop" in query
    assert "Where-Object { [int]$_.LocalPort -eq 8000 }" in query
    assert "return @($listeners | ForEach-Object { [int]$_.OwningProcess } | Sort-Object -Unique)" in query
    assert "Cannot verify ownership of TCP port 8000" in query
    assert "-LocalPort 8000" not in query


def test_e128_free_port_and_missing_owner_state_enables_manual_start():
    text = _text(MANAGER)
    state = text.split("function Get-VerifiedState {", 1)[1].split("\nfunction ", 1)[0]
    controls = _text(CONTROLS)
    assert "if (Test-Path -LiteralPath $RuntimePath -PathType Leaf)" in state
    assert "if ($apiProcesses.Count -gt 0)" in state
    assert "if ($listeners.Count -gt 0)" in state
    assert "$listeners = @(Get-ApiListeners)" in state
    assert 'return @{ state="STOPPED"; message="No Atlas background run is recorded." }' in state
    apply_status = controls.split("function Apply-AtlasStatus($Result) {", 1)[1].split("\n}\n", 1)[0]
    assert 'Set-StatusMessage "$($Result.state): $($Result.message)" $color' in apply_status
    assert "$startButton.Enabled = ($Result.state -eq \"STOPPED\")" in controls
    assert '$stopButton.Enabled = ($Result.state -eq "running")' in apply_status
    assert "$statusButton.Enabled = $true" in apply_status


def test_e128_unknown_or_duplicate_port_owners_remain_ambiguous():
    state = _text(MANAGER).split("function Get-VerifiedState {", 1)[1].split("\nfunction ", 1)[0]
    assert "$listeners.Count -gt 1" in state
    assert "$listeners[0] -ne [int]$runtime.pid" in state
    assert "Port 8000 is occupied by an unowned process" in state
    assert "$apiProcess.Count -ne 1" in state


def test_e128_unknown_and_duplicate_api_processes_remain_ambiguous():
    text = _text(MANAGER)
    state = text.split("function Get-VerifiedState {", 1)[1].split("\nfunction ", 1)[0]
    processes = text.split("function Get-AtlasApiProcesses {", 1)[1].split("\nfunction ", 1)[0]
    assert "if ($apiProcesses.Count -gt 0)" in state
    assert "Atlas API process exists without a background owner" in state
    assert "$unexpectedProcesses.Count -gt 0" in state
    assert "Cannot verify Atlas API process ownership" in processes
    assert "uvicorn\\s+app\\.main:app" in processes


def test_e128_stale_manifest_and_mismatched_run_ids_remain_ambiguous():
    state = _text(MANAGER).split("function Get-VerifiedState {", 1)[1].split("\nfunction ", 1)[0]
    assert "[string]$runtime.run_id -cne [string]$owner.run_id" in state
    assert "Test-AtlasDeadSession" in state
    assert "Move-AtlasDeadSessionMetadata" in state
    assert "runtime manifest exists without a background owner" in state


def test_e128_background_stop_timeout_never_force_stops_api():
    text = _text(MANAGER)
    stop = text.split("function Stop-OwnedApi", 1)[1].split("\nfunction ", 1)[0]
    assert "Stop-Process" not in stop
    assert "stop_timeout" in stop
    assert "operator intervention" in stop.lower()
    assert "ownership were retained" in stop


def test_e128_docker_container_inspection_uses_json_not_nested_label_templates():
    text = _text(MANAGER)
    assert "docker inspect --format '{{json .}}' $Name" in text
    assert "ConvertFrom-AtlasContainerInspection" in text
    assert 'index .Config.Labels "com.docker.compose.project"' not in text


@pytest.mark.parametrize(
    ("project", "service", "name", "root", "compose_file", "should_pass"),
    [
        ("atlas", "postgres", "/atlas-postgres", "D:\\Atlas", "D:\\Atlas\\docker-compose.yml", True),
        ("projectatlas", "redis", "/atlas-redis", "D:\\Work\\Project Atlas",
         "D:\\Work\\Project Atlas\\docker-compose.yml", True),
        ("atlas", "postgres", "/atlas-postgres", "D:\\Atlas", None, False),
        ("genesis", "postgres", "/atlas-postgres", "D:\\Atlas",
         "D:\\Atlas\\docker-compose.yml", False),
        ("atlas", "redis", "/atlas-postgres", "D:\\Atlas",
         "D:\\Atlas\\docker-compose.yml", False),
    ],
)
def test_e128_docker_labels_validate_name_service_project_and_compose_root(
    project, service, name, root, compose_file, should_pass
):
    labels = {
        "com.docker.compose.project": project,
        "com.docker.compose.service": service,
        "com.docker.compose.project.working_dir": root,
    }
    if compose_file is not None:
        labels["com.docker.compose.project.config_files"] = compose_file
    payload = json.dumps(
        {
            "Name": name,
            "Config": {"Labels": labels},
            "State": {"Running": True, "Health": {"Status": "healthy"}},
        }
    )
    _assert_container_parser_result(payload, root, service, should_pass)


def test_e128_docker_label_parser_rejects_malformed_inspection_output():
    _assert_container_parser_result("{malformed", "D:\\Atlas", "postgres", False)


def test_e128_stop_request_for_old_run_is_ignored_by_new_run(tmp_path, monkeypatch):
    import app.services.desktop_control as module

    signals = []
    monkeypatch.setattr(module.signal, "raise_signal", signals.append)
    control = module.DesktopControl(tmp_path, "new-run-id")
    (tmp_path / "stop.json").write_text(json.dumps({"run_id": "old-run-id"}))

    async def run():
        await control.start()
        assert not control.requested()
        await control.stop()

    asyncio.run(run())
    assert signals == []


def _assert_container_parser_result(payload, root, service, should_pass):
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        pytest.skip("Windows PowerShell is required to exercise the container identity module.")
    module_path = str(CONTAINER_MODULE).replace("'", "''")
    payload_literal = payload.replace("'", "''")
    root_literal = root.replace("'", "''")
    service_literal = service.replace("'", "''")
    expectation = "$true" if should_pass else "$false"
    script = f"""
Import-Module '{module_path}' -Force
$expected = {expectation}
try {{
    $result = ConvertFrom-AtlasContainerInspection 'atlas-{service}' '{service_literal}' '{root_literal}' '{payload_literal}'
    if (-not $expected) {{ throw 'Invalid inspection was accepted.' }}
    if (-not $result.running -or $result.health -ne 'healthy') {{ throw 'Inspection result lost state.' }}
    Write-Output 'PASS'
}} catch {{
    if ($expected) {{ Write-Error $_; exit 1 }}
    if ($_.Exception.Message -notmatch 'malformed JSON|exact Atlas Compose identity|missing container identity') {{ Write-Error $_; exit 1 }}
    Write-Output 'REJECTED'
}}
"""
    completed = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    expected_output = "PASS" if should_pass else "REJECTED"
    assert expected_output in completed.stdout


def test_e128_background_shortcut_preserves_existing_atlas_shortcuts():
    installer = _text(INSTALLER)
    controls = _text(CONTROLS)
    assert '"Atlas Background.lnk"' in installer
    assert 'CreateShortcut($ShortcutPath)' in installer
    assert '"Project Atlas.lnk"' not in installer
    assert '"Stop Atlas.lnk"' not in installer
    assert "Start Atlas Background" in controls
    assert "Atlas Status" in controls
    assert "Stop Atlas Background" in controls
    assert "Install-DesktopShortcut.ps1" not in installer


def test_e128_background_start_is_manual_and_isolated_from_genesis_and_shared_services():
    text = _text(MANAGER)
    lower = text.lower()
    assert '"atlas-postgres" "postgres"' in text
    assert '"atlas-redis" "redis"' in text
    assert 'docker compose --project-name atlas --file $ComposePath up -d --no-recreate postgres redis' in text
    assert "docker compose down" not in lower
    assert "docker stop" not in lower
    assert "wsl --shutdown" not in lower
    assert "stop-process -name" not in lower
    assert "Get-Process python,node" not in text
    assert "Genesis" not in text
    assert "ATLAS-STOP.bat" not in text
    assert "ATLAS.bat" not in text
    assert "Set-Content.*\\.env" not in text
    assert "Project Atlas.lnk" not in text
    assert "Stop Atlas.lnk" not in text


def test_e128_background_controls_never_open_a_browser_or_console_window():
    controls = _text(CONTROLS)
    installer = _text(INSTALLER)
    assert "System.Windows.Forms" in controls
    assert "Start-Process -FilePath $PowerShell" in controls
    assert "-WindowStyle Hidden" in controls
    assert "-RedirectStandardOutput $outputPath" in controls
    assert "-RedirectStandardError $errorPath" in controls
    assert "Start-Process \"http://" not in controls
    assert "-WindowStyle Hidden -STA" in installer


def test_e128_background_controls_run_manager_operations_off_the_ui_thread():
    controls = _text(CONTROLS)
    assert "Start-Process -FilePath $PowerShell" in controls
    assert "-EncodedCommand {0}" in controls
    assert "exit_code_path = $exitCodePath" in controls
    assert "ConvertFrom-AtlasManagerCompletion" in controls
    assert ".process.ExitCode" not in controls
    assert "$active.process.HasExited" in controls
    assert "System.Windows.Forms.Timer" in controls
    assert "WaitForExit" not in controls
    assert ".Result" not in controls
    assert "completion_deadline = $null" in controls
    assert "AddSeconds(10)" in controls
    assert 'if ($files.state -eq "pending")' in controls
    assert "if ($files -and $files.state -eq \"ready\")" in controls
    assert "Start-BackgroundManager \"Status\"" in controls


def test_e128_background_controls_do_not_pass_quoted_color_expressions():
    controls = _text(CONTROLS)
    assert "Import-Module (Join-Path $PSScriptRoot \"Atlas-Background-Ui.psm1\") -Force" in controls
    assert "Set-AtlasBackgroundStatusRendering $status $statusTip $Message $Color" in controls
    assert not re.search(
        r"Set-StatusMessage[^\r\n]*[\"'][^\"']*\[System\.Drawing\.Color\]::", controls
    )
    assert not re.search(
        r"(?:ForeColor|BackColor)\s*=\s*[\"'][^\"']*(?:Color|Red|Green|Orange|SlateGray)",
        controls,
    )
    assert "[System.Drawing.Color]" in controls


def test_e128_background_status_rendering_uses_real_windows_forms_colors():
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        pytest.skip("Windows PowerShell is required to exercise Windows Forms rendering.")
    module_path = str(UI_MODULE).replace("'", "''")
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Import-Module '{module_path}' -Force
$label = New-Object System.Windows.Forms.Label
$tooltip = New-Object System.Windows.Forms.ToolTip
$checks = @(
    @{{ state='running'; expected=[System.Drawing.Color]::DarkGreen }},
    @{{ state='STOPPED'; expected=[System.Drawing.Color]::DarkSlateGray }},
    @{{ state='starting'; expected=[System.Drawing.Color]::DarkOrange }},
    @{{ state='stopping'; expected=[System.Drawing.Color]::DarkOrange }},
    @{{ state='AMBIGUOUS'; expected=[System.Drawing.Color]::DarkRed }}
)
foreach ($check in $checks) {{
    $color = Get-AtlasBackgroundStatusColor $check.state
    if ($color.GetType() -ne [System.Drawing.Color]) {{
        throw "Status color is not a System.Drawing.Color object for $($check.state)."
    }}
    Set-AtlasBackgroundStatusRendering $label $tooltip $check.state $color
    if ($label.ForeColor.ToArgb() -ne $check.expected.ToArgb() -or $label.Text -ne $check.state) {{
        throw "Status label did not render expected color/text for $($check.state)."
    }}
}}
$tooltip.Dispose()
$label.Dispose()
Write-Output 'PASS'
"""
    completed = subprocess.run(
        [powershell, "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert "PASS" in completed.stdout


def test_e128_background_async_callbacks_report_errors_without_escaping():
    controls = _text(CONTROLS)
    assert "$timer.Add_Tick({" in controls
    assert "Invoke-AtlasBackgroundUiCallback { Poll-BackgroundManager }" in controls
    assert "STATUS CHECK FAILED:" in controls
    assert "Atlas background timer callback failed:" in controls
    assert "Invoke-AtlasBackgroundUiCallback { Start-BackgroundManager \"Start\" }" in controls
    assert "try { $active.process.Dispose() } catch {" in controls
    assert "try { Remove-ManagerOutput $active } catch {" in controls
    assert "WaitForExit" not in controls


def test_e128_manager_completion_validates_exit_code_json_and_stderr():
    module_path = str(UI_MODULE).replace("'", "''")
    script = f"""
Import-Module '{module_path}' -Force
$stopped = ConvertFrom-AtlasManagerCompletion 'Status' '{{"state":"STOPPED","message":"No Atlas run."}}' '' '0'
if (-not $stopped.success -or $stopped.result.state -ne 'STOPPED') {{ throw 'Exit-code-zero STOPPED JSON was rejected.' }}
$running = ConvertFrom-AtlasManagerCompletion 'Status' '{{"state":"running","message":"Atlas is ready."}}' '' '0'
if (-not $running.success -or $running.result.state -ne 'running') {{ throw 'RUNNING JSON was rejected.' }}
$malformed = ConvertFrom-AtlasManagerCompletion 'Status' '{{malformed' '' '0'
if ($malformed.success -or $malformed.error -notmatch 'malformed JSON') {{ throw 'Malformed JSON was accepted or not reported.' }}
$nonzero = ConvertFrom-AtlasManagerCompletion 'Status' '' 'ownership query failed' '7'
if ($nonzero.success -or $nonzero.error -notmatch 'exit code 7' -or $nonzero.error -notmatch 'ownership query failed') {{ throw 'Nonzero exit/stderr were not reported.' }}
$missing = ConvertFrom-AtlasManagerCompletion 'Status' '{{"state":"STOPPED","message":"must not be trusted"}}' '' ''
if ($missing.success -or $missing.error -notmatch 'exit status was reported') {{ throw 'Missing exit-code data was treated as success.' }}
$badCode = ConvertFrom-AtlasManagerCompletion 'Status' '{{"state":"STOPPED","message":"must not be trusted"}}' '' 'unknown'
if ($badCode.success -or $badCode.error -notmatch 'exit status was reported') {{ throw 'Unparseable exit-code data was treated as success.' }}
Write-Output 'PASS'
"""
    completed = subprocess.run(
        [shutil.which("powershell.exe") or "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert "PASS" in completed.stdout


@pytest.mark.parametrize(
    ("locked_name", "expected_reason"),
    [("stdout", "stdout"), ("stderr", "stderr"), ("exit marker", "exit marker")],
)
def test_e128_locked_manager_completion_files_are_pending_until_writer_releases(
    tmp_path, locked_name, expected_reason
):
    module_path = str(UI_MODULE).replace("'", "''")
    temp_path = str(tmp_path).replace("'", "''")
    script = f"""
Import-Module '{module_path}' -Force
$directory = '{temp_path}'
$out = Join-Path $directory 'status.out'
$err = Join-Path $directory 'status.err'
$marker = Join-Path $directory 'status.exit'
[System.IO.File]::WriteAllText($out, '{{"state":"STOPPED","message":"verified"}}')
[System.IO.File]::WriteAllText($err, '')
[System.IO.File]::WriteAllText($marker, '0')
$lockedPath = switch ('{locked_name}') {{
    'stdout' {{ $out }}
    'stderr' {{ $err }}
    default {{ $marker }}
}}
$writer = [System.IO.File]::Open(
    $lockedPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Write,
    [System.IO.FileShare]::None
)
try {{
    $pending = Read-AtlasManagerCompletionFiles $out $err $marker
    if ($pending.state -ne 'pending' -or $pending.reason -notmatch '{expected_reason}') {{
        throw "Locked file was not reported pending: $($pending | ConvertTo-Json -Compress)"
    }}
}} finally {{
    $writer.Dispose()
}}
$ready = Read-AtlasManagerCompletionFiles $out $err $marker
if ($ready.state -ne 'ready' -or $ready.exit_code.Trim() -ne '0') {{
    throw "Completion files were not ready after writer release: $($ready | ConvertTo-Json -Compress)"
}}
Write-Output 'PASS'
"""
    completed = subprocess.run(
        [shutil.which("powershell.exe") or "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert "PASS" in completed.stdout


def test_e128_delayed_writer_release_is_polled_without_blocking_the_ui(tmp_path):
    module_path = str(UI_MODULE).replace("'", "''")
    temp_path = str(tmp_path).replace("'", "''")
    script = f"""
Import-Module '{module_path}' -Force
$directory = '{temp_path}'
$out = Join-Path $directory 'status.out'
$err = Join-Path $directory 'status.err'
$marker = Join-Path $directory 'status.exit'
[System.IO.File]::WriteAllText($out, '{{"state":"STOPPED","message":"verified"}}')
[System.IO.File]::WriteAllText($err, '')
[System.IO.File]::WriteAllText($marker, '0')
$writer = [System.IO.File]::Open(
    $out, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Write,
    [System.IO.FileShare]::None
)
$released = $false
$polls = 0
$deadline = (Get-Date).AddSeconds(4)
try {{
    while ((Get-Date) -lt $deadline) {{
        $pollStarted = [datetime]::UtcNow
        $state = Read-AtlasManagerCompletionFiles $out $err $marker
        $elapsedMs = ([datetime]::UtcNow - $pollStarted).TotalMilliseconds
        if ($elapsedMs -gt 200) {{ throw "A file-read retry blocked the polling thread for $elapsedMs ms." }}
        $polls++
        if ($state.state -eq 'ready') {{ $released = $true; break }}
        if ($polls -ge 4) {{
            $writer.Dispose()
            $writer = $null
        }}
        Start-Sleep -Milliseconds 50
    }}
}} finally {{
    if ($writer) {{ $writer.Dispose() }}
}}
if (-not $released -or $polls -lt 5) {{
    throw "Delayed handle release was not observed through polling; polls=$polls."
}}
Write-Output "PASS; polls=$polls"
"""
    completed = subprocess.run(
        [shutil.which("powershell.exe") or "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert "PASS; polls=" in completed.stdout


def test_e128_ui_defers_temp_cleanup_until_all_completion_handles_are_released():
    controls = _text(CONTROLS)
    poll = controls.split("function Poll-BackgroundManager {", 1)[1].split("\n}\n", 1)[0]
    pending_check = poll.index('if ($files.state -eq "pending")')
    pending_return = poll.index("return", pending_check)
    cleanup_guard = poll.index('if ($files -and $files.state -eq "ready")')
    cleanup_call = poll.index("Remove-ManagerOutput $active", cleanup_guard)
    assert pending_return < cleanup_guard < cleanup_call
    assert "Temporary files were retained for inspection." in poll


def test_e128_missing_exit_marker_waits_and_cleanup_is_deferred_until_ready(tmp_path):
    module_path = str(UI_MODULE).replace("'", "''")
    temp_path = str(tmp_path).replace("'", "''")
    script = f"""
Import-Module '{module_path}' -Force
$directory = '{temp_path}'
$out = Join-Path $directory 'status.out'
$err = Join-Path $directory 'status.err'
$marker = Join-Path $directory 'status.exit'
[System.IO.File]::WriteAllText($out, '{{"state":"STOPPED","message":"must not be accepted early"}}')
[System.IO.File]::WriteAllText($err, '')
$pending = Read-AtlasManagerCompletionFiles $out $err $marker
if ($pending.state -ne 'pending' -or (Test-Path $out) -eq $false -or (Test-Path $err) -eq $false) {{
    throw 'Missing marker was not treated as pending or output was prematurely cleaned.'
}}
[System.IO.File]::WriteAllText($marker, '0')
$ready = Read-AtlasManagerCompletionFiles $out $err $marker
if ($ready.state -ne 'ready') {{ throw 'Files did not become ready after marker creation.' }}
$completion = ConvertFrom-AtlasManagerCompletion 'Status' $ready.output $ready.error_output $ready.exit_code
if (-not $completion.success -or $completion.result.state -ne 'STOPPED') {{
    throw 'Completed STOPPED JSON was not accepted after marker became available.'
}}
Write-Output 'PASS'
"""
    completed = subprocess.run(
        [shutil.which("powershell.exe") or "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert "PASS" in completed.stdout


def test_e128_repeated_actual_manager_status_calls_wait_for_released_files(tmp_path):
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        pytest.skip("Windows PowerShell is required to launch the actual manager.")
    manager_path = str(MANAGER).replace("'", "''")
    module_path = str(UI_MODULE).replace("'", "''")
    temp_path = str(tmp_path).replace("'", "''")
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Import-Module '{module_path}' -Force
$manager = '{manager_path}'
$directory = '{temp_path}'
for ($iteration = 1; $iteration -le 3; $iteration++) {{
$stdout = Join-Path $directory "manager-$iteration.out"
$stderr = Join-Path $directory "manager-$iteration.err"
$exitFile = Join-Path $directory "manager-$iteration.exit"
$managerScript = @"
`$ErrorActionPreference = 'Stop'
`$ProgressPreference = 'SilentlyContinue'
`$exitCode = 1
try {{
    & '$manager' -Action Status -Json
    `$exitCode = 0
}} catch {{
    [Console]::Error.WriteLine(`$_.ToString())
}} finally {{
    [System.IO.File]::WriteAllText('$exitFile', [string]`$exitCode)
}}
exit `$exitCode
"@
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($managerScript))
$process = Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -EncodedCommand $encoded" `
    -WorkingDirectory (Split-Path (Split-Path $manager -Parent) -Parent) `
    -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
$deadline = (Get-Date).AddSeconds(20)
while (-not $process.HasExited -and (Get-Date) -lt $deadline) {{ Start-Sleep -Milliseconds 50 }}
if (-not $process.HasExited) {{ throw 'Status child did not complete asynchronously.' }}
$files = $null
$deadline = (Get-Date).AddSeconds(10)
do {{
    $files = Read-AtlasManagerCompletionFiles $stdout $stderr $exitFile
    if ($files.state -eq 'ready') {{ break }}
    if ($files.state -eq 'failed') {{ throw "Completion file access failed: $($files.reason)" }}
    Start-Sleep -Milliseconds 50
}} while ((Get-Date) -lt $deadline)
if (-not $files -or $files.state -ne 'ready') {{
    throw "Manager streams did not become available: $($files.reason)"
}}
$completion = ConvertFrom-AtlasManagerCompletion 'Status' $files.output $files.error_output $files.exit_code
if (-not $completion.success -or $completion.result.state -notin @('STOPPED','RUNNING','AMBIGUOUS')) {{
    throw "Status child was not accepted: $($completion.error)"
}}
Write-Output "PASS; iteration=$iteration; state=$($completion.result.state); Process.ExitCodeNull=$($null -eq $process.ExitCode); Marker=$($files.exit_code.Trim())"
$process.Dispose()
Remove-Item $stdout,$stderr,$exitFile -Force
}}
"""
    completed = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, (
        f"PowerShell status harness failed ({completed.returncode}).\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout.count("PASS; iteration=") == 3
    assert completed.stdout.count("Marker=0") == 3


def test_e128_gui_callback_exceptions_are_captured_and_reported():
    module_path = str(UI_MODULE).replace("'", "''")
    script = f"""
Import-Module '{module_path}' -Force
$errors = New-Object System.Collections.Generic.List[string]
$completed = Invoke-AtlasBackgroundUiCallback {{ throw 'simulated timer callback failure' }} {{
    param($errorRecord)
    $errors.Add($errorRecord.Exception.Message)
}}
if ($completed -or $errors.Count -ne 1 -or $errors[0] -ne 'simulated timer callback failure') {{
    throw 'GUI callback exception escaped or was not reported.'
}}
Write-Output 'PASS'
"""
    completed = subprocess.run(
        [shutil.which("powershell.exe") or "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert "PASS" in completed.stdout


def _run_ownership_powershell(script: str, timeout: int = 15) -> str:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        pytest.skip("Windows PowerShell is required to exercise process ownership.")
    module_path = str(OWNERSHIP_MODULE).replace("'", "''")
    completed = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
         f"Import-Module '{module_path}' -Force\n{script}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return completed.stdout


def test_e128_parent_child_pid_mismatch_is_accepted_only_for_verified_run_identity():
    output = _run_ownership_powershell(r"""
$root = 'D:\Atlas'
$exe = 'D:\Atlas\backend\.venv\Scripts\python.exe'
$run = '898b6a15-6dde-4667-89bf-5aa54a027b68'
$created = [datetime]::Parse('2026-10-14T06:29:37.3959580Z').ToUniversalTime()
$owner = [pscustomobject]@{
    root=$root; run_id=$run; pid=31204; created_utc=$created.ToString('o')
    started_utc='2026-10-14T06:29:37.4018446Z'
}
$runtime = [pscustomobject]@{pid=19444; run_id=$run; started_utc='2026-10-14T06:29:37.4018446Z'}
$api = [pscustomobject]@{
    ProcessId=19444; ParentProcessId=31204; ExecutablePath=$exe
    CommandLine='"D:\Atlas\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --log-config "D:\Atlas\deploy\logging.json"'
    CreationDate=$created
}
$launcher = [pscustomobject]@{
    ProcessId=31204; ParentProcessId=100; CreationDate=$created
    ExecutablePath=$exe; CommandLine=$api.CommandLine
}
if (-not (Test-AtlasApiProcessOwnership $owner $runtime $api $launcher $exe $root)) {
    throw 'Verified direct parent/child API PID pair was rejected.'
}
$api.ParentProcessId = 777
if (Test-AtlasApiProcessOwnership $owner $runtime $api $launcher $exe $root) {
    throw 'Mismatched parent/child process relationship was accepted.'
}
$api.ParentProcessId = 31204
$launcher.CreationDate = [datetime]::Parse('2026-10-15T06:29:37.3959580Z')
if (Test-AtlasApiProcessOwnership $owner $runtime $api $launcher $exe $root) {
    throw 'Reused launcher PID with a changed creation time was accepted.'
}
Write-Output 'PASS'
""")
    assert "PASS" in output


def test_e128_windows_venv_base_interpreter_child_requires_verified_launcher():
    output = _run_ownership_powershell(r"""
$root = 'D:\Work\Project Atlas'
$venvExe = 'D:\Work\Project Atlas\backend\.venv\Scripts\python.exe'
$baseExe = 'C:\Users\renal\AppData\Local\Programs\Python\Python312\python.exe'
$run = '867a9b46-e377-4018-b42f-010a71332caa'
$apiCreated = [datetime]::Parse('2026-10-14T07:41:51.2012980Z')
$launcherCreated = [datetime]::Parse('2026-10-14T07:41:51.1660240Z')
$launcherCommand = '"D:\Work\Project Atlas\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-config "D:\Work\Project Atlas\deploy\logging-desktop.json"'
$apiCommand = '"C:\Users\renal\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-config "D:\Work\Project Atlas\deploy\logging-desktop.json"'
$owner = [pscustomobject]@{
    root=$root; run_id=$run; pid=31552; created_utc=$apiCreated.ToUniversalTime().ToString('o')
    started_utc='2026-10-14T07:41:55.418405+00:00'; state='stop_timeout'
    launcher_pid=24880; launcher_created_utc=$launcherCreated.ToUniversalTime().ToString('o')
    launcher_executable=$venvExe; launcher_command_line=$launcherCommand
}
$runtime = [pscustomobject]@{pid=31552; run_id=$run; started_utc=$owner.started_utc}
$api = [pscustomobject]@{
    ProcessId=31552; ParentProcessId=24880; ExecutablePath=$baseExe
    CommandLine=$apiCommand; CreationDate=$apiCreated
}
$launcher = [pscustomobject]@{
    ProcessId=24880; ParentProcessId=28384; ExecutablePath=$venvExe
    CommandLine=$launcherCommand; CreationDate=$launcherCreated
}
if (-not (Test-AtlasApiProcessOwnership $owner $runtime $api $launcher $venvExe $root $baseExe)) {
    throw 'The actual Windows venv redirector child/parent identity was rejected.'
}
$api.ParentProcessId = 777
if (Test-AtlasApiProcessOwnership $owner $runtime $api $launcher $venvExe $root $baseExe) {
    throw 'Base interpreter with an unrelated parent was accepted.'
}
$api.ParentProcessId = 24880
if (Test-AtlasApiProcessOwnership $owner $runtime $api $launcher $venvExe $root 'C:\Other\python.exe') {
    throw 'Base interpreter outside pyvenv.cfg identity was accepted.'
}
$launcher.CommandLine = $launcherCommand + ' --foreign'
if (Test-AtlasApiProcessOwnership $owner $runtime $api $launcher $venvExe $root $baseExe) {
    throw 'A launcher command line different from the owner record was accepted.'
}
Write-Output 'PASS'
""")
    assert "PASS" in output


def test_e128_pid_reuse_and_mismatched_run_id_are_rejected():
    output = _run_ownership_powershell(r"""
$root = 'D:\Atlas'
$exe = 'D:\Atlas\backend\.venv\Scripts\python.exe'
$run = '898b6a15-6dde-4667-89bf-5aa54a027b68'
$owner = [pscustomobject]@{root=$root; run_id=$run; pid=19444; created_utc='2026-10-14T06:29:37.3959580Z'; started_utc='2026-10-14T06:29:37.4018446Z'}
$runtime = [pscustomobject]@{pid=19444; run_id=$run; started_utc='2026-10-14T06:29:37.4018446Z'}
$api = [pscustomobject]@{
    ProcessId=19444; ParentProcessId=31204; ExecutablePath=$exe
    CommandLine='"D:\Atlas\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --log-config "D:\Atlas\deploy\logging.json"'
    CreationDate=[datetime]::Parse('2026-10-15T06:29:37.3959580Z')
}
if (Test-AtlasApiProcessOwnership $owner $runtime $api $null $exe $root) {
    throw 'Reused PID with a different process creation time was accepted.'
}
$api.CreationDate = [datetime]::Parse('2026-10-14T06:29:37.3959580Z')
$runtime.run_id = '63e6113d-5a6c-4e1f-baf7-4c45d5585388'
if (Test-AtlasApiProcessOwnership $owner $runtime $api $null $exe $root) {
    throw 'Mismatched run IDs were accepted.'
}
Write-Output 'PASS'
""")
    assert "PASS" in output


def test_e128_confirmed_dead_session_archives_metadata_and_rejects_ambiguity(tmp_path):
    runtime_dir = str(tmp_path).replace("'", "''")
    output = _run_ownership_powershell(rf"""
$runtimeDir = '{runtime_dir}'
$ownerPath = Join-Path $runtimeDir 'atlas-background-owner.json'
$manifestPath = Join-Path $runtimeDir 'runtime.json'
$archiveRoot = Join-Path $runtimeDir 'stale-sessions'
$run = '898b6a15-6dde-4667-89bf-5aa54a027b68'
$owner = [pscustomobject]@{{root='D:\Atlas'; run_id=$run; pid=31204}}
$runtime = [pscustomobject]@{{pid=19444; run_id=$run}}
$owner | ConvertTo-Json | Set-Content -LiteralPath $ownerPath
$runtime | ConvertTo-Json | Set-Content -LiteralPath $manifestPath
$archive = Move-AtlasDeadSessionMetadata $ownerPath $manifestPath $archiveRoot `
    $owner $runtime 'D:\Atlas' @() @() @() $false
if ((Test-Path $ownerPath) -or (Test-Path $manifestPath) -or
    -not (Test-Path (Join-Path $archive 'atlas-background-owner.json')) -or
    -not (Test-Path (Join-Path $archive 'runtime.json'))) {{
    throw 'Dead-session evidence was not archived as expected.'
}}
$reuseRejected = $false
try {{
    Move-AtlasDeadSessionMetadata (Join-Path $archive 'atlas-background-owner.json') `
        (Join-Path $archive 'runtime.json') $archiveRoot $owner $runtime 'D:\Atlas' `
        @(19444) @() @() $false | Out-Null
}} catch {{ $reuseRejected = $true }}
if (-not $reuseRejected) {{ throw 'A live/reused PID was treated as a dead session.' }}
$runtime.run_id = '63e6113d-5a6c-4e1f-baf7-4c45d5585388'
if (Test-AtlasDeadSession $owner $runtime 'D:\Atlas' @() @() @() $false) {{
    throw 'Mismatched run IDs were treated as a dead session.'
}}
if (Test-AtlasDeadSession $owner $runtime 'D:\Atlas' @() @() @() $true) {{
    throw 'A session with a lifecycle lock was treated as dead.'
}}
if (Test-AtlasDeadSession $owner $runtime 'D:\Atlas' @() @(19444) @() $false) {{
    throw 'A matching API process was treated as dead.'
}}
if (Test-AtlasDeadSession $owner $runtime 'D:\Atlas' @() @() @(19444) $false) {{
    throw 'An active port listener was treated as dead.'
}}
Write-Output 'PASS'
""")
    assert "PASS" in output


def test_e128_windows_python_graceful_signal_delivery_is_supported():
    code = (
        "import signal; "
        "signal.signal(signal.SIGTERM, lambda *_: print('graceful-handler-ran', flush=True)); "
        "signal.raise_signal(signal.SIGTERM)"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert "graceful-handler-ran" in completed.stdout
