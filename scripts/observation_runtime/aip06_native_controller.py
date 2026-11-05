"""AIP06 Windows fixture composition. Inert until initialize is explicitly called.

No installed runtime, provider, account enrollment, default command, CLI or
execution consent. A future single-use native plan must pin these source files
and the exact D: runtime before selecting the explicit Windows backends.
"""

import copy
import hashlib
import ntpath
import threading

from app.services.paper_financial_replay import body, digest, strict

from scripts.observation_runtime.aip06_fixture_guard import (
    CreateNewJournal,
    FixtureGuard,
)
from scripts.observation_runtime.aip06_harness import (
    ROOTS,
    SCOPE_HASH,
    BootstrapReservation,
    FixturePaths,
    SharedResources,
    WorkerOwnership,
    need,
    path_for,
)
from scripts.observation_runtime.native_fixture_budget import reserve_budget


class BootstrapBudget:
    """Bounded pre-journal escrow. Never returns a fabricated durable ACK.

    An absent journal directory cannot journal its own creation beforehand.
    All initial allocations are charged here, then imported by the FIRST real
    journal event. Existing/partial roots refuse; no restart adopts this escrow.
    """

    def __init__(self, clock_ns):
        self.clock = clock_ns
        self.owner = "BOOTSTRAP_UNBOUND"
        self.started = clock_ns()
        self.sealed = False
        self._state = {
            "owners": {},
            "resources": {},
            "stops": {},
            "mode": "WORK",
            "entries": 0,
            "charged_bytes": 0,
        }
        self.released = set()

    @property
    def state(self):
        return copy.deepcopy(self._state)

    def read(self):
        need(
            not self.sealed
            and self.started <= self.clock() <= self.started + 30 * 10**9,
            "BOOTSTRAP_WINDOW",
        )
        return {
            "domain": "PRE_JOURNAL_ESCROW_NOT_DURABLE_EVIDENCE",
            "state": self.state,
        }

    def reserve(self, owner, key, kind, *, entries=0, size=0, cleanup=False):
        self.read()
        need(
            owner == self.owner and key not in self._state["resources"] and not cleanup,
            "BOOTSTRAP_RESOURCE_OWNER",
        )
        need(
            kind in ("file", "directory", "handle", "image", "thread", "pipe", "job"),
            "BOOTSTRAP_RESOURCE_KIND",
        )
        if kind in ("file", "directory"):
            self._state.update(
                reserve_budget(
                    {k: self._state[k] for k in ("entries", "charged_bytes")},
                    entries=entries,
                    size=size,
                    unit=4096,
                    max_entries=64,
                    max_bytes=1024**2,
                )
            )
        else:
            need(
                entries == size == 0 and len(self._state["resources"]) < 128,
                "BOOTSTRAP_NATIVE_ALLOCATION_CAP",
            )
        self._state["resources"][key] = {"owner": owner, "kind": kind, "closed": False}

    def close(self, owner, key, *, observer):
        self.read()
        need(
            self._state["resources"][key]["owner"] == owner
            and observer.closed(owner, key) is True,
            "BOOTSTRAP_RELEASE",
        )
        self._state["resources"][key]["closed"] = True

    def bind_owner(self, owner):
        self.read()
        need(self.owner == "BOOTSTRAP_UNBOUND", "BOOTSTRAP_OWNER_ONCE")
        self.owner = digest(owner)
        self._state["owners"][self.owner] = strict(body(owner))
        for r in self._state["resources"].values():
            r["owner"] = self.owner
        return self.owner

    def seal(self, owner):
        self.read()
        need(digest(owner) == self.owner, "BOOTSTRAP_OWNER_PROOF")
        self.sealed = True
        return BootstrapReservation(
            SCOPE_HASH,
            copy.deepcopy(owner),
            self._state["entries"],
            self._state["charged_bytes"],
            self.started,
            copy.deepcopy(self._state["resources"]),
        )


