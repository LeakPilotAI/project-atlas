"""Bounded acceptance orchestration; inert, no default native backend or grant.

The offline qualification entry uses injected process ports. The native entry
has a refusal-only authorization gate: no issuance, redemption or execution
capability exists here. Ports are trusted code dependencies, never manifest
callbacks. Original guarded adapters remain the sole process creation boundary.
"""

import copy
import hashlib
import ntpath
from dataclasses import dataclass
from subprocess import list2cmdline

from app.services.paper_financial_replay import body, digest, strict
from scripts.observation_runtime.aip06_acceptance_plan import decode_plan, schedule
from scripts.observation_runtime.aip06_harness import LIMITS, ROOTS, SCOPE_HASH, need
from scripts.observation_runtime.launch_ownership import RetainedLaunchBinding, identity

NS = 10**9
INJECTED = 'INJECTED_SOURCE_ONLY'
ROLES = ('financial_worker', 'readonly_reader', 'race_one', 'race_two', 'query')


@dataclass(frozen=True)
class Scenario:
    id: str
    roles: tuple
    seconds: int
    proof: str
    sample: int | None = None


def scenarios():
    """Exact manifest order and unchanged aggregate work budget (464 seconds).

    Remaining 76 work seconds cover preflight/bootstrap and final evidence;
    cleanup owns its separate 60-second reserve. Per-case inner deadlines in
    the guarded worker/IPC interfaces are still mandatory.
    """
    result = []
    for row in schedule():
        name = row['id']
        roles = ('race_one', 'race_two') if name == 'F04' else ('financial_worker',)
        if name == 'OWNERSHIP-PROBES': roles = ('financial_worker', 'query')
        if name.startswith('STOP-'): roles = ('financial_worker', 'readonly_reader')
        seconds = 48 if name.startswith('STOP-') else (60 if name == 'OWNERSHIP-PROBES' else 20)
        result.append(Scenario(name, roles, seconds, row.get('proof', 'complete-stop-and-cold-restart'), row.get('sample')))
    return tuple(result)


class RefusalOnlyAuthorization:
    """No approval can be created, consumed or converted from a JSON claim."""

    def require(self, supplied, *, manifest_sha256):
        need(supplied is not None, 'FRESH_SCOPED_SINGLE_USE_AUTHORIZATION_REQUIRED')
        if type(supplied) is dict:
            need(supplied.get('consumed') is not True, 'REUSED_AUTHORIZATION_REFUSED')
        raise ValueError('AUTHORIZATION_ISSUER_AND_ATOMIC_SINGLE_USE_REDEMPTION_NOT_BOUND')


