import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "scripts" / "windows" / "Atlas-Background.ps1"
CONTROLS = ROOT / "scripts" / "windows" / "Atlas-Background-Controls.ps1"
INSTALLER = ROOT / "scripts" / "windows" / "Install-AtlasBackgroundShortcut.ps1"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_e128_background_owner_requires_pid_process_identity_and_unique_run_id():
    text = _text(MANAGER)
    assert "function Test-IdentityRecord" in text
    assert "current.executable -ieq $ExpectedExecutable" in text
    assert "current.command_line -ceq [string]$Record.command_line" in text
    assert "current.created_utc -ceq [string]$Record.created_utc" in text
    assert "[string]$runtime.run_id -cne [string]$owner.run_id" in text
    assert "[int]$runtime.pid -ne [int]$owner.pid" in text
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
    assert "$startButton.Enabled = ($current.state -eq \"STOPPED\")" in controls


def test_e128_unknown_or_duplicate_port_owners_remain_ambiguous():
    state = _text(MANAGER).split("function Get-VerifiedState {", 1)[1].split("\nfunction ", 1)[0]
    assert "$listeners.Count -gt 1" in state
    assert "$listeners[0] -ne [int]$owner.pid" in state
    assert "Port 8000 is occupied by an unowned process" in state
    assert "$apiProcesses.Count -ne 1" in state


def test_e128_unknown_and_duplicate_api_processes_remain_ambiguous():
    text = _text(MANAGER)
    state = text.split("function Get-VerifiedState {", 1)[1].split("\nfunction ", 1)[0]
    processes = text.split("function Get-AtlasApiProcesses {", 1)[1].split("\nfunction ", 1)[0]
    assert "if ($apiProcesses.Count -gt 0)" in state
    assert "Atlas API process exists without a background owner" in state
    assert "$apiProcesses.Count -ne 1" in state
    assert "Cannot verify Atlas API process ownership" in processes
    assert "uvicorn\\s+app\\.main:app" in processes


def test_e128_stale_manifest_and_mismatched_run_ids_remain_ambiguous():
    state = _text(MANAGER).split("function Get-VerifiedState {", 1)[1].split("\nfunction ", 1)[0]
    assert "Recorded Atlas PID or process identity is stale or changed" in state
    assert "[string]$runtime.run_id -cne [string]$owner.run_id" in state
    assert "[int]$runtime.pid -ne [int]$owner.pid" in state
    assert "runtime manifest exists without a background owner" in state


def test_e128_background_stop_timeout_never_force_stops_api():
    text = _text(MANAGER)
    stop = text.split("function Stop-OwnedApi", 1)[1].split("\nfunction ", 1)[0]
    assert "Stop-Process" not in stop
    assert "stop_timeout" in stop
    assert "operator intervention" in stop.lower()
    assert "ownership were retained" in stop


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
