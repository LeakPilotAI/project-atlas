"""Offline regression for legacy desktop shortcut entrypoints; no launch."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_desktop_start_never_cascades_into_stop():
    batch = (ROOT / 'ATLAS.bat').read_text(encoding='utf-8')
    active = [line.strip().lower() for line in batch.splitlines()
              if line.strip() and not line.lstrip().lower().startswith(('rem ', '::'))]
    assert sum('atlas-launch.ps1' in line for line in active) == 1
    assert not any('atlas-stop.ps1' in line or 'atlas-stop.bat' in line for line in active)
    assert any('exit /b %atlas_launch_exit%' in line for line in active)
    assert any('set "atlas_launch_exit=%errorlevel%"' in line for line in active)


def test_legacy_start_and_stop_scripts_remain_fenced():
    start = (ROOT / 'scripts/windows/Atlas-Launch.ps1').read_text(encoding='utf-8')
    stop = (ROOT / 'scripts/windows/Atlas-Stop.ps1').read_text(encoding='utf-8')
    assert 'ATLAS_LEGACY_LIFECYCLE_BLOCKED' in start
    assert 'ATLAS_LEGACY_LIFECYCLE_BLOCKED' in stop
    assert start.index('ATLAS_LEGACY_LIFECYCLE_BLOCKED') < start.index('Set-Location $Root')
    assert stop.index('ATLAS_LEGACY_LIFECYCLE_BLOCKED') < stop.index('function Stop-Tree')


def test_stop_shortcut_does_not_claim_success_after_refusal():
    batch = (ROOT / 'ATLAS-STOP.bat').read_text(encoding='utf-8').lower()
    assert 'if errorlevel 1' in batch
    assert 'shutdown was not confirmed' in batch
    assert 'exit /b 1' in batch