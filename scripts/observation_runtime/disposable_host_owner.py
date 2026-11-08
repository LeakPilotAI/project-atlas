"""Retained-child ownership for the explicitly disposable acceptance host only."""
import argparse
import ctypes
import json
import os
import queue
import subprocess
import sys
import threading
from ctypes import wintypes
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def observe_handle(handle):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    times = kernel.GetProcessTimes
    times.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    times.restype = wintypes.BOOL
    creation, exit_time, system, user = (wintypes.FILETIME() for _ in range(4))
    if not times(handle, *[ctypes.byref(x) for x in (creation, exit_time, system, user)]):
        raise ctypes.WinError(ctypes.get_last_error())
    return (creation.dwHighDateTime << 32) | creation.dwLowDateTime


def observe_pid(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    image = kernel.QueryFullProcessImageNameW
    image.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        buf, size = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
        if not image(handle, 0, buf, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"pid": pid, "created": observe_handle(handle), "image": str(Path(buf.value).resolve()).casefold()}
    finally:
        kernel.CloseHandle(handle)


class OwnedHost:
    """Only retained Popen ownership permits stdin EOF; never kill/terminate."""
    def __init__(self, root, manifest_digest, *, runtime_fixture=False, control_fixture=False):
        if os.name != "nt":
            raise RuntimeError("WINDOWS_NATIVE_ACCEPTANCE_ONLY")
        root = Path(root).absolute()
        if (root.parent != REPO / "logs/diagnostics" or not root.name.startswith("qd-http-browser-")
                or not root.is_dir() or any(p.is_symlink() or p.is_junction() for p in [root, *root.parents])):
            raise ValueError("EXPLICIT_DISPOSABLE_ROOT_REQUIRED_BEFORE_PROCESS_OR_LOG")
        script = REPO / "scripts/observation_runtime/selected_account_readonly_host.py"
        if runtime_fixture or control_fixture:
            if not root.name.startswith("qd-http-browser-runtime-"):
                raise ValueError("EXPLICIT_RUNTIME_FIXTURE_ROOT_REQUIRED")
            script = REPO / "tests/qd_autonomous_runtime_host.py"
            if control_fixture:
                script = REPO / "tests/qd_control_stop_host.py"
        self.lines, self.closed, self.shutdown_requested = queue.Queue(), False, False
        # Windows venv redirectors may spawn a second PID. Directly retain the
        # actual interpreter; use only the already installed venv libraries.
        executable = Path(sys._base_executable).resolve()
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(Path(sys.prefix) / "Lib/site-packages"), str(REPO / "backend")])
        with (Path(root) / "host-errors.log").open("a", encoding="utf-8") as errors:
            self.process = subprocess.Popen([str(executable), "-B", str(script),
                "--fixture-root", str(root), "--fixture-sha256", manifest_digest],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                text=True, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            self._accept(executable)
        except BaseException as original:
            # Even a failed observer never authorizes PID-based termination.
            # The original pipe belongs only to this directly created child.
            try:
                self.process.stdin.close()
            except OSError:
                pass
            try:
                self.process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                error = RuntimeError("OWNED_STARTUP_INCOMPLETE_RETAINED")
                error.owner = self
                raise error from original
            raise

    def _accept(self, executable):
        # The original creation handle is retained by CPython's Windows Popen.
        # Compare a separately opened query-only handle before accepting PID.
        self.identity = observe_pid(self.process.pid)
        if (self.identity["created"] != observe_handle(int(self.process._handle))
                or self.identity["image"] != str(executable).casefold()):
            raise RuntimeError("CREATION_HANDLE_IDENTITY_MISMATCH")
        def collect():
            for line in self.process.stdout:
                self.lines.put(json.loads(line))
            self.lines.put({"error": "HOST_EOF"})
        threading.Thread(target=collect, daemon=True).start()
        self.ready = self.lines.get(timeout=15)
        if (self.ready.get("pid") != self.process.pid or self.ready.get("mode") != "DISPOSABLE_SYNTHETIC_READ_ONLY"
                or type(self.ready.get("host_id")) is not str or len(self.ready["host_id"]) != 32):
            raise RuntimeError("HOST_READY_IDENTITY_MISMATCH")
        self.verify(self.identity)

    def verify(self, expected):
        if expected != self.identity or self.process.poll() is not None:
            raise ValueError("OWNED_ACTIVE_IDENTITY_REQUIRED")
        if (observe_pid(self.process.pid) != self.identity
                or observe_handle(int(self.process._handle)) != self.identity["created"]):
            raise ValueError("PROCESS_IDENTITY_CHANGED")

    def control(self, *, phase="entry", mode="normal", delay=0):
        self.verify(self.identity)
        self.process.stdin.write(json.dumps({"phase": phase, "mode": mode, "delay": delay}) + "\n")
        self.process.stdin.flush()
        reply = self.lines.get(timeout=5)
        if reply.get("host_id") != self.ready["host_id"] or "control" not in reply:
            raise ValueError("CONTROL_ACK_MISMATCH")
        return reply

    def runtime_control(self, action):
        self.verify(self.identity)
        if not self.ready.get("runtime_fixture") or action not in ("start", "pause", "stop", "status", "disconnect"):
            raise ValueError("RUNTIME_FIXTURE_CONTROL_ONLY")
        self.process.stdin.write(json.dumps({"action": action}) + "\n")
        self.process.stdin.flush()
        reply = self.lines.get(timeout=12)
        if reply.get("host_id") != self.ready["host_id"] or "runtime" not in reply:
            raise ValueError("RUNTIME_CONTROL_ACK_MISMATCH")
        return reply

    def close(self, expected):
        if expected != self.identity:
            raise ValueError("FOREIGN_OR_MISMATCHED_PROCESS")
        if self.closed:
            return
        if self.process.poll() is None:
            self.verify(expected)
            if not self.shutdown_requested:
                self.shutdown_requested = True
                self.process.stdin.close()
        # Existing dashboard grace is 12 seconds; no deadline is changed.
        self.process.wait(timeout=12)
        if self.process.returncode != 0:
            raise RuntimeError("HOST_EXIT_INCOMPLETE")
        self.closed = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-root", required=True)
    parser.add_argument("--fixture-sha256", required=True)
    parser.add_argument("--runtime-fixture", action="store_true")
    args = parser.parse_args()
    owner = OwnedHost(Path(args.fixture_root), args.fixture_sha256, runtime_fixture=args.runtime_fixture)
    print(json.dumps({**owner.ready, "owned_identity": owner.identity}), flush=True)
    try:
        for line in sys.stdin:
            value = json.loads(line)
            if value == {"shutdown": True}:
                break
            reply = owner.runtime_control(value["action"]) if args.runtime_fixture else owner.control(**value)
            print(json.dumps(reply), flush=True)
    finally:
        owner.close(owner.identity)
        print(json.dumps({"owned_shutdown": "COMPLETE", "host_id": owner.ready["host_id"]}), flush=True)


if __name__ == "__main__":
    main()
