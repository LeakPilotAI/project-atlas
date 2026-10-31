"""Initial non-runtime gaming-profile safety contract for Atlas."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "backend/app/core/config.py"
MAIN = ROOT / "backend/app/main.py"
MANAGER = ROOT / "scripts/windows/Atlas-Background.ps1"


def test_paper_management_remains_independently_configured():
    source = CONFIG.read_text(encoding="utf-8")
    assert "perp_micro_manage_seconds: float = 8.0" in source
    assert "perp_micro_scan_seconds: float = 60.0" in source


def test_runtime_configuration_validation_precedes_dependencies():
    source = MAIN.read_text(encoding="utf-8")
    assert "settings.validate_runtime_configuration()" in source
    assert source.index(
        "settings.validate_runtime_configuration()"
    ) < source.index("await get_redis_client()")


def test_background_manager_remains_manual():
    source = MANAGER.read_text(encoding="utf-8")
    assert '[ValidateSet("Start", "Status", "Stop", "Worker", "StopWorker")]' in source
    assert 'if ($Action -eq "Start")' in source
    assert 'if ($Action -eq "Stop")' in source


def test_manager_preserves_graceful_shutdown():
    source = MANAGER.read_text(encoding="utf-8")
    assert '"--timeout-graceful-shutdown", "20"' in source
    assert 'if ($Action -eq "StopWorker")' in source


def test_gaming_profile_not_implicitly_enabled():
    source = CONFIG.read_text(encoding="utf-8")
    if "atlas_gaming_mode:" in source:
        assert "atlas_gaming_mode: bool = False" in source