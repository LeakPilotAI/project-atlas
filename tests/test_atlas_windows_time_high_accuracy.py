"""Offline/host-readonly verification for the bounded Microsoft time profile."""
import ctypes
import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/windows/Atlas-Windows-Time-High-Accuracy.ps1"


def script():
    return SCRIPT.read_text(encoding="utf-8")


def process(*args):
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(SCRIPT), *args],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )


@pytest.mark.skipif(os.name != "nt", reason="requires actual Windows registry read")
def test_preview_no_mutation():
    response = process()
    assert response.returncode == 0, response.stderr
    assert "ATLAS_TIME_HA_READONLY_UPDATE_INTERVAL=" in response.stdout
    assert "ATLAS_TIME_HA_DOCUMENTED_PROFILE_UPDATE=100_FREQUENCY=2" in response.stdout
    assert "ATLAS_TIME_HA_NO_OS_MODIFICATION" in response.stdout
    assert "ATLAS_TIME_HA_MICROSOFT_PROFILE_APPLIED" not in response.stdout


@pytest.mark.skipif(os.name != "nt", reason="requires actual non-admin Windows token")
def test_normal_user_refused_before_mutation():
    if ctypes.windll.shell32.IsUserAnAdmin():
        pytest.skip("avoid running any mutation under elevated test runner")
    before = process()
    assert before.returncode == 0
    attempted = process("-ExecuteApproved")
    assert attempted.returncode != 0
    assert "ATLAS_TIME_HA_ELEVATED_ADMIN_REQUIRED" in attempted.stderr
    assert process().stdout == before.stdout


def test_exact_host_profile_and_fail_closed_invariants():
    s = script()
    for evidence in (
        "PhaseCorrectRate -ne 7",
        "MinPollInterval -ne 6",
        "MaxPollInterval -ne 6",
        "MaxAllowedPhaseOffset -ne 1",
        "ATLAS_TIME_HA_STANDALONE_HOST_REQUIRED",
        "ATLAS_TIME_HA_GROUP_POLICY_OVERRIDE_REFUSED",
        "ATLAS_TIME_HA_UNREVIEWED_UPDATE_FREQUENCY_PAIR_REFUSED",
        "ATLAS_TIME_HA_PRIOR_PHASE_FIX_EVIDENCE_CHANGED",
        "ATLAS_TIME_HA_ELEVATED_ADMIN_REQUIRED",
        "Set-ItemProperty -LiteralPath $cfgPath -Name UpdateInterval -Value 100",
        "Set-ItemProperty -LiteralPath $cfgPath -Name FrequencyCorrectRate -Value 2",
        "Set-ItemProperty -LiteralPath $cfgPath -Name UpdateInterval -Value $state.UpdateInterval",
        "Set-ItemProperty -LiteralPath $cfgPath -Name FrequencyCorrectRate -Value $state.FrequencyCorrectRate",
        "ATLAS_TIME_HA_EFFECTIVE_W32TIME_CONFIG_REFUSED",
        "ATLAS_TIME_HA_ROLLBACK_UNVERIFIED_ADMIN_ATTENTION_REQUIRED",
    ):
        assert evidence in s
    assert s.index("if(-not $ExecuteApproved)") < s.index(
        "Set-ItemProperty -LiteralPath $cfgPath -Name UpdateInterval -Value 100")
    assert "Start-Atlas" not in s
    assert "& $w32tm /resync" not in s
    assert "/manualpeerlist" not in s
    assert "Restart-Service" not in s and "Set-Date" not in s
    assert "Start-Process" not in s


def test_durable_receipt_explicitly_denies_financial_auth():
    s = script()
    assert "atlas_180_second_clock_lease_passed=$false" in s
    assert "atlas_code_install_performed=$false" in s
    assert "financial_authority=$false" in s
    assert "atlas_autostart=$false" in s
    assert "FileMode]::CreateNew" in s
    assert "1c67ef71c2f64ef3db0386fd30335fed84c60272023be49fb649cc2da49425df" in s
