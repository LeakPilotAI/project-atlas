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
    assert s.index("if (-not $ExecuteApproved)") < s.index("& $python -B -m")
    assert s.index("IsInRole(") < s.index("& $python -B -m")
    # Repeated forced rediscovery discards filter/error history. The
    # qualification must NOT alter time, even in an authorized admin shell.
    assert "& $w32tm '/resync' '/rediscover'" not in s
    assert "& $w32tm '/resync'" not in s
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
    assert "[ValidateRange(3, 12)][int]$StabilizationChecks = 10" in s
    assert "[ValidateRange(10, 60)][int]$StabilizationIntervalSeconds = 30" in s
    assert "for ($check = 1; $check -le $StabilizationChecks; $check++)" in s
    assert "for ($index = 2; $index -le $Samples; $index++)" in s
    assert "if ($quality.Accepted -ne $true)" in s
    assert "ATLAS_V4_TIME_SOURCE_OR_SERVICE_CHANGED" in s
    assert "ATLAS_V4_TIME_STABILIZATION_FAILED" in s
    assert "ATLAS_V4_TIME_SUSTAINED_QUALITY_FAILED" in s
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


def test_qualification_refuses_unknown_clock_failures_during_stabilization():
    s = SCRIPT.read_text(encoding="utf-8-sig")
    assert "if ($nativeExit -eq 0)" in s
    assert "^NATIVE_CLOCK_QUALITY_ACCEPTED:[0-9]+ms$" in s
    assert "NATIVE_CLOCK_QUALITY_REFUSED:CLOCK_UNCERTAINTY_EXCEEDED" in s
    assert "NATIVE_CLOCK_QUALITY_REFUSED:CLOCK_STALE_OR_NEGATIVE_QUALITY" in s
    assert "if ($check -eq $StabilizationChecks)" in s
    assert "throw ('ATLAS_V4_TIME_NATIVE_QUALITY_REFUSED:'" in s
    assert "Start-Sleep -Seconds $StabilizationIntervalSeconds" in s
    assert "Start-Sleep -Seconds $IntervalSeconds" in s


def test_quality_warmup_never_counts_as_a_sustained_pass():
    s = SCRIPT.read_text(encoding="utf-8-sig")
    assert s.index("$qualified = $null") < s.index("ATLAS_V4_CLOCK_QUALITY_SAMPLE=1/")
    assert s.index("ATLAS_V4_CLOCK_QUALITY_SAMPLE=1/") < s.index("for ($index = 2;")
    assert "if ($quality.Accepted -ne $true)" in s
    assert "throw ('ATLAS_V4_TIME_SUSTAINED_QUALITY_FAILED:'" in s
    assert "ATLAS_V4_CLOCK_WINDOW_AND_SINGLE_LEASE_QUALIFIED_NO_INSTALL_PERFORMED" in s
    assert "& $python -B -m scripts.observation_runtime.atlas_v4_installer_clock_lease_preflight" in s
    assert "ATLAS_V4_TIME_PERSISTENT_LEASE_REFUSED" in s
    assert "ATLAS_V4_TIME_PERSISTENT_LEASE_OUTPUT_UNVERIFIED" in s


@pytest.mark.skipif(os.name != "nt", reason="PowerShell 5.1 native invocation contract")
@pytest.mark.parametrize("mode,accepted,reason", [
    ("pass", True, "NATIVE_CLOCK_QUALITY_ACCEPTED:493ms"),
    ("transient", False, "NATIVE_CLOCK_QUALITY_REFUSED:CLOCK_UNCERTAINTY_EXCEEDED:7977ms"),
    ("stale", False, "NATIVE_CLOCK_QUALITY_REFUSED:CLOCK_STALE_OR_NEGATIVE_QUALITY"),
    ("unrecognized", None, "ATLAS_V4_TIME_NATIVE_QUALITY_REFUSED"),
    ("forged_success", None, "ATLAS_V4_TIME_NATIVE_QUALITY_REFUSED"),
    ("wrong_success", None, "ATLAS_V4_TIME_NATIVE_QUALITY_OUTPUT_UNVERIFIED"),
])
def test_native_quality_classifier_is_fail_closed_without_contacting_ntp(mode, accepted, reason):
    import base64

    script = SCRIPT.read_text(encoding="utf-8-sig")
    contract = ("    function Test-AtlasGenuineClockQuality {" + script.split(
        "    function Test-AtlasGenuineClockQuality {", 1)[1].split(
            "    # A bounded warmup", 1)[0])
    response = {
        "pass": "  $global:LASTEXITCODE=0;Write-Output 'NATIVE_CLOCK_QUALITY_ACCEPTED:493ms'",
        "transient": "  $global:LASTEXITCODE=1;Write-Error 'NATIVE_CLOCK_QUALITY_REFUSED:CLOCK_UNCERTAINTY_EXCEEDED:7977ms'",
        "stale": "  $global:LASTEXITCODE=1;Write-Error 'NATIVE_CLOCK_QUALITY_REFUSED:CLOCK_STALE_OR_NEGATIVE_QUALITY'",
        "unrecognized": "  $global:LASTEXITCODE=1;Write-Error 'SYNTHETIC_UNEXPECTED_PROCESS_ERROR'",
        "forged_success": "  $global:LASTEXITCODE=1;Write-Output 'NATIVE_CLOCK_QUALITY_ACCEPTED:493ms'",
        "wrong_success": "  $global:LASTEXITCODE=0;Write-Output 'NOT_AN_ATLAS_CLOCK_QUALITY_RESULT'",
    }[mode]
    # Evaluate only the exact classifier with inert process mocks. Do not
    # execute the admin-gated qualification or touch the Windows Time service.
    powershell = ("$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'\n"
                  "$python='OfflineFakePython'\n"
                  "function Assert-AtlasTrustedTimeSource {}\n"
                  "function OfflineFakePython { " + response + " }\n"
                  + contract + "\n$q=Test-AtlasGenuineClockQuality;"
                  "Write-Output ('ACCEPTED='+$q.Accepted+';REASON='+$q.Reason)\n")
    process = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand",
         base64.b64encode(powershell.encode("utf-16le")).decode("ascii")],
        capture_output=True, text=True, timeout=16, check=False,
    )
    if accepted is None:
        assert process.returncode != 0
        assert reason in process.stderr
    else:
        assert process.returncode == 0, process.stderr
        assert f"ACCEPTED={str(accepted)};REASON={reason}" in process.stdout


def test_independent_npt_samples_cannot_claim_code_install_without_a_single_lease():
    s = SCRIPT.read_text(encoding="utf-8-sig")
    assert s.index("for ($index = 2; $index -le $Samples; $index++)") < s.index(
        "& $python -B -m scripts.observation_runtime.atlas_v4_installer_clock_lease_preflight")
    assert s.index("ATLAS_V4_TIME_PERSISTENT_LEASE_REFUSED") < s.index(
        "ATLAS_V4_CLOCK_WINDOW_AND_SINGLE_LEASE_QUALIFIED_NO_INSTALL_PERFORMED")
    assert "CONTINUOUS_NATIVE_LEASE_PREFLIGHT_PASSED_NOT_INSTALLATION_AUTHORITY" in s
    assert "ATLAS_V4_INSTALL_CLOCK_PREFLIGHT_SAMPLES=[0-9]+" in s
    assert "ATLAS_V4_CLOCK_WINDOW_SAMPLED_WITH_TRUSTED_NTP_NO_INSTALL_PERFORMED" not in s
