"""Concrete Windows process/pipe calls for AIP06; no calls at import time.

All creation methods require a reserved NativeProcessPort plan. These methods
are never selected by the offline test runner and provide no execution grant.
"""

import ctypes as C
import ntpath
import os
import subprocess
import time
from contextlib import contextmanager
from contextvars import ContextVar
from ctypes import wintypes as W
from dataclasses import dataclass

from scripts.observation_runtime.aip06_harness import LIMITS, need


class SuspendedLaunchFailure(ValueError):
    """Creation outcome retained even if restoring inheritance flags fails."""

    def __init__(self, *, created, cause, restore_errors):
        super().__init__('SUSPENDED_LAUNCH_OR_INHERITANCE_RESTORATION_FAILED')
        self.created = created
        self.cause = cause
        self.restore_errors = tuple(restore_errors)


class BasicLimits(C.Structure):
    _fields_ = [
        ("process_cpu", C.c_int64),
        ("job_cpu", C.c_int64),
        ("flags", W.DWORD),
        ("min_ws", C.c_size_t),
        ("max_ws", C.c_size_t),
        ("active", W.DWORD),
        ("affinity", C.c_size_t),
        ("priority", W.DWORD),
        ("scheduling", W.DWORD),
    ]


class ExtendedLimits(C.Structure):
    _fields_ = [
        ("basic", BasicLimits),
        ("io", C.c_uint64 * 6),
        ("process_memory", C.c_size_t),
        ("job_memory", C.c_size_t),
        ("peak_process", C.c_size_t),
        ("peak_job", C.c_size_t),
    ]


class MemoryCounters(C.Structure):
    _fields_ = [
        ("size", W.DWORD),
        ("faults", W.DWORD),
        ("peak_ws", C.c_size_t),
        ("ws", C.c_size_t),
        ("peak_paged", C.c_size_t),
        ("paged", C.c_size_t),
        ("peak_nonpaged", C.c_size_t),
        ("nonpaged", C.c_size_t),
        ("pagefile", C.c_size_t),
        ("peak_pagefile", C.c_size_t),
        ("private", C.c_size_t),
    ]


class JobAccounting(C.Structure):
    _fields_ = [(n, C.c_int64) for n in ('user', 'kernel', 'period_user', 'period_kernel')] + [
        (n, W.DWORD) for n in ('faults', 'total', 'active', 'terminated')
    ]


