"""Concrete retained Windows launch/session port; inert until guard.spawn.

No native loader, CLI, approval or discovery/adoption path. Transport endpoints
must be made from the session's prospectively reserved creation handles. Offline
tests inject Win32 responses into this same implementation.
"""

import copy
import hashlib
import ntpath
import secrets
from dataclasses import dataclass, field
from subprocess import list2cmdline

from app.services.paper_financial_replay import body, digest

from scripts.observation_runtime.aip06_harness import (
    BASE,
    LIMITS,
    ROOTS,
    SCOPE_HASH,
    need,
)
from scripts.observation_runtime.aip06_ipc import MAX_IPC_NS
from scripts.observation_runtime.aip06_windows_process import NativeProcessObserver, SuspendedLaunchFailure
from scripts.observation_runtime.launch_ownership import LaunchRequest


def raw_handle(h):
    h = h.value if hasattr(h, "value") else h
    need(type(h) is int and 0 < h < 2**64 - 1, "SESSION_ORIGINAL_HANDLE_REQUIRED")
    return h


@dataclass
class Session:
    name: str
    plan: dict
    permit: dict
    keys: tuple
    argv: tuple
    options: dict
    observer: object
    native: dict = field(default_factory=dict)
    released: set = field(default_factory=set)
    job: int | None = None
    parent_handle: int | None = None
    image_handle: int | None = None
    launch_handle: int | None = None
    runtime_handle: int | None = None
    thread: int | None = None
    channel: object = None
    receipt: dict | None = None
    binding: object = None
    suspended: bool = True
    target_released: bool = False
    failed: bool = False
    closed: bool = False
    creation_native: dict | None = None
    creation_attempted: bool = False


class NativeSessionFactory:
    """Binds the controller's actual IO/CIM/budget ports to its launch port.

    Protocol owns framing/endpoint construction, not process creation. Its
    prepare method receives this session's reserved-handle allocator. It cannot
    receive a blanket success callback in place of retained process evidence.
    """

    def __init__(self, protocol, *, stop_factory=None):
        need(
            protocol is not None
            and type(protocol.resource_kinds) is tuple
            and all(k in ("pipe", "thread", "handle") for k in protocol.resource_kinds),
            "EXPLICIT_RESERVED_SESSION_PROTOCOL",
        )
        self.protocol = protocol
        self.requires_aggregate = bool(getattr(getattr(protocol, 'endpoints', None), 'requires_aggregate', False))
        need(
            stop_factory is None or callable(stop_factory),
            "EXPLICIT_STOP_FACTORY_REQUIRED",
        )
        self.stop_factory = stop_factory

    def __call__(self, controller, resources, io, cim, allocations):
        if self.requires_aggregate:
            from scripts.observation_runtime.aip06_job_budget import AggregateJobBudget
            need(type(getattr(controller, 'aggregate', None)) is AggregateJobBudget
                 and controller.aggregate.job is not None and not controller.aggregate.failed,
                 'PHYSICAL_SESSIONS_REQUIRE_AGGREGATE_ENVELOPE')
        port = WindowsSessionPort(
            controller=controller,
            resources=resources,
            io=io,
            cim=cim,
            allocations=allocations,
            protocol=self.protocol,
        )
        port.stop_assembly = (
            None if self.stop_factory is None else self.stop_factory(port)
        )
        return port


