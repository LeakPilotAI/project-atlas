from pathlib import Path

SCRIPT = Path("scripts/windows/Pull-And-Ready.ps1")

def _text():
    return SCRIPT.read_text(encoding="utf-8")

def test_e121_update_targets_intended_atlas_branch():
    text = _text()
    assert '$ExpectedBranch = "chatgpt/atlas-rebuild-v1"' in text
    assert '$branch -ne $ExpectedBranch' in text
    assert '"origin/$ExpectedBranch"' in text

def test_e121_update_refuses_tracked_local_modifications():
    text = _text()
    assert "git status --porcelain --untracked-files=no" in text
    assert "tracked local modifications are present" in text

def test_e121_update_is_fast_forward_only():
    text = _text()
    assert "git merge --ff-only $remoteRef" in text
    assert "Local history diverged" in text

def test_e121_update_has_no_destructive_git_cleanup():
    text = _text().lower()
    assert "git reset --hard" not in text
    assert "git clean" not in text
    assert "git checkout -f" not in text

def test_e121_update_does_not_force_stop_global_python_or_node():
    text = _text()
    assert "Get-Process python, node" not in text
    assert "Stop-Process -Force" not in text

def test_e121_untracked_diagnostics_are_explicitly_preserved():
    text = _text()
    assert "--untracked-files=no" in text
    assert "untracked diagnostics were left in place" in text
