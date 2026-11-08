"""Offline-only guards for the administrator-scoped V4 Windows Time qualification.

Never run the approved command on an elevated account in a test; the accepted
path can contact only the existing Windows Time service and trusted NTP peers.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/windows/Atlas-V4-Windows-Time-Qualification.ps1"


def ps(*args):
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(SCRIPT), *args],
        capture_output=True, text=True, timeout=20, check=False,
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows service-only qualification")
def test_unapproved_invocation_refuses_before_any_windows_time_action():
    result = ps()
    assert result.returncode != 0
    assert "ATLAS_V4_TIME_MAINTENANCE_EXPLICIT_APPROVAL_REQUIRED" in result.stderr
    assert "ATLAS_V4_CLOCK_QUALITY_SAMPLE" not in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows service-only qualification")
def test_explicit_approval_cannot_run_from_standard_user():
    import ctypes

    if ctypes.windll.shell32.IsUserAnAdmin():
        pytest.skip("Do not perform real Windows service resync in elevated tests")
    result = ps("-ExecuteApproved")
    assert result.returncode != 0
    assert "ATLAS_V4_TIME_MAINTENANCE_ELEVATED_ADMIN_REQUIRED" in result.stderr
    assert "ATLAS_V4_CLOCK_QUALITY_SAMPLE" not in result.stdout


def test_clock_maintenance_never_mutates_trusted_peers_or_atlas_installation():
    s = SCRIPT.read_text(encoding="utf-8-sig")
    assert "if (-not $ExecuteApproved)" in s
    assert "IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)" in s
    assert s.index("if (-not $ExecuteApproved)") < s.index("& $w32tm '/resync' '/rediscover'")
    assert s.index("IsInRole(") < s.index("& $w32tm '/resync' '/rediscover'")
    assert "time.cloudflare.com,0x8 time.google.com,0x8" in s
    assert "Get-AuthenticodeSignature -LiteralPath $w32tm" in s
    assert "LocalWindowsClock(expected_source=" in s
    for forbidden in ("Set-ItemProperty", "New-ItemProperty", "Set-Service", "sc.exe",
                      "schtasks", "Install-DesktopShortcut", "--execute-approved-unselected",
                      "Atlas-Launch.ps1", "Atlas-Stop.ps1", "taskkill", "Stop-Process",
                      "Start-Process", "-Verb RunAs", "MaxAge =", "MAX_AGE ="):
        assert forbidden not in s


def test_clock_maintenance_is_bounded_and_has_no_unattended_privilege_elevation():
    s = SCRIPT.read_text(encoding="utf-8-sig")
    assert "[ValidateRange(5, 10)][int]$Samples = 6" in s
    assert "[ValidateRange(30, 60)][int]$IntervalSeconds = 40" in s
    assert "for ($index = 0; $index -lt $Samples; $index++)" in s
    assert "ATLAS_V4_TIME_SOURCE_OR_SERVICE_CHANGED" in s
    assert "ATLAS_V4_TIME_SERVICE_RESYNC_REFUSED" in s
    assert "ATLAS_V4_TIME_NATIVE_QUALITY_REFUSED" in s
    assert "NO_INSTALL_PERFORMED" in s


def test_existing_installer_clock_authority_not_replaced_by_maintenance_script():
    installer = (ROOT / "scripts/install_verified_release.py").read_text(encoding="utf-8-sig")
    assert "clock=LocalWindowsClock(expected_source=clock_source" in installer
    assert "clock.require_operational(runtime)" in installer
    assert "SEPARATE_CODE_INSTALL_AUTHORIZATION_REQUIRED" in installer
    assert "Atlas-V4-Windows-Time-Qualification" not in installer
