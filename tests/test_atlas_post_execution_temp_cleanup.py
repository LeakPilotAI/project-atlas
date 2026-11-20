"""Regression for narrow Atlas execution-end Windows C: Temp cleanup."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT / "scripts/windows/Atlas-Post-Execution-Temp-Cleanup.ps1"
STORAGE=ROOT / "docs/ATLAS_SINGLE_HOME_STORAGE_POLICY_2026-11-12.md"


def test_cleanup_explicit_optin_and_only_c_atlas_test_chrome_profiles():
    raw=SCRIPT.read_text(encoding="utf-8-sig")
    assert "param([switch]$ExecuteVerified)" in raw
    assert "^atlas-disposable-chrome-[a-z0-9_]{8}$" in raw
    assert "TotalMinutes -lt 5" in raw
    assert "ReparsePoint" in raw
    assert "Get-CimInstance Win32_Process" in raw
    assert "if ($ExecuteVerified)" in raw
    assert "Remove-Item -LiteralPath $target.FullName -Recurse -Force" in raw
    assert raw.count("Remove-Item") == 1
    assert "536870912" in raw
    assert "25000" in raw


def test_cleanup_never_targets_native_accounts_or_shared_python_caches():
    raw=SCRIPT.read_text(encoding="utf-8-sig")
    assert "CLEANUP_REFUSED_ACTIVE_PROFILES" in raw
    assert "ATLAS_SHARED_C_CACHES_AND_WINDOWS_OS_FILES_UNTOUCHED=True" in raw
    for forbidden in (
        "AtlasRuntime\\", "AtlasCustody\\", "AtlasPaper\\",
        "pip\\Cache", "PROJECT_ATLAS_MASTER_ROADMAP.txt",
        "git clean", "Get-ChildItem C:\\ -Recurse",
    ):
        assert forbidden not in raw


def test_main_policy_requires_end_of_every_execution_cleanup():
    text=STORAGE.read_text(encoding="utf-8-sig")
    assert "end of every future Atlas development/Commander execution" in text
    assert "Atlas-Post-Execution-Temp-Cleanup.ps1 -ExecuteVerified" in text
    assert "C:\\Windows" in text
    assert "If a cleanup check refuses" in text
