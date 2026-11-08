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
from tests.v6_http_diagnostic import verify_http_diagnostic_listener
from tests.v6_job_attribution import (
    admit_disposable_adapter_console,
    inspect_adapter_job,
    retire_disposable_adapter,
    verify_disposable_adapter_candidate,
)
from tests.v6_stable_listener_evidence import verify_stable_interval

owner = None
child = None
controller = None
candidate_handles = {}
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
    if scope.get("stable_listener_probe_only") is True:
        assert scope.get("http_diagnostic_only") is True
        command = [
            sys.executable,
            "-I",
            "-B",
            str(repo / "tests/v6_stable_listener_fixture.py"),
            "--disposable-stable-listener-only",
            str(root),
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
    result["retained_controller_identity"] = identity
    # Capture before any membership admission; a refusal must not erase the
    # original launch/ancestry/member evidence again.
    result["launch_request"] = {
        "command": command,
        "handle": int(child._handle),
        "parent_pid": os.getpid(),
    }
    packet, candidate_handles = inspect_adapter_job(owner, child, command)
    write("job-attribution.json", packet)
    adapter = owner.records["control_center_adapter"][1]
    spec = scope["ownership"]["images"]["console"]
    candidate = verify_disposable_adapter_candidate(
        packet,
        owner.worker,
        adapter,
        command,
        (spec["path"].casefold(), tuple(spec["id"]), spec["sha256"]),
        scope["ownership"]["console_command"],
    )
    result["candidate_topology"] = candidate
    if scope.get("identity_probe_only") is True:
        seed = json.loads(read_ready(child, seconds=5))
        result["seed_port"] = seed["seed_port"]
        child.stdin.close()
        child.stdin = None
        out, err = child.communicate(timeout=5)
        assert child.returncode == 0 and not err
        child.stdout.close()
        child.stderr.close()
        result["original_controller_exit"] = owner.raw.lifecycle(int(child._handle))
        assert result["original_controller_exit"]["exit_code"] == 0
        result["candidate_exits"] = {}
        for pid, h in candidate_handles.items():
            assert owner.k.WaitForSingleObject(h, 3000) == 0
            result["candidate_exits"][str(pid)] = owner.raw.lifecycle(h)
            observed = next(
                row["native"]
                for row in packet["records"]
                if row["native"]["pid"] == pid
            )
            assert result["candidate_exits"][str(pid)] == {
                "pid": pid,
                "created": observed["created"],
                "exited": True,
                "exit_code": 0,
            }
        child._handle.Close()
        child = None
        owner.records.pop("control_center_adapter")
        result["final_claims"] = owner.verify()
        result["final_job_members_before_worker_exit"] = sorted(owner.raw.members())
        result["attribution_only"] = True
        result["accepted"] = True
        write("rehearsal-result.json", result)
        raise SystemExit(0)
    admit_disposable_adapter_console(owner, packet, candidate_handles, command)
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

    class DisposableController(AcceptanceController):
        def finish(self, *, timeout=12):
            final = super().finish(timeout=timeout)
            if final["accepted"]:
                retire_disposable_adapter(owner)
            return final

    controller = DisposableController(child, identity)
    if scope.get("http_diagnostic_only") is True:
        # One direct HTTP diagnostic, never browser ACK/two-cycle acceptance.
        result["kind"] = "DIRECT_HTTP_AND_SUPPLEMENTAL_CLEANUP_ONLY"
        ready = json.loads(read_ready(child, seconds=10))
        assert ready["mode"] == "DISPOSABLE_CONTROL_FIXTURE"
        assert ready["pid"] == identity["pid"]
        assert ready["image"].casefold() == identity["image"]
        endpoint = int(ready["url"].rstrip("/").rsplit(":", 1)[-1])
        assert ready["url"] == f"http://127.0.0.1:{endpoint}/"
        assert all(
            ready[k] is False
            for k in ("providers", "financial_writers", "trading", "automatic_startup")
        )
        owner.verify()
        result["ready"] = ready
        result["ready_observed_ns"] = time.perf_counter_ns()
        result["ready_observed_utc_ns"] = time.time_ns()
        result["stable_observations"] = []
        stable_probe = scope.get("stable_listener_probe_only") is True
        for sample_number in range(1, 4) if stable_probe else (1,):
            if stable_probe:
                child.stdin.write(b"WITNESS\n")
                child.stdin.flush()
                before_witness = json.loads(read_ready(child, seconds=3))
            live_boundary = time.perf_counter_ns()
            live = collect(
                repo=repo,
                evidence=root,
                port=endpoint,
                after_ns=live_boundary,
                label=f"stable-listening-{sample_number}"
                if stable_probe
                else "http-listening",
                run=run,
            )
            if stable_probe:
                child.stdin.write(b"WITNESS\n")
                child.stdin.flush()
                after_witness = json.loads(read_ready(child, seconds=3))
                interval = verify_stable_interval(
                    before_witness, after_witness, live["observations"]
                )
                result["stable_observations"].append(
                    {
                        "sample": sample_number,
                        "before": before_witness,
                        "after": after_witness,
                        "interval": interval,
                        "readers": live,
                    }
                )
        result["independent_listening"] = live
        try:
            result["http_probe_readiness"] = verify_http_diagnostic_listener(
                live,
                port=endpoint,
                pid=identity["pid"],
                after_ns=live_boundary,
                now_ns=time.perf_counter_ns(),
            )
        except ValueError as exc:
            # The operator explicitly authorized this exact fixture's direct
            # GET for diagnosis. A successful GET cannot clear the native
            # listener refusal or become browser/financial startup authority.
            result["http_probe_readiness"] = {
                "accepted": False,
                "error": str(exc),
                "three_reader_acceptance": False,
                "financial_or_browser_authority": False,
            }
        before_http = time.perf_counter_ns()
        response = probe(port=endpoint, path="/")
        assert (
            response["status"] == 200 and b"synthetic test evidence" in response["data"]
        )
        result["direct_http"] = {
            "status": response["status"],
            "started_ns": before_http,
            "finished_ns": time.perf_counter_ns(),
            "peer_eof": response["peer_eof"],
            "client_handle_closed": response["client_handle_closed"],
            "bytes": len(response["data"]),
        }
        controller.ready(ready["host_id"])
        result["stop"] = controller.stop()
        result["drain"] = {
            k: v
            for k, v in controller.finish().items()
            if k not in ("stdout", "stderr")
        }
        assert result["drain"]["accepted"]
        child = None
        result["supplemental_cleanup"] = []
        # New independent cuts, not retroactive acceptance of earlier failures.
        for number in (endpoint, 60103, 60105, 62833):
            proof = collect(
                repo=repo,
                evidence=root,
                port=number,
                after_ns=controller.stopped_ns,
                label=f"http-final-{number}",
                run=run,
            )
            assert (
                proof["crosscheck"]["cleanup_clear"]
                and proof["socket_process"]["accepted"]
            )
            result["supplemental_cleanup"].append({"port": number, "evidence": proof})
        result["final_claims"] = owner.verify()
        result["final_job_members_before_worker_exit"] = sorted(owner.raw.members())
        assert result["final_job_members_before_worker_exit"] == [os.getpid()]
        result["accepted"] = True
        result["diagnostic_completed_not_browser_or_native_listener_acceptance"] = True
        write("rehearsal-result.json", result)
        raise SystemExit(0)
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
            child = None
    result["final_port_readbacks"] = []
    for completed in result["cycles"]:
        endpoint = completed["cleanup"]["port"]
        proof = collect(
            repo=repo,
            evidence=root,
            port=endpoint,
            after_ns=controller.stopped_ns,
            label=f"final-{completed['cycle']}",
            run=run,
        )
        assert (
            proof["crosscheck"]["cleanup_clear"] and proof["socket_process"]["accepted"]
        )
        result["final_port_readbacks"].append(proof)
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
            if child.stdin is not None:
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
        for h in candidate_handles.values():
            owner.native.check(owner.k.CloseHandle(h))
        candidate_handles.clear()
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