@dataclass(frozen=True)
class OwnerLaunch:
    binding: RetainedLaunchBinding
    manifest_sha256: str
    session: object = None
    intent: object = None

    def verify(self, plan, pin):
        need(type(self.binding) is RetainedLaunchBinding and self.manifest_sha256 == pin,
             'ORIGINAL_RETAINED_CONTROLLER_LAUNCH_BINDING_REQUIRED')
        from scripts.observation_runtime.aip06_controller_contract import ControllerIntent, ROLE, bootstrap_argv
        from scripts.observation_runtime.aip06_native_session import Session
        need(type(self.intent) is ControllerIntent and self.intent.sha256 == pin and self.intent.plan() == plan
             and type(self.session) is Session and self.session.binding is self.binding
             and self.session.name == ROLE and self.session.plan['request'] is self.binding.request
             and self.session.argv == self.intent.argv and self.session.target_released
             and not self.session.suspended and not self.session.failed and not self.session.closed
             and self.session.launch_handle == self.binding.launch_handle
             and self.session.runtime_handle == self.binding.runtime_handle
             and self.session.parent_handle == self.binding.parent_handle,
             'EXACT_GUARDED_CONTROLLER_SESSION_AND_INTENT_REQUIRED')
        request = self.binding.request
        command = list2cmdline(bootstrap_argv(plan['executable'], request.nonce))
        need(request.role == 'acceptance_supervisor' and request.topology == 'direct'
             and ntpath.normcase(request.launch_image[0]) == ntpath.normcase(plan['executable'])
             and request.launch_command == self.binding.runtime['command_line'] == command,
             'EXACT_CONTROLLER_LAUNCH_ROLE_IMAGE_AND_COMMAND')
        need(self.session.receipt is not None and self.session.receipt.get('guarded') is True
             and self.session.receipt.get('scope') == SCOPE_HASH
             and self.session.receipt.get('nonce') == request.nonce
             and self.session.receipt.get('owner') == digest(self.binding.runtime)
             and type(self.session.receipt.get('reservation_head')) is str and len(self.session.receipt['reservation_head']) == 64,
             'CONTROLLER_BOOTSTRAP_RECEIPT_REQUIRED')
        self.binding.verify()
        return identity(self.binding.parent), identity(self.binding.runtime)

    def preparation_packet(self, plan, pin):
        self.verify(plan, pin)
        packet = {'schema':'AIP06_CONTROLLER_PREPARE_V1','scope':SCOPE_HASH,'manifest':pin,
                'raw':self.intent.raw.decode('utf-8'),'nonce':self.binding.request.nonce,
                'owner':digest(self.binding.runtime),'parent_owner':digest(self.binding.parent)}
        need(len(body(packet).encode('utf-8')) <= 65536, 'CONTROLLER_INPUT_WITHIN_EXISTING_GUARD_CAP')
        return packet


class Deadline:
    def __init__(self, clock_ns):
        self.clock = clock_ns
        self.started = self.last = self.clock()
        need(type(self.started) is int and self.started >= 0, 'MONOTONIC_CLOCK_REQUIRED')
        self.work = self.started + LIMITS['work_seconds'] * NS
        self.dispatch = self.started + 524 * NS  # Leave the original final 16s.
        self.total = self.started + LIMITS['seconds'] * NS

    def now(self, limit):
        value = self.clock()
        need(type(value) is int and self.last <= value <= limit, 'BOUNDED_MONOTONIC_DEADLINE')
        self.last = value
        return value


def verify_bytes(plan, reader, deadline, *, deadline_ns):
    """Read-only pins, including EVERY file of the retained runtime snapshot.

    No stat/hash result is promoted to native identity or ACL clearance. Native
    preflight must independently hold the same files/roots while using them.
    """
    def read(path, maximum):
        deadline.now(deadline_ns)
        raw = reader.read_bytes(path, maximum_bytes=maximum, deadline_ns=deadline_ns)
        need(type(raw) is bytes and len(raw) <= maximum, 'BOUNDED_PIN_READ')
        deadline.now(deadline_ns)
        return raw

    for path, pin in plan['source_pins'].items():
        need(hashlib.sha256(read(path, 8 * 1024**2)).hexdigest() == pin, 'SOURCE_HASH_MISMATCH:' + path)
    ref = plan['runtime_inventory']
    raw = read(ref['path'], 16 * 1024**2)
    need(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'RUNTIME_INVENTORY_HASH_MISMATCH')
    inventory = strict(raw.decode('utf8'))
    need(inventory.get('schema') == 'AIP06_READONLY_RUNTIME_BYTES_V1'
         and inventory.get('runtime') == ntpath.dirname(plan['executable'])
         and type(inventory.get('records')) is list, 'EXACT_RUNTIME_INVENTORY')
    seen, files, directories, size, executable_sha256 = set(), 0, 0, 0, None
    for row in inventory['records']:
        path = row['path']
        need(type(path) is str and path and not ntpath.isabs(path) and ':' not in path
             and ntpath.normpath(path) == path and '/' not in path
             and all(p not in ('', '.', '..') and p[-1:] not in ('.', ' ') for p in path.split('\\'))
             and path.casefold() not in seen, 'DEPENDENCY_NAMESPACE_OR_COLLISION')
        seen.add(path.casefold())
        need(row.get('links') == 1 and row.get('kind') in ('file', 'directory'), 'ORDINARY_DEPENDENCY_REQUIRED')
        if row['kind'] == 'directory': directories += 1; continue
        need(type(row.get('size')) is int and 0 <= row['size'] <= ref['read_bytes'], 'DEPENDENCY_SIZE')
        raw = read(ntpath.join(inventory['runtime'], path), row['size'])
        need(len(raw) == row['size'] and hashlib.sha256(raw).hexdigest() == row.get('sha256'),
             'EXECUTABLE_OR_DEPENDENCY_HASH_MISMATCH:' + path)
        files += 1; size += len(raw)
        if ntpath.join(inventory['runtime'], path) == plan['executable']:
            executable_sha256 = row['sha256']
        need(size <= ref['read_bytes'], 'RUNTIME_READ_BUDGET')
    need((files, directories, size) == (ref['files'], ref['directories'], ref['read_bytes'])
         and 'python.exe' in seen, 'COMPLETE_RUNTIME_PIN_INVENTORY')
    need(executable_sha256 is not None, 'EXACT_EXECUTABLE_BYTES_REQUIRED')
    return {'files': files, 'directories': directories, 'bytes': size, 'executable_sha256': executable_sha256,
            'native_identity_accepted': False}


