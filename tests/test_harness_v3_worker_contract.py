"""Execute the actual prepared worker's finally suite with disposable ports.

Only Python fixture callbacks run. No imported worker entry, native dependency,
selector, service, installed resource or Windows configuration is accessed.
"""

import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WORKER = REPO / "scripts/acceptance_harness_v3/worker.py"
BASELINE = "c9bc240c11c148cd6c6f6dda7c6760aa2d2ac9547ee8c44847bf239b6382ffbc"


@pytest.mark.parametrize(
    "case",
    [
        "browser_timeout",
        "audit_after_stop",
        "ambiguous_stop",
        "drain_timeout",
        "rollback_unknown",
        "preselection_refused",
        "receipt_changed",
    ],
)
def test_actual_worker_finally_no_double_stop_drain_and_exact_rollback(tmp_path, case):
    if not WORKER.exists():
        pytest.fail(
            "Prepared V3 worker source must exist for this local contract check"
        )
    tree = ast.parse(WORKER.read_text())
    suite = next(
        n.finalbody for n in tree.body if isinstance(n, ast.Try) and n.finalbody
    )
    effects = []

    class Controller:
        host_id = "a" * 32
        stop_attempted = case in ("audit_after_stop", "ambiguous_stop")
        stopped_ns = None

        def stop(self):
            effects.append("STOP_ONCE")
            self.stop_attempted = True
            self.host_id = None
            return {"closed": True, "seconds": 0.1, "financial_actions": 0}

        def finish(self):
            effects.append("DRAIN")
            if case == "drain_timeout":
                raise ValueError("OWNERSHIP_RETAINED_NO_FORCE")
            return {"accepted": True, "exit_code": 0, "stdout": b"", "stderr": b""}

    if case == "audit_after_stop":
        Controller.host_id = None
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    protected = tmp_path / "original-receipt"
    protected.write_bytes(b"preserved")
    before = hashlib.sha256(protected.read_bytes()).hexdigest()
    result = {
        "status": "REFUSED_PRESERVE_EVIDENCE",
        "support_preflight_verified": case != "preselection_refused",
    }

    def run(command, _name, _timeout):
        effects.append("ROLLBACK")
        assert command[-2] == "--execute-approved-known-head-rollback"
        if case == "rollback_unknown":
            raise ValueError("UNKNOWN_NO_RETRY")
        return json.dumps(
            {
                "receipt": {"revision": 8, "restores": BASELINE},
                "final_current": {"head": "b" * 64, "selected": None},
            }
        ).encode()

    def verify(*_args, **_kwargs):
        effects.append("VERIFY_EXISTING_ONLY")

    env = {
        "result": result,
        "controller": None if case == "preselection_refused" else object(),
        "lifecycle": Controller(),
        "ready": None,
        "selection": None if case == "preselection_refused" else {"head": "c" * 64},
        "remaining": lambda: 500,
        "python": "DISPOSABLE_ONLY",
        "e": tmp_path,
        "run": run,
        "json": json,
        "manifest": manifest,
        "verify_deployment": verify,
        "receipt_pin": "fixture",
        "baseline": BASELINE,
        "Path": Path,
        "hashlib": hashlib,
        "retained_actions": [],
        "save": lambda: None,
        "protected_before": {
            str(protected): "0" * 64 if case == "receipt_changed" else before
        },
    }
    exec(  # noqa: S102 - exact repository AST, all native/effect ports replaced by fixture callbacks.
        compile(
            ast.Module(body=suite, type_ignores=[]),
            "<actual-v3-finally-fixture>",
            "exec",
        ),
        env,
    )
    assert effects.count("ROLLBACK") == (0 if case == "preselection_refused" else 1)
    assert effects.count("STOP_ONCE") == (
        0
        if case in ("preselection_refused", "ambiguous_stop", "audit_after_stop")
        else 1
    )
    assert "ROLLBACK" not in effects or effects.index("DRAIN") < effects.index(
        "ROLLBACK"
    )
    assert result["status"] == "REFUSED_PRESERVE_EVIDENCE"
    if case == "drain_timeout":
        assert result["cleanup_error"] == "OWNERSHIP_RETAINED_NO_FORCE"
    if case == "rollback_unknown":
        assert result["rollback"]["status"] == "UNRESOLVED_PRESERVE_NO_RETRY"
    if case == "receipt_changed":
        assert "final_readback_error" in result
    assert protected.read_bytes() == b"preserved"


def test_preselection_dispatch_really_wraps_native_select_call_in_worker():
    tree = ast.parse(WORKER.read_text())
    selector = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "select_with_verified_cut"
    )
    assert any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "cli"
        for n in ast.walk(selector)
    )
    outer = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(isinstance(v, ast.Name) and v.id == "selection" for v in n.targets)
        and isinstance(n.value, ast.Call)
    )
    assert (
        isinstance(outer.value.func, ast.Attribute)
        and outer.value.func.attr == "dispatch"
    )
    assert outer.value.args[0].id == "select_with_verified_cut"


def test_worker_delegates_cycles_to_tested_shared_sequence_not_legacy_wait():
    text = WORKER.read_text()
    assert "sample=run_cycle(" in text
    assert "browser-ack.json')).exists()" not in text
    assert "get('revision')==8" in text


@pytest.mark.parametrize(
    "entry",
    [
        "supervise.py",
        "worker.py",
        "clock_preflight.py",
        "native_preflight.py",
        "restore_known_head.py",
    ],
)
def test_review_templates_refuse_default_invocation_before_native_action(entry):
    env = {k: v for k, v in os.environ.items() if not k.startswith("ATLAS_AUTH_")}
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(WORKER.parent / entry)],
        capture_output=True,
        env=env,
        timeout=8,
        check=False,
    )
    assert result.returncode != 0
    assert (
        b"NO_NATIVE_ACTION" in result.stderr
        or b"NO_LIVE_EXPLICITLY_APPROVED_ACCEPTANCE_SESSION" in result.stderr
    )
    assert not (WORKER.parent / "single-use-claim.json").exists()


def test_blocked_native_validation_cannot_be_overridden_by_approval_arguments(
    tmp_path, monkeypatch
):
    spec = importlib.util.spec_from_file_location(
        "v3_blocked_template_gate", WORKER.parent / "gate.py"
    )
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    proposal = {
        "public_scope_document": "scope.json",
        "status": "BLOCKED_NATIVE_TWO_CYCLE_CLEANUP_VALIDATION",
    }
    raw = json.dumps(proposal).encode()
    (tmp_path / "proposal.json").write_bytes(raw)
    (tmp_path / "scope.json").write_bytes(raw)
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "REPO", tmp_path)
    scope = hashlib.sha256(gate.canonical(proposal)).hexdigest()
    with pytest.raises(
        ValueError, match="V3_NATIVE_VALIDATION_BLOCKED_NO_OPERATIONAL_ENTRY"
    ):
        gate.validate_scope(scope, "0" * 40)
    assert not (tmp_path / "single-use-claim.json").exists()
