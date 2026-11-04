"""Combined source-owner/log/ACK/EOF/socket/Stop rehearsal; no Atlas installation."""

import ast
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

root = Path(__file__).parent
repo = Path(r"D:\Work\Project Atlas")
if (
    sys.argv[1:] != ["--approved-installed-worker"]
    or root.parent != repo / "logs/diagnostics"
    or not root.name.startswith("qd-v6-integrated-rehearsal-")
):
    raise SystemExit("EXPLICIT_DISPOSABLE_COMPOSITION_ONLY")
sys.path[:0] = [
    str(repo),
    str(repo / "backend"),
    str(repo / "backend/.venv/Lib/site-packages"),
]
sys.stdout = (root / "worker-stdout.log").open("x", buffering=1, encoding="utf-8")
sys.stderr = (root / "worker-stderr.log").open("x", buffering=1, encoding="utf-8")
from scripts.acceptance_harness_v6.worker_log import publish_worker_logs

publish_worker_logs(root, sys.stdout, sys.stderr)
from scripts.acceptance_harness_v5.ownership import Ownership
from scripts.installed_nonfinancial_launcher import read_ready
from scripts.observation_runtime.acceptance_http_probe import probe
from scripts.observation_runtime.disposable_host_owner import (
    observe_handle,
    observe_pid,
)
from scripts.observation_runtime.installed_acceptance_capture_v4 import collect
from scripts.observation_runtime.installed_acceptance_cleanup import (
    AcceptanceController,
)
from scripts.observation_runtime.installed_acceptance_sequence import (
    PreselectionCut,
    run_cycle,
)

owner = None
child = None
controller = None
result = {
    "accepted": False,
    "domain": "DISPOSABLE_INTEGRATED_ONLY",
    "cycles": [],
    "installed_launches": 0,
    "selection_mutations": 0,
    "financial_actions": 0,
    "provider_connections": 0,
    "emergency_cleanup": False,
}
started = time.perf_counter()
scope = json.loads((root / "fixture-scope.json").read_bytes())
assert scope["domain"] == "DISPOSABLE_INTEGRATED_ONLY"
claim = json.loads((root / "single-use-claim.json").read_bytes())


def write(name, value):
    (root / name).write_text(json.dumps(value, indent=2))


