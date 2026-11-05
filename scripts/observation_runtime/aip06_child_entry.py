"""Preaccounted inherited native entry. No calls or execution at import time.

Only main's exact private inherited-session form selects Windows backends.
Offline tests pass native responses into this SAME runtime, not a second runner.
The reservation lease permits bounded startup reads, never a financial target.
The existing BIND/guard/ACK/RELEASE fence is required before pinned-byte execution.
"""

import copy
import ctypes as C
import hashlib
import ntpath
import os
import sys
import time
from ctypes import wintypes as W
from types import SimpleNamespace

from app.services.paper_financial_replay import body, digest
from scripts.observation_runtime.aip06_bootstrap_lease import (
    InheritedBootstrapLease,
    ObserverBatch,
)
from scripts.observation_runtime.aip06_child_bootstrap import (
    ChildBootstrap,
    InheritedIdentity,
)
from scripts.observation_runtime.aip06_fixture_guard import FixtureGuard
from scripts.observation_runtime.aip06_harness import (
    BASE,
    ROOTS,
    FixturePaths,
    WorkerOwnership,
    need,
)
from scripts.observation_runtime.aip06_ipc import RemoteResources
from scripts.observation_runtime.aip06_native_controller import NativeAllocations
from scripts.observation_runtime.aip06_native_session import (
    ChannelSessionProtocol,
    WindowsSessionPort,
)
from scripts.observation_runtime.aip06_remote_handles import RemoteHandleProofs
from scripts.observation_runtime.aip06_session_io import ChildSessionIO
from scripts.observation_runtime.aip06_windows_cim import (
    BoundedCimQuery,
    CimProcessQuery,
)
from scripts.observation_runtime.aip06_windows_endpoints import (
    InheritedChannel,
    WindowsChildEndpoints,
)
from scripts.observation_runtime.aip06_windows_io import AllocationBook, NativeIO
from scripts.observation_runtime.aip06_windows_process import (
    CancellableCalls,
    NativeProcessObserver,
)


