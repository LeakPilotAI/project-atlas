"""Explicit opt-in: one ephemeral loopback socket, never an installed runtime."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts.installed_nonfinancial_launcher import read_ready
from scripts.observation_runtime.disposable_host_owner import (
    observe_handle,
    observe_pid,
)
from scripts.observation_runtime.installed_acceptance_cleanup import socket_cleanup


@pytest.mark.skipif(
    os.name != "nt" or os.environ.get("ATLAS_DISPOSABLE_SOCKET_DIAGNOSTIC") != "1",
    reason="Explicit disposable Windows socket diagnostic opt-in required",
)
def test_owned_ephemeral_socket_visible_then_closed_after_exact_child_exit(tmp_path):
    started = time.perf_counter()
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts/windows/Atlas-Acceptance-Resource-Audit.ps1"
    )
    ps = (
        Path(os.environ["SystemRoot"])
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    claims = [observe_pid(os.getpid()), observe_pid(os.getppid())]
    env = dict(
        os.environ,
        ATLAS_AUTH_HELPER_CLAIMS=json.dumps(claims),
        TEMP=str(tmp_path),
        TMP=str(tmp_path),
        PSModuleAnalysisCachePath=str(tmp_path / "module.cache"),
        PSModulePath=str(ps.parent / "Modules"),
    )
    # A daemon only watches this child's original stdin. A 20-second natural
    # lifetime closes the socket even if the parent is interrupted; no kill API.
    code = """import json,os,socket,sys,threading
s=socket.socket();s.bind(('127.0.0.1',0));s.listen(1)
print(json.dumps({'pid':os.getpid(),'port':s.getsockname()[1]}),flush=True)
done=threading.Event()
def watch():sys.stdin.readline();done.set()
threading.Thread(target=watch,daemon=True).start()
done.wait(20);s.close();print(json.dumps({'closed':True}),flush=True)
"""
    child = subprocess.Popen(
        [sys._base_executable, "-I", "-B", "-c", code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    claim = observe_pid(child.pid)
    assert claim["created"] == observe_handle(int(child._handle))
    ready = json.loads(read_ready(child, seconds=3))
    assert ready["pid"] == claim["pid"] and ready["port"] not in (8000, 58145, 60840)

    def collect(label):
        before = time.perf_counter_ns()
        result = subprocess.run(
            [
                str(ps),
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(script),
                "-OwnedPort",
                str(ready["port"]),
                "-OwnedAddress",
                "127.0.0.1",
            ],
            env=env,
            capture_output=True,
            check=False,
            timeout=5,
        )
        (tmp_path / (label + "-stdout.json")).write_bytes(result.stdout)
        (tmp_path / (label + "-stderr.log")).write_bytes(result.stderr)
        assert result.returncode == 0 and not result.stderr, result.stdout.decode(
            errors="replace"
        )
        data = json.loads(result.stdout)
        return data, socket_cleanup(
            data, address="127.0.0.1", port=ready["port"], stopped_ns=before
        )

    try:
        _observed, decision = collect("listening")
        assert not decision["accepted"] and decision["enumeration_error"] is None
        listener = [row for row in decision["matching_rows"] if row["state"] == 2]
        assert (
            len(listener) == 1
            and listener[0]["owner_pid"] == child.pid
            and listener[0]["owner_present"] is True
        )
    finally:
        # Native creation time still matches the retained handle before EOF.
        assert observe_handle(int(child._handle)) == claim["created"]
        if child.stdin is not None:
            child.stdin.close()
            child.stdin = None
        out, err = child.communicate(timeout=5)
        (tmp_path / "child-final-stdout.json").write_bytes(out)
        (tmp_path / "child-final-stderr.log").write_bytes(err)
        assert child.returncode == 0 and not err and json.loads(out) == {"closed": True}
        child._handle.Close()
    _closed, decision = collect("closed")
    assert decision["accepted"], decision
    assert time.perf_counter() - started <= 30
    assert len(list(tmp_path.iterdir())) <= 64
    assert (
        sum(p.stat().st_size for p in tmp_path.iterdir() if p.is_file()) <= 8 * 1024**2
    )
    (tmp_path / "summary.json").write_text(
        json.dumps(
            {
                "seconds": time.perf_counter() - started,
                "ephemeral_listener_only": True,
                "exact_native_identity_verified": True,
                "listener_owner_matched": True,
                "child_exit_code": child.returncode,
                "closed_snapshot_accepted": decision["accepted"],
                "installed_application_launches": 0,
                "financial_actions": 0,
            },
            indent=2,
        )
    )
