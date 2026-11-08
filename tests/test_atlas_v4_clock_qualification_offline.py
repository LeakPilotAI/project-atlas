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
    assert "& $python -B -m scripts.observation_runtime.atlas_v4_time_quality_probe" in s
    assert "& $python -B -c" not in s
    assert "$qualityScript" not in s
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


def test_qualified_clock_python_module_preserves_genuine_authority_and_revokes(monkeypatch, capsys):
    from scripts.observation_runtime import atlas_v4_time_quality_probe as probe

    observed = []

    class SyntheticClock:
        def __init__(self, *, expected_source, runtime_id, lifetime):
            observed.append((expected_source, runtime_id, lifetime))
            self.evidence = {"bound_ms": 175}

        def require_operational(self, runtime_id):
            observed.append(("require_operational", runtime_id))

        def revoke(self):
            observed.append(("revoke",))

    monkeypatch.setattr(probe, "LocalWindowsClock", SyntheticClock)
    probe.main()
    assert observed == [
        (probe.EXPECTED_PEERS, probe.RUNTIME_ID, 240),
        ("require_operational", probe.RUNTIME_ID),
        ("revoke",),
    ]
    assert capsys.readouterr().out.strip() == "NATIVE_CLOCK_QUALITY_ACCEPTED:175ms"


def test_qualified_clock_python_module_revokes_even_on_quality_refusal(monkeypatch):
    from scripts.observation_runtime import atlas_v4_time_quality_probe as probe

    closed = []

    class RefusingClock:
        def __init__(self, **kwargs):
            pass

        def require_operational(self, runtime_id):
            raise ValueError("OFFLINE_SIMULATED_CLOCK_REFUSAL")

        def revoke(self):
            closed.append(True)

    monkeypatch.setattr(probe, "LocalWindowsClock", RefusingClock)
    with pytest.raises(ValueError, match="OFFLINE_SIMULATED_CLOCK_REFUSAL"):
        probe.main()
    assert closed == [True]


def test_qualification_probe_is_read_only_and_never_mutates_time_or_installs():
    s = (ROOT / "scripts/observation_runtime/atlas_v4_time_quality_probe.py").read_text(encoding="utf-8-sig")
    assert 'from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock' in s
    assert "clock.require_operational(RUNTIME_ID)" in s
    assert "clock.revoke()" in s
    assert "time.cloudflare.com,0x8 time.google.com,0x8" in s
    for forbidden in ("subprocess.run", "w32tm", "Set-ItemProperty", "install_verified_release",
                      "PAPER_START", "--execute-approved-unselected", "os.system", "Start-Process"):
        assert forbidden not in s
