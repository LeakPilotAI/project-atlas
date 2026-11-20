"""Regression: observation-only desktop launcher never uses C for Atlas temp.

Only process-scoped cache control. The original fixed native financial roots are
not moved, symlinked, deleted or reinitialized through this helper.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/windows/Atlas-Use-Project-Storage.ps1"
START = ROOT / "scripts/windows/Atlas-Observation-Shortcut.ps1"
STOP = ROOT / "scripts/windows/Atlas-Observation-Shortcut-Stop.ps1"
POLICY = ROOT / "docs/ATLAS_SINGLE_HOME_STORAGE_POLICY_2026-11-12.md"


def test_single_project_home_is_explicit_and_reparse_points_refused():
    text = HELPER.read_text(encoding="utf-8-sig")
    assert "$atlasExpectedHome = 'D:\\Work\\Project Atlas'" in text
    assert "ATLAS_LOCAL_STORAGE_REQUIRES_EXACT_PROJECT_HOME_D_DRIVE" in text
    assert "ReparsePoint" in text
    assert "Join-Path $atlasActualHome 'logs'" in text
    assert "ATLAS_LOCAL_STORAGE_PATH_OUTSIDE_PROJECT_REFUSED" in text
    for key in ("TEMP", "TMP", "TMPDIR", "PIP_CACHE_DIR",
                "RUFF_CACHE_DIR", "XDG_CACHE_HOME", "PYTHONDONTWRITEBYTECODE"):
        assert f"$env:{key}" in text
    assert "SetEnvironmentVariable" not in text
    assert "Move-Item" not in text
    assert "Remove-Item" not in text
    assert "D:\\AtlasRuntime" not in text
    assert "D:\\AtlasCustody" not in text
    assert "D:\\AtlasPaper" not in text


def test_existing_desktop_launcher_applies_single_home_before_any_python():
    script = START.read_text(encoding="utf-8-sig")
    hook = '. (Join-Path $PSScriptRoot "Atlas-Use-Project-Storage.ps1") -ProjectRoot $root'
    assert script.count(hook) == 1
    assert script.index(hook) < script.index("$mutexName")
    assert script.index(hook) < script.index("backend\\.venv\\Scripts\\python.exe")
    assert "PAPER trading: DISABLED" in script
    assert "Production trading: DISABLED" in script


def test_stop_stays_observation_only_without_new_temp_dependencies():
    script = STOP.read_text(encoding="utf-8-sig")
    assert "AtlasObservationStop" in script
    assert "Atlas-Use-Project-Storage.ps1" not in script
    assert "TerminateProcess" not in script
    assert "Atlas-Observation-Shortcut-Stop.ps1" not in script


def test_explicit_canonical_layout_policy_retains_original_native_roots():
    doc = POLICY.read_text(encoding="utf-8-sig")
    assert "D:\\Work\\Project Atlas" in doc
    assert "D:\\AtlasRuntime" in doc
    assert "D:\\AtlasCustody" in doc
    assert "D:\\AtlasPaper" in doc
    assert "not complete" in doc
    assert "no" in doc.lower()
