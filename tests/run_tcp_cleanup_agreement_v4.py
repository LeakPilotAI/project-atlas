"""Opt-in bounded disposable TCP experiment; never launches installed Atlas."""

import ctypes
import json
import os
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

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
from scripts.observation_runtime.installed_acceptance_sequence import PreselectionCut
from scripts.observation_runtime.socket_evidence import ip_helper


def verify_fixture_ready(ready, identity):
    """Match the native observer's existing canonical Windows path contract."""
    if (
        type(ready) is not dict
        or type(ready.get("pid")) is not int
        or ready["pid"] != identity["pid"]
        or type(ready.get("image")) is not str
        or str(Path(ready["image"]).resolve()).casefold() != identity["image"]
        or ready.get("release") != "SYNTHETIC_FIXTURE"
        or ready.get("head") != "f" * 64
        or any(
            ready.get(k) is not False
            for k in ("providers", "financial_writers", "trading", "automatic_startup")
        )
    ):
        raise ValueError("EXACT_DISPOSABLE_READY_IDENTITY_REQUIRED")


def main():
    if sys.argv[1:] not in (
        ["--execute-disposable-tcp-only"],
        ["--execute-disposable-tcp-only", "--image-comparison-corrected"],
        ["--execute-disposable-tcp-only", "--peer-eof-drained"],
    ):
        raise SystemExit("EXPLICIT_DISPOSABLE_TCP_ONLY_ENTRY_REQUIRED")
    root = (
        REPO
        / "logs/diagnostics/qd-windows-tcp-cleanup-agreement-v4-20261103/native-run"
    )
    if sys.argv[-1] == "--image-comparison-corrected":
        root = root.with_name("native-run-image-corrected")
    elif sys.argv[-1] == "--peer-eof-drained":
        root = root.with_name("native-run-eof-drained")
    if any(p.is_symlink() or p.is_junction() for p in [root, *root.parents]):
        raise ValueError("CONFINED_NONREPARSE_ROOT_REQUIRED")
    if ctypes.windll.shell32.IsUserAnAdmin():
        raise ValueError("NORMAL_TOKEN_ONLY")
    root.mkdir(exist_ok=False)
    started = time.perf_counter()
    result = {
        "accepted": False,
        "cycles": [],
        "queries": 0,
        "query_handles_closed": 0,
        "child_handles_closed": 0,
        "forced_termination": False,
        "installed_launches": 0,
        "operational_selection_actions": 0,
        "financial_actions": 0,
        "provider_connections": 0,
        "attempts_retried": 0,
    }
    env = dict(
        os.environ,
        TEMP=str(root),
        TMP=str(root),
        PYTHONDONTWRITEBYTECODE="1",
        PSModulePath=r"C:\Windows\System32\WindowsPowerShell\v1.0\Modules",
        PSModuleAnalysisCachePath=str(root / "module.cache"),
    )
    children, pending, sockets = [], [], []
    controller = None
    claims = [observe_pid(os.getpid())]
    env["ATLAS_AUTH_HELPER_CLAIMS"] = json.dumps(claims)

    def guard():
        entries = logical = 0
        for parent, dirs, files in os.walk(root, followlinks=False):
            for p in [Path(parent), *[Path(parent) / n for n in files + dirs]]:
                if p.is_symlink() or p.is_junction():
                    raise ValueError("REPARSE_ESCAPE_REFUSED")
            entries += len(files) + len(dirs)
            logical += sum((Path(parent) / n).stat().st_size for n in files)
        if (
            time.perf_counter() - started >= 165
            or entries >= 1000
            or logical + entries * 4096 >= 15 * 1024**2
        ):
            raise ValueError("DISPOSABLE_CLEANUP_RESERVE_REACHED")
        return {
            "entries": entries,
            "logical_bytes": logical,
            "accounted_bytes": logical + entries * 4096,
        }

    def write(name, value):
        guard()
        (root / name).write_text(json.dumps(value, indent=2))

    def run(command, label, maximum):
        guard()
        p = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        pending.append(p)
        result["queries"] += 1
        assert observe_pid(p.pid)["created"] == observe_handle(int(p._handle))
        out, err = p.communicate(timeout=maximum)
        p.stdout.close()
        p.stderr.close()
        p._handle.Close()
        pending.remove(p)
        result["query_handles_closed"] += 1
        (root / (label + "-stdout.log")).write_bytes(out)
        (root / (label + "-stderr.log")).write_bytes(err)
        if p.returncode or err:
            raise ValueError("QUERY_REFUSAL:" + label)
        return out

    def cut(port, boundary, label):
        guard()
        proof = collect(
            repo=REPO, evidence=root, port=port, after_ns=boundary, label=label, run=run
        )
        proof["port"] = port
        assert proof["snapshot"]["started_ticks"] * 10**9 // proof["snapshot"][
            "frequency"
        ] >= max(o["finished_ns"] for o in proof["observations"])
        return proof

    def permitted(port):
        if port in (8000, 52159, 58145, 60840):
            raise ValueError("PROTECTED_OR_PRODUCTION_PORT_REFUSED")
        return port

    def listener():
        p = socket.socket()
        sockets.append(p)
        p.bind(("127.0.0.1", 0))
        permitted(p.getsockname()[1])
        p.listen(1)
        return p

    def child(*, claimed):
        p = subprocess.Popen(
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
        children.append(p)
        identity = observe_pid(p.pid)
        assert identity["created"] == observe_handle(int(p._handle))
        if claimed:
            claims.append(identity)
            env["ATLAS_AUTH_HELPER_CLAIMS"] = json.dumps(claims)
        seed = json.loads(read_ready(p, seconds=3))
        permitted(seed["seed_port"])
        return p, identity, seed

    def close_child(p):
        if p.stdin is not None:
            p.stdin.close()
            p.stdin = None
        out, err = p.communicate(timeout=8)
        assert p.returncode == 0 and not err
        p.stdout.close()
        p.stderr.close()
        p._handle.Close()
        children.remove(p)
        result["child_handles_closed"] += 1
        return {
            "exit_code": p.returncode,
            "stdout": out.decode(),
            "stderr": err.decode(),
        }

    try:
        # Hold the peer open after our FIN so FIN_WAIT2 is genuinely unresolved.
        listening = listener()
        port = listening.getsockname()[1]
        client = socket.socket()
        sockets.append(client)
        client.settimeout(3)
        client.connect(("127.0.0.1", port))
        accepted, _ = listening.accept()
        sockets.append(accepted)
        accepted.settimeout(3)
        accepted.shutdown(socket.SHUT_WR)
        fast = [ip_helper(port=port) for _ in range(8)]
        write("rapid-fin-native.json", fast)
        proof = cut(port, time.perf_counter_ns(), "held-fin")
        assert not proof["crosscheck"]["cleanup_clear"]
        observed = {
            r["state"]
            for value in fast
            for table in value["tables"]
            for r in table["rows"]
        }
        result["rapid_native_states"] = sorted(observed)
        assert observed & {6, 7}
        result["held_fin_refused"] = True
        assert client.recv(1) == b""  # actual peer EOF, not a sleep/settle guess
        client.close()
        accepted.close()
        listening.close()
        result["rapid_final"] = cut(port, time.perf_counter_ns(), "rapid-closed")
        # This is a separate diagnostic cut, never a retry/admission of held-FIN.

        untouched = listener()
        absent_port = untouched.getsockname()[1]
        untouched.close()
        absent = cut(absent_port, time.perf_counter_ns(), "absent")
        assert (
            absent["crosscheck"]["cleanup_clear"]
            and absent["socket_process"]["accepted"]
        )
        result["absent_endpoint_passed"] = True

        unexpected, _, extra_seed = child(claimed=False)
        try:
            cut(absent_port, time.perf_counter_ns(), "unexpected-process")
            raise AssertionError("UNCLAIMED_PROCESS_WAS_NOT_REFUSED")
        except ValueError as exc:
            assert str(exc) == "QUERY_REFUSAL:unexpected-process-roster"
            raw = json.loads(
                (root / "unexpected-process-roster-stdout.log").read_bytes()
            )
            assert (
                raw["non_helpers"] >= 1 and "APP_PROCESS_NOT_RELEASED" in raw["error"]
            )
            result["unexpected_process_refused"] = True
        result["unexpected_child_drain"] = close_child(unexpected)
        result["unexpected_seed_port"] = extra_seed["seed_port"]

        p, identity, seed = child(claimed=True)
        seed_port = seed["seed_port"]
        boundary = time.perf_counter_ns()
        held = cut(seed_port, boundary, "retained-listener")
        assert not held["crosscheck"]["cleanup_clear"]
        callbacks = []
        try:
            PreselectionCut(
                address="127.0.0.1", port=seed_port, after_ns=boundary, packet=held
            ).dispatch(lambda: callbacks.append("INVALID"))
            raise AssertionError("RETAINED_LISTENER_ADMITTED")
        except ValueError:
            assert not callbacks
        result["retained_listener_refused"] = True
        p.stdin.write(b"RELEASE_SEED\n")
        p.stdin.flush()
        assert json.loads(read_ready(p, seconds=3)) == {"seed_closed": True}
        boundary = time.perf_counter_ns()
        pre = cut(seed_port, boundary, "preselection")

        def begin():
            callbacks.append("FIXTURE_BEGIN_ONLY")
            p.stdin.write(b"BEGIN\n")
            p.stdin.flush()

        PreselectionCut(
            address="127.0.0.1", port=seed_port, after_ns=boundary, packet=pre
        ).dispatch(begin)
        result["fixture_callback_count"] = len(callbacks)
        controller = AcceptanceController(p, identity)
        for number in (1, 2):
            ready = json.loads(read_ready(p, seconds=3))
            write(
                f"cycle-{number}-ready-identity.json",
                {"ready": ready, "native": identity},
            )
            endpoint = int(ready["url"].split(":")[-1].strip("/"))
            permitted(endpoint)
            verify_fixture_ready(ready, identity)
            controller.ready(ready["host_id"])
            # Real complete HTTP responses/EOF and local client handle closure.
            # No browser signoff is synthesized: this is TCP-only acceptance.
            for _ in range(4):
                response = probe(port=endpoint, path="/")
                assert response["status"] == 200 and b"UNAVAILABLE" in response["data"]
                assert response["peer_eof"] and response["client_handle_closed"]
            start = time.perf_counter_ns()
            ack = controller.stop()
            write(f"cycle-{number}-stop-ack.json", ack)
            proof = cut(endpoint, controller.stopped_ns, f"cycle-{number}")
            if (
                not proof["crosscheck"]["cleanup_clear"]
                or not proof["socket_process"]["accepted"]
            ):
                controller.refused = True
                raise ValueError(f"CYCLE_{number}_CLEANUP_UNRESOLVED_NO_RETRY")
            if number == 1:
                controller.next_cycle(
                    proof["snapshot"],
                    address="127.0.0.1",
                    port=endpoint,
                    observations=proof["observations"],
                )
            else:
                drain = controller.finish()
                assert drain["accepted"]
                children.remove(p)
                result["child_handles_closed"] += 1
            seconds = (time.perf_counter_ns() - start) / 1e9
            assert seconds <= 8
            result["cycles"].append(
                {
                    "cycle": number,
                    "port": endpoint,
                    "stop": ack,
                    "complete_stop_seconds": seconds,
                    "proof": proof,
                }
            )
        result["two_cycle_passed"] = True
        result["final_cleanup"] = [
            cut(v["port"], time.perf_counter_ns(), f"final-{v['cycle']}")
            for v in result["cycles"]
        ]
        assert all(
            v["crosscheck"]["cleanup_clear"] and v["socket_process"]["accepted"]
            for v in result["final_cleanup"]
        )
        result["accepted"] = True
    except (
        ValueError,
        OSError,
        AssertionError,
        RuntimeError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        result.update(
            error_type=type(exc).__name__,
            error=str(exc),
            traceback=traceback.format_exc(),
        )
    finally:
        for s in sockets:
            s.close()
        if controller is not None and not controller.closed:
            if controller.host_id is not None and not controller.stop_attempted:
                controller.stop()
            drain = controller.finish()
            result["failure_drain"] = {
                k: v for k, v in drain.items() if k not in ("stdout", "stderr")
            }
            if controller.process in children:
                children.remove(controller.process)
                result["child_handles_closed"] += 1
        for p in children[:]:
            close_child(p)
        for query in pending:
            query.communicate(timeout=5)
            query.stdout.close()
            query.stderr.close()
            query._handle.Close()
            result["query_handles_closed"] += 1
        result["seconds"] = time.perf_counter() - started
        result["resource_usage"] = guard()
        assert (
            result["seconds"] < 180
            and result["query_handles_closed"] == result["queries"]
        )
        write("result.json", result)
        print(
            json.dumps(
                {
                    k: v
                    for k, v in result.items()
                    if k not in ("cycles", "final_cleanup", "rapid_final")
                }
            ),
            flush=True,
        )
    return 0 if result["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
