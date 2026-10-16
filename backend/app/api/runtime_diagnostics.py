"""Cheap process/runtime diagnostics for Atlas operator debugging.

No network calls, brokerage access, trading decisions, or evidence mutation.
"""
from __future__ import annotations

import gc
import os
import sys
import threading
import time
from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])
_STARTED_MONOTONIC = time.monotonic()


def _process_memory() -> Dict[str, Any]:
    result: Dict[str, Any] = {"pid": os.getpid()}
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS_EX()
            counters.cb = ctypes.sizeof(counters)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(counters), counters.cb
            )
            if ok:
                result.update({
                    "working_set_mb": round(counters.WorkingSetSize / 1048576, 2),
                    "peak_working_set_mb": round(counters.PeakWorkingSetSize / 1048576, 2),
                    "private_mb": round(counters.PrivateUsage / 1048576, 2),
                })
    except Exception as exc:
        result["memory_error"] = type(exc).__name__
    return result


@router.get("/runtime")
async def runtime_diagnostics() -> Dict[str, Any]:
    """Return local-only process pressure indicators without expensive scans."""
    counts = gc.get_count()
    return {
        **_process_memory(),
        "uptime_seconds": round(time.monotonic() - _STARTED_MONOTONIC, 1),
        "threads": threading.active_count(),
        "gc_counts": {"gen0": counts[0], "gen1": counts[1], "gen2": counts[2]},
        "gc_objects": len(gc.get_objects()),
        "execution": "OBSERVABILITY_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
