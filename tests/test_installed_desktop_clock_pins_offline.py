"""Offline source contract only: never starts a Windows runtime or contacts a provider."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = 'expected_source="time.cloudflare.com,0x8 time.google.com,0x8"'
OBSOLETE = 'expected_source="time.windows.com,0x9"'


def test_selected_nonfinancial_entry_binds_current_reviewed_ntp_roster():
    source = (ROOT / "scripts/installed_nonfinancial_launcher.py").read_text(encoding="utf-8")
    assert source.count(EXPECTED) == 1
    assert OBSOLETE not in source
    assert 'INSTALLED_ENTRY_REQUIRED_NO_WORKSPACE_FALLBACK' in source


def test_support_deployment_selection_uses_same_explicit_ntp_roster():
    source = (ROOT / "scripts/support_deployment.py").read_text(encoding="utf-8")
    assert source.count(EXPECTED) == 1
    assert OBSOLETE not in source
    assert 'EXACT_REVIEWED_SELECTION_INVOCATION_REQUIRED' in source
