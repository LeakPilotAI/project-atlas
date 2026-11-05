"""Read-only observations of already owned native objects. Inert at import.

Never opens a process by PID or adopts an object by name. NtQueryObject is used
only for bounded type information, not unbounded object-name queries. Unknown
types, sockets and incomplete observations refuse; CloseHandle is not a socket
release protocol. Callers retain original handles and prospective ledger slots.
"""

import ctypes as C
from ctypes import wintypes as W

from scripts.observation_runtime.aip06_harness import need


class UnicodeString(C.Structure):
    _fields_ = [("length", W.USHORT), ("maximum", W.USHORT), ("buffer", C.c_void_p)]


class WindowsObjectCalls:
    def __init__(self, kernel, ntdll, *, process_calls, files):
        self.k, self.nt, self.processes, self.files = (
            kernel,
            ntdll,
            process_calls,
            files,
        )
        for name, args, result in (
            ("CompareObjectHandles", [W.HANDLE, W.HANDLE], W.BOOL),
            ("GetThreadId", [W.HANDLE], W.DWORD),
            ("GetProcessIdOfThread", [W.HANDLE], W.DWORD),
            ("GetThreadTimes", [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4, W.BOOL),
            ("GetFileType", [W.HANDLE], W.DWORD),
            (
                "GetNamedPipeInfo",
                [
                    W.HANDLE,
                    C.POINTER(W.DWORD),
                    C.POINTER(W.DWORD),
                    C.POINTER(W.DWORD),
                    C.POINTER(W.DWORD),
                ],
                W.BOOL,
            ),
        ):
            f = getattr(kernel, name)
            f.argtypes, f.restype = args, result
        ntdll.NtQueryObject.argtypes = [
            W.HANDLE,
            C.c_int,
            C.c_void_p,
            W.ULONG,
            C.POINTER(W.ULONG),
        ]
        ntdll.NtQueryObject.restype = C.c_int32

    def type_name(self, handle):
        raw, size = C.create_string_buffer(4096), W.ULONG()
        status = self.nt.NtQueryObject(handle, 2, raw, len(raw), C.byref(size))
        need(
            status >= 0 and C.sizeof(UnicodeString) <= size.value <= len(raw),
            "NATIVE_OBJECT_TYPE_INCOMPLETE",
        )
        text = UnicodeString.from_buffer(raw)
        start, address = C.addressof(raw), text.buffer
        need(
            type(address) is int
            and text.length > 0
            and text.length % 2 == 0
            and text.length <= text.maximum
            and start <= address <= start + size.value - text.length,
            "NATIVE_OBJECT_TYPE_POINTER",
        )
        return C.wstring_at(address, text.length // 2)

    def same(self, original, duplicate):
        return bool(self.k.CompareObjectHandles(original, duplicate))

    def observe(self, handle):
        kind = self.type_name(handle)
        if kind == "Process":
            return {
                "type": kind,
                **self.processes.native(handle),
                **self.processes.lifecycle(handle),
            }
        if kind == "Thread":
            pid, tid = self.k.GetProcessIdOfThread(handle), self.k.GetThreadId(handle)
            times = [W.FILETIME() for _ in range(4)]
            self.processes.check(
                self.k.GetThreadTimes(handle, *(C.byref(t) for t in times))
            )
            need(pid > 4 and tid > 0, "THREAD_IDENTITY_UNAVAILABLE")
            return {
                "type": kind,
                "pid": pid,
                "tid": tid,
                "created": (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
            }
        if kind == "Token":
            token = self.files.token_identity(handle)
            return {"type": kind, "sid": token["sid"], "token_type": token["type"]}
        if kind == "Job":
            return {
                "type": kind,
                "members": sorted(self.processes.members(handle)),
                "limits": self.processes.job_limits(handle),
            }
        if kind in ("Event", "Mutant", "Semaphore", "Timer"):
            # A retained kernel duplicate plus CompareObjectHandles establishes
            # object continuity; a mutable name or signalled state does not.
            return {"type": kind}
        if kind == "File":
            if self.k.GetFileType(handle) == 3:
                fields = [W.DWORD() for _ in range(4)]
                self.processes.check(
                    self.k.GetNamedPipeInfo(handle, *(C.byref(f) for f in fields))
                )
                need(
                    any(f.value for f in fields[1:3]), "NAMED_PIPE_CAPACITY_UNAVAILABLE"
                )
                return {"type": "Pipe"}
            info = self.files.describe(handle)
            return {"type": kind, "native": info, "path": self.files.final_path(handle)}
        raise ValueError("UNSUPPORTED_NATIVE_OBJECT_TYPE:" + kind)


class DeclaredDescendants:
    """Parent-held launch declarations, never an allowlist of reported PIDs.

    A declaration must be recorded before creation. Import duplicates original
    parent/launch/runtime/Job handles from the currently retained peer, rebuilds
    the existing RetainedLaunchBinding, then retains all duplicates through exit.
    Unknown handles, unexpected commands and incomplete transfer fail closed.
    """

    def __init__(
        self, *, peer, calls, objects, allocations, observer_factory, aggregate
    ):
        self.peer, self.calls, self.objects = peer, calls, objects
        self.allocations, self.observer_factory, self.aggregate = (
            allocations,
            observer_factory,
            aggregate,
        )
        self.declarations, self.bindings, self.held, self.finished = {}, {}, {}, set()
        self.failed = False

    def declare(self, request, *, slot, parent_owner, resources):
        from app.services.paper_financial_replay import digest
        from scripts.observation_runtime.launch_ownership import LaunchRequest

        need(type(request) is LaunchRequest, "DESCENDANT_EXACT_LAUNCH_REQUEST")
        request.validate()
        self.peer.verify()
        need(
            not self.failed
            and request.topology == "direct"
            and request.role == "acceptance_worker"
            and request.auxiliary_image is None
            and request.nonce not in self.declarations
            and parent_owner == digest(self.peer.runtime)
            and resources.state["resources"].get(slot)
            == {"owner": parent_owner, "kind": "launch", "closed": False},
            "DESCENDANT_PRIOR_DECLARATION_AND_RESERVATION",
        )
        self.declarations[request.nonce] = (request, slot)

    def import_binding(self, proof):
        from app.services.paper_financial_replay import body
        from scripts.observation_runtime.launch_ownership import RetainedLaunchBinding

        need(
            not self.failed
            and type(proof) is dict
            and set(proof) == {"nonce", "parent", "launch", "runtime", "job", "ready"}
            and proof["nonce"] in self.declarations
            and proof["nonce"] not in self.bindings,
            "DESCENDANT_EXACT_TRANSFER_DECLARATION",
        )
        self.failed = True
        self.peer.verify()
        request, slot = self.declarations[proof["nonce"]]
        held = self.held.setdefault(proof["nonce"], [])
        local = {}
        for name in ("parent", "launch", "runtime", "job"):
            need(
                type(proof[name]) is int and proof[name] > 0,
                "DESCENDANT_ORIGINAL_HANDLE_REQUIRED",
            )
            ticket = self.allocations.reserve("descendant:" + name, "handle")
            handle = self.calls.duplicate(self.peer.runtime_handle, proof[name])
            held.append((ticket, handle))
            local[name] = handle
        need(
            self.objects.same(local["parent"], self.peer.runtime_handle),
            "DESCENDANT_PARENT_KERNEL_OBJECT_MISMATCH",
        )
        need(
            self.objects.same(local["launch"], local["runtime"]),
            "DIRECT_DESCENDANT_HANDLE_ALIAS_REQUIRED",
        )
        api = self.observer_factory(job=local["job"], parent=local["parent"])
        bound = RetainedLaunchBinding(api, request, local["parent"], local["launch"])
        bound.bind_runtime(local["runtime"], proof["ready"])
        need(
            body(bound.parent) == body(self.peer.runtime),
            "DESCENDANT_CURRENT_ANCESTRY_CONFLICT",
        )
        self.aggregate.bind_retained(bound, handle=local["runtime"], job=local["job"])
        self.bindings[proof["nonce"]] = (bound, local["runtime"], slot)
        self.peer.verify()
        self.failed = False
        return bound, local["runtime"]

    def release(self, nonce, *, deadline_ns):
        need(
            not self.failed and nonce in self.bindings and nonce not in self.finished,
            "DESCENDANT_BOUND_RELEASE_REQUIRED",
        )
        bound, handle, _ = self.bindings[nonce]
        self.failed = True
        result = bound.verify_exit()
        self.aggregate.exited(bound, handle=handle)
        for ticket, h in reversed(self.held[nonce]):
            need(self.aggregate.clock() < deadline_ns, "DESCENDANT_RELEASE_DEADLINE")
            self.calls.close(h)
            need(self.calls.closed(h), "DESCENDANT_DUPLICATE_RELEASE_INCOMPLETE")
            self.allocations.release(ticket)
        self.finished.add(nonce)
        self.failed = False
        return result
