"""Fail-closed offline checks: never modify W32Time during testing."""

import ctypes
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/windows/Atlas-V4-Windows-Time-Poll-Cap.ps1"


def invoke(*args):
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(SCRIPT), *args],
        capture_output=True, text=True, timeout=15, check=False,
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows only")
def test_unapproved_administrator_change_refuses_before_any_native_action():
    result = invoke()
    assert result.returncode != 0
    assert "ATLAS_V4_POLL_CAP_SEPARATE_OPERATOR_APPROVAL_REQUIRED" in result.stderr
    assert "MAXPOLL_6_REQUESTED" not in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows only")
def test_approved_but_unelevated_refuses_before_any_native_action():
    if ctypes.windll.shell32.IsUserAnAdmin():
        pytest.skip("Do not execute approved host changes during tests")
    result = invoke("-ExecuteApproved")
    assert result.returncode != 0
    assert "ATLAS_V4_POLL_CAP_ELEVATED_ADMIN_REQUIRED" in result.stderr
    assert "MAXPOLL_6_REQUESTED" not in result.stdout


def test_exact_w32time_only_existing_peers_and_microsoft_signature():
    s = SCRIPT.read_text(encoding="utf-8-sig")
    assert "time.cloudflare.com,0x8 time.google.com,0x8" in s
    assert "[Security.Principal.WindowsBuiltInRole]::Administrator" in s
    assert "Get-AuthenticodeSignature -LiteralPath $systemW32tm" in s
    assert "if (-not $ExecuteApproved)" in s
    assert "ATLAS_V4_POLL_CAP_GROUP_POLICY_OVERRIDE_REFUSED" in s
    assert "ATLAS_V4_POLL_CAP_NATIVE_SETTINGS_CHANGED" in s
    assert "if ($previous -eq 6)" in s
    assert s.index("if (-not $ExecuteApproved)") < s.index("Set-ItemProperty")
    assert s.index("IsInRole(") < s.index("Set-ItemProperty")
    assert s.count("Set-ItemProperty -LiteralPath $config -Name 'MaxPollInterval'") == 2
    assert "Set-ItemProperty -LiteralPath $config -Name 'MaxPollInterval' -Value 6" in s
    assert "Set-ItemProperty -LiteralPath $config -Name 'MaxPollInterval' -Value $previous" in s
    assert "& $systemW32tm '/config' '/update'" in s


def test_no_unattended_elevation_restart_resync_or_atlas_mutation():
    s = SCRIPT.read_text(encoding="utf-8-sig")
    for forbidden in (
        "-Verb RunAs", "Start-Process", "Restart-Service", "Stop-Service",
        "Set-Service", "w32tm.exe /resync", "'/resync'", "'/rediscover'",
        "Set-ItemProperty -LiteralPath $ntp", "paper_startup", "--execute-approved-unselected",
        "Atlas-Launch", "Install-DesktopShortcut", "taskkill", "MaxAllowedPhaseOffset",
        "LocalClockDispersion", "CLOCK_UNCERTAINTY_EXCEEDED", "MAX_AGE =",
    ):
        assert forbidden not in s
    assert "ATLAS_V4_WINDOWS_TIME_MAXPOLL_6_REQUESTED_CONFIG_READBACK_PASS" in s
    assert "NOT_INSTALL_AUTHORIZATION" in s


def test_preflight_reuses_exact_same_native_lease_for_full_copy_horizon():
    source = (ROOT / "scripts/observation_runtime/atlas_v4_installer_clock_lease_preflight.py").read_text()
    assert "PREFLIGHT_SECONDS = 180" in source
    assert "INTERVAL_SECONDS = 5" in source
    assert "clock.require_operational(RUNTIME_ID)" in source
    assert "clock.revoke()" in source
    assert '"installer_ran": False' in source