class NativeAllocations:
    """Prospective lifetime tickets for explicit COM/thread/image allocations."""

    def __init__(self, resources, owner, *, namespace="native"):
        self.resources, self.owner, self.namespace = resources, owner, namespace
        self.serial = 0
        self.live = set()
        self.done = set()
        self.native_keys = set()
        self.lock = threading.RLock()

    def reserve(self, label, kind):
        with self.lock:
            self.serial += 1
            key = f"{self.namespace}:{self.owner}:{label}:{self.serial}"
            cleanup = self.resources.state["mode"] == "STOP" or any(
                r["state"] == "PENDING" for r in self.resources.state["stops"].values()
            )
            self.resources.reserve(self.owner, key, kind, cleanup=cleanup)
            self.live.add(key)
            return key

    def release(self, ticket):
        with self.lock:
            need(ticket in self.live, "ONE_NATIVE_RELEASE_TICKET")
            self.live.remove(ticket)
            self.done.add(ticket)
            if hasattr(self.resources, 'defer_native_release') and ticket not in self.native_keys:
                self.resources.defer_native_release(self.owner, ticket)
            else:
                self.resources.close(self.owner, ticket, observer=self)

    def bind_native(self, ticket, handle):
        need(ticket in self.live and ticket not in self.native_keys, 'RESERVED_NATIVE_ALLOCATION_BINDING')
        if hasattr(self.resources, 'bind_native_handle'):
            self.resources.bind_native_handle(ticket,handle)
        self.native_keys.add(ticket)

    def closed(self, owner, key):
        return owner == self.owner and key in self.done


