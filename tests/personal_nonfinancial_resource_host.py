"""Installed observation/static host fixture; no financial or retained sources.

The parent must verify the complete candidate before invoking this test helper.
No enrollment, app.main lifespan, provider, scanner, writer or account is used.
"""
import argparse
import ctypes as C
import json
import math
import os
import sys
import threading
import time
from ctypes import wintypes as W
from pathlib import Path


def metrics():
    class Memory(C.Structure):
        _fields_ = [("cb", W.DWORD), ("faults", W.DWORD)] + [
            (name, C.c_size_t) for name in ("peak_working", "working", "peak_paged", "paged",
                                          "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile", "private")]

    k = C.WinDLL("kernel32", use_last_error=True)
    k.GetCurrentProcess.restype = W.HANDLE
    handle = k.GetCurrentProcess()
    k.K32GetProcessMemoryInfo.argtypes = [W.HANDLE, C.POINTER(Memory), W.DWORD]
    k.GetProcessHandleCount.argtypes = [W.HANDLE, C.POINTER(W.DWORD)]
    k.GetProcessTimes.argtypes = [W.HANDLE, *([C.POINTER(W.FILETIME)] * 4)]
    memory = Memory(); memory.cb = C.sizeof(memory)
    count = W.DWORD(); stamps = [W.FILETIME() for _ in range(4)]
    if (not k.K32GetProcessMemoryInfo(handle, C.byref(memory), memory.cb)
            or not k.GetProcessHandleCount(handle, C.byref(count))
            or not k.GetProcessTimes(handle, *(C.byref(s) for s in stamps))):
        raise C.WinError(C.get_last_error())
    ticks = lambda v: (v.dwHighDateTime << 32) | v.dwLowDateTime
    return {"working_set_bytes": memory.working, "peak_working_set_bytes": memory.peak_working,
            "private_bytes": memory.private, "cpu_seconds": (ticks(stamps[2]) + ticks(stamps[3])) / 10**7,
            "handles": count.value, "threads": threading.active_count()}


class EmptySession:
    """Explicit unavailable data; no journal path, constructor or file reader."""
    def __init__(self, initial):
        self.initial = initial

    def snapshot(self):
        return self.initial()

    def diagnostics(self):
        return {"status": "UNAVAILABLE", "reason": "NO_OBSERVATIONS_IN_RESOURCE_TEST"}

    def research(self):
        return {"status": "UNAVAILABLE", "reason": "NO_RESEARCH_IN_RESOURCE_TEST"}

    def history(self):
        return {"sessions": [], "status": "UNAVAILABLE", "reason": "NO_JOURNALS_IN_RESOURCE_TEST"}


def verify_resource_limits(sample):
    if type(sample) is not dict or not {"working_set_bytes", "private_bytes", "cpu_seconds"}.issubset(sample):
        raise ValueError("NONFINANCIAL_RESOURCE_MEASUREMENT_INCOMPLETE")
    for name in ("working_set_bytes", "private_bytes"):
        if type(sample[name]) is not int or not 0 <= sample[name] <= 512 * 1024**2:
            raise ValueError("NONFINANCIAL_RESOURCE_LIMIT")
    cpu = sample["cpu_seconds"]
    # Include process bootstrap CPU, not only CPU since HTTP readiness.
    if type(cpu) not in (int, float) or not math.isfinite(cpu) or not 0 <= cpu <= 15:
        raise ValueError("NONFINANCIAL_RESOURCE_LIMIT")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--candidate", required=True)
    p.add_argument("--seconds", type=int, default=120)
    args = p.parse_args()
    if not 1 <= args.seconds <= 120:
        raise ValueError("BOUNDED_NONFINANCIAL_HOST_REQUIRED")
    candidate = Path(args.candidate).resolve()
    if Path(sys.executable).resolve() != candidate / "python/python.exe":
        raise ValueError("EXACT_INSTALLED_INTERPRETER_REQUIRED")
    if Path(sys.base_prefix).resolve() != candidate / "python":
        raise ValueError("EXACT_INSTALLED_BASE_REQUIRED")
    sys.path[:0] = [str(candidate / "backend"), str(candidate)]
    from scripts.observation_runtime import desktop_observation as installed
    from scripts.observation_runtime.disposable_host_owner import observe_pid
    assert Path(installed.__file__).resolve().is_relative_to(candidate)
    assert "app.main" not in sys.modules
    session = EmptySession(installed.initial)
    server, host_id = installed.make_host(session, request_limit=96, deadline_seconds=args.seconds)
    stop = threading.Event(); refused = []

    def commands():
        for line in sys.stdin:
            if line.strip() == "CLOSE " + host_id:
                stop.set(); return
            refused.append("OWNER_OR_COMMAND_MISMATCH")
        stop.set()

    threading.Thread(target=commands, daemon=True).start()
    before = metrics()
    verify_resource_limits(before)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    started = time.perf_counter(); worker.start()
    print(json.dumps({"ready": True, "host_id": host_id, "process": observe_pid(os.getpid()),
                      "url": f"http://127.0.0.1:{server.server_port}", "before": before,
                      "installed_module": installed.__file__, "mode": "NONFINANCIAL_RESOURCE_FIXTURE"}), flush=True)
    peak = dict(before)
    failure = None
    try:
        while worker.is_alive() and time.perf_counter() - started < args.seconds:
            current = metrics()
            for field in ("working_set_bytes", "peak_working_set_bytes", "private_bytes", "handles", "threads"):
                peak[field] = max(peak[field], current[field])
            verify_resource_limits(current)
            if stop.wait(.05):
                break
    except (ValueError, OSError, RuntimeError) as error:
        failure = str(error)
    finally:
        if worker.is_alive():
            server.shutdown()
        worker.join(4)
        if worker.is_alive():
            raise ValueError("OWNED_SERVER_THREAD_DRAIN_INCOMPLETE")
        server.server_close()
        after = metrics(); counts = server.counts()
        try:
            verify_resource_limits(after)
        except ValueError as error:
            failure = str(error)
        assert counts["total_attempted"] == counts["admitted"] + counts["rejected"] and counts["pending"] == 0
        assert counts["total_attempted"] <= 96
        print(json.dumps({"closed": True, "before": before, "peak": peak, "after": after,
                          "handle_delta": after["handles"] - before["handles"], "counts": counts,
                          "cpu_seconds": after["cpu_seconds"] - before["cpu_seconds"],
                          "seconds": round(time.perf_counter() - started, 3), "failure": failure,
                          "wrong_commands_refused": len(refused), "financial_actions": 0,
                          "provider_actions": 0, "journal_reads": 0}), flush=True)
    if failure:
        raise ValueError(failure)


if __name__ == "__main__":
    main()
