"""Regression guards for the manually operated Atlas background GUI.

These tests inspect source only. They never launch Atlas or its manager.
"""

import re
from pathlib import Path

CONTROLS = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "windows"
    / "Atlas-Background-Controls.ps1"
)


def source():
    return CONTROLS.read_text(encoding="utf-8-sig")


def test_initial_window_is_fail_closed():
    text = source()

    assert '$status.Text = "Status not checked - click Atlas Status."' in text

    expected = (
        ("startButton", "false"),
        ("statusButton", "true"),
        ("stopButton", "false"),
    )

    for button, state in expected:
        pattern = (
            rf"\${button}\.Size\s*=\s*"
            rf"New-Object System\.Drawing\.Size\(445,\s*34\)"
            rf"\s*\${button}\.Enabled\s*=\s*\${state}"
            rf"\s*\$form\.Controls\.Add\(\${button}\)"
        )
        assert re.search(pattern, text), button


def test_no_automatic_status_scheduling():
    text = source()

    for forbidden in (
        "$script:refreshStatus",
        "$script:nextStatusCheck",
        "$form.Add_Shown",
    ):
        assert forbidden not in text, forbidden

    assert text.count('Start-BackgroundManager "Status"') == 1


def test_status_is_explicitly_user_triggered():
    text = source()

    pattern = (
        r"\$statusButton\.Add_Click\(\{\s*"
        r"Invoke-AtlasBackgroundUiCallback\s*\{\s*"
        r'Start-BackgroundManager\s+"Status"'
    )

    assert re.search(pattern, text)


def test_lifecycle_actions_remain_explicit():
    text = source()

    for button, action in (
        ("startButton", "Start"),
    ):
        assert text.count(f'Start-BackgroundManager "{action}"') == 1

        pattern = (
            rf"\${button}\.Add_Click\(\{{\s*"
            rf"Invoke-AtlasBackgroundUiCallback\s*\{{\s*"
            rf'Start-BackgroundManager\s+"{action}"'
        )

        assert re.search(pattern, text), action

    stop = text.split('$stopButton.Add_Click({', 1)[1].split('$runtimeSummary', 1)[0]
    assert 'Invoke-AtlasPaperStop $AcceptedPaperSession' in stop
    assert 'Start-BackgroundManager' not in stop
    assert 'Invoke-AtlasPaperStop $AcceptedPaperSession -Emergency' in text


def test_idle_timer_does_not_launch_status():
    text = source()

    pattern = (
        r"function\s+Poll-BackgroundManager\s*\{\s*"
        r"if\s*\(-not\s+\$script:activeManager\)\s*\{\s*"
        r"return\s*\}"
    )

    assert re.search(pattern, text)
    assert "$timer.Interval = 250" in text
    assert "Poll-BackgroundManager" in text


def test_lifecycle_completion_requires_manual_recheck():
    text = source()

    pattern = (
        r"if\s*\(\$active\.action\s+-eq\s+"
        r'"Status"\)\s*\{\s*'
        r"Apply-AtlasStatus\s+\$result\s*\}\s*else\s*\{"
        r".*?"
        r"\$startButton\.Enabled\s*=\s*\$false"
        r"\s*\$stopButton\.Enabled\s*=\s*\$false"
        r"\s*\$statusButton\.Enabled\s*=\s*\$true"
    )

    assert re.search(pattern, text, re.DOTALL)


def test_manager_actions_are_not_triggered_on_form_show():
    text = source()

    assert not re.search(
        r"\$form\.Add_(?:Shown|Load|Activated)\s*\(",
        text,
        re.IGNORECASE,
    )