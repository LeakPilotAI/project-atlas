"""R17 host-only Windows CPU budget for nonfinancial native code installation.

A Windows IDLE priority is not a CPU cap on an otherwise idle machine.
This guard restricts only the current installer process to at most two
logical processors, checks actual OS affinity after setting it, and samples
whole-system GetSystemTimes to refuse installation while host CPU is busy.

No process pool, taskkill, user-wide affinity, timer thread, installer bypass,
financial capability or provider network access. Original affinity restored
even on an error. This is a prerequisite, not installation authorization.
"""
from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

MAX_LOGICAL_CPUS = 2
MIN_AVAILABLE_LOGICAL_CPUS = 4
MAX_SYSTEM_CPU_PERCENT = 70.0
INITIAL_SAMPLE_SECONDS = 0.60
INITIAL_SAMPLE_WINDOWS = 4
POLL_SECONDS = 1.25


def choose_bounded_mask(available, *, maximum=MAX_LOGICAL_CPUS):
    """Choose at most two *permitted* logical processors from a native bitmask."""
    if (type(available) is not int or available <= 0
            or type(maximum) is not int or not 1 <= maximum <= 2
            or available.bit_count() < MIN_AVAILABLE_LOGICAL_CPUS):
        raise ValueError("R17_CPU_NOT_ENOUGH_ALLOWED_LOGICAL_PROCESSORS")
    bits = [1 << i for i in range(available.bit_length())
            if available & (1 << i)]
    return sum(bits[-maximum:])


def cpu_busy_percent(previous, current):
    """GetSystemTimes: kernel includes idle; total=kernel+user."""
    if (type(previous) is not tuple or type(current) is not tuple
            or len(previous) != 3 or len(current) != 3
            or any(type(v) is not int or v < 0 for v in previous + current)):
        raise ValueError("R17_CPU_SYSTEM_SAMPLE_INVALID")
    idle = current[0] - previous[0]
    kernel = current[1] - previous[1]
    user = current[2] - previous[2]
    total = kernel + user
    if total <= 0 or idle < 0 or idle > total:
        raise ValueError("R17_CPU_SYSTEM_SAMPLE_INCONCLUSIVE")
    return 100.0 * (total - idle) / total


class NativeR17CpuBudget:
    """In-process original Windows affinity + system load, no external agents."""

    def __init__(self, *, kernel=None, wait=time.sleep,
                 monotonic=time.monotonic):
        self.kernel = kernel
        self.wait = wait
        self.monotonic = monotonic
        self.process = None
        self.original_mask = None
        self.restricted_mask = None
        self.last_sample = None
        self.last_check = None
        self.active = False

    def _native(self):
        if os.name != "nt":
            raise ValueError("R17_CPU_WINDOWS_NATIVE_REQUIRED")
        if self.kernel is None:
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        k = self.kernel
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.GetProcessAffinityMask.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_size_t),
        ]
        k.GetProcessAffinityMask.restype = wintypes.BOOL
        k.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        k.SetProcessAffinityMask.restype = wintypes.BOOL
        k.GetSystemTimes.argtypes = [
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        ]
        k.GetSystemTimes.restype = wintypes.BOOL
        self.process = k.GetCurrentProcess()
        if not self.process:
            raise ValueError("R17_CPU_CURRENT_ORIGINAL_PROCESS_HANDLE_REQUIRED")

    def _affinity(self):
        process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
        if not self.kernel.GetProcessAffinityMask(
                self.process, ctypes.byref(process_mask),
                ctypes.byref(system_mask)):
            raise ValueError("R17_CPU_ORIGINAL_AFFINITY_READBACK_REFUSED")
        if (process_mask.value <= 0 or system_mask.value <= 0
                or process_mask.value & ~system_mask.value):
            raise ValueError("R17_CPU_INVALID_NATIVE_PROCESS_AFFINITY")
        return process_mask.value, system_mask.value

    def _set_affinity(self, mask):
        if not self.kernel.SetProcessAffinityMask(self.process, mask):
            raise ValueError("R17_CPU_AFFINITY_SET_REFUSED")
        current, _ = self._affinity()
        if current != mask:
            raise ValueError("R17_CPU_AFFINITY_SET_READBACK_REFUSED")

    def _times(self):
        idle, kernel, user = (
            wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        )
        if not self.kernel.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            raise ValueError("R17_CPU_SYSTEM_UTILIZATION_UNAVAILABLE")
        def ticks(item):
            return item.dwLowDateTime | (item.dwHighDateTime << 32)
        return ticks(idle), ticks(kernel), ticks(user)

    def __enter__(self):
        self._native()
        current, system = self._affinity()
        allowed = current & system
        target = choose_bounded_mask(allowed)
        if target == current:
            raise ValueError("R17_CPU_AFFINITY_MUST_RESTRICT_COPY_PROCESS")
        self.original_mask = current
        try:
            self._set_affinity(target)
            self.restricted_mask = target
            # A single quiet 0.3-second window is insufficient before a
            # 10,599-file native copy on an interactive desktop. Require
            # four consecutive safe, independent system-CPU intervals.
            initial = self._times()
            for _ in range(INITIAL_SAMPLE_WINDOWS):
                self.wait(INITIAL_SAMPLE_SECONDS)
                after = self._times()
                if cpu_busy_percent(initial, after) >= MAX_SYSTEM_CPU_PERCENT:
                    raise ValueError("R17_CPU_HOST_BUSY_NO_NATIVE_COPY")
                initial = after
            self.last_sample = initial
            self.last_check = self.monotonic()
            self.active = True
            return self
        except BaseException:
            self._restore()
            raise

    def pulse(self):
        if not self.active:
            raise ValueError("R17_CPU_BUDGET_NOT_ACTIVE")
        now = self.monotonic()
        if now < self.last_check:
            raise ValueError("R17_CPU_MONOTONIC_ROLLBACK")
        if now - self.last_check >= POLL_SECONDS:
            current_mask, _ = self._affinity()
            if current_mask != self.restricted_mask:
                raise ValueError("R17_CPU_AFFINITY_DRIFT_PRESERVE_PARTIAL")
            current = self._times()
            if cpu_busy_percent(self.last_sample, current) >= MAX_SYSTEM_CPU_PERCENT:
                raise ValueError("R17_CPU_HOST_BUSY_PRESERVE_PARTIAL")
            self.last_sample = current
            self.last_check = now
        return True

    def _restore(self):
        mask = self.original_mask
        self.active = False
        self.original_mask = None
        if mask is not None:
            self._set_affinity(mask)
        self.restricted_mask = None

    def __exit__(self, typ, value, traceback):
        self._restore()
