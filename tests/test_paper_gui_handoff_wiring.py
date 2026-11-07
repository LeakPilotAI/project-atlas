from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "scripts/windows/Atlas-Background-Controls.ps1"


def test_gui_opt_in_handoff_is_wired_to_all_three_stop_paths():
    source = GUI.read_text(encoding="utf-8-sig")
    assert "[object]$AcceptedPaperStopHandoff = $null" in source
    assert source.count("Invoke-AtlasPaperStopWithHandoff $AcceptedPaperStopHandoff $AcceptedPaperSession") == 3
    assert "Invoke-AtlasPaperStop $AcceptedPaperSession -RequireFinished" in source
    assert "Invoke-AtlasPaperStop $AcceptedPaperSession -Emergency" in source


def test_gui_emergency_refuses_normal_handoff_mode():
    source = GUI.read_text(encoding="utf-8-sig")
    assert "$AcceptedPaperStopHandoff['mode'] -cne 'EMERGENCY'" in source
    assert source.count("$AcceptedPaperStopHandoff['mode'] -cne 'SHUTDOWN_FLATTEN'") == 2
    assert "PAPER_STOP_HANDOFF_MODE_UNVERIFIED" in source


def test_gui_still_has_no_automatic_enrollment():
    source = GUI.read_text(encoding="utf-8-sig")
    assert "[object]$AcceptedPaperSession = $null" in source
    assert "[object]$AcceptedPaperStopHandoff = $null" in source
    assert "$startButton.Enabled = $false" in source



def test_keep_running_button_cannot_orphan_enrolled_paper_session():
    source = GUI.read_text(encoding="utf-8-sig")
    assert "if ($null -ne $AcceptedPaperSession) {" in source
    assert "PAPER session enrolled: closing requires verified flatten" in source
    assert "$script:KeepAtlasRunning = $false" in source
    assert "$script:KeepAtlasRunning = $true" in source
    assert "$form.Close()" in source



def test_form_closing_always_attempts_verified_shutdown_for_enrolled_session():
    source = GUI.read_text(encoding="utf-8-sig")
    section = source.split("$form.Add_FormClosing({", 1)[1].split("\n})", 1)[0]
    assert "if ($null -ne $AcceptedPaperSession) {" in section
    assert "-not $script:KeepAtlasRunning" not in section
    assert "Invoke-AtlasPaperStopWithHandoff" in section
    assert "Invoke-AtlasPaperStop $AcceptedPaperSession -RequireFinished" in section
    assert "$eventArgs.Cancel = $true" in section



def test_form_closing_never_releases_financial_session_on_failed_stop():
    source = GUI.read_text(encoding="utf-8-sig")
    section = source.split("$form.Add_FormClosing({", 1)[1].split("\n})", 1)[0]
    assert "$script:KeepAtlasRunning = $false" in section
    assert section.index("$script:KeepAtlasRunning = $false") < section.index("Invoke-AtlasPaperStopWithHandoff")
    assert section.index("Close-AtlasSelectedPaperDashboard") < section.index("} catch {")
    assert "$eventArgs.Cancel = $true" in section
