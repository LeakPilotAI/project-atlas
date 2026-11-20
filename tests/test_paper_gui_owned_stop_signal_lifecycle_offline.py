"""Source contract for the opt-in Control Center owner/Stop event lifecycle.

No GUI, financial Atlas runtime, provider or browser listener is started.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "scripts/windows/Atlas-Background-Controls.ps1"
SIGNAL = ROOT / "scripts/windows/Atlas-Paper-Owned-Stop-Signal.psm1"


def source():
    return GUI.read_text(encoding="utf-8-sig")


def test_no_default_financial_owner_or_desktop_shortcut_auto_activation():
    s = source()
    assert "[object]$AcceptedPaperSession = $null" in s
    assert "$script:paperStopSignalOwner = $null" in s
    assert "if ($null -ne $AcceptedPaperSession) {" in s
    assert "New-AtlasAcceptedPaperStopSignalOwner -AcceptedSession $AcceptedPaperSession" in s
    assert s.index("if ($null -ne $AcceptedPaperSession) {") < s.index("New-AtlasAcceptedPaperStopSignalOwner")
    assert "Project Atlas.lnk" not in s and "Stop Atlas.lnk" not in s


def test_failed_owner_signal_setup_does_not_discard_accepted_gui_session():
    s = source()
    assert "$script:paperStopSignalError = $_.Exception.Message" in s
    section = s.split("New-AtlasAcceptedPaperStopSignalOwner -AcceptedSession $AcceptedPaperSession", 1)[1]
    assert "# Failure to install the desktop signal must not abandon" in section
    assert "PAPER Stop signal unavailable" in s


def test_gui_event_listener_is_nonblocking_and_dispatches_only_to_accepted_owner():
    s = source()
    timer = s.split("$timer.Add_Tick({", 1)[1].split("Invoke-AtlasBackgroundUiCallback { Poll-BackgroundManager }",1)[0]
    assert "Wait-AtlasOwnedPaperStopSignal -Ownership $script:paperStopSignalOwner -TimeoutMilliseconds 0" in timer
    assert "$script:paperStopSignalOwner.used -eq $false" in timer
    assert "$script:paperStopSignalVerifiedReceipt = $stopReceipt" in timer
    assert "Stop UNVERIFIED" in timer and "No automatic retry or forced kill" in timer
    assert "-TimeoutMilliseconds 30000" not in timer


def test_verified_signal_stop_is_not_sent_again_on_gui_form_closing():
    s = source()
    section = s.split("$form.Add_FormClosing({", 1)[1].split("\n})",1)[0]
    assert "$result = if ($null -ne $script:paperStopSignalVerifiedReceipt)" in section
    assert section.index("$script:paperStopSignalVerifiedReceipt") < section.index("Invoke-AtlasPaperStopWithHandoff")
    assert "$eventArgs.Cancel = $true" in section
    assert "Close-AtlasSelectedPaperDashboard" in section


def test_owner_event_cleanup_only_after_real_form_closed_not_cancelled():
    s = source()
    assert "$form.Add_FormClosed({" in s
    close = s.split("$form.Add_FormClosed({",1)[1].split("\n})",1)[0]
    assert "Close-AtlasPaperStopSignalOwner -Ownership $script:paperStopSignalOwner" in close
    assert "$script:paperStopSignalOwner = $null" in close
    assert s.index("$form.Add_FormClosed({") < s.index("[void]$form.ShowDialog()")


def test_signal_owner_requires_exact_usable_stop_and_durable_proof_methods():
    s = SIGNAL.read_text(encoding="utf-8-sig")
    for name in ("verify_session", "request_stop", "verify_durable_stop_receipt"):
        assert "-ccontains '" + name + "'" in s
    assert "PAPER_STOP_SIGNAL_OWNER_IDENTITY_CHANGED" in s
    assert "PAPER_STOP_SIGNAL_DURABLE_RECEIPT_UNVERIFIED" in s
    assert "REQUESTED_NOT_VERIFIED" in s


def test_future_desktop_stop_script_is_request_only_and_not_installed():
    script = (ROOT / "scripts/windows/Atlas-Paper-Stop-Request.ps1").read_text(encoding="utf-8-sig")
    assert "Request-AtlasPaperOwnedStopSignal" in script
    assert "REQUESTED_NOT_VERIFIED" in script
    assert "financial_flatness_verified -ne $false" in script
    assert "NOT YET CONFIRMED" in script
    assert "exit 1" in script
    for unsafe in ("Atlas-Stop.ps1", "Atlas-Launch.ps1", "Start-Process",
                   "Invoke-RestMethod", "control_token", "docker stop", "taskkill"):
        assert unsafe not in script


def test_desktop_observation_shortcuts_are_not_repointed_by_paper_owner_code():
    signal = SIGNAL.read_text(encoding="utf-8-sig")
    gui = source()
    for unsafe in ("CreateShortcut", "Install-DesktopShortcut.ps1",
                   "Stop Atlas.lnk", "Start Atlas.lnk", "ATLAS-STOP.bat"):
        assert unsafe not in signal
        assert unsafe not in gui