class ChildServices:
    def __init__(self, port, runtime):
        self.port, self.runtime, self.streams = port, runtime, None
        self.watchdogs, self.done = {}, set()
        self.descendant_gateway = None
        if type(getattr(port,'resources',None)) is RemoteResources:
            from scripts.observation_runtime.aip06_descendant_gateway import DescendantGateway
            self.descendant_gateway = DescendantGateway(port)
            port.descendant_gateway = self.descendant_gateway

    def __getattr__(self, name):
        return getattr(self.port, name)

    def plan(self, argv, options):
        need(
            self.descendant_gateway is not None,
            "STAGED_DESCENDANT_GATEWAY_REQUIRED_BEFORE_CREATION",
        )
        return self.descendant_gateway.plan(argv, options)

    def emit_output(self, value):
        return self.streams.emit_output(value)

    def read_input(self, **kw):
        return self.streams.read_input(**kw)

    def read_line(self, **kw):
        return self.streams.read_line(**kw)

    def run_unexpected_challenge(self):
        self.runtime.verify_source(ntpath.join(ntpath.dirname(__file__),'aip06_unexpected_probe.py'))
        from scripts.observation_runtime.aip06_unexpected_probe import run_guarded_challenge
        return run_guarded_challenge(self)

    def financial_readback(self, value):
        return self.streams.financial_readback(value)

    def wait_readonly_ack(self, value):
        return self.streams.wait_readonly_ack(value)

    def output_context(self):
        return self.streams.output_context()

    def start_watchdog(self, *, seconds, exit_code, owner, keys):
        need(
            owner == self.port.guard.owner and len(keys) == 2,
            "EXACT_CHILD_WATCHDOG_RESERVATIONS",
        )
        calls, clock = self.runtime.calls, self.runtime.clock
        k = calls.k
        k.CreateEventW.argtypes = [C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR]
        k.CreateEventW.restype = W.HANDLE
        k.SetEvent.argtypes = [W.HANDLE]
        k.SetEvent.restype = W.BOOL
        k.ExitProcess.argtypes = [W.UINT]
        k.ExitProcess.restype = None
        event = calls.check(k.CreateEventW(None, True, False, None))
        self.watchdogs[keys] = {"event": event, "thread": None, "closed": False}
        self.port.resources.bind_native_handle(keys[1], event)
        prototype = C.WINFUNCTYPE(W.DWORD, C.c_void_p)

        @prototype
        def action(_):
            status = k.WaitForSingleObject(event, seconds * 1000)
            if status != 0:
                k.ExitProcess(exit_code)
            return 0

        k.CreateThread.argtypes = [
            C.c_void_p,
            C.c_size_t,
            prototype,
            C.c_void_p,
            W.DWORD,
            C.POINTER(W.DWORD),
        ]
        k.CreateThread.restype = W.HANDLE
        ident = W.DWORD()
        thread = calls.check(k.CreateThread(None, 0, action, None, 0, C.byref(ident)))
        item = self.watchdogs[keys]
        item.update(thread=thread, callback=action)
        self.port.resources.bind_native_handle(keys[0], thread)
        timer = {
            "owner": owner,
            "thread": ident.value,
            "handle": thread,
            "created": clock(),
        }
        item["timer"] = timer
        return copy.deepcopy(timer)

    def cancel_watchdog(self, timer):
        matches = [
            (keys, row)
            for keys, row in self.watchdogs.items()
            if row.get("timer") == timer and not row["closed"]
        ]
        need(len(matches) == 1, "ORIGINAL_CHILD_WATCHDOG_REQUIRED")
        keys, row = matches[0]
        calls = self.runtime.calls
        calls.check(calls.k.SetEvent(row["event"]))
        calls.wait(row["thread"], self.runtime.clock() + 10**9)
        for handle in (row["thread"], row["event"]):
            calls.close(handle)
            need(calls.closed(handle), "CHILD_WATCHDOG_HANDLE_NOT_CLOSED")
        self.done.update(keys)
        row["closed"] = True

    def closed(self, owner, key):
        return (
            owner == self.port.guard.owner and key in self.done
        ) or self.port.closed(owner, key)


