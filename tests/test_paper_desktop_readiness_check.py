import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/windows/atlas_paper_readiness_check.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("atlas_readiness", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readiness_checker_refuses_real_desktop_shortcuts():
    result = load_checker().inspect()
    assert result["decision"] == "NO_GO"
    assert result["paper_startup_authorized"] is False
    assert result["live_trading_authorized"] is False
    assert result["desktop"] == {
        "desktop_start": "BLOCKED_LEGACY", "desktop_stop": "BLOCKED_LEGACY"
    }


def test_readiness_checker_refuses_unrecognized_shortcut_and_missing_script(tmp_path):
    checker = load_checker()
    (tmp_path / "ATLAS.bat").write_text("echo fake startup", encoding="utf-8")
    (tmp_path / "ATLAS-STOP.bat").write_text("echo fake stop", encoding="utf-8")
    (tmp_path / "scripts/windows").mkdir(parents=True)
    (tmp_path / "scripts/windows/Atlas-Launch.ps1").write_text("Write-Host unsafe", encoding="utf-8")
    result = checker.inspect(tmp_path)
    assert result["decision"] == "NO_GO"
    assert result["desktop"] == {"desktop_start": "UNVERIFIED", "desktop_stop": "UNVERIFIED"}


def test_readiness_checker_cli_emits_machine_readable_no_go_and_nonzero_exit():
    run = subprocess.run([sys.executable, str(CHECKER)], capture_output=True, text=True, check=False)
    assert run.returncode == 2
    assert json.loads(run.stdout)["decision"] == "NO_GO"
    assert not run.stderr



def test_readiness_gate_matrix_is_explicit_and_never_promotes_from_shortcuts(tmp_path):
    checker = load_checker()
    (tmp_path / "scripts/windows").mkdir(parents=True)
    for _, batch_name, script_name in checker.CHECKS:
        (tmp_path / batch_name).write_text(script_name.replace("/", "\\"), encoding="utf-8")
        (tmp_path / script_name).write_text("Write-Host 'looks operational'", encoding="utf-8")
    result = checker.inspect(tmp_path)
    assert result["desktop"] == {"desktop_start": "UNVERIFIED", "desktop_stop": "UNVERIFIED"}
    assert result["unverified_gate_count"] == len(checker.ACCEPTANCE_GATES) == 9
    assert set(result["acceptance"]) == set(checker.ACCEPTANCE_GATES)
    assert all(value == "NOT_INDEPENDENTLY_VERIFIED" for value in result["acceptance"].values())
    assert result["decision"] == "NO_GO"
    assert result["paper_startup_authorized"] is False


def test_readiness_does_not_treat_comment_only_guard_as_active(tmp_path):
    checker = load_checker()
    (tmp_path / "scripts/windows").mkdir(parents=True)
    for _, batch_name, script_name in checker.CHECKS:
        (tmp_path / batch_name).write_text(script_name.replace("/", "\\"), encoding="utf-8")
        (tmp_path / script_name).write_text(
            "# ATLAS_LEGACY_LIFECYCLE_BLOCKED was removed\nWrite-Host 'unsafe placeholder'\n",
            encoding="utf-8")
    result = checker.inspect(tmp_path)
    assert result["desktop"] == {"desktop_start": "UNVERIFIED", "desktop_stop": "UNVERIFIED"}
    assert result["decision"] == "NO_GO"
