"""Bounded anonymous-pipe transport without recursive IPC thread allocation.

Each data direction has a separate private credit pipe. Credits describe bytes
actually read, not an event/financial ACK. A sender writes no more than the
observed pipe capacity minus its unconsumed bytes. Exclusive inherited endpoints
and monotonically numbered credits are required; no socket or polling process.
"""

import ctypes as C
import struct
import threading
from ctypes import wintypes as W

from scripts.observation_runtime.aip06_harness import need


class Win32PipeCalls:
    def __init__(self, kernel):
        self.k = kernel
        specs = {
            "PeekNamedPipe": (
                [
                    W.HANDLE,
                    C.c_void_p,
                    W.DWORD,
                    C.c_void_p,
                    C.POINTER(W.DWORD),
                    C.c_void_p,
                ],
                W.BOOL,
            ),
            "GetNamedPipeInfo": (
                [
                    W.HANDLE,
                    C.c_void_p,
                    C.POINTER(W.DWORD),
                    C.POINTER(W.DWORD),
                    C.c_void_p,
                ],
                W.BOOL,
            ),
            "ReadFile": (
                [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p],
                W.BOOL,
            ),
            "WriteFile": (
                [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p],
                W.BOOL,
            ),
            "Sleep": ([W.DWORD], None),
        }
        for name, (args, result) in specs.items():
            f = getattr(kernel, name)
            f.argtypes, f.restype = args, result

    @staticmethod
    def check(ok):
        if not ok:
            raise C.WinError(C.get_last_error())

    def capacity(self, h):
        a, b = W.DWORD(), W.DWORD()
        self.check(self.k.GetNamedPipeInfo(h, None, C.byref(a), C.byref(b), None))
        # Anonymous pipes have one inbound and outbound buffer. Some Windows
        # versions report only the applicable side; a zero/unknown bound refuses.
        sizes = [x for x in (a.value, b.value) if x]
        need(sizes, "PIPE_CAPACITY_UNAVAILABLE")
        return min(sizes)

    def available(self, h):
        value = W.DWORD()
        self.check(self.k.PeekNamedPipe(h, None, 0, None, C.byref(value), None))
        return value.value

    def read(self, h, count):
        buf = C.create_string_buffer(count)
        done = W.DWORD()
        self.check(self.k.ReadFile(h, buf, count, C.byref(done), None))
        need(0 < done.value <= count, "PIPE_READ_PROGRESS")
        return buf.raw[: done.value]

    def write(self, h, raw):
        done = W.DWORD()
        self.check(self.k.WriteFile(h, raw, len(raw), C.byref(done), None))
        need(done.value == len(raw), "PIPE_WRITE_PARTIAL")
        return done.value

    def pause(self):
        self.k.Sleep(1)


class CreditedPipeEndpoint:
    def __init__(
        self,
        *,
        api,
        read_handle,
        write_handle,
        credit_read,
        credit_write,
        clock_ns,
        verify_peer,
        session_tag,
        capacities,
    ):
        need(type(session_tag) is bytes and len(session_tag) == 16, "PIPE_SESSION_TAG")
        self.api, self.read_handle, self.write_handle = api, read_handle, write_handle
        self.credit_read, self.credit_write = credit_read, credit_write
        self.clock, self.verifier, self.tag = clock_ns, verify_peer, session_tag
        # Capacities come from GetNamedPipeInfo on the original READ ends at
        # CreatePipe time. A write-only endpoint need not have READ_ATTRIBUTES.
        need(
            type(capacities) is dict
            and set(capacities) == {"data", "credit"}
            and all(type(v) is int for v in capacities.values()),
            "OBSERVED_PIPE_PAIR_CAPACITIES",
        )
        self.capacity = min(65536, capacities["data"])
        need(
            4096 <= self.capacity and capacities["credit"] >= 4096,
            "SUPPORTED_PIPE_BUFFER_CAPACITY",
        )
        self.outstanding, self.sent_credit, self.received_credit = 0, 0, 0
        self.credit_buffer = bytearray()
        self.failed = False
        self.credit_pending = 0
        self.rlock, self.wlock = threading.Lock(), threading.Lock()

    def verify_peer(self, binding):
        need(not self.failed, "PIPE_TRANSPORT_UNKNOWN")
        self.verifier(binding)

    def _fresh(self, deadline):
        need(not self.failed and self.clock() < deadline, "PIPE_TRANSPORT_DEADLINE")

    def _credits(self):
        available = self.api.available(self.credit_read)
        if available:
            need(len(self.credit_buffer) + available <= 65536, "CREDIT_QUEUE_CAPACITY")
            self.credit_buffer.extend(self.api.read(self.credit_read, available))
        while len(self.credit_buffer) >= 32:
            tag, sequence, count = struct.unpack("!16sQQ", self.credit_buffer[:32])
            del self.credit_buffer[:32]
            need(
                tag == self.tag
                and sequence == self.received_credit + 1
                and 0 < count <= self.outstanding,
                "PIPE_CREDIT_REPLAY_OR_CONFLICT",
            )
            self.received_credit = sequence
            self.outstanding -= count

    def write_all(self, raw, *, deadline_ns):
        need(type(raw) is bytes and 0 < len(raw) <= 1024**2 + 4, "BOUNDED_PIPE_WRITE")
        with self.wlock:
            try:
                offset = 0
                while offset < len(raw):
                    self._fresh(deadline_ns)
                    self._credits()
                    free = self.capacity - self.outstanding
                    if not free:
                        self.api.pause()
                        continue
                    block = raw[offset : offset + min(free, 32768)]
                    self.api.write(self.write_handle, block)
                    self.outstanding += len(block)
                    offset += len(block)
                self._fresh(deadline_ns)
            except BaseException:
                self.failed = True
                raise

    def read_exact(self, count, *, deadline_ns):
        need(type(count) is int and 0 < count <= 1024**2, "BOUNDED_PIPE_READ")
        with self.rlock:
            result = bytearray()
            try:
                while len(result) < count:
                    self._fresh(deadline_ns)
                    available = self.api.available(self.read_handle)
                    if not available:
                        self.api.pause()
                        continue
                    raw = self.api.read(
                        self.read_handle, min(available, count - len(result), 32768)
                    )
                    result.extend(raw)
                    self.credit_pending += len(raw)
                    if self.credit_pending >= 4096:
                        self._credit()
                # A 4-byte frame header is followed by its body. Coalescing it
                # prevents a small header read from exhausting the credit queue.
                if count != 4 and self.credit_pending:
                    self._credit()
                self._fresh(deadline_ns)
                return bytes(result)
            except BaseException:
                self.failed = True
                raise

    def _credit(self):
        self.sent_credit += 1
        self.api.write(
            self.credit_write,
            struct.pack("!16sQQ", self.tag, self.sent_credit, self.credit_pending),
        )
        self.credit_pending = 0