class WindowsSessionPort:
    """One exact direct launch per declared role; original handles retained.

    All resources are reserved by FixtureGuard before create_suspended. Failure
    cleanup operates only on this session's retained Job/handles; it never uses
    a PID to reopen or terminate a process. A failed session never becomes PASS.
    """

    BASE_KINDS = ("job", "handle", "image", "thread")

    def __init__(self, *, controller, resources, io, cim, allocations, protocol):
        self.controller, self.resources, self.io = controller, resources, io
        self.calls, self.files, self.clock = (
            controller.calls,
            controller.files,
            controller.clock,
        )
        self.cim, self.allocations_port, self.protocol = cim, allocations, protocol
        self.executable = controller.profile["executable"]
        self.pinned_images = copy.deepcopy(controller.profile['images'])
        self.guard = None
        self.plans, self.sessions, self.preallocated = {}, [], {}
        self.current_plan_nonce = None
        self.closed_proofs = set()
        self.failed = False
        self.stop_assembly = None
        self.aggregate = getattr(controller, 'aggregate', None)
        self.native_queries = None
        self.descendant_gateway = None
        self.ownership_probes = None

    def ownership_probe(self, case, *, deadline_ns):
        """Current supervisor and unexpected-child cut; no launch authority."""
        try:
            return self._ownership_probe(case, deadline_ns=deadline_ns)
        except BaseException:
            self.failed = self.guard.failed = True
            raise

    def _ownership_probe(self, case, *, deadline_ns):
        if self.ownership_probes is None:
            from scripts.observation_runtime.aip06_cleanup_providers import CimTables
            from scripts.observation_runtime.aip06_ownership_probes import OwnershipProbes
            from scripts.observation_runtime.aip06_windows_process import CancellableCalls
            runner = self.controller.legacy_probes
            need(runner is not None, 'OWNERSHIP_PROBE_OUTPUT_NOT_BOUND')
            path = ntpath.join(ntpath.dirname(__file__), 'aip06_ownership_probes.py')
            self.controller.verify_source(path)
            worker = CancellableCalls(calls=self.calls, allocations=self.allocations_port, clock_ns=self.clock)
            tables = CimTables(api=self.controller.cim_api, allocations=self.allocations_port,
                               worker=worker, clock_ns=self.clock)
            self.ownership_probes = OwnershipProbes(self, tables, runner.output)
        return self.ownership_probes.collect(case, deadline_ns=deadline_ns)

    def native_query(self, argv, *, timeout, maximum_bytes=65536):
        need(self.native_queries is not None, 'BOUNDED_NATIVE_QUERY_EXECUTOR_NOT_BOUND')
        try:
            return self.native_queries.execute(argv, timeout=timeout, maximum_bytes=maximum_bytes)
        except BaseException:
            self.failed = self.guard.failed = True
            raise

    def legacy_probe(self, root, cases):
        from scripts.observation_runtime.aip06_outputs import LegacyProbeAdapter
        need(getattr(self.controller,'legacy_probes',None) is not None,
             'NATIVE_LEGACY_CONTROLLER_PORT_NOT_BOUND')
        return LegacyProbeAdapter(self.controller,self.controller.legacy_probes.output).run(root,cases)

    def query_result(self, child, *, timeout, maximum_bytes):
        """Compatibility readback for a guarded, pinned Python query target.

        System netstat uses native_query directly; no READY is invented for it.
        """
        need(child.plan['name'] == 'query' and 0 < timeout <= 6
             and type(maximum_bytes) is int and 0 < maximum_bytes <= 65536,
             'EXACT_QUERY_READBACK_REQUIRED')
        identity = child.identity()
        stdout,stderr = self.communicate(child.child,None,timeout=timeout,maximum_bytes=maximum_bytes)
        code = self.returncode(child.child)
        need(len(stdout.encode()) + len(stderr.encode()) <= maximum_bytes
             and code == 0,
             'BOUNDED_QUERY_OUTPUT_AND_EXIT_REQUIRED')
        child.close()
        return {'stdout':stdout,'stderr':stderr,'exit_code':0,'identity':identity,'closed':True}

    def bind_guard(self, guard):
        need(
            self.guard is None
            and guard.resources is self.resources
            and guard.io is self.io,
            "SESSION_EXACT_GUARD_BINDING",
        )
        self.guard = guard

    def verify_test_source(self, module):
        from scripts.observation_runtime.aip06_test_driver import SELECTION

        need(module in SELECTION, "EXACT_REVIEWED_TEST_SOURCE")
        path = ntpath.join(
            ntpath.dirname(ntpath.dirname(BASE)), module.replace("/", "\\")
        )
        return self.controller.verify_source(path)

    def owned_stop_spec(self, *args):
        need(self.stop_assembly is not None, "OWNED_STOP_ASSEMBLY_REQUIRED")
        sample = args[0]
        if self.aggregate is not None and sample in (2,3):
            self.aggregate.rearm(sample)
        return self.stop_assembly.spec(*args)

    def financial_ready(self, *args, **kwargs):
        need(self.stop_assembly is not None, "OWNED_STOP_ASSEMBLY_REQUIRED")
        return self.stop_assembly.ready(*args, **kwargs)

    def send_stop(self, *args, **kwargs):
        need(self.stop_assembly is not None, "OWNED_STOP_ASSEMBLY_REQUIRED")
        return self.stop_assembly.send(*args, **kwargs)

    def collect_stop(self, *args, **kwargs):
        need(self.stop_assembly is not None, "OWNED_STOP_ASSEMBLY_REQUIRED")
        return self.stop_assembly.collect(*args, **kwargs)

    def _role(self, argv):
        ENTRY = ntpath.join(ntpath.dirname(ntpath.dirname(BASE)), 'scripts', 'observation_runtime', 'aip06_acceptance_controller.py')
        if len(argv) >= 3 and argv[2] == ENTRY:
            self.controller.verify_source(ntpath.join(ntpath.dirname(__file__), 'aip06_controller_contract.py'))
            from scripts.observation_runtime.aip06_controller_contract import ControllerIntent
            intent = getattr(self, 'controller_intent', None)
            need(type(intent) is ControllerIntent, 'EXPLICIT_CONTROLLER_INTENT_BEFORE_CREATION')
            try:
                return intent.claim(self, argv)
            except BaseException:
                self.failed = self.guard.failed = True
                raise
        need(
            len(argv) >= 3 and argv[0] == self.executable and argv[1] == "-B",
            "PINNED_DIRECT_D_COMMAND",
        )
        race=getattr(self,'race_roles',None)
        if race is not None and len(argv)>=3 and argv[2] in {
                self.controller.profile['targets'].get('race_one'),
                self.controller.profile['targets'].get('race_two')}:
            return race.claim(argv)
        matches = [
            name
            for name, path in self.controller.profile["targets"].items()
            if path == argv[2]
            and name not in {s.name for s in self.sessions if not s.closed}
        ]
        need(len(matches) == 1, "EXACT_UNAMBIGUOUS_DECLARED_TARGET")
        return matches[0]

    def declare_race_pair(self, commands):
        try:
            self.controller.verify_source(ntpath.join(ntpath.dirname(__file__),'aip06_race_roles.py'))
            from scripts.observation_runtime.aip06_race_roles import declare_pair
            return declare_pair(self,commands)
        except BaseException:
            self.failed=self.guard.failed=True
            raise

    def plan(self, argv, options):
        need(
            self.guard is not None and not self.failed and type(options) is dict,
            "BOUND_HEALTHY_SESSION_PORT_REQUIRED",
        )
        self.guard.check()
        need(self.aggregate is None or not self.aggregate.dormant, 'FRESH_SAMPLE_ENVELOPE_REQUIRED_BEFORE_LAUNCH')
        scoped = getattr(self, 'scoped_case', None)
        if scoped is not None:
            scoped.admit(argv)
        inherited = getattr(self, 'inherited_case_scope', None)
        if inherited is not None:
            from scripts.observation_runtime.aip06_scoped_context import verify_inherited_scope, forward_scope
            inherited = forward_scope(inherited, self.guard)
            verify_inherited_scope(inherited, {'binding':{'parent':self.resources.state['owners'][self.guard.owner]},
                'source_pins':self.controller.profile['source_pins'], 'targets':self.controller.profile['targets'],
                'argv':list(argv)})
        name = self._role(argv)
        need(
            set(options)
            <= {"env", "cwd", "stdin", "stdout", "stderr", "text", "bufsize"}
            and options.get("cwd", self.controller.profile.get("cwd"))
            in (None, ntpath.dirname(ntpath.dirname(ntpath.dirname(__file__)))),
            "NO_UNDECLARED_LAUNCH_OPTIONS",
        )
        target = argv[2]
        self.controller.verify_source(target)
        nonce = options.get("env", {}).get(
            "ATLAS_SYNTHETIC_STOP_NONCE"
        ) or secrets.token_hex(16)
        command = self.protocol.command(tuple(argv), options, nonce=nonce)
        need(
            type(command) is tuple and command and command[0] == self.executable,
            "EXACT_PROTOCOL_BOOTSTRAP_COMMAND",
        )
        pin = self.controller.profile["images"][ntpath.normcase(self.executable)]
        image = (ntpath.normcase(self.executable), tuple(pin["file_id"]), pin["sha256"])
        self.controller.verify_source(ntpath.join(ntpath.dirname(__file__), 'aip06_launch_roles.py'))
        from scripts.observation_runtime.aip06_launch_roles import launch_role
        request = LaunchRequest(
            launch_role(argv, self.controller.profile['targets']),
            nonce,
            "direct",
            image,
            image,
            list2cmdline(command),
            list2cmdline(command),
        )
        request.validate()
        parent = self.resources.state["owners"][self.guard.owner]
        observer = NativeProcessObserver(
            calls=self.calls,
            cim=self.cim,
            images=self.controller.profile["images"],
            clock_ns=self.clock,
        )
        limits = {
            k: LIMITS[k]
            for k in ("processes", "private_bytes", "child_private_bytes", "cpu_ns")
        }
        limits["kill_on_close"] = True
        plan = {
            "name": name,
            "request": request,
            "parent_owner": self.guard.owner,
            "api": observer,
            "parent_handle": None,
            "job_limits": limits,
            "resource_kinds": self.BASE_KINDS + self.protocol.resource_kinds,
        }
        need(
            len(plan["resource_kinds"]) <= 64 and "pipe" in plan["resource_kinds"],
            "SESSION_ALLOCATION_COUNT",
        )
        self.plans[nonce] = {
            "plan": plan,
            "argv": tuple(argv),
            "command": command,
            "options": copy.deepcopy(options),
            "parent": parent,
            'case_scope':scoped.wire() if scoped is not None else copy.deepcopy(inherited),
        }
        self.current_plan_nonce = nonce
        return plan

    def command_line(self, argv, options):
        current = self.plans.get(self.current_plan_nonce)
        need(
            current is not None
            and current["argv"] == tuple(argv)
            and current["options"] == options,
            "ONE_CURRENT_EXACT_LAUNCH_PLAN",
        )
        return list2cmdline(current["command"])

    def preallocate(self, plan, keys):
        nonce = plan["request"].nonce
        need(
            nonce == self.current_plan_nonce
            and nonce not in self.preallocated
            and len(keys) == len(plan["resource_kinds"]),
            "SESSION_PREALLOCATE_ONCE",
        )
        for key, kind in zip(keys, plan["resource_kinds"], strict=True):
            need(
                self.resources.state["resources"].get(key)
                == {"owner": self.guard.owner, "kind": kind, "closed": False},
                "PROSPECTIVE_NATIVE_SESSION_RESERVATION",
            )
        self.preallocated[nonce] = tuple(keys)

    def _claim(self, session, kind, handle):
        h = raw_handle(handle)
        available = [
            k
            for k in session.keys
            if k not in session.native
            and self.resources.state["resources"][k]["kind"] == kind
        ]
        need(
            available and h not in {v["handle"] for v in session.native.values()},
            "RESERVED_UNIQUE_NATIVE_ALLOCATION",
        )
        key = available[0]
        session.native[key] = {"kind": kind, "handle": h}
        return h

    def allocate(self, session, kinds, create):
        """Check all tickets before a Windows API may allocate even one handle."""
        need(any(retained is session for retained in self.sessions) and not session.failed,
             "KNOWN_NATIVE_SESSION")
        for kind in set(kinds):
            need(
                sum(
                    self.resources.state["resources"][k]["kind"] == kind
                    and k not in session.native
                    for k in session.keys
                )
                >= kinds.count(kind),
                "RESERVE_BEFORE_NATIVE_ALLOCATION",
            )
        result = create()
        handles = (result,) if len(kinds) == 1 else tuple(result)
        need(len(handles) == len(kinds), "NATIVE_ALLOCATION_ARITY")
        return tuple(
            self._claim(session, kind, h)
            for kind, h in zip(kinds, handles, strict=True)
        )

    def create_suspended(self, plan, permit, argv, options):
        nonce = plan["request"].nonce
        p = self.plans[nonce]
        need(
            tuple(argv) == p["argv"]
            and options == p["options"]
            and plan is p["plan"]
            and self.guard.ownership.prepared.get(plan["name"]) == permit
            and nonce in self.preallocated,
            "EXACT_RESERVED_SUSPENDED_LAUNCH",
        )
        s = Session(
            plan["name"],
            plan,
            copy.deepcopy(permit),
            self.preallocated[nonce],
            tuple(argv),
            copy.deepcopy(options),
            plan["api"],
        )
        self.sessions.append(s)
        try:
            s.job = self.allocate(
                s,
                ("job",),
                lambda: self.calls.create_job(
                    "Local\\Atlas-AIP06-" + nonce, plan["job_limits"]
                ),
            )[0]
            s.parent_handle = self.allocate(
                s,
                ("handle",),
                lambda: self.calls.duplicate(
                    self.calls.current(), self.calls.current()
                ),
            )[0]
            s.observer.job, s.observer.parent = s.job, s.parent_handle
            parent = s.observer.observe(s.parent_handle)
            need(
                body(parent) == body(p["parent"]),
                "CURRENT_PARENT_CHANGED_BEFORE_LAUNCH",
            )
            plan["parent_handle"] = s.parent_handle
            s.image_handle = self.allocate(
                s, ("image",), lambda: self.files.open_image(self.executable)
            )[0]
            pin = self.controller.profile["images"][ntpath.normcase(self.executable)]
            image = self.files.describe(s.image_handle)
            need(
                image["id"] == list(pin["file_id"])
                and not image["reparse"]
                and image["links"] == 1
                and hashlib.sha256(
                    self.files.read(s.image_handle, 32 * 1024**2)
                ).hexdigest()
                == pin["sha256"],
                "RETAINED_LAUNCH_IMAGE_CHANGED",
            )
            launch = self.protocol.prepare(s, self)
            need(
                type(launch) is dict
                and set(launch)
                == {
                    "environment",
                    "cwd",
                    "inherit_handles",
                    "stdin",
                    "stdout",
                    "stderr",
                }
                and set(launch["inherit_handles"])
                <= {r["handle"] for r in s.native.values()}
                and all(
                    launch[k] in launch["inherit_handles"]
                    for k in ("stdin", "stdout", "stderr")
                ),
                "EXACT_OWNED_INHERITANCE_AND_STDIO",
            )
            need(
                launch["cwd"] == ntpath.dirname(ntpath.dirname(BASE))
                and type(launch["environment"]) is dict
                and all(
                    not launch["environment"].get(k)
                    for k in (
                        "ATLAS_PERSONAL_NATIVE_TEST_APPROVAL",
                        "ATLAS_SYNTHETIC_INSTALL_SCOPE",
                        "ATLAS_SYNTHETIC_INSTALL_SCOPE_SHA256",
                    )
                ),
                "SESSION_WORKSPACE_AND_NO_OLD_AUTHORITY",
            )
            need(
                any(
                    k not in s.native
                    and self.resources.state["resources"][k]["kind"] == "thread"
                    for k in s.keys
                )
                and len(permit["slots"]) == 1
                and self.resources.state["resources"].get(permit["slots"][0])
                == {"owner": self.guard.owner, "kind": "launch", "closed": False},
                "ORIGINAL_PROCESS_AND_THREAD_RESERVATIONS",
            )
            # The launch slot was charged by WorkerOwnership.prepare before
            # this call. There is exactly one direct process, never adoption.
            if self.descendant_gateway is not None:self.descendant_gateway.before_create(s)
            s.creation_attempted = True
            try:
                process, thread, pid, tid = self.calls.create_suspended(
                    executable=self.executable, argv=p["command"], **launch
                )
            except SuspendedLaunchFailure as exc:
                if exc.created is None:
                    # This concrete API reports a known failure before creation.
                    # Unknown third-party/injected failures retain the refusal.
                    s.creation_attempted = False
                else:
                    process, thread, _, _ = exc.created
                    s.launch_handle = s.runtime_handle = raw_handle(process)
                    s.creation_native = copy.deepcopy(self.calls.native(s.launch_handle))
                    s.thread = self._claim(s, "thread", thread)
                raise
            s.launch_handle = s.runtime_handle = raw_handle(process)
            s.thread_id = tid
            s.thread = self._claim(s, "thread", thread)
            native = self.calls.native(s.launch_handle)
            s.creation_native = copy.deepcopy(native)
            need(
                type(pid) is int
                and native["pid"] == pid
                and type(tid) is int
                and tid > 0,
                "CREATED_PROCESS_HANDLE_PID_CONFLICT",
            )
            if self.aggregate is not None:
                self.aggregate.attach_created(handle=s.launch_handle, job=s.job, native=native)
            self.calls.assign(s.job, s.launch_handle)
            need(
                self.calls.in_job(s.launch_handle, s.job)
                and self.calls.members(s.job) == {pid},
                "SUSPENDED_JOB_MEMBERSHIP",
            )
            if self.descendant_gateway is not None:self.descendant_gateway.after_create(s)
            return s
        except BaseException:
            s.failed = True
            self.failed = True
            self.abort(s, deadline_ns=self.clock() + 8 * 10**9)
            raise

    def verify_suspended_job(self, child, plan):
        need(
            child in self.sessions
            and child.suspended
            and child.plan is plan
            and not child.failed,
            "KNOWN_SUSPENDED_SESSION",
        )
        return {
            "limits": self.calls.job_limits(child.job),
            "members": sorted(self.calls.members(child.job)),
            "suspended": True,
            "handle": child.job,
        }

    def resume(self, child):
        self.verify_suspended_job(child, child.plan)
        if self.descendant_gateway is None:self.calls.resume(child.thread)
        else:self.descendant_gateway.resume(child)
        child.suspended = False

    def ready(self, child, *, timeout, maximum_bytes):
        need(not child.suspended and not child.failed, "RESUMED_BOOTSTRAP_ONLY")
        observed = child.observer.observe(child.launch_handle)
        need(
            observed["parent_pid"]
            == self.resources.state["owners"][self.guard.owner]["pid"],
            "CHILD_ANCESTRY",
        )
        return self.protocol.ready(
            child, observed, timeout=timeout, maximum_bytes=maximum_bytes
        )

    def attach_guards(self, child, guard, name, keys):
        need(
            guard is self.guard and child.name == name and tuple(keys) == child.keys,
            "SESSION_GUARD_ATTACHMENT",
        )
        child.binding = guard.ownership.bindings[name]
        child.binding.verify()
        if self.aggregate is not None:
            self.aggregate.bind_retained(child.binding, handle=child.runtime_handle, job=child.job)
        from scripts.observation_runtime.aip06_ipc import RemoteResources
        if type(self.resources) is RemoteResources:
            self.resources.register_descendant_channel(child.channel.channel.binding)
            snapshot=copy.deepcopy(self.resources.snapshot)
        else:
            snapshot = self.resources.read()
        child.receipt = self.protocol.bind(
            child,
            snapshot=snapshot,
            roots=dict(ROOTS),
            source_pins=self.controller.profile["source_pins"],
            target=child.argv[2],
        )

    def allocations(self, child):
        need(set(child.native) == set(child.keys), "ALL_NATIVE_SESSION_TICKETS_BOUND")
        return copy.deepcopy(child.native)

    def guard_receipt(self, child):
        return copy.deepcopy(child.receipt)

    def verify_case_host_scope(self, child):
        from scripts.observation_runtime.aip06_scoped_context import CaseContext
        case = getattr(self, 'scoped_case', None)
        need(type(case) is CaseContext and case.factory.pending is case
             and case.guard is self.guard and not case.closed and not case.failed
             and type(case.reservation) is dict
             and case.reservation.get('held') is True
             and case.reservation.get('stop_capacity_reserved') is True,
             'ORIGINAL_HELD_CASE_HOST_SCOPE_REQUIRED')
        reservation = case.reservation
        state = self.guard.ledger('read')['state']
        need(state['resources'].get(reservation['key']) ==
             {'owner': self.guard.owner, 'kind': 'directory', 'closed': False},
             'ORIGINAL_CASE_HOST_DIRECTORY_RESERVATION_STILL_HELD')
        nonce = child.plan['request'].nonce
        recorded = self.plans.get(nonce)
        need(child in self.sessions and not child.closed and not child.failed
             and not child.suspended and not child.target_released
             and recorded is not None and recorded['plan'] is child.plan
             and recorded['argv'] == tuple(child.argv)
             and recorded['case_scope'] == case.wire()
             and recorded['parent'] == self.resources.state['owners'][self.guard.owner]
             and child.binding is self.guard.ownership.bindings.get('case_host')
             and child.binding.request is child.plan['request']
             and child.receipt is not None
             and child.receipt.get('guarded') is True
             and child.receipt.get('nonce') == nonce
             and child.receipt.get('owner') == digest(child.binding.runtime),
             'ORIGINAL_CASE_HOST_RELEASE_PLAN_REQUIRED')
        return None

    def release_target(self, child):
        need(
            child.binding is not None
            and not child.target_released
            and not child.failed,
            "BOUND_TARGET_ONCE_ONLY",
        )
        child.binding.verify()
        if child.name == 'case_host':
            self.verify_case_host_scope(child)
        expected = {
            "scope": SCOPE_HASH,
            "nonce": child.plan["request"].nonce,
            "owner": digest(child.binding.runtime),
            "reservation_head": child.receipt.get("reservation_head"),
            "guarded": True,
        }
        need(child.receipt == expected, "EXACT_CHILD_GUARD_RECEIPT")
        self.protocol.release(
            child,
            receipt=digest(child.receipt),
            target=child.argv[2],
            sha256=self.controller.profile["source_pins"][child.argv[2]],
        )
        child.target_released = True

    def deliver_case_host_input(self, child, handoff, *, deadline_ns):
        """One owner-held, authenticated INPUT after the original guarded release.

        This transports data only. It cannot authorize native case execution.
        """
        from scripts.observation_runtime.aip06_scoped_context import CaseContext
        case = getattr(self, 'scoped_case', None)
        need(type(case) is CaseContext and case.guard is self.guard
             and case.factory.pending is case and not case.closed and not case.failed,
             'ORIGINAL_CASE_HOST_INPUT_OWNER_REQUIRED')
        need(any(session is child for session in self.sessions)
             and child.name == 'case_host' and child.target_released and not child.failed and not child.closed
             and not child.suspended and child.binding is not None
             and child.channel is not None,
             'RELEASED_ORIGINAL_CASE_HOST_INPUT_CHILD_REQUIRED')
        need(not getattr(child, 'case_host_input_sent', False),
             'CASE_HOST_INPUT_REPLAY_REFUSED')
        need(type(deadline_ns) is int and self.clock() < deadline_ns,
             'CASE_HOST_INPUT_DEADLINE_EXPIRED')
        self.verify_case_host_input_binding(child)
        expected = case.physical_host_handoff(case.reservation, deadline_ns=deadline_ns)
        # Recheck original Stop reservation immediately before sending.
        self.verify_case_host_input_binding(child)
        need(type(handoff) is dict and handoff == expected,
             'ORIGINAL_CASE_HOST_INPUT_PACKET_REQUIRED')
        # Mark before I/O: a failed/partial send cannot be replayed.
        child.case_host_input_sent = True
        try:
            self.protocol.send_case_host_input(child, handoff, deadline_ns=deadline_ns)
        except BaseException:
            child.failed = True
            self.failed = True
            # The original retained child/Job handles are the only cleanup
            # authority. Never rediscover a child by PID after INPUT failure.
            try:
                self.abort(child, deadline_ns=deadline_ns)
            except BaseException as cleanup_error:
                self.case_host_input_cleanup_failure = str(cleanup_error)
            raise
        return None

    def verify_case_host_input_binding(self, child):
        self.verify_case_host_scope_after_release(child)

    def verify_case_host_scope_after_release(self, child):
        # Release verification already ran; retain its exact session/receipt
        # identity without reusing its pre-release-only predicate.
        case = self.scoped_case
        need(type(case.reservation) is dict
             and case.reservation.get('held') is True
             and case.reservation.get('stop_capacity_reserved') is True
             and self.guard.ledger('read')['state']['resources'].get(case.reservation['key']) ==
             {'owner': self.guard.owner, 'kind': 'directory', 'closed': False},
             'ORIGINAL_CASE_HOST_INPUT_STOP_RESERVATION_REQUIRED')
        nonce = child.plan['request'].nonce
        recorded = self.plans.get(nonce)
        need(recorded is not None and recorded['plan'] is child.plan
             and recorded['argv'] == tuple(child.argv)
             and recorded['case_scope'] == case.wire()
             and recorded['parent'] == self.resources.state['owners'][self.guard.owner]
             and child.binding is self.guard.ownership.bindings.get('case_host')
             and child.binding.request is child.plan['request']
             and child.receipt is not None and child.receipt.get('guarded') is True
             and child.receipt.get('nonce') == nonce
             and child.receipt.get('owner') == digest(child.binding.runtime),
             'ORIGINAL_RELEASED_CASE_HOST_INPUT_BINDING_REQUIRED')

    def all_members(self):
        if self.aggregate is not None:
            if self.aggregate.dormant:
                self.aggregate.observe_closed(commit=False)
                return set()
            self.aggregate._controller()
            members = self.calls.members(self.aggregate.job)
            need(self.aggregate.controller['pid'] in members,
                 'AGGREGATE_CONTROLLER_MISSING_FROM_JOB_ROSTER')
            return members - {self.aggregate.controller['pid']}
        result = set()
        for s in self.sessions:
            if s.job is not None:
                members = self.calls.members(s.job)
                need(not s.closed or not members,
                     'CLOSED_SESSION_JOB_STILL_HAS_DESCENDANTS')
                need(not result.intersection(members), "SESSION_JOB_ALIAS")
                result.update(members)
        return result

    def returncode(self, child):
        state = self.calls.lifecycle(child.launch_handle)
        known = (
            child.binding.runtime
            if child.binding is not None
            else self.calls.native(child.launch_handle)
        )
        need(
            state["pid"] == known["pid"] and state["created"] == known["created"],
            "RETAINED_EXIT_BIRTH_CHANGED",
        )
        return state["exit_code"] if state["exited"] else None

    def wait(self, child, *, timeout):
        self.calls.wait(child.launch_handle, self.clock() + int(timeout * 10**9))
        return self.returncode(child)

    def communicate(self, child, value, *, timeout, maximum_bytes):
        end = self.clock() + int(timeout * 10**9)
        try:
            output = self.protocol.communicate(
                child, value, deadline_ns=end, maximum_bytes=maximum_bytes
            )
            self.calls.wait(child.launch_handle, end)
            need(self.returncode(child) is not None, "CHILD_TERMINATION_MISSING")
            return output
        except BaseException:
            self.refuse_current_launch()
            raise

    def _close(self, s, key):
        h = s.native[key]["handle"]
        if key not in s.released:
            self.calls.close(h)
            need(self.calls.closed(h), "SESSION_HANDLE_CLOSE_UNVERIFIED")
            s.released.add(key)
            self.closed_proofs.add((self.guard.owner, key))

    def close_owned_handles(self, child, keys):
        need(any(retained is child for retained in self.sessions),
             'ORIGINAL_RETAINED_CLOSE_SESSION_REQUIRED')
        need(type(keys) in (tuple, list) and len(keys) == len(set(keys))
             and all(type(key) is str for key in keys),
             'UNIQUE_TYPED_CLOSE_RESOURCE_KEYS_REQUIRED')
        need(all(key in keys for key in child.permit['slots']),
             'EXACT_RETAINED_PROCESS_SLOT')
        need(all(key in child.native for key in child.keys),
             'RETAINED_NATIVE_HANDLE_BEFORE_CLEANUP')
        need(
            child.binding is not None
            and child.binding.finished
            and not self.calls.members(child.job),
            "VERIFIED_EXIT_BEFORE_HANDLE_CLOSE",
        )
        if self.descendant_gateway is not None:self.descendant_gateway.release(child)
        self.protocol.close(child, deadline_ns=self.clock() + MAX_IPC_NS)
        if self.aggregate is not None:
            self.aggregate.exited(child.binding, handle=child.runtime_handle)
        for key in reversed(child.keys):
            self._close(child, key)
        for key in child.permit["slots"]:
            need(key in keys, "EXACT_RETAINED_PROCESS_SLOT")
            self.calls.close(child.launch_handle)
            need(self.calls.closed(child.launch_handle), "PROCESS_HANDLE_NOT_CLOSED")
            self.closed_proofs.add((digest(child.binding.runtime), key))
        child.closed = True

    def verify_budget(self):
        if self.aggregate is not None:
            return self.aggregate.observe()

    def closed(self, owner, key):
        if (owner, key) in self.closed_proofs:
            return True
        for observer in (
            self.io,
            getattr(self.io, "book", None),
            self.allocations_port,
            self.protocol if hasattr(self.protocol, "closed") else None,
        ):
            if observer is not None and observer.closed(owner, key) is True:
                return True
        return False

    def resources_closed(self, child, keys):
        need(any(retained is child for retained in self.sessions),
             'ORIGINAL_RETAINED_RESOURCE_CLOSE_PROOF_REQUIRED')
        return child.closed and all(
            self.closed(self.resources.state["resources"][k]["owner"], k) for k in keys
        )

    def exchange_reader(self, reader, value, *, deadline_ns):
        reader.identity()
        need(reader.plan["name"] == "readonly_reader", "READ_ONLY_EXACT_CHILD_REQUIRED")
        return self.protocol.exchange_reader(
            reader.child, value, deadline_ns=deadline_ns
        )

    def ack_reader(self, reader, request, financial):
        reader.identity()
        need(
            reader.plan["name"] == "readonly_reader", "RETAINED_READER_RECEIPT_REQUIRED"
        )
        self.protocol.ack_reader(reader.child, request, financial)

    def abort(self, child, *, deadline_ns):
        """Retain unresolved handles if termination/close cannot be verified."""
        need(any(retained is child for retained in self.sessions),
             'ORIGINAL_RETAINED_ABORT_SESSION_REQUIRED')
        child.failed = True
        self.failed = True
        if child.launch_handle is not None:
            life = self.calls.lifecycle(child.launch_handle)
            if child.creation_native is not None:
                need(
                    life["pid"] == child.creation_native["pid"]
                    and life["created"] == child.creation_native["created"],
                    "ABORT_ORIGINAL_PROCESS_BIRTH_MISMATCH",
                )
            if not life["exited"]:
                if child.job is not None and self.calls.in_job(
                    child.launch_handle, child.job
                ):
                    self.calls.terminate_owned_job(child.job)
                else:
                    need(
                        child.creation_native is not None,
                        "ORIGINAL_CREATED_PROCESS_IDENTITY_MISSING",
                    )
                    self.calls.terminate_created(
                        child.launch_handle, child.creation_native
                    )
            self.calls.wait(child.launch_handle, deadline_ns)
            after = self.calls.lifecycle(child.launch_handle)
            need(after['exited'] is True and child.creation_native is not None
                 and after['pid'] == child.creation_native['pid']
                 and after['created'] == child.creation_native['created'],
                 'ABORT_ORIGINAL_PROCESS_EXIT_NOT_INDEPENDENTLY_VERIFIED')
            need(not self.calls.members(child.job), "ABORT_JOB_NOT_EMPTY")
        self.protocol.close(child, deadline_ns=deadline_ns)
        for key in reversed(tuple(child.native)):
            self._close(child, key)
        if child.launch_handle is not None:
            self.calls.close(child.launch_handle)
            need(self.calls.closed(child.launch_handle), "ABORT_PROCESS_HANDLE_OPEN")
        child.closed = True

    def refuse_current_launch(self):
        self.failed = True
        deadline = min(
            self.clock() + 8 * 10**9,
            self.resources.state["started_ns"] + LIMITS["seconds"] * 10**9,
        )
        for child in reversed(self.sessions):
            if not child.closed:
                self.abort(child, deadline_ns=deadline)