class GuardedScenarioBridge:
    """Adapter to the existing guard, NOT a raw-spawn implementation.

    A reviewed per-case binding must supply exact argv, prospective reservation,
    execution/fault/load and cleanup. None is supplied by default. No source
    case name is eval'd or imported to discover a financial entry point.
    """
    domain = 'GUARDED_NATIVE_BINDING_NOT_QUALIFIED'

    def __init__(self, controller, guard, bindings):
        self.controller, self.guard, self.bindings = controller, guard, dict(bindings)

    def check(self, scenario, *, deadline_ns):
        self.guard.check()
        need(self.guard.processes is self.controller.process_port, 'EXACT_GUARDED_PROCESS_PORT')
        need(scenario.id in self.bindings, 'NATIVE_FAULT_LOAD_CAPACITY_BINDING_MISSING:' + scenario.id)
        binding = self.bindings[scenario.id]
        need(binding.roles == scenario.roles and binding.source_pins == self.controller.profile['source_pins'],
             'EXACT_PINNED_CASE_ROLES_AND_IMPLEMENTATION')
        binding.check(self.controller, self.guard, deadline_ns=deadline_ns)
        return binding

    def reserve(self, scenario, *, deadline_ns):
        return self.check(scenario, deadline_ns=deadline_ns).reserve(self.guard, deadline_ns=deadline_ns)

    def execute(self, scenario, reservation, *, deadline_ns):
        binding = self.check(scenario, deadline_ns=deadline_ns)
        # Only existing guard.spawn/port declaration/credited IPC are available
        # to a binding. Exact race argv admission stays in declare_race_pair.
        return binding.execute(self.controller, self.guard, reservation, deadline_ns=deadline_ns)

    def release(self, scenario, reservation, evidence, *, deadline_ns):
        return self.check(scenario, deadline_ns=deadline_ns).release(
            self.guard, reservation, evidence, deadline_ns=deadline_ns)

    def abort(self, scenario, reservation, *, deadline_ns):
        # An interrupted reservation is not refunded on a missing receipt.
        self.guard.failed = True
        need(scenario.id in self.bindings, 'NO_UNKNOWN_ABORT_BINDING')
        return self.bindings[scenario.id].abort(self.guard, reservation, deadline_ns=deadline_ns)


