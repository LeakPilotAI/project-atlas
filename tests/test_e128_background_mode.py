import asyncio
import json
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


def test_e128_background_stop_uses_graceful_run_id_handshake_without_forced_fallback():
    text = _text(MANAGER)
    assert "Write-JsonAtomic @{run_id=[string]$Owner.run_id} $StopPath" in text
    assert "Start-Sleep -Milliseconds 500" in text
    assert "Test-IdentityRecord $Owner $VenvPy" in text
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
    assert "$startButton.Enabled = ($Result.state -eq \"STOPPED\")" in controls


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
    assert "System.Diagnostics.ProcessStartInfo" in controls
    assert "CreateNoWindow = $true" in controls
    assert "-WindowStyle Hidden" in controls
    assert "Start-Process \"http://" not in controls
    assert "-WindowStyle Hidden -STA" in installer


def test_e128_background_controls_run_manager_operations_off_the_ui_thread():
    controls = _text(CONTROLS)
    assert "Start-Process -FilePath $PowerShell" in controls
    assert "$script:activeManager.process.HasExited" in controls
    assert "System.Windows.Forms.Timer" in controls
    assert "WaitForExit" not in controls
    assert ".Result" not in controls
    assert "Start-BackgroundManager \"Status\"" in controls


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