try:
    owner = Ownership(root, scope)
    # Execute the SAME V6 short-action implementation. No fake True callbacks.
    fn = next(
        n
        for n in ast.parse(
            (repo / "scripts/acceptance_harness_v6/worker.py").read_bytes()
        ).body
        if isinstance(n, ast.FunctionDef) and n.name == "run"
    )
    bindings = {
        "ownership": owner,
        "result": {"status": "DISPOSABLE_ONLY"},
        "e": root,
        "r": repo,
        "remaining": lambda: 600 - (time.perf_counter() - started),
        "os": os,
        "subprocess": subprocess,
        "json": json,
        "observe_handle": observe_handle,
        "retained_actions": [],
    }
    exec(  # noqa: S102 - execute the exact guarded source action, never the operational entry.
        compile(
            ast.Module(body=[fn], type_ignores=[]), "<actual V6 guarded action>", "exec"
        ),
        bindings,
    )
    run = bindings["run"]
    env = dict(
        os.environ,
        TEMP=str(root / "temp"),
        TMP=str(root / "temp"),
        PYTHONDONTWRITEBYTECODE="1",
        PSModuleAnalysisCachePath=str(root / "fixture-module.cache"),
    )
    command = [
        sys.executable,
        "-I",
        "-B",
        str(repo / "tests/harness_v3_fixture_controller.py"),
        "--disposable-fixture-only",
    ]
    owner.verify()
    child = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    identity = observe_pid(child.pid)
    assert identity["created"] == observe_handle(int(child._handle))
    owner.controller(child, command)
    owner.verify()
    result["retained_controller_identity"] = identity
    write("registered-role-claims.json", owner.export())
    seed = json.loads(read_ready(child, seconds=5))
    port = seed["seed_port"]
    assert port not in (8000, 52159, 58145, 60840)
    child.stdin.write(b"RELEASE_SEED\n")
    child.stdin.flush()
    assert json.loads(read_ready(child, seconds=3)) == {"seed_closed": True}
    boundary = time.perf_counter_ns()
    cut = collect(
        repo=repo,
        evidence=root,
        port=port,
        after_ns=boundary,
        label="preselection",
        run=run,
    )
    cut["port"] = port
    result["preselection"] = cut

    def begin_fixture():
        owner.verify_native()
        child.stdin.write(b"BEGIN\n")
        child.stdin.flush()
        result["fixture_begin_dispatches"] = 1

    PreselectionCut(
        address="127.0.0.1", port=port, after_ns=boundary, packet=cut
    ).dispatch(begin_fixture)
    controller = AcceptanceController(child, identity)
    for cycle in (1, 2):
        ready = json.loads(read_ready(child, seconds=10))
        observed = time.perf_counter_ns()
        assert (
            ready["mode"] == "DISPOSABLE_CONTROL_FIXTURE"
            and ready["release"] == "SYNTHETIC_FIXTURE"
        )
        assert (
            ready["pid"] == identity["pid"]
            and Path(ready["image"]).resolve().as_posix().casefold()
            == Path(identity["image"]).resolve().as_posix().casefold()
        )
        owner.verify()
        write(f"cycle-{cycle}-ready.json", ready)

        def notify(ticket, cycle=cycle):
            print(
                json.dumps(
                    {
                        "stage": "BROWSER_REQUIRED",
                        "domain": "DISPOSABLE",
                        "cycle": cycle,
                        "url": ticket["url"],
                        "request_path": str(
                            root / f"cycle-{cycle}-browser-request.json"
                        ),
                        "deadline_ns": ticket["deadline_ns"],
                    }
                ),
                flush=True,
            )

        def diagnose(current):
            endpoint = int(current["url"].rstrip("/").rsplit(":", 1)[-1])
            response = probe(port=endpoint, path="/")
            assert (
                response["status"] == 200
                and b"Selected PAPER account: UNAVAILABLE" in response["data"]
                and b"synthetic test evidence" in response["data"]
            )
            return {
                "actual_peer_eof_and_client_closed": True,
                "source": "GENUINE_DISPOSABLE_HTTP_NOT_INSTALLED",
            }

        def capture(current, after, cycle=cycle):
            endpoint = int(current["url"].rstrip("/").rsplit(":", 1)[-1])
            proof = collect(
                repo=repo,
                evidence=root,
                port=endpoint,
                after_ns=after,
                label=f"cycle-{cycle}",
                run=run,
            )
            proof["port"] = endpoint
            return proof

        sample = run_cycle(
            controller=controller,
            ready=ready,
            expected={
                "release": "SYNTHETIC_FIXTURE",
                "head": "f" * 64,
                "image": sys.executable,
            },
            cycle=cycle,
            root=root,
            domain="DISPOSABLE",
            ready_ns=observed,
            notify=notify,
            diagnose=diagnose,
            collect=capture,
            final=cycle == 2,
        )
        result["cycles"].append(sample)
        write("rehearsal-result.json", result)
        if cycle == 2:
            owner.controller_closed()
            child = None
    result["final_claims"] = owner.verify()
    result["final_job_members_before_worker_exit"] = sorted(owner.raw.members())
    assert result["final_job_members_before_worker_exit"] == [os.getpid()]
    result["accepted"] = True
except Exception as exc:  # noqa: BLE001 - retain refusal and exact owned cleanup evidence.
    result.update(error=repr(exc), traceback=traceback.format_exc())
finally:
    if controller is not None and not controller.closed:
        try:
            if controller.host_id is not None and not controller.stop_attempted:
                result["failure_stop"] = controller.stop()
            result["failure_drain"] = {
                k: v
                for k, v in controller.finish().items()
                if k not in ("stdout", "stderr")
            }
            if owner is not None:
                owner.cleanup_controller()
        except Exception as exc:  # noqa: BLE001 - retain refusal and exact owned cleanup evidence.
            result["cleanup_error"] = str(exc)
    elif child is not None:
        try:
            child.stdin.close()
            child.stdin = None
            out, err = child.communicate(timeout=5)
            child.stdout.close()
            child.stderr.close()
            child._handle.Close()
            result["precycle_child_closed"] = child.returncode == 0 and not err
        except Exception as exc:  # noqa: BLE001 - retain refusal and exact owned cleanup evidence.
            result["cleanup_error"] = str(exc)
    if owner is not None:
        try:
            owner.close()
            result["retained_handles_closed"] = True
        except Exception as exc:  # noqa: BLE001 - retain refusal and exact owned cleanup evidence.
            result["cleanup_error"] = str(exc)
    result["seconds"] = time.perf_counter() - started
    if "cleanup_error" in result:
        result["accepted"] = False
    write("rehearsal-result.json", result)
    print(
        json.dumps(
            {
                "stage": "DISPOSABLE_REHEARSAL_COMPLETE",
                "accepted": result["accepted"],
                "error": result.get("error"),
            }
        ),
        flush=True,
    )
raise SystemExit(0 if result["accepted"] else 2)