class Dispatcher:
    """Serial, one-shot schedule. Failed reservation/cleanup burns the attempt."""

    def __init__(self, *, adapter, grader, deadline):
        self.adapter, self.grader, self.deadline = adapter, grader, deadline
        self.used, self.failure, self.pending, self.completed = set(), None, None, []
        self.tickets, self.cleanup_failure = set(), None

    def run(self):
        need(not self.used and self.failure is None, 'DISPATCH_ONCE_ONLY')
        try:
            # Fail before the first reservation if ANY scenario is unbound.
            for scenario in scenarios():
                self.adapter.check(scenario, deadline_ns=self.deadline.dispatch)
                self.deadline.now(self.deadline.dispatch)
            for scenario in scenarios():
                self.used.add(scenario.id)
                start = self.deadline.now(self.deadline.dispatch)
                end = min(start + scenario.seconds * NS, self.deadline.dispatch)
                self.pending = (scenario, None)
                reservation = self.adapter.reserve(scenario, deadline_ns=end)
                # Keep even an incomplete reservation for bounded owned cleanup.
                self.pending = (scenario, reservation)
                need(type(reservation) is dict and reservation.get('scenario') == scenario.id
                     and reservation.get('roles') == scenario.roles
                     and reservation.get('held') is True and reservation.get('stop_capacity_reserved') is True
                     and type(reservation.get('key')) is str and reservation['key']
                     and reservation.get('root') == ROOTS['E']
                     and type(reservation.get('commands')) is dict
                     and set(reservation['commands']) == set(scenario.roles)
                     and all(type(cmd) is tuple and len(cmd) >= 3 for cmd in reservation['commands'].values()),
                     'PROSPECTIVE_SHARED_RESOURCE_RESERVATION_REQUIRED')
                need(reservation['key'] not in self.tickets, 'RESOURCE_TICKET_REPLAY')
                need(all(cmd[0] == self.grader.plan['executable'] and cmd[1] == '-B'
                         and cmd[2] in self.grader.plan['source_pins'] for cmd in reservation['commands'].values()),
                     'ONLY_EXACT_PINNED_EXECUTABLE_AND_TARGET_COMMANDS')
                self.tickets.add(reservation['key'])
                result = self.adapter.execute(scenario, copy.deepcopy(reservation), deadline_ns=end)
                self.deadline.now(end)
                evidence = self.grader.qualify_offline(scenario, reservation, result, started_ns=start, deadline_ns=end)
                released = self.adapter.release(scenario, reservation, evidence, deadline_ns=end)
                need(released is True, 'COMPLETE_OWNED_RESOURCE_RELEASE_REQUIRED')
                evidence = self.grader.complete_release(scenario, reservation, result, evidence, deadline_ns=end)
                self.deadline.now(end)
                self.pending = None
                self.completed.append(evidence)
            self.grader.finish(self.completed)
            return copy.deepcopy(self.completed)
        except Exception as exc:
            self.failure = str(exc)
            if self.pending is not None:
                try:
                    self.deadline.now(self.deadline.total)
                    need(self.adapter.abort(*self.pending, deadline_ns=self.deadline.total) is True,
                         'DISPATCH_OWNED_ABORT_INCOMPLETE')
                    self.deadline.now(self.deadline.total)
                except Exception as cleanup:
                    self.cleanup_failure = str(cleanup)
            raise


