"""Host-only time correction repair contract; never mutates W32Time in tests."""
import ctypes
import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/windows/Atlas-Windows-Time-Stabilize-Phase.ps1"
RECEIPT = ROOT / "logs/diagnostics/atlas-windows-time-phase-stability-20261108.json"


def script_text():
    assert SCRIPT.is_file()
    return SCRIPT.read_text(encoding="utf-8")


def invoke(*args):
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(SCRIPT), *args],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )


@pytest.mark.skipif(os.name != "nt", reason="real Windows host checks only")
def test_readonly_default_reports_phase_without_writes():
    value = invoke()
    assert value.returncode == 0, value.stderr
    assert "ATLAS_W32TIME_READ_ONLY_PHASE_CURRENT=" in value.stdout
    assert "ATLAS_W32TIME_DOCUMENTED_STANDALONE_DEFAULT_PHASE=7" in value.stdout
    assert "ATLAS_W32TIME_NO_MODIFICATION" in value.stdout
    assert "ATLAS_W32TIME_STANDALONE_PHASE_7_APPLIED_AND_NATIVE_READBACK_PASS" not in value.stdout


@pytest.mark.skipif(os.name != "nt", reason="real Windows host checks only")
def test_non_admin_invocation_fails_closed_without_registry_change():
    if ctypes.windll.shell32.IsUserAnAdmin():
        pytest.skip("never run a privileged mutation in a test runner")
    before = invoke()
    assert before.returncode == 0
    value = invoke("-ExecuteApproved")
    assert value.returncode != 0
    assert "ATLAS_W32TIME_ELEVATED_ADMIN_REQUIRED" in value.stderr
    assert "ATLAS_W32TIME_STANDALONE_PHASE_7_APPLIED_AND_NATIVE_READBACK_PASS" not in value.stdout
    after = invoke()
    assert after.returncode == 0 and after.stdout == before.stdout


def test_script_hardcodes_expected_nonfinancial_windows_scope():
    source = script_text()
    for exact in (
        "$trusted = 'time.cloudflare.com,0x8 time.google.com,0x8'",
        "MinPollInterval -ne 6",
        "MaxPollInterval -ne 6",
        "UpdateInterval -ne 360000",
        "MaxAllowedPhaseOffset -ne 1",
        "FrequencyCorrectRate -ne 4",
        "PhaseCorrectRate -notin @(1, 7)",
        "ATLAS_W32TIME_ELEVATED_ADMIN_REQUIRED",
        "ATLAS_W32TIME_PHASE_GROUP_POLICY_OVERRIDE_REFUSED",
        "ATLAS_W32TIME_DOMAIN_MANAGED_HOST_REFUSED",
        "Set-ItemProperty -LiteralPath $registry -Name PhaseCorrectRate -Value 7",
        "Set-ItemProperty -LiteralPath $registry -Name PhaseCorrectRate -Value $old",
        "ATLAS_W32TIME_EFFECTIVE_CONFIG_READBACK_REFUSED",
        "NOT_A_PROOF_OF_SUSTAINED_180_SECOND_CLOCK_QUALITY_OR_FINANCIAL_START",
    ):
        assert exact in source
    assert source.index("if (-not $ExecuteApproved)") < source.index(
        "Set-ItemProperty -LiteralPath $registry -Name PhaseCorrectRate -Value 7")
    assert "-Verb RunAs" not in source
    assert "Start-Service" not in source and "Restart-Service" not in source
    assert "& $w32tm /resync" not in source and "/manualpeerlist:" not in source
    assert "Set-Date" not in source and "SetSystemTime" not in source
    assert "Start-Atlas" not in source


def test_receipt_never_claims_financial_or_clock_lease_acceptance():
    source = script_text()
    assert "continuous_clock_180_seconds_accepted = $false" in source
    assert "financial_authority = $false" in source
    assert "atlas_code_installed = $false" in source
    assert "auto_start_atlas = $false" in source
    assert "FileMode]::CreateNew" in source
    assert str(RECEIPT.name) in source