class Win32ProcessCalls:
    """Original creation handles only. No OpenProcess-by-PID method exists."""

    def __init__(self, kernel, *, clock_ns=time.perf_counter_ns):
        self.k, self.clock = kernel, clock_ns

    @classmethod
    def load(cls):
        k = C.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "GetCurrentProcess": ([], W.HANDLE),
            "GetProcessId": ([W.HANDLE], W.DWORD),
            "GetProcessTimes": ([W.HANDLE] + [C.POINTER(W.FILETIME)] * 4, W.BOOL),
            "QueryFullProcessImageNameW": (
                [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)],
                W.BOOL,
            ),
            "DuplicateHandle": (
                [
                    W.HANDLE,
                    W.HANDLE,
                    W.HANDLE,
                    C.POINTER(W.HANDLE),
                    W.DWORD,
                    W.BOOL,
                    W.DWORD,
                ],
                W.BOOL,
            ),
            "CloseHandle": ([W.HANDLE], W.BOOL),
            "GetHandleInformation": ([W.HANDLE, C.POINTER(W.DWORD)], W.BOOL),
            "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
            "SetInformationJobObject": (
                [W.HANDLE, C.c_int, C.c_void_p, W.DWORD],
                W.BOOL,
            ),
            "QueryInformationJobObject": (
                [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p],
                W.BOOL,
            ),
            "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
            "IsProcessInJob": ([W.HANDLE, W.HANDLE, C.POINTER(W.BOOL)], W.BOOL),
            "ResumeThread": ([W.HANDLE], W.DWORD),
            "SuspendThread": ([W.HANDLE], W.DWORD),
            "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
            "GetExitCodeProcess": ([W.HANDLE, C.POINTER(W.DWORD)], W.BOOL),
            "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
            "TerminateProcess": ([W.HANDLE, W.UINT], W.BOOL),
            "ReadFile": (
                [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p],
                W.BOOL,
            ),
            "WriteFile": (
                [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p],
                W.BOOL,
            ),
            "CancelSynchronousIo": ([W.HANDLE], W.BOOL),
        }
        for name, (args, result) in signatures.items():
            f = getattr(k, name)
            f.argtypes, f.restype = args, result
        return cls(k)

    @staticmethod
    def check(result):
        if not result:
            raise C.WinError(C.get_last_error())
        return result

    def current(self):
        return self.k.GetCurrentProcess()

    def duplicate(
        self, source_process, handle, target_process=None, *, inherit=False, access=0
    ):
        result = W.HANDLE()
        self.check(
            self.k.DuplicateHandle(
                source_process,
                handle,
                target_process or self.current(),
                C.byref(result),
                access,
                inherit,
                0 if access else 2,
            )
        )
        return result.value

    def close(self, handle):
        self.check(self.k.CloseHandle(handle))

    def closed(self, handle):
        flags = W.DWORD()
        if self.k.GetHandleInformation(handle, C.byref(flags)):
            return False
        need(C.get_last_error() == 6, "PROCESS_HANDLE_CLOSE_QUERY_FAILED")
        return True

    def signalled(self, handle):
        state = self.k.WaitForSingleObject(handle,0)
        need(state in (0,258), 'NATIVE_SIGNAL_STATE_UNAVAILABLE')
        return state == 0

    def native(self, handle):
        pid = self.check(self.k.GetProcessId(handle))
        times = [W.FILETIME() for _ in range(4)]
        self.check(self.k.GetProcessTimes(handle, *(C.byref(t) for t in times)))
        buf = C.create_unicode_buffer(32768)
        size = W.DWORD(32768)
        self.check(self.k.QueryFullProcessImageNameW(handle, 0, buf, C.byref(size)))
        return {
            "pid": pid,
            "created": (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
            "image": buf.value.casefold(),
        }

    def lifecycle(self, handle):
        pid = self.check(self.k.GetProcessId(handle))
        times = [W.FILETIME() for _ in range(4)]
        self.check(self.k.GetProcessTimes(handle, *(C.byref(t) for t in times)))
        wait = self.k.WaitForSingleObject(handle, 0)
        need(wait in (0, 258), "PROCESS_WAIT_QUERY_FAILED")
        code = W.DWORD()
        self.check(self.k.GetExitCodeProcess(handle, C.byref(code)))
        return {
            "pid": pid,
            "created": (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
            "exited": wait == 0,
            "exit_code": code.value,
        }

    def create_job(self, name, limits):
        C.set_last_error(0)
        h = self.check(self.k.CreateJobObjectW(None, name))
        if C.get_last_error() == 183:
            self.close(h)
            raise ValueError("NO_EXISTING_JOB_ADOPTION")
        try:
            info = ExtendedLimits()
            info.basic.flags = (0x2000 if limits['kill_on_close'] else 0) | 0x8 | 0x100 | 0x200 | 0x4
            info.basic.active = limits["processes"]
            info.basic.job_cpu = limits["cpu_ns"] // 100
            info.process_memory = limits["child_private_bytes"]
            info.job_memory = limits["private_bytes"]
            self.check(
                self.k.SetInformationJobObject(h, 9, C.byref(info), C.sizeof(info))
            )
            need(self.job_limits(h) == limits, "NATIVE_JOB_LIMIT_READBACK")
            return h
        except BaseException:
            self.close(h)
            raise

    def job_limits(self, job):
        info = ExtendedLimits()
        self.check(
            self.k.QueryInformationJobObject(
                job, 9, C.byref(info), C.sizeof(info), None
            )
        )
        need(
            info.basic.flags in (0x2000 | 0x8 | 0x100 | 0x200 | 0x4, 0x8 | 0x100 | 0x200 | 0x4),
            "UNEXPECTED_NATIVE_JOB_FLAGS",
        )
        return {
            "processes": info.basic.active,
            "private_bytes": info.job_memory,
            "child_private_bytes": info.process_memory,
            "cpu_ns": info.basic.job_cpu * 100,
            "kill_on_close": bool(info.basic.flags & 0x2000),
        }

    def job_accounting(self, job):
        info = JobAccounting()
        self.check(self.k.QueryInformationJobObject(job, 1, C.byref(info), C.sizeof(info), None))
        need(info.user >= 0 and info.kernel >= 0 and info.active <= info.total, "INCOMPLETE_NATIVE_JOB_ACCOUNTING")
        return {'user_ns': info.user * 100, 'kernel_ns': info.kernel * 100,
                'active': info.active, 'total': info.total, 'terminated': info.terminated}

    def members(self, job):
        class List(C.Structure):
            _fields_ = [
                ("assigned", W.DWORD),
                ("count", W.DWORD),
                ("pids", C.c_size_t * LIMITS["processes"]),
            ]

        value = List()
        self.check(
            self.k.QueryInformationJobObject(
                job, 3, C.byref(value), C.sizeof(value), None
            )
        )
        need(
            value.assigned == value.count <= LIMITS["processes"],
            "INCOMPLETE_NATIVE_JOB_ROSTER",
        )
        return set(value.pids[: value.count])

    def assign(self, job, process):
        self.check(self.k.AssignProcessToJobObject(job, process))

    def in_job(self, process, job):
        value = W.BOOL()
        self.check(self.k.IsProcessInJob(process, job, C.byref(value)))
        return bool(value.value)

    def resume(self, thread):
        need(self.k.ResumeThread(thread) == 1, "EXACT_SUSPEND_COUNT_REQUIRED")

    def hold_created_thread(self, thread):
        # Only a declared CREATE_SUSPENDED primary thread is eligible. Keep
        # the extra verifier fence until the independent graph permits release.
        need(self.k.SuspendThread(thread) == 1,'STAGED_PRIMARY_THREAD_WAS_NOT_SUSPENDED')

    def resume_staged_thread(self, thread):
        need(self.k.ResumeThread(thread) == 2,'STAGED_VERIFIER_SUSPEND_FENCE_CHANGED')
        self.resume(thread)

    def wait(self, handle, deadline_ns):
        remaining = deadline_ns - self.clock()
        need(remaining >= 0, "NATIVE_WAIT_DEADLINE")
        need(
            self.k.WaitForSingleObject(
                handle, min(2**32 - 2, (remaining + 999999) // 10**6)
            )
            == 0,
            "NATIVE_WAIT_TIMEOUT",
        )

    def pipe(self):
        import _winapi

        return tuple(_winapi.CreatePipe(None, 65536))

    def create_suspended(
        self,
        *,
        executable,
        argv,
        environment,
        cwd,
        inherit_handles,
        stdin,
        stdout,
        stderr,
    ):
        import _winapi

        need(
            len(set(inherit_handles)) == len(inherit_handles)
            and all(type(h) is int and h > 0 for h in inherit_handles),
            "EXPLICIT_INHERITANCE_LIST",
        )
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESTDHANDLES
        si.hStdInput, si.hStdOutput, si.hStdError = stdin, stdout, stderr
        si.lpAttributeList = {"handle_list": list(inherit_handles)}
        originals = {}
        created = None
        failure = None
        restore_errors = []
        try:
            for handle in inherit_handles:
                originals[handle] = os.get_handle_inheritable(handle)
                os.set_handle_inheritable(handle, True)
            created = _winapi.CreateProcess(
                executable,
                subprocess.list2cmdline(argv),
                None,
                None,
                True,
                0x4 | 0x8,
                environment,
                cwd,
                si,
            )  # suspended, detached: no implicit console
        except BaseException as exc:
            failure = exc
        finally:
            for handle, original in reversed(tuple(originals.items())):
                try:
                    os.set_handle_inheritable(handle, original)
                    need(os.get_handle_inheritable(handle) == original,
                         'INHERITANCE_RESTORATION_READBACK_FAILED')
                except BaseException as exc:
                    restore_errors.append(exc)
        if failure is not None or restore_errors:
            # Never lose successful CreateProcess's original capabilities to a
            # later finally error. The guarded caller must abort that exact
            # suspended process, without reopening by PID.
            raise SuspendedLaunchFailure(created=created, cause=failure,
                                         restore_errors=restore_errors) from failure
        return created

    def terminate_owned_job(self, job):
        self.check(self.k.TerminateJobObject(job, 71))

    def terminate_created(self, handle, original):
        need(
            self.native(handle) == original,
            "ORIGINAL_CREATED_HANDLE_CHANGED_BEFORE_ABORT",
        )
        self.check(self.k.TerminateProcess(handle, 71))

    def usage(self, process):
        ps = C.WinDLL("psapi", use_last_error=True)
        f = ps.GetProcessMemoryInfo
        f.argtypes = [W.HANDLE, C.c_void_p, W.DWORD]
        f.restype = W.BOOL
        memory = MemoryCounters()
        memory.size = C.sizeof(memory)
        self.check(f(process, C.byref(memory), C.sizeof(memory)))
        times = [W.FILETIME() for _ in range(4)]
        self.check(self.k.GetProcessTimes(process, *(C.byref(t) for t in times)))
        return memory.private, sum(
            ((t.dwHighDateTime << 32) | t.dwLowDateTime) * 100 for t in times[2:]
        )


_observation_deadline = ContextVar('aip06_observation_deadline', default=None)


@contextmanager
def bounded_observations(deadline_ns):
    """One absolute bound across recursive retained-identity observations."""
    previous = _observation_deadline.get()
    token = _observation_deadline.set(min(previous, deadline_ns) if previous is not None else deadline_ns)
    try:
        yield
    finally:
        _observation_deadline.reset(token)


class NativeProcessObserver:
    """Independent CIM plus original kernel handles, per-launch Job, pinned images."""

    def __init__(self, *, calls, cim, images, clock_ns):
        self.calls, self.cim, self.images, self.clock = calls, cim, images, clock_ns
        self.job, self.parent = None, None

    def observe(self, handle):
        started = self.clock()
        deadline = _observation_deadline.get()
        deadline = min(started + 5 * 10**9, deadline) if deadline is not None else started + 5 * 10**9
        need(started < deadline, 'RETAINED_OBSERVATION_DEADLINE')
        before = self.calls.native(handle)
        need(
            not self.calls.lifecycle(handle)["exited"], "LIVE_RETAINED_PROCESS_REQUIRED"
        )
        if handle != self.parent:
            need(
                self.job is not None and self.calls.in_job(handle, self.job),
                "PROCESS_NOT_IN_RETAINED_JOB",
            )
        row = self.cim.process(before["pid"], deadline_ns=deadline)
        need(
            type(row) is dict
            and set(row) == {"pid", "created", "image", "parent_pid", "command_line"}
            and type(row["parent_pid"]) is int
            and row["parent_pid"] > 4
            and type(row["command_line"]) is str
            and 0 < len(row["command_line"]) < 32767,
            "INDEPENDENT_PROCESS_FIELDS_REQUIRED",
        )
        after = self.calls.native(handle)
        need(
            before == after
            and row["pid"] == before["pid"]
            and row["created"] // 10 == before["created"] // 10
            and ntpath.normcase(row["image"]) == ntpath.normcase(before["image"])
            and not self.calls.lifecycle(handle)["exited"]
            and started <= self.clock() <= deadline,
            "CIM_NATIVE_PROCESS_DISAGREEMENT",
        )
        pin = self.images.get(ntpath.normcase(before["image"]))
        need(pin is not None, "UNPINNED_PROCESS_IMAGE")
        return {
            **row,
            "created": before["created"],
            "image": before["image"],
            "file_id": tuple(pin["file_id"]),
            "sha256": pin["sha256"],
        }

    def members(self):
        need(self.job is not None, "ORIGINAL_JOB_HANDLE_REQUIRED")
        return self.calls.members(self.job)

    def lifecycle(self, handle):
        return self.calls.lifecycle(handle)


@dataclass
class NativeTask:
    handle: int
    callback: object
    state: dict
    ticket: object


class CancellableCalls:
    """Original CreateThread handle retained until IO completion/cancellation.

    A cancellation timeout keeps the callback/buffers/ticket alive and reports
    UNKNOWN. It never frees a running callback or claims a closed resource.
    """

    def __init__(self, *, calls, allocations, clock_ns):
        self.calls, self.allocations, self.clock = calls, allocations, clock_ns
        self.pending = {}

    def run(self, callback, *, deadline_ns, cancel=None):
        need(self.clock() < deadline_ns, "IO_OPERATION_DEADLINE")
        ticket = self.allocations.reserve("synchronous-io", "thread")
        state = {}
        prototype = C.WINFUNCTYPE(W.DWORD, C.c_void_p)

        @prototype
        def procedure(_):
            try:
                state["result"] = callback()
            except BaseException as exc:
                state["error"] = exc
            return 0

        f = self.calls.k.CreateThread
        f.argtypes = [
            C.c_void_p,
            C.c_size_t,
            prototype,
            C.c_void_p,
            W.DWORD,
            C.POINTER(W.DWORD),
        ]
        f.restype = W.HANDLE
        ident = W.DWORD()
        handle = self.calls.check(f(None, 0, procedure, None, 0, C.byref(ident)))
        task = NativeTask(handle, procedure, state, ticket)
        self.pending[handle] = task
        if hasattr(self.allocations,'bind_native'):
            self.allocations.bind_native(ticket,handle)
        try:
            self.calls.wait(handle, deadline_ns)
        except BaseException:
            if cancel is not None:
                cancel(ident.value)
            else:
                cancelled = self.calls.k.CancelSynchronousIo(handle)
                if not cancelled:
                    need(C.get_last_error() == 1168, "IO_CANCELLATION_UNAVAILABLE")
            self.calls.wait(handle, min(deadline_ns + 10**9, self.clock() + 10**9))
            self._close(task)
            raise
        self._close(task)
        if "error" in state:
            raise state["error"]
        need(
            "result" in state and self.clock() <= deadline_ns,
            "IO_COMPLETION_MISSING_OR_LATE",
        )
        return state["result"]

    def _close(self, task):
        self.calls.close(task.handle)
        need(self.calls.closed(task.handle), "IO_THREAD_HANDLE_NOT_CLOSED")
        self.allocations.release(task.ticket)
        del self.pending[task.handle]


class WindowsPipeEndpoint:
    def __init__(self, *, calls, cancellable, read_handle, write_handle, peer_verifier):
        self.calls, self.cancellable = calls, cancellable
        self.read_handle, self.write_handle = read_handle, write_handle
        self.peer_verifier = peer_verifier

    def verify_peer(self, binding):
        self.peer_verifier(binding)

    def read_exact(self, count, *, deadline_ns):
        need(type(count) is int and 0 < count <= 1024**2, "PIPE_READ_CAPACITY")

        def read():
            result = bytearray()
            while len(result) < count:
                buf = C.create_string_buffer(min(65536, count - len(result)))
                received = W.DWORD()
                self.calls.check(
                    self.calls.k.ReadFile(
                        self.read_handle, buf, len(buf), C.byref(received), None
                    )
                )
                need(received.value > 0, "IPC_UNEXPECTED_EOF")
                result.extend(buf.raw[: received.value])
            return bytes(result)

        return self.cancellable.run(read, deadline_ns=deadline_ns)

    def write_all(self, raw, *, deadline_ns):
        need(type(raw) is bytes and 0 < len(raw) <= 1024**2 + 4, "PIPE_WRITE_CAPACITY")

        def write():
            offset = 0
            while offset < len(raw):
                block = raw[offset : offset + 65536]
                count = W.DWORD()
                self.calls.check(
                    self.calls.k.WriteFile(
                        self.write_handle, block, len(block), C.byref(count), None
                    )
                )
                need(0 < count.value <= len(block), "PIPE_WRITE_PROGRESS")
                offset += count.value

        return self.cancellable.run(write, deadline_ns=deadline_ns)