class ChildRuntime:
    def __init__(self, *, files, calls, cim_api, pipes, clock_ns, interpreter=None):
        self.files, self.calls, self.cim_api, self.pipes, self.clock = (
            files,
            calls,
            cim_api,
            pipes,
            clock_ns,
        )
        self.descriptor = self.identity = self.lease = self.guard = None
        self.book = self.bootstrap_book = self.self_key = self.self_handle = None
        self.validated = False
        self.observer_batch = None
        self.interpreter = sys if interpreter is None else interpreter

    def verify_runtime(self, current):
        runtime = self.interpreter
        repo = ntpath.dirname(ntpath.dirname(BASE))
        base = ntpath.normcase(ntpath.normpath(runtime.base_prefix))
        need(
            base.startswith("d:\\")
            and ntpath.normcase(ntpath.normpath(runtime.executable))
            == ntpath.normcase(current["image"])
            and runtime.dont_write_bytecode is True
            and runtime.flags.no_user_site == 1,
            "EXACT_D_CHILD_RUNTIME_NO_USER_SITE_OR_BYTECODE",
        )
        allowed = (base, ntpath.normcase(repo))
        need(
            all(
                type(p) is str
                and ntpath.isabs(p)
                and any(
                    ntpath.normcase(ntpath.normpath(p)) == root
                    or ntpath.normcase(ntpath.normpath(p)).startswith(root + "\\")
                    for root in allowed
                )
                for p in runtime.path
            ),
            "CHILD_RUNTIME_IMPORT_PATH_ESCAPE",
        )
        for name, module in tuple(runtime.modules.items()):
            if (
                name == "app"
                or name.startswith("app.")
                or name == "scripts"
                or name.startswith("scripts.")
            ):
                path = getattr(module, "__file__", None)
                if path is not None:
                    need(
                        ntpath.normcase(ntpath.normpath(path))
                        in {ntpath.normcase(p) for p in self.descriptor["source_pins"]},
                        "UNPINNED_LOADED_CHILD_SOURCE_ORIGIN",
                    )

    def _cim(self, allocations):
        return BoundedCimQuery(
            CimProcessQuery(
                api=self.cim_api,
                allocations=allocations,
                clock_ns=self.clock,
                cancellation=True,
            ),
            CancellableCalls(
                calls=self.calls, allocations=allocations, clock_ns=self.clock
            ),
        )

    def inherited_identity(self, descriptor):
        self.descriptor = copy.deepcopy(descriptor)
        binding = descriptor["binding"]
        self.lease = InheritedBootstrapLease(descriptor["lease"], binding, self.clock)
        self.observer_batch = ObserverBatch(self.lease)
        self.book = self.bootstrap_book = AllocationBook(
            self.lease, self.lease.owner, self.files, self.clock
        )
        self.self_key, self.self_handle = self.book.open(
            lambda: self.calls.duplicate(self.calls.current(), self.calls.current())
        )
        allocations = NativeAllocations(
            self.observer_batch, self.lease.owner, namespace="child-observer"
        )
        observer = NativeProcessObserver(
            calls=self.calls,
            cim=self._cim(allocations),
            images=descriptor["images"],
            clock_ns=self.clock,
        )
        observer.parent, observer.job = descriptor["handles"][4:]
        identity = InheritedIdentity(
            observer=observer,
            current_handle=self.self_handle,
            parent_handle=observer.parent,
            job_handle=observer.job,
        )
        current = identity.verify(binding)
        need(
            ntpath.normcase(current["image"]) == ntpath.normcase(descriptor["argv"][0]),
            "INHERITED_DIRECT_INTERPRETER_REQUIRED",
        )
        self.verify_runtime(current)
        # The runtime image uses a retained parent lease and an independently
        # opened child read-only native handle; a path string alone is not a pin.
        pin = descriptor["images"].get(ntpath.normcase(current["image"]))
        need(pin is not None, "INHERITED_RUNTIME_IMAGE_PIN_REQUIRED")
        observed = self._source(current["image"], pin["sha256"])
        need(
            observed["file_id"] == list(pin["file_id"]),
            "INHERITED_RUNTIME_IMAGE_IDENTITY",
        )
        key, token = self.book.open(self.files.open_current_token)
        try:
            token_identity = self.files.token_identity(token)
            need(
                token_identity == {"sid": descriptor["sid"], "type": 1},
                "INHERITED_PRIMARY_TOKEN_SCOPE",
            )
        finally:
            self.book.close(key, token)
        self.identity = identity
        self.validated = True
        return identity

    def _source(self, path, expected):
        need(
            type(path) is str
            and ntpath.splitdrive(path)[0].casefold() == 'd:'
            and ntpath.normpath(path) == path,
            "CHILD_EXACT_D_SOURCE_PATH",
        )
        key, h = self.book.open(lambda: self.files.open_image(path))
        try:
            info = self.files.describe(h)
            raw = self.files.read(h, 32 * 1024**2)
            need(
                info["kind"] == "file"
                and info["links"] == 1
                and not info["reparse"]
                and ntpath.normcase(self.files.final_path(h)) == ntpath.normcase(path)
                and hashlib.sha256(raw).hexdigest() == expected,
                "CHILD_PINNED_SOURCE_NATIVE_READBACK",
            )
            result = {
                "path": path,
                "file_id": info["id"],
                "sha256": expected,
                "closed": True,
            }
        finally:
            self.book.close(key, h)
        return result

    def verify_source(self, path):
        need(path in self.descriptor["source_pins"], "CHILD_UNREVIEWED_SOURCE")
        return self._source(path, self.descriptor["source_pins"][path])

    def guard_factory(self, *, channel, owner, initial):
        need(
            self.validated and type(self.identity) is InheritedIdentity
            and body(self.identity.verify(channel.binding))==body(channel.binding['child'])
            and owner == digest(channel.binding["child"]),
            "CHILD_CURRENT_BOOTSTRAP_IDENTITY",
        )
        need(
            type(self.descriptor["root_bindings"]) is dict
            and set(self.descriptor["root_bindings"]) <= set(ROOTS),
            "EXACT_INHERITED_ROOT_BINDINGS",
        )
        remote = RemoteResources(
            channel,
            owner=owner,
            initial=initial,
            clock_ns=self.clock,
            proofs=RemoteHandleProofs(owner),
        )
        book = AllocationBook(remote, owner, self.files, self.clock)
        io = NativeIO(
            calls=self.files, book=book, sid=self.descriptor["sid"], clock_ns=self.clock
        )
        allocations = NativeAllocations(remote, owner)
        cim = self._cim(allocations)
        profile = {
            "session": channel.binding["session"],
            "executable": self.descriptor["argv"][0],
            "images": self.descriptor["images"],
            "source_pins": self.descriptor["source_pins"],
            "targets": self.descriptor["targets"],
            "accounts": channel.accounts,
        }
        context = SimpleNamespace(
            profile=profile,
            calls=self.calls,
            files=self.files,
            clock=self.clock,
            verify_source=self.verify_source,
        )
        output = SimpleNamespace(
            append=lambda value: self.guard.processes.emit_output(value)
        )
        endpoints = WindowsChildEndpoints(
            pipe_calls=self.pipes, clock_ns=self.clock, output=output
        )
        protocol = ChannelSessionProtocol(endpoints, self.clock, output)
        port = WindowsSessionPort(
            controller=context,
            resources=remote,
            io=io,
            cim=cim,
            allocations=allocations,
            protocol=protocol,
        )
        services = ChildServices(port, self)
        context.process_port = services
        self.identity.descendants = services.descendant_gateway.rows
        paths = FixturePaths(io)
        # These are creator-to-child transfers over the original private pipe,
        # not adoption of an arbitrary existing directory. Native ancestry/ACLs
        # and each creator identity must still match under retained IO handles.
        # Preserve BIND's exact reservation cut. Pre-ACK ancestry reads spend
        # the parent's already charged bootstrap escrow, not new RPC entries.
        startup_io = NativeIO(
            calls=self.files,
            book=self.bootstrap_book,
            sid=self.descriptor["sid"],
            clock_ns=self.clock,
        )
        startup_paths = FixturePaths(startup_io)
        try:
            parents = startup_paths.parent()
            for alias, row in self.descriptor["root_bindings"].items():
                paths._record(row, ROOTS[alias])
                need(
                    row["parent_id"] == parents[-1]["id"]
                    and startup_io.inspect(ROOTS[alias]) == row,
                    "INHERITED_ROOT_NATIVE_IDENTITY_CHANGED",
                )
                paths.bound[alias] = copy.deepcopy(row)
        finally:
            startup_io.close_cache()
        roster = WorkerOwnership(remote, all_members=port.all_members)
        guard = FixtureGuard(
            resources=remote,
            paths=paths,
            ownership=roster,
            owner=owner,
            io=io,
            processes=services,
            clock_ns=self.clock,
        )
        port.bind_guard(guard)
        self.guard = guard
        services.streams = ChildSessionIO(guard, clock_ns=self.clock)
        self.book = book
        self.lease.seal(retained=(self.self_key, *self.observer_batch.slots))
        guard.bootstrap_export=self.lease.evidence
        return guard

    def run(self, handles, nonce, *, runner=None):
        try:
            channel, descriptor = InheritedChannel.open(
                handles=handles,
                nonce=nonce,
                pipes=self.pipes,
                identity_factory=self.inherited_identity,
                clock_ns=self.clock,
            )
            self.verify_source(ntpath.join(ntpath.dirname(__file__), 'aip06_launch_roles.py'))
            from scripts.observation_runtime.aip06_launch_roles import launch_role
            ENTRY = ntpath.join(ntpath.dirname(__file__), 'aip06_acceptance_controller.py')
            if descriptor['argv'][2] == ENTRY:
                self.verify_source(ntpath.join(ntpath.dirname(__file__), 'aip06_controller_contract.py'))
            boot = ChildBootstrap(
                channel=channel,
                identity=self.identity,
                target=descriptor["argv"][2],
                source_pins=descriptor["source_pins"],
                verify_source=self.verify_source,
                guard_factory=self.guard_factory,
                clock_ns=self.clock,
                role=launch_role(descriptor['argv'], descriptor['targets']),
                controller_command=descriptor['argv'],
                controller_targets=descriptor['targets'],
            )
            boot.prepare()

            def execute(path):
                old = sys.argv
                try:
                    sys.argv = list(descriptor["argv"][2:])
                    if runner is not None:
                        return runner(path)
                    # Compile the same native-read bytes whose digest is pinned;
                    # never verify a path, close it, then runpy reread new bytes.
                    key, h = self.book.open(lambda: self.files.open_image(path))
                    try:
                        raw = self.files.read(h, 32 * 1024**2)
                        need(
                            hashlib.sha256(raw).hexdigest()
                            == descriptor["source_pins"][path],
                            "CHILD_TARGET_CHANGED_BEFORE_EXECUTION",
                        )
                        code = compile(raw, path, "exec")
                    finally:
                        self.book.close(key, h)
                    try:
                        exec(
                            code,
                            {
                                "__name__": "__main__",
                                "__file__": path,
                                "__package__": "",
                                "__spec__": None,
                                "__cached__": None,
                            },
                        )
                    except SystemExit as exc:
                        need(exc.code in (None, 0), "CHILD_TARGET_FAILED")
                    return {"exit_code": 0, "native_acceptance": False}
                finally:
                    sys.argv = old

            return boot.run(execute)
        finally:
            # Unknown locators are never closed as if they were owned. The
            # original parent's abort/Job path owns a failed pre-validation run.
            if self.validated:
                if self.guard is not None:
                    self.guard.io.close_cache()
                if self.self_key is not None:
                    self.bootstrap_book.close(self.self_key, self.self_handle)
                if self.observer_batch is not None:
                    self.observer_batch.finish()
                for h in reversed(handles):
                    self.calls.close(h)
                    need(self.calls.closed(h), "INHERITED_CHILD_HANDLE_NOT_CLOSED")