class OuterOwner:
    """One-shot owner; only an injected qualification can enter the drive path.

    Adapter owns the original outer/controller launch handles, bounded Job,
    shared ledger and exact ancestry. Its preflight/launch/cleanup observations
    are independently graded. No OS loader, Popen or grant issuer is imported.
    """

    def __init__(self, raw, sha256, *, clock_ns, files, owner, dispatcher_factory):
        self.plan = decode_plan(raw, sha256)
        self.raw = raw
        self.pin, self.clock, self.files, self.owner = sha256, clock_ns, files, owner
        self.dispatcher_factory = dispatcher_factory
        self.started = self.failed = False
        self.failure = self.cleanup_failure = None

    def start(self, authorization=None):
        # ALWAYS before file/native queries or prospective mutation. This
        # source-only milestone cannot redeem even a seemingly valid grant.
        RefusalOnlyAuthorization().require(authorization, manifest_sha256=self.pin)

    def qualify_offline(self):
        need(not self.started, 'OUTER_OWNER_ONCE_ONLY')
        self.started = True
        need(self.owner.domain == INJECTED, 'OFFLINE_ENTRY_REQUIRES_INJECTED_PORTS')
        clock = Deadline(self.clock)
        preflight_end = clock.started + 60 * NS
        first = None
        try:
            need(self.plan == decode_plan(self.raw, self.pin), 'PLAN_MUTATED_AFTER_CONSTRUCTION')
            pins = verify_bytes(self.plan, self.files, clock, deadline_ns=preflight_end)
            # Native identity/ACL/async cuts are still separately mandatory in
            # a real run. An injected preflight is never authority for one.
            preflight = self.owner.preflight(copy.deepcopy(self.plan), manifest_sha256=self.pin, deadline_ns=preflight_end)
            need(type(preflight) is dict and preflight.get('domain') == INJECTED
                 and preflight.get('manifest') == self.pin and preflight.get('roots') == dict(ROOTS)
                 and preflight.get('roots_absent') is True and preflight.get('native_identity_and_acl_checks') is True
                 and preflight.get('async_socket_guard_compatible') is True
                 and preflight.get('network') == self.plan['network'], 'COMPLETE_ISOLATED_PREFLIGHT_REQUIRED')
            clock.now(preflight_end)
            reserved = self.owner.reserve(copy.deepcopy(dict(LIMITS)), deadline_ns=preflight_end)
            need(type(reserved) is dict and reserved.get('held') is True
                 and reserved.get('limits') == dict(LIMITS) and reserved.get('includes_outer_owner') is True
                 and reserved.get('stop_capacity_reserved') is True, 'SHARED_OUTER_OWNER_CAPACITY_REQUIRED')
            clock.now(preflight_end)
            first = self.owner.launch_controller(self.plan['entry'], self.plan['executable'], deadline_ns=preflight_end)
            need(type(first) is OwnerLaunch, 'TYPED_RETAINED_CONTROLLER_LAUNCH_REQUIRED')
            need(first.binding.request.launch_image[2] == pins['executable_sha256'],
                 'RETAINED_CONTROLLER_IMAGE_DIFFERS_FROM_PINNED_BYTES')
            first.verify(self.plan, self.pin)
            self.owner.verify_controller(first, deadline_ns=preflight_end)
            clock.now(preflight_end)
            dispatcher = self.dispatcher_factory(clock)
            need(dispatcher.adapter.domain == INJECTED and dispatcher.grader.domain == INJECTED,
                 'NO_NATIVE_BACKEND_IN_OFFLINE_QUALIFICATION')
            need(dispatcher.adapter.owner_launch is first and dispatcher.grader.owner_launch is first,
                 'ONE_RETAINED_OWNER_AND_SHARED_DISPATCHER_BINDING')
            result = dispatcher.run()
            clock.now(clock.work)
        except Exception as exc:
            self.failed, self.failure = True, str(exc)
            raise
        finally:
            try:
                clock.now(clock.total)
                need(self.owner.cleanup(first, deadline_ns=clock.total) is True, 'OUTER_OWNER_CLEANUP_INCOMPLETE')
                self.owner.verify_released(deadline_ns=clock.total)
                clock.now(clock.total)
            except Exception as exc:
                self.failed, self.cleanup_failure = True, str(exc)
                # Preserve first failure; later successful cleanup cannot pass.
                if self.failure is None: raise
        return {'status': 'SOURCE_CONTROL_PLANE_QUALIFIED', 'native_acceptance': False,
                'manifest_sha256': self.pin, 'pins': pins, 'scenarios': result}