class ChannelSessionProtocol:
    """Actual Channel handshake/release/Stop transport over owned endpoints.

    Endpoint construction is a separate Windows IO boundary, supplied with the
    reserved allocator; it cannot launch, discover/adopt processes or return
    ownership booleans. All received data passes Channel's identity/chain gate.
    """

    def __init__(self, endpoints, clock_ns, output):
        self.endpoints, self.clock, self.output = endpoints, clock_ns, output
        self.resource_kinds = endpoints.resource_kinds

    def command(self, argv, options, *, nonce):
        return self.endpoints.command(argv, options, nonce=nonce)

    def prepare(self, child, port):
        return self.endpoints.prepare(child, port)

    def ready(self, child, observed, *, timeout, maximum_bytes):
        child.channel = self.endpoints.channel(child, observed)
        result = child.channel.receive(
            deadline_ns=self.clock() + min(timeout * 10**9, MAX_IPC_NS),
            expected_kind="HELLO",
        )["payload"]
        need(
            type(result) is dict
            and set(result) == {"pid", "nonce", "role"}
            and result
            == {
                "pid": observed["pid"],
                "nonce": child.plan["request"].nonce,
                "role": child.plan['request'].role,
            },
            "SESSION_HELLO_IDENTITY",
        )
        return result

    def bind(self, child, *, snapshot, roots, source_pins, target):
        end = self.clock() + MAX_IPC_NS
        child.channel.send(
            "BIND",
            {
                "snapshot": snapshot,
                "roots": roots,
                "source_pins": source_pins,
                "target": target,
                "nonce": child.plan["request"].nonce,
            },
            deadline_ns=end,
        )
        # Resource RPCs must be serviced by the endpoint's bounded broker while
        # the child installs its guard; an ACK cannot bypass that installation.
        return self.endpoints.receive_guard_receipt(
            child, snapshot=snapshot, deadline_ns=end
        )

    def release(self, child, **payload):
        child.channel.send("RELEASE", payload, deadline_ns=self.clock() + MAX_IPC_NS)

    def communicate(self, child, value, **limits):
        return self.endpoints.communicate(child, value, **limits)

    def close(self, child, *, deadline_ns):
        return self.endpoints.close(child, deadline_ns=deadline_ns)

    def closed(self, owner, key):
        return self.endpoints.closed(owner,key)

    def send_case_host_input(self, child, packet, *, deadline_ns):
        """Original authenticated channel only; no secondary transport."""
        from scripts.observation_runtime.aip06_ipc import MAX_IPC_NS
        need(type(packet) is dict and packet.get('schema') ==
             'AIP06_PHYSICAL_CASE_HOST_HANDOFF_V1',
             'CASE_HOST_INPUT_SCHEMA_REQUIRED')
        end = min(deadline_ns, self.clock() + MAX_IPC_NS)
        need(self.clock() < end, 'CASE_HOST_INPUT_DEADLINE_EXPIRED')
        child.channel.send('INPUT', packet, deadline_ns=end)

    def exchange_reader(self, child, value, *, deadline_ns):
        child.channel.send(
            "INPUT", value, deadline_ns=min(deadline_ns, self.clock() + MAX_IPC_NS)
        )
        for _ in range(16):
            payload = child.channel.receive(
                deadline_ns=min(deadline_ns, self.clock() + MAX_IPC_NS),
                expected_kind="OUTPUT",
            )["payload"]
            if (
                type(payload) is dict
                and payload.get("schema") == "AIP06_CHILD_OUTPUT_V1"
            ):
                need(
                    payload.get("owner") == digest(child.binding.runtime),
                    "READER_OUTPUT_OWNER_CONFLICT",
                )
                if payload.get("stream") != "stdout":
                    continue
                payload = payload.get("value")
            if type(payload) is dict and set(payload) == {"request", "financial"}:
                return payload
        raise ValueError("READER_FINANCIAL_RESPONSE_MISSING")

    @staticmethod
    def phase_payload(child, payload, phase):
        if type(payload) is dict and payload.get("schema") == "AIP06_CHILD_OUTPUT_V1":
            need(
                payload.get("owner") == digest(child.binding.runtime),
                "WORKER_OUTPUT_OWNER_CONFLICT",
            )
            if payload.get("stream") != "stdout":
                return None
            payload = payload.get("value")
        if type(payload) is not dict or payload.get("phase") != phase:
            return None
        row = child.binding.runtime
        observed = payload.get("identity", {})
        need(
            payload.get("timing_channel") == child.plan["request"].nonce
            and observed.get("pid") == row["pid"]
            and observed.get("creation_filetime") == row["created"]
            and ntpath.normcase(observed.get("image", ""))
            == ntpath.normcase(row["image"]),
            "WORKER_PHASE_IDENTITY_CONFLICT",
        )
        return payload

    def financial_ready(self, child, *, timeout):
        need(
            type(timeout) in (int, float) and 0 < timeout <= 40,
            "ORIGINAL_FINANCIAL_READY_DEADLINE",
        )
        end = self.clock() + int(timeout * 10**9)
        for _ in range(128):
            payload = child.channel.receive(deadline_ns=end, expected_kind="OUTPUT")[
                "payload"
            ]
            result = self.phase_payload(child, payload, "READY")
            if result is not None:
                return result
        raise ValueError("FINANCIAL_READY_MISSING")

    def ack_reader(self, child, request, financial):
        child.channel.send(
            "ACK",
            {
                "schema": "AIP06_READER_RECEIVED_V1",
                "request": digest(request),
                "financial": digest(financial),
                "reader": digest(child.binding.runtime),
                "financial_verified": False,
            },
            deadline_ns=self.clock() + MAX_IPC_NS,
        )

    def readback_input(self, child, request, *, deadline_ns):
        need(
            body(request["worker"]) == body(child.binding.runtime),
            "READBACK_STOP_WORKER_CONFLICT",
        )
        for frame in reversed(getattr(child.channel, "saved_outputs", ())):
            payload = self.phase_payload(child, frame["payload"], "READBACK")
            if payload is not None:
                now = self.clock()
                need(
                    now < deadline_ns and 0 <= now - frame["sent_ns"] <= MAX_IPC_NS,
                    "STALE_NATIVE_READBACK_INPUT",
                )
                return copy.deepcopy(payload["value"])
        raise ValueError("GENUINE_NATIVE_READBACK_INPUT_MISSING")
