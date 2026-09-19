from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_launcher_is_api_served_and_preserves_docker_desktop():
    text = _text("scripts/windows/Atlas-Launch.ps1")
    assert '"-m", "uvicorn", "app.main:app"' in text
    assert 'http://127.0.0.1:8000/health' in text
    assert 'http://127.0.0.1:8000/dashboard?v=desk-v7' in text
    assert 'Docker Desktop and other apps (Genesis, etc.) stay running.' in text
    assert 'Start-Process "http://127.0.0.1:3000' not in text


def test_stop_script_scopes_shutdown_to_atlas():
    text = _text("scripts/windows/Atlas-Stop.ps1")
    assert '$env:COMPOSE_PROJECT_NAME = "atlas"' in text
    assert 'docker stop atlas-postgres atlas-redis' in text
    assert 'Docker Desktop / Genesis were not touched.' in text
    assert 'Stop-Process -Name "Docker Desktop"' not in text


def test_shortcut_installer_targets_root_batch_files():
    text = _text("scripts/windows/Install-DesktopShortcut.ps1")
    assert '"Project Atlas.lnk"' in text
    assert '"Stop Atlas.lnk"' in text
    assert '$s.TargetPath = $LaunchBat' in text
    assert '$t.TargetPath = $StopBat' in text


def test_desktop_smoke_is_fail_closed_and_no_live():
    text = _text("scripts/windows/Atlas-Desktop-Smoke.ps1")
    for endpoint in ("/health", "/dashboard", "/api/research", "/api/command-center/summary"):
        assert endpoint in text
    assert 'paper_shadow_only = $true' in text
    assert 'live_capital_allowed = $false' in text
    assert 'automatic_real_money_execution = $false' in text
    assert 'ATLAS_DESKTOP_SMOKE_BLOCKED' in text
    assert 'exit 2' in text


def test_desktop_smoke_supports_longevity_and_reconciliation_probes():
    text = _text("scripts/windows/Atlas-Desktop-Smoke.ps1")
    assert "[int]$LongevitySeconds = 0" in text
    assert "[int]$ProbeIntervalSeconds = 15" in text
    assert "/diagnostics/paper-reconciliation" in text
    assert "longevity = $longevity" in text
    assert "$longevity.green" in text
