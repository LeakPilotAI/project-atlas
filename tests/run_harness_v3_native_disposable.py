"""Explicitly disposable Windows validation; never imports an installed runtime."""

import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.installed_nonfinancial_launcher import read_ready
from scripts.observation_runtime.disposable_host_owner import (
    observe_handle,
    observe_pid,
)
from scripts.observation_runtime.installed_acceptance_capture import (
    collect,
)
from scripts.observation_runtime.installed_acceptance_cleanup import (
    AcceptanceController,
)
from scripts.observation_runtime.installed_acceptance_sequence import (
    PreselectionCut,
    run_cycle,
)


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "--execute-disposable-only":
        raise SystemExit("EXPLICIT_DISPOSABLE_ONLY_ENTRY_REQUIRED")
    root = Path(sys.argv[2]).absolute()
    if (
        root
        != REPO
        / "logs/diagnostics/qd-installed-acceptance-harness-v3-correction-20261103/native-run"
        or any(p.is_symlink() or p.is_junction() for p in [root, *root.parents])
        or ctypes.windll.shell32.IsUserAnAdmin()
    ):
        raise ValueError("EXACT_ORDINARY_TOKEN_DISPOSABLE_ROOT_REQUIRED")
    root.mkdir(exist_ok=False)
    started = time.perf_counter()
    result = {
        "scope": "DISPOSABLE_ONLY_NOT_INSTALLED_ACCEPTANCE",
        "accepted": False,
        "cycles": [],
        "selection_callbacks": 0,
        "rollback_callbacks": 0,
        "query_handles_closed": 0,
        "query_helpers": 0,
        "forced_termination": False,
        "operational_actions": 0,
    }
    env = dict(os.environ)
    env.update(
        TEMP=str(root),
        TMP=str(root),
        PYTHONDONTWRITEBYTECODE="1",
        PSModulePath=r"C:\Windows\System32\WindowsPowerShell\v1.0\Modules",
        PSModuleAnalysisCachePath=str(root / "module.cache"),
    )
    child = None
    lifecycle = None
    pending_queries = []

    def guard():
        entries = total = 0
        for parent, _dirs, files in os.walk(root, followlinks=False):
            for path in [Path(parent), *[Path(parent) / n for n in files]]:
                if path.is_symlink() or path.is_junction():
                    raise ValueError("FIXTURE_REPARSE_REFUSAL")
                entries += 1
                if path.is_file():
                    total += path.stat().st_size
        if (
            time.perf_counter() - started >= 165
            or entries >= 1000
            or total + entries * 4096 >= 15 * 1024**2
        ):
            raise ValueError("FIXTURE_CLEANUP_RESERVE_REACHED")
        return {
            "entries": entries,
            "logical_bytes": total,
            "accounted_bytes": total + entries * 4096,
        }

    def line(seconds=3):
        return json.loads(read_ready(child, seconds=seconds))

    def run(command, label, maximum):
        guard()
        proc = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        pending_queries.append(proc)
        result["query_helpers"] += 1
        assert observe_pid(proc.pid)["created"] == observe_handle(int(proc._handle))
        out, err = proc.communicate(timeout=maximum)
        for stream in (proc.stdout, proc.stderr):
            stream.close()
        proc._handle.Close()
        pending_queries.remove(proc)
        result["query_handles_closed"] += 1
        (root / (label + "-stdout.log")).write_bytes(out)
        (root / (label + "-stderr.log")).write_bytes(err)
        if proc.returncode or err:
            raise ValueError("DISPOSABLE_QUERY_REFUSED:" + label)
        return out

    def cut(port, boundary, label):
        proof = collect(
            repo=REPO, evidence=root, port=port, after_ns=boundary, label=label, run=run
        )
        proof["port"] = port
        return proof

    try:
        child = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-B",
                str(REPO / "tests/harness_v3_fixture_controller.py"),
                "--disposable-fixture-only",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        identity = observe_pid(child.pid)
        assert identity["created"] == observe_handle(int(child._handle))
        env["ATLAS_AUTH_HELPER_CLAIMS"] = json.dumps(
            [observe_pid(os.getpid()), identity]
        )
        seed = line()
        port = seed["seed_port"]
        assert seed["fixture_only"] and port not in (8000, 52159, 58145, 60840)
        boundary = time.perf_counter_ns()
        negative = cut(port, boundary, "held-seed")
        rejected = False
        try:
            PreselectionCut(
                address="127.0.0.1", port=port, after_ns=boundary, packet=negative
            ).dispatch(
                lambda: result.update(
                    selection_callbacks=result["selection_callbacks"] + 1
                )
            )
        except ValueError:
            rejected = True
        assert rejected and result["selection_callbacks"] == 0
        result["held_socket_refused_before_effect"] = True
        child.stdin.write(b"RELEASE_SEED\n")
        child.stdin.flush()
        assert line() == {"seed_closed": True}
        boundary = time.perf_counter_ns()
        positive = cut(port, boundary, "closed-seed")

        def synthetic_select():
            result["selection_callbacks"] += 1
            child.stdin.write(b"BEGIN\n")
            child.stdin.flush()

        PreselectionCut(
            address="127.0.0.1", port=port, after_ns=boundary, packet=positive
        ).dispatch(synthetic_select)
        lifecycle = AcceptanceController(child, identity)
        for cycle in (1, 2):
            guard()
            ready = line()
            ready_ns = time.perf_counter_ns()
            expected = {k: ready[k] for k in ("release", "head", "image")}

            def notify(ticket, cycle=cycle):
                print(
                    json.dumps(
                        {
                            "stage": "DISPOSABLE_BROWSER_REQUIRED",
                            "root": str(root),
                            "cycle": cycle,
                            "url": ticket["url"],
                            "deadline_ns": ticket["deadline_ns"],
                        }
                    ),
                    flush=True,
                )

            def diagnose(_ready, cycle=cycle):
                # Intentionally AFTER the ACK, not in its critical path.
                guard()
                result.setdefault("diagnostic_order", []).append(cycle)
                return {"synthetic_only": True, "financial_values": "UNAVAILABLE"}

            def cleanup(current, after, cycle=cycle):
                p = int(current["url"].rstrip("/").rsplit(":", 1)[-1])
                return cut(p, after, "cycle-" + str(cycle))

            sample = run_cycle(
                controller=lifecycle,
                ready=ready,
                expected=expected,
                cycle=cycle,
                root=root,
                domain="DISPOSABLE",
                ready_ns=ready_ns,
                notify=notify,
                diagnose=diagnose,
                collect=cleanup,
                final=cycle == 2,
            )
            result["cycles"].append(sample)
        assert lifecycle.closed and lifecycle.final_result["accepted"]
        result["rollback_callbacks"] += (
            1  # Explicit in-memory fixture only; no native selector.
        )
        result["final_ports"] = []
        for sample in result["cycles"]:
            p = int(sample["ready"]["url"].rstrip("/").rsplit(":", 1)[-1])
            proof = cut(p, lifecycle.stopped_ns, "final-" + str(sample["cycle"]))
            assert (
                proof["crosscheck"]["cleanup_clear"]
                and proof["socket_process"]["accepted"]
            )
            result["final_ports"].append(proof)
        result["accepted"] = True
    except (
        ValueError,
        OSError,
        RuntimeError,
        AssertionError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        result.update(error_type=type(exc).__name__, error=str(exc))
    finally:
        if lifecycle is not None and not lifecycle.closed:
            try:
                if lifecycle.host_id is not None and not lifecycle.stop_attempted:
                    lifecycle.stop()
            finally:
                drained = lifecycle.finish()
                (root / "failure-drain-stdout.log").write_bytes(drained["stdout"])
                (root / "failure-drain-stderr.log").write_bytes(drained["stderr"])
                result["failure_drain"] = {
                    k: v for k, v in drained.items() if k not in ("stdout", "stderr")
                }
        elif child is not None and lifecycle is None:
            child.stdin.close()
            child.stdin = None
            out, err = child.communicate(timeout=8)
            child.stdout.close()
            child.stderr.close()
            child._handle.Close()
            result["early_child_exit"] = child.returncode
            (root / "early-child-output.log").write_bytes(out + err)
        for query in pending_queries:
            try:
                query.communicate(timeout=5)
                query.stdout.close()
                query.stderr.close()
                query._handle.Close()
                result["query_handles_closed"] += 1
            except subprocess.TimeoutExpired:
                result["accepted"] = False
                result["query_drain_incomplete"] = True
        result["child_handle_closed"] = (
            bool(lifecycle.closed) if lifecycle else child is not None
        )
        result["seconds"] = time.perf_counter() - started
        result["resource_usage"] = guard()
        assert result["seconds"] < 180 and result["resource_usage"]["entries"] < 1024
        (root / "result.json").write_text(json.dumps(result, indent=2))
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in ("accepted", "seconds", "resource_usage", "error")
                    if k in result
                }
            ),
            flush=True,
        )
    return 0 if result["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