def main(argv=None, environ=None, *, backend=None, clock_ns=time.perf_counter_ns):
    args = list(sys.argv[1:] if argv is None else argv)
    env = os.environ if environ is None else environ
    need(
        len(args) == 2
        and args[0] == "--inherited-session"
        and len(args[1]) == 32
        and set(args[1]) <= set("0123456789abcdef"),
        "AIP06_NATIVE_CHILD_LAUNCH_PORT_NOT_BOUND",
    )
    raw = env.get("ATLAS_AIP06_INHERITED_HANDLES", "")
    need(
        type(raw) is str
        and len(raw) <= 160
        and len(raw.split(",")) == 6
        and all(
            n.isascii() and n.isdecimal() and 0 < int(n) < 2**64 - 1
            for n in raw.split(",")
        ),
        "EXACT_INHERITED_SESSION_LOCATORS_REQUIRED",
    )
    handles = tuple(int(n) for n in raw.split(","))
    need(len(set(handles)) == 6, "INHERITED_HANDLES_MUST_BE_DISTINCT")
    if backend is None:
        from scripts.observation_runtime.aip06_windows_io import WindowsFileCalls
        from scripts.observation_runtime.aip06_windows_process import Win32ProcessCalls
        from scripts.observation_runtime.aip06_windows_cim import ComAPI
        from scripts.observation_runtime.aip06_pipe_transport import Win32PipeCalls

        calls = Win32ProcessCalls.load()
        backend = SimpleNamespace(
            calls=calls,
            files=WindowsFileCalls.load(),
            cim_api=ComAPI.load(),
            pipes=Win32PipeCalls(calls.k),
        )
    runtime = ChildRuntime(
        files=backend.files,
        calls=backend.calls,
        cim_api=backend.cim_api,
        pipes=backend.pipes,
        clock_ns=clock_ns,
        interpreter=getattr(backend, "interpreter", None),
    )
    return runtime.run(handles, args[1])
