"""Source-only safety checks for explicit Atlas gaming launcher."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts/windows/Atlas-Background-Gaming.ps1"
MANAGER = ROOT / "scripts/windows/Atlas-Background.ps1"


def test_launcher_requires_explicit_start():
    source = LAUNCHER.read_text(encoding="utf-8")
    assert '[string]$Action = "Status"' in source
    assert '[ValidateSet("Start", "Status", "Stop")]' in source


def test_launcher_sets_gaming_environment_only_for_start():
    source = LAUNCHER.read_text(encoding="utf-8")
    assert 'if ($Action -ne "Start")' in source
    assert '"ATLAS_GAMING_MODE"' in source
    assert '"true"' in source
    assert "-Action Start" in source
    assert "-EncodedCommand $encodedScript" in source


def test_launcher_restores_previous_environment():
    source = LAUNCHER.read_text(encoding="utf-8")
    assert "finally {" in source
    assert "$priorGamingMode" in source


def test_launcher_uses_existing_manager():
    source = LAUNCHER.read_text(encoding="utf-8")
    assert 'Join-Path $PSScriptRoot "Atlas-Background.ps1"' in source
    assert "Start-Process" not in source
    assert "docker compose" not in source
    assert "-EncodedCommand $encodedScript" in source
    assert "$LASTEXITCODE -ne 0" in source
    assert '& $manager -Action $Action' in source


def test_manager_still_owns_lifecycle():
    source = MANAGER.read_text(encoding="utf-8")
    assert 'if ($Action -eq "Start")' in source
    assert 'if ($Action -eq "Stop")' in source
    assert 'if ($Action -eq "StopWorker")' in source
