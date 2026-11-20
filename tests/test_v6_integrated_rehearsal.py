"""Preparation/fixture boundaries; no installed runtime or browser launch."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "name", ["v6_integrated_rehearsal_worker.py", "v6_rehearsal_gate.py"]
)
def test_fixture_entries_refuse_default_invocation(name):
    p = subprocess.run(
        [sys.executable, "-I", "-B", str(REPO / "tests" / name)],
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert p.returncode != 0 and b"DISPOSABLE" in p.stderr


@pytest.mark.parametrize("fault", [None, "domain", "installed_image", "hash", "source"])
def test_disposable_static_gate_cannot_be_operational_authority(tmp_path, fault):
    root = tmp_path / "qd-v6-integrated-rehearsal-unit"
    root.mkdir()
    gate = root / "gate.py"
    gate.write_bytes((REPO / "tests/v6_rehearsal_gate.py").read_bytes())
    file = root / "synthetic-source.txt"
    file.write_bytes(b"source only")
    scope = {
        "domain": "DISPOSABLE_INTEGRATED_ONLY",
        "ownership": {"images": {"observer": {"path": str(file)}}},
    }
    if fault == "domain":
        scope["domain"] = "OPERATIONAL"
    if fault == "installed_image":
        scope["ownership"]["images"]["observer"]["path"] = (
            r"D:\AtlasRuntime\releases\unauthorized\python.exe"
        )
    (root / "fixture-scope.json").write_text(json.dumps(scope))
    (root / "fixture-source-manifest.json").write_text(
        json.dumps(
            [
                {
                    "path": str(file),
                    "bytes": 11,
                    "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                }
            ]
        )
    )
    digest = hashlib.sha256(
        json.dumps(scope, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if fault == "hash":
        digest = "0" * 64
    if fault == "source":
        file.write_bytes(b"changed")
    p = subprocess.run(
        [sys.executable, "-I", "-B", str(gate), "--verify-only", digest, "f" * 40],
        capture_output=True,
        timeout=5,
        check=False,
    )
    if fault is None:
        assert (
            p.returncode == 0
            and b"NO_OPERATIONAL_AUTHORITY" in (root / "gate-stdout.log").read_bytes()
        )
    else:
        assert p.returncode != 0


def test_rehearsal_runs_actual_outer_body_with_confined_accounting_only():
    ps = (REPO / "tests/run_v6_integrated_rehearsal.ps1").read_text()
    assert (
        "$bodyStart=$source.IndexOf('$parent=[Diagnostics.Process]::GetCurrentProcess()')"
        in ps
    )
    assert ". ([scriptblock]::Create($source.Substring($bodyStart)))" in ps
    account = ps.split("\nfunction Account-Scope {", 1)[1].split("$bodyStart=", 1)[0]
    assert "-LiteralPath $root" in account and "AtlasRuntime" not in account
    worker = (REPO / "tests/v6_integrated_rehearsal_worker.py").read_text()
    for marker in (
        "Ownership(root, scope)",
        "PreselectionCut(",
        "run_cycle(",
        'domain="DISPOSABLE"',
        'str(repo / "tests/harness_v3_fixture_controller.py")',
    ):
        assert marker in worker
    assert '"selection_mutations": 0' in worker


def test_http_diagnostic_exits_before_browser_or_two_cycle_execution():
    import ast

    worker = ast.parse((REPO / "tests/v6_integrated_rehearsal_worker.py").read_text())
    guarded = next(n for n in worker.body if isinstance(n, ast.Try))
    branch = next(
        n
        for n in guarded.body
        if isinstance(n, ast.If) and "http_diagnostic_only" in ast.unparse(n.test)
    )
    names = [ast.unparse(n.func) for n in ast.walk(branch) if isinstance(n, ast.Call)]
    assert "probe" in names and "collect" in names and "owner.verify" in names
    assert "run_cycle" not in names and "BrowserWindow" not in names
    assert any(
        isinstance(n, ast.Raise) and ast.unparse(n.exc) == "SystemExit(0)"
        for n in branch.body
    )
    assert guarded.body.index(branch) < next(
        i
        for i, n in enumerate(guarded.body)
        if isinstance(n, ast.For) and ast.unparse(n.target) == "cycle"
    )
