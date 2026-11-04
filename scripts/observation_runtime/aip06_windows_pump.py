"""Pre-reserved, retained Windows IO workers for anonymous-pipe bootstrap.

Two persistent workers avoid recursively reserving a new thread over the very
IPC connection needed to make that reservation. Every worker/event/handle has
a concrete prelaunch ticket; no unmetered thread or PID-based cleanup fallback.
"""

import ctypes as C
import threading
from ctypes import wintypes as W

from scripts.observation_runtime.aip06_harness import need


class WindowsPump:
    def __init__(self, *, calls, clock_ns, tickets, observe):
        need(
            type(tickets) is tuple and len(tickets) == 3 and len(set(tickets)) == 3,
            "THREE_PRE_RESERVED_PUMP_TICKETS",
        )
        self.calls, self.clock, self.tickets, self.observe = (
            calls,
            clock_ns,
            tickets,
            observe,
        )
        self.lock = threading.Lock()
        self.state = {}
        self.stopping = False
        self.closed = False
        self.pending = False
        self.handles = []
        k = calls.k
        k.CreateEventW.argtypes = [C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR]
        k.CreateEventW.restype = W.HANDLE
        k.SetEvent.argtypes = [W.HANDLE]
        k.SetEvent.restype = W.BOOL
        k.ResetEvent.argtypes = [W.HANDLE]
        k.ResetEvent.restype = W.BOOL
        self.work = calls.check(k.CreateEventW(None, False, False, None))
        self.handles.append(self.work)
        self.done = calls.check(k.CreateEventW(None, True, False, None))
        self.handles.append(self.done)
        prototype = C.WINFUNCTYPE(W.DWORD, C.c_void_p)

        @prototype
        def procedure(_):
            while True:
                if k.WaitForSingleObject(self.work, 0xFFFFFFFF) != 0:
                    return 73
                if self.stopping:
                    return 0
                action = self.state.get("action")
                try:
                    need(callable(action), "PUMP_ACTION_REQUIRED")
                    self.state["result"] = action()
                except BaseException as exc:
                    self.state["error"] = exc
                finally:
                    k.SetEvent(self.done)

        self.callback = procedure
        k.CreateThread.argtypes = [
            C.c_void_p,
            C.c_size_t,
            prototype,
            C.c_void_p,
            W.DWORD,
            C.POINTER(W.DWORD),
        ]
        k.CreateThread.restype = W.HANDLE
        tid = W.DWORD()
        self.thread = calls.check(
            k.CreateThread(None, 0, procedure, None, 0, C.byref(tid))
        )
        self.handles.append(self.thread)
        self.thread_id = tid.value
        self.observe.created(
            dict(zip(tickets, (self.thread, self.work, self.done), strict=True))
        )

    @property
    def allocation_map(self):
        return dict(zip(self.tickets, (self.thread, self.work, self.done), strict=True))

    def run(self, action, *, deadline_ns):
        with self.lock:
            need(
                not self.closed and not self.pending and self.clock() < deadline_ns,
                "OPEN_IDLE_BOUNDED_PUMP",
            )
            self.pending = True
            self.state = {"action": action}
            k = self.calls.k
            self.calls.check(k.ResetEvent(self.done))
            self.calls.check(k.SetEvent(self.work))
            try:
                self.calls.wait(self.done, deadline_ns)
            except BaseException:
                ok = k.CancelSynchronousIo(self.thread)
                if not ok:
                    need(C.get_last_error() == 1168, "PUMP_CANCELLATION_FAILED")
                # A failed cancellation leaves the worker and callback retained.
                self.calls.wait(
                    self.done, min(deadline_ns + 10**9, self.clock() + 10**9)
                )
                self.pending = False
                raise
            self.pending = False
            need(self.clock() <= deadline_ns, "PUMP_COMPLETION_LATE")
            if "error" in self.state:
                raise self.state["error"]
            need("result" in self.state, "PUMP_COMPLETION_MISSING")
            return self.state["result"]

    def close(self, *, deadline_ns):
        with self.lock:
            need(
                not self.closed and not self.pending,
                "PUMP_CLOSE_REQUIRES_IDLE_OWNED_WORKER",
            )
            self.stopping = True
            self.calls.check(self.calls.k.SetEvent(self.work))
            self.calls.wait(self.thread, deadline_ns)
            for h in reversed(self.handles):
                self.calls.close(h)
                need(self.calls.closed(h), "PUMP_HANDLE_NOT_CLOSED")
            self.observe.released(self.allocation_map)
            self.closed = True


class Mailbox:
    """Bounded multiplexing: a Stop can arrive while a resource reply is due."""

    def __init__(self, channel):
        self.channel = channel
        self.pending = []
        self.lock = threading.RLock()

    def receive(self, kind, *, deadline_ns):
        with self.lock:
            while True:
                for i, item in enumerate(self.pending):
                    if item["kind"] == kind:
                        return self.pending.pop(i)
                need(len(self.pending) < 16, "IPC_MAILBOX_CAPACITY")
                item = self.channel.receive(deadline_ns=deadline_ns)
                if item["kind"] == kind:
                    return item
                need(
                    item["kind"]
                    in {
                        "STOP",
                        "REPLY",
                        "BIND",
                        "RELEASE",
                        "ACK",
                        "DRAIN",
                        "OUTPUT",
                        "EXIT",
                        "FAILURE",
                    },
                    "UNSUPPORTED_IPC_INTERLEAVING",
                )
                self.pending.append(item)
