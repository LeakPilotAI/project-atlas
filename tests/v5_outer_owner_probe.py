"""Disposable original-handle/RPC probe; cannot launch installed Atlas."""

import ast
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

if len(sys.argv) != 3 or sys.argv[1] != "--disposable-native-owner-probe":
    raise SystemExit("DISPOSABLE_PROBE_ARGUMENTS_REQUIRED_NO_NATIVE_ACTION")
ROOT = Path(sys.argv[2]).absolute()
REPO = Path(__file__).resolve().parents[1]
if ROOT.parent != REPO / "logs/diagnostics" or not ROOT.name.startswith(
    "qd-v5-outer-owner-probe-"
):
    raise SystemExit("CONFINED_DISPOSABLE_OWNER_PROBE_REQUIRED")
sys.path.insert(0, str(REPO))
sys.stdout = (ROOT / "probe-stdout.log").open("x", buffering=1)
sys.stderr = (ROOT / "probe-stderr.log").open("x", buffering=1)
from scripts.acceptance_harness_v5.ownership import Ownership

owner = None
result = {
    "domain": "DISPOSABLE_NATIVE_OWNERSHIP_ONLY",
    "installed_launches": 0,
    "financial_actions": 0,
    "startup_authorized": False,
    "accepted": False,
}
try:
    owner = Ownership(ROOT, json.loads((ROOT / "fixture-scope.json").read_bytes()))
    from scripts.observation_runtime.disposable_host_owner import observe_handle

    definition = next(
        n
        for n in ast.parse(
            (REPO / "scripts/acceptance_harness_v5/worker.py").read_bytes()
        ).body
        if isinstance(n, ast.FunctionDef) and n.name == "run"
    )
    begun = time.perf_counter()
    env = {
        "ownership": owner,
        "result": {"status": "DISPOSABLE_ONLY"},
        "e": ROOT,
        "r": REPO,
        "remaining": lambda: 60 - (time.perf_counter() - begun),
        "os": __import__("os"),
        "subprocess": subprocess,
        "json": json,
        "observe_handle": observe_handle,
        "retained_actions": [],
    }
    exec(  # noqa: S102 - AST-extracted actual read-only action function, never the worker entry/body.
        compile(
            ast.Module(body=[definition], type_ignores=[]),
            "<actual V5 read-only action owner>",
            "exec",
        ),
        env,
    )
    ps = owner.scope["ownership"]["images"]["powershell"]["path"]
    for index in range(4):
        output = env["run"](
            [
                ps,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "[Console]::Out.Write('V5-DIAG')",
            ],
            f"fixture-query-{index}",
            5,
        )
        if output != b"V5-DIAG":
            raise RuntimeError("GENUINE_DIAGNOSTIC_OUTPUT_MISSING")
    result["actual_worker_action_queries"] = 4
    result["claims"] = owner.verify()
    result["job_members"] = sorted(owner.raw.members())
    result["original_handles_verified"] = True
    result["accepted"] = True
except Exception as exc:  # noqa: BLE001 - preserve disposable failure and cleanup evidence.
    result["error"] = repr(exc)
    result["traceback"] = traceback.format_exc()
finally:
    if owner is not None:
        try:
            owner.close()
            result["duplicate_handles_and_images_closed"] = True
        except Exception as exc:  # noqa: BLE001 - preserve disposable failure and cleanup evidence.
            result["cleanup_error"] = repr(exc)
            result["accepted"] = False
    (ROOT / "probe-result.json").write_text(json.dumps(result, indent=2) + "\n")
raise SystemExit(0 if result["accepted"] else 2)
