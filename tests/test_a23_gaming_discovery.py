"""Gaming discovery cadence must not affect paper management."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MICRO = ROOT / "backend/app/services/perp_micro_coach.py"
CONFIG = ROOT / "backend/app/core/config.py"


def test_discovery_uses_gaming_aware_interval():
    source = MICRO.read_text(encoding="utf-8")
    assert (
        "await asyncio.sleep(float("
        "settings.effective_perp_micro_scan_seconds or 90))"
    ) in source


def test_paper_management_keeps_independent_interval():
    source = MICRO.read_text(encoding="utf-8")
    assert (
        'await asyncio.sleep(float(getattr(settings, '
        '"perp_micro_manage_seconds", 8.0) or 8.0))'
    ) in source


def test_gaming_mode_is_opt_in():
    source = CONFIG.read_text(encoding="utf-8")
    assert "atlas_gaming_mode: bool = False" in source
    assert "return max(float(self.perp_micro_scan_seconds), 180.0)" in source