class NativeController:
    """Compose the actual IO, shared ledger, strict launch and evidence ports.

    Constructor receives concrete backends or injected Windows responses. It
    does not query Windows, create roots, start threads or launch processes.
    initialize is deliberately separate and is not called by offline tests.
    """

    def __init__(self, *, files, process_calls, cim_api, clock_ns, profile):
        need(
            type(profile) is dict
            and set(profile)
            == {"session", "executable", "images", "source_pins", "accounts", "targets"}
            and type(profile["session"]) is str
            and len(profile["session"]) == 32
            and set(profile["session"]) <= set("0123456789abcdef")
            and type(profile["executable"]) is str
            and profile["executable"].startswith("D:\\")
            and ntpath.normpath(profile["executable"]) == profile["executable"]
            and type(profile["source_pins"]) is dict
            and profile["source_pins"]
            and type(profile["targets"]) is dict
            and profile["targets"]
            and type(profile["images"]) is dict
            and profile["images"]
            and type(profile["accounts"]) is dict
            and profile["accounts"],
            "EXACT_NATIVE_CONTROLLER_PROFILE",
        )
        need(
            all(
                type(p) is str
                and p.startswith("D:\\")
                and ntpath.normpath(p) == p
                and type(h) is str
                and len(h) == 64
                and set(h) <= set("0123456789abcdef")
                for p, h in profile["source_pins"].items()
            )
            and all(
                type(k) is str
                and k
                in (
                    "financial_worker",
                    "readonly_reader",
                    "race_one",
                    "race_two",
                    "query",
                    "acceptance_controller",
                )
                and type(v) is str
                and v in profile["source_pins"]
                for k, v in profile["targets"].items()
            ),
            "EXACT_CONTROLLER_SOURCE_TARGET_PINS",
        )
        if 'acceptance_controller' in profile['targets']:
            from scripts.observation_runtime.aip06_controller_contract import ENTRY
            need(profile['targets']['acceptance_controller'] == ENTRY,
                 'ONLY_PINNED_ACCEPTANCE_CONTROLLER_TARGET')
        need(
            set(profile["accounts"]) <= {"QUALITY_DIPS", "HYPERLIQUID"}
            and all(
                type(v) is dict
                and set(v) == {"account_id", "epoch", "currency"}
                and all(type(x) is str and x for x in v.values())
                and v["currency"] == ("USD" if k == "QUALITY_DIPS" else "USDC")
                for k, v in profile["accounts"].items()
            ),
            "EXACT_CONTROLLER_ACCOUNT_SCOPE",
        )
        self.files, self.calls, self.cim_api, self.clock = (
            files,
            process_calls,
            cim_api,
            clock_ns,
        )
        self.profile = copy.deepcopy(profile)
        self.initialized = False
        self.failed = False
        self.guard = None
        self.book = None
        self.channels = {}
        self.children = []
        self.io = None
        self.process_port = self.process_allocations = self.cleanup = None
        self.precreation_receipt = None
        self.legacy_probes = None

    def bind_legacy_probes(self, output):
        self.require_ready()
        from scripts.observation_runtime.aip06_legacy_probe import LegacyProbeRunner
        need(self.legacy_probes is None and callable(getattr(output,'append',None)),
             'ONE_RETAINED_LEGACY_PROBE_BINDING')
        self.legacy_probes = LegacyProbeRunner(self,output)
        return self.legacy_probes

    def probe_case(self, name):
        self.require_ready()
        need(self.legacy_probes is not None,'RETAINED_LEGACY_PROBE_RUNNER_NOT_BOUND')
        return self.legacy_probes.run_case(name)

    def probe_supervisor(self, *, deadline_ns):
        self.require_ready()
        return self.process_port.ownership_probe('supervisor', deadline_ns=deadline_ns)

    def probe_unexpected_children(self, *, deadline_ns):
        self.require_ready()
        return self.process_port.ownership_probe('unexpected-child', deadline_ns=deadline_ns)

    def initialize(self, process_port_factory, *, aggregate_factory=None, precreation_intent=None):
        """Future explicitly authorized execution only. Never called offline."""
        need(
            callable(process_port_factory),
            "NATIVE_PROCESS_PORT_FACTORY_REQUIRED_BEFORE_MUTATION",
        )
        from scripts.observation_runtime.aip06_windows_cim import (
            BoundedCimQuery,
            CimProcessQuery,
        )
        from scripts.observation_runtime.aip06_windows_process import CancellableCalls
        from scripts.observation_runtime.aip06_windows_io import (
            AllocationBook,
            NativeIO,
            NativeJournalIO,
        )

        need(not self.initialized and not self.failed, "ONE_CREATE_NEW_CONTROLLER")
        if precreation_intent is not None:
            from scripts.observation_runtime.aip06_controller_contract import ControllerIntent
            need(type(precreation_intent) is ControllerIntent
                 and precreation_intent.plan()['source_pins'] == self.profile['source_pins']
                 and precreation_intent.plan()['executable'] == self.profile['executable'],
                 'EXACT_CREATE_NEW_CONTROLLER_INTENT_BEFORE_EFFECTS')
        if getattr(process_port_factory, 'requires_aggregate', False) and aggregate_factory is None:
            from scripts.observation_runtime.aip06_job_budget import AggregateJobBudget
            aggregate_factory = AggregateJobBudget
        self.failed = True
        need(callable(getattr(self.files, 'allocation_unit', None))
             and self.files.allocation_unit() == 4096, 'OBSERVED_D_ALLOCATION_UNIT_MUST_MATCH_4096_BEFORE_MUTATION')
        escrow = BootstrapBudget(self.clock)
        allocations = NativeAllocations(escrow, escrow.owner, namespace="bootstrap")
        cim = BoundedCimQuery(
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
        native = self.calls.native(self.calls.current())
        observed = cim.process(native["pid"], deadline_ns=self.clock() + 5 * 10**9)
        need(
            observed["pid"] == native["pid"]
            and observed["created"] // 10 == native["created"] // 10
            and ntpath.normcase(observed["image"])
            == ntpath.normcase(self.profile["executable"]),
            "CONTROLLER_NATIVE_CIM_IDENTITY",
        )
        pin = self.profile["images"].get(ntpath.normcase(native["image"]))
        need(
            type(pin) is dict and set(pin) == {"file_id", "sha256"},
            "CONTROLLER_IMAGE_PIN",
        )
        owner = {
            **observed,
            "created": native["created"],
            "image": native["image"],
            "file_id": tuple(pin["file_id"]),
            "sha256": pin["sha256"],
        }
        # Image verification reads an original read-only handle; not a PID claim.
        ticket = allocations.reserve("self-image", "image")
        image = self.files.open_image(self.profile["executable"])
        try:
            info = self.files.describe(image)
            raw = self.files.read(image, 32 * 1024**2)
            need(
                info["id"] == list(pin["file_id"])
                and hashlib.sha256(raw).hexdigest() == pin["sha256"],
                "CONTROLLER_IMAGE_INTEGRITY",
            )
        finally:
            self.files.close(image)
            need(self.files.closed(image), "CONTROLLER_IMAGE_CLOSE")
            allocations.release(ticket)
        token_ticket = allocations.reserve("self-token", "handle")
        token = self.files.open_current_token()
        try:
            token_identity = self.files.token_identity(token)
            need(token_identity["type"] == 1, "PRIMARY_CONTROLLER_TOKEN")
        finally:
            self.files.close(token)
            need(self.files.closed(token), "CONTROLLER_TOKEN_CLOSE")
            allocations.release(token_ticket)
        owner_key = escrow.bind_owner(owner)
        book = AllocationBook(escrow, owner_key, self.files, self.clock)
        self.book = book
        io = NativeIO(
            calls=self.files, book=book, sid=token_identity["sid"], clock_ns=self.clock
        )
        self.io = io
        paths = FixturePaths(io)
        if precreation_intent is not None:
            from scripts.observation_runtime.aip06_controller_contract import PrecreationReceipt
            self.precreation_receipt = PrecreationReceipt.capture(precreation_intent, paths=paths,
                clock_ns=self.clock, deadline_ns=escrow.started+30*10**9)
        intent = paths.prepare("E")
        escrow.reserve(owner_key, "bootstrap:E", "directory", entries=1)
        io.begin(owner_key, "bootstrap:E", "directory", ROOTS["E"])
        io.mkdir(ROOTS["E"])
        paths.bind_created(intent)
        escrow.close(owner_key, "bootstrap:E", observer=io)
        journal_path = path_for("E", "journal")
        paths.verify("E", "journal")
        escrow.reserve(owner_key, "bootstrap:journal", "directory", entries=1)
        io.begin(owner_key, "bootstrap:journal", "directory", journal_path)
        io.mkdir(journal_path)
        escrow.close(owner_key, "bootstrap:journal", observer=io)
        identity = io.inspect(journal_path)["id"]
        from scripts.observation_runtime.aip06_intrinsic_io import IntrinsicJournalIO

        book.intrinsic = IntrinsicJournalIO(
            owner=owner_key, clock_ns=self.clock, started_ns=escrow.started
        )
        journal = CreateNewJournal(NativeJournalIO(io, identity), identity)
        resources = SharedResources(
            journal,
            clock_ns=self.clock,
            bootstrap=escrow.seal(owner),
            intrinsic_io=book.intrinsic,
        )
        need(
            resources.register_owner(owner, controller=True) == owner_key,
            "DURABLE_BOOTSTRAP_OWNER",
        )
        book.resources = resources
        for source in self.profile["source_pins"]:
            self.verify_source(source)
        process_allocations = NativeAllocations(resources, owner_key)
        if aggregate_factory is not None:
            from scripts.observation_runtime.aip06_job_budget import AggregateJobBudget
            self.aggregate = aggregate_factory(
                calls=self.calls, resources=resources, allocations=process_allocations, clock_ns=self.clock
            )
            need(type(self.aggregate) is AggregateJobBudget, 'EXACT_AGGREGATE_JOB_PROVIDER_REQUIRED')
            self.aggregate.initialize()
        cim = BoundedCimQuery(
            CimProcessQuery(
                api=self.cim_api,
                allocations=process_allocations,
                clock_ns=self.clock,
                cancellation=True,
            ),
            CancellableCalls(
                calls=self.calls, allocations=process_allocations, clock_ns=self.clock
            ),
        )
        process_port = process_port_factory(
            self, resources, io, cim, process_allocations
        )
        roster = WorkerOwnership(resources, all_members=process_port.all_members)
        guard = FixtureGuard(
            resources=resources,
            paths=paths,
            ownership=roster,
            owner=owner_key,
            io=io,
            processes=process_port,
            clock_ns=self.clock,
        )
        process_port.bind_guard(guard)
        self.process_port, self.process_allocations = process_port, process_allocations
        self.guard, self.book, self.initialized, self.failed = guard, book, True, False
        return guard

    def bind_cleanup(self, *, ip_helper_dll, output, query_argv):
        """Wire concrete readers to the existing financial Stop assembly.

        No query or process runs here. The query target must be a reviewed
        guarded source (and still needs a concrete query-result implementation
        before native eligibility); a raw external-command fallback is forbidden.
        The aggregate root handle lifetime is deliberately NOT silently excluded
        from the original complete-release verifier.
        """
        self.require_ready()
        need(self.cleanup is None and getattr(self, 'aggregate', None) is not None,
             'ONE_AGGREGATE_NATIVE_CLEANUP_BINDING')
        from scripts.observation_runtime.aip06_native_query import ARGS, NativeQueryExecutor
        native_command = tuple(query_argv) == ARGS
        need(type(query_argv) in (list, tuple) and (native_command or (len(query_argv) >= 3
             and list(query_argv[:2]) == [self.profile['executable'], '-B']
             and query_argv[2] == self.profile['targets'].get('query'))),
             'EXACT_REVIEWED_SOCKET_QUERY_SOURCE')
        if native_command:
            from scripts.observation_runtime.aip06_pipe_transport import Win32PipeCalls
            need(self.process_port.native_queries is None,'ONE_NATIVE_QUERY_EXECUTOR')
            self.process_port.native_queries = NativeQueryExecutor(self.process_port,
                pipes=Win32PipeCalls(self.calls.k),output=output)
        from scripts.observation_runtime.aip06_cleanup_providers import (
            CimSockets, CimTables, GuardedNetstat, StrictProcessCleanup,
            TcpTables, ThreeReaderCleanup,
        )
        from scripts.observation_runtime.aip06_windows_process import CancellableCalls
        from scripts.observation_runtime.aip06_owned_stop import OwnedStopAssembly
        from scripts.observation_runtime.aip06_stop import GuardedStopCollector

        worker = CancellableCalls(calls=self.calls, allocations=self.process_allocations, clock_ns=self.clock)
        tables = CimTables(api=self.cim_api, allocations=self.process_allocations, worker=worker, clock_ns=self.clock)
        sockets = ThreeReaderCleanup(readers={
            'CIM': CimSockets(tables),
            'IP_HELPER': TcpTables(ip_helper_dll, worker=worker, clock_ns=self.clock),
            'NETSTAT': GuardedNetstat(self.guard, query_argv),
        }, port=self.process_port, output=output, clock_ns=self.clock)
        processes = StrictProcessCleanup(port=self.process_port, tables=tables, output=output, clock_ns=self.clock)
        collector = GuardedStopCollector(clock_ns=self.clock, output=output,
            sockets=sockets, processes=processes, close_io=self.close_native_io,
            finalize_resources=self.close_sample_envelope)
        need(self.process_port.stop_assembly is None, 'NO_REPLACE_EXISTING_STOP_ASSEMBLY')
        self.process_port.stop_assembly = OwnedStopAssembly(self.process_port, collector)
        self.cleanup = {'sockets': sockets, 'processes': processes, 'collector': collector}
        return collector

    def close_sample_envelope(self, *, deadline_ns):
        """Last action before the original complete-release Stop verifier.

        Original controller/Job query handles close; no persistent reservation
        is exempted. The next reviewed sample creates a fresh nested envelope
        and retains the same ledger, process CPU history and cumulative charges.
        """
        self.require_ready()
        need(self.guard.stop is not None and self.guard.stop.request is not None
             and deadline_ns == self.guard.stop.started + 8*10**9
             and self.clock() < deadline_ns, 'EXACT_SAMPLE_STOP_FINALIZATION')
        self.guard.io.close_cache()
        expected = {key for key,_ in self.aggregate.held}
        need(self.process_allocations.live == expected and not self.book.live
             and not self.book.journal_live, 'SAMPLE_NATIVE_ALLOCATION_LEAK')
        self.aggregate.close(deadline_ns=deadline_ns)
        need(not self.process_allocations.live and self.clock() <= deadline_ns,
             'SAMPLE_ENVELOPE_RELEASE_INCOMPLETE')

    def verify_source(self, path):
        """Read-only original-handle source pin; the handle is charged first."""
        need(
            self.book is not None
            and type(path) is str
            and path.startswith("D:\\")
            and ntpath.normpath(path) == path
            and path in self.profile["source_pins"],
            "EXPLICIT_D_RESIDENT_SOURCE_PIN_REQUIRED",
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
                and hashlib.sha256(raw).hexdigest()
                == self.profile["source_pins"][path],
                "SOURCE_PIN_OR_NATIVE_IDENTITY_MISMATCH",
            )
            result = {
                "path": path,
                "file_id": info["id"],
                "sha256": hashlib.sha256(raw).hexdigest(),
                "closed": False,
            }
        finally:
            self.book.close(key, h)
        result["closed"] = True
        return result

    def require_ready(self):
        need(
            self.initialized and self.guard is not None and not self.failed,
            "INITIALIZED_NATIVE_CONTROLLER_REQUIRED",
        )
        self.guard.check()

    def close_native_io(self):
        self.require_ready()
        self.guard.io.close_cache()
        need(not self.book.live and not self.book.journal_live, "CONTROLLER_IO_LEAK")

    def verify_probe_result(self, result):
        self.require_ready()
        need(self.legacy_probes is not None,'NATIVE_PROBE_RETAINED_EXIT_AND_RELEASE_PORT_NOT_BOUND')
        return self.legacy_probes.verify(result)
