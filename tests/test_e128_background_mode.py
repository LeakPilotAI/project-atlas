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


def test_e128_background_stop_uses_graceful_run_id_handshake_and_exact_pid_fallback():
    text = _text(MANAGER)
    assert "Write-JsonAtomic @{run_id=[string]$Owner.run_id} $StopPath" in text
    assert "Start-Sleep -Milliseconds 500" in text
    assert "Test-IdentityRecord $Owner $VenvPy" in text
    assert "Stop-Process -Id ([int]$Owner.pid) -Force" in text
    assert "docker stop" not in text
    assert "Atlas-Stop.ps1" not in text


def test_e128_background_stop_timeout_retains_verified_ownership():
    text = _text(MANAGER)
    assert '$TimeoutSeconds = 30' in text
    assert '$owner.state = "stop_timeout"' in text
    assert "ownership was retained" in text
    assert "background owner" in text


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
