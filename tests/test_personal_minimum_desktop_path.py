"""Static runtime dependency/close wiring; no host,job or financial execution."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_does_not_depend_on_native_compatibility_harness():
    forbidden = {"personal_native_compatibility_run", "personal_native_job", "personal_native_windows_api", "personal_native_compatibility_fixture"}
    paths = list((ROOT / "backend/app").rglob("*.py"))
    paths += [ROOT / "scripts/observation_runtime/quality_dips_windows_bridge.py"]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node,ast.Import):names=[n.name for n in node.names]
            elif isinstance(node,ast.ImportFrom):names=[node.module or ""]
            assert not any(set(name.split(".")) & forbidden for name in names),path


def test_form_close_requires_finished_shutdown_and_keeps_cancel_handler():
    text=(ROOT / "scripts/windows/Atlas-Background-Controls.ps1").read_text(encoding="utf-8-sig")
    close=text.split("$form.Add_FormClosing",1)[1].split("function Set-StatusMessage",1)[0]
    assert "Invoke-AtlasPaperStop $AcceptedPaperSession -RequireFinished" in close
    assert "$eventArgs.Cancel = $true" in close
    assert close.index("Invoke-AtlasPaperStop") < close.index("Close-AtlasSelectedPaperDashboard")
