"""Concrete read-only Windows observations; no loaders, launcher or authority.

Uses the existing handle/CIM/Job/socket providers. Callers supply original
retained capabilities and a separately identified observer. No owner result
dictionary or PID lookup is accepted as independent evidence. Injected Windows
responses exercise these same methods offline; native grading remains closed.
"""

import copy
import hashlib
import ntpath

from app.services.paper_financial_replay import digest
from scripts.observation_runtime.aip06_acceptance_control import RefusalOnlyAuthorization
from scripts.observation_runtime.aip06_acceptance_grade import READERS
from scripts.observation_runtime.aip06_cleanup_providers import (
    CimSockets, GuardedNetstat, StrictProcessCleanup, TcpTables, ThreeReaderCleanup,
)
from scripts.observation_runtime.aip06_harness import LIMITS, ROOTS, SCOPE_HASH, need
from scripts.observation_runtime.aip06_windows_io import NativeOpenFailed
from scripts.observation_runtime.aip06_windows_process import bounded_observations
from scripts.observation_runtime.launch_ownership import RetainedLaunchBinding, identity

DOMAIN = 'WINDOWS_OBSERVER_ADAPTER_NOT_NATIVE_ACCEPTANCE_AUTHORITY'


class PinnedWindowsRead:
    """Account each original read-only handle; verify identity before/after read.

    Paths are closed pins, not an arbitrary file-reading service. Parent-chain
    and protected ACL validation must come from the native file port as well
    as final-path checking; this port performs no create/write/delete calls.
    """

    def __init__(self, *, files, allocations, clock_ns, sid, pins):
        need(type(pins) is dict and pins and type(sid) is str and sid, 'PINNED_WINDOWS_READ_SCOPE')
        self.files, self.allocations, self.clock, self.sid = files, allocations, clock_ns, sid
        self.pins = copy.deepcopy(pins)
        self.failed = False

    def read_bytes(self, path, *, maximum_bytes, deadline_ns):
        need(not self.failed and path in self.pins and path.startswith('D:\\')
             and ntpath.normpath(path) == path and type(maximum_bytes) is int
             and 0 <= maximum_bytes <= 32 * 1024**2 and self.clock() < deadline_ns,
             'EXACT_BOUNDED_PINNED_WINDOWS_READ')
        self.failed = True
        ticket = self.allocations.reserve('acceptance-read', 'image')
        handle = None
        complete = False
        failed_before_acquisition = False
        try:
            try:
                handle = self.files.open_image(path)
            except NativeOpenFailed:
                failed_before_acquisition = True
                raise
            before = self.files.describe(handle)
            need(before['kind'] == 'file' and before['reparse'] is False and before['links'] == 1
                 and before['id'] == self.pins[path]['file_id']
                 and before['bytes'] <= maximum_bytes and self.files.final_path(handle) == path,
                 'PINNED_NATIVE_FILE_IDENTITY_OR_NAMESPACE')
            self.files.acl(handle, self.sid)
            raw = self.files.read(handle, maximum_bytes)
            need(type(raw) is bytes and len(raw) == before['bytes'] and self.files.describe(handle) == before
                 and self.files.final_path(handle) == path and self.clock() < deadline_ns
                 and hashlib.sha256(raw).hexdigest() == self.pins[path]['sha256'],
                 'PINNED_NATIVE_FILE_CHANGED_OR_HASH_MISMATCH')
            complete = True
            return raw
        finally:
            if handle is not None:
                self.files.close(handle)
                need(self.files.closed(handle), 'PINNED_READ_ORIGINAL_HANDLE_NOT_CLOSED')
            # No handle was returned only when open failed before acquisition.
            if handle is not None or failed_before_acquisition:
                self.allocations.release(ticket)
            self.failed = not complete or self.clock() >= deadline_ns


class WindowsProcessEvidence:
    """Independent native/CIM observer, with retained birth/ancestry history.

    Capture MUST occur while live. Post-exit identity comes from the exact
    retained original handle, not a best-effort CIM query of an exited PID.
    Missing capture, closed originals or incomplete Jobs refuse.
    """

    def __init__(self, *, observer, reader_binding, clock_ns):
        need(type(reader_binding) is RetainedLaunchBinding, 'INDEPENDENT_READER_RETAINED_BINDING')
        self.observer, self.reader_binding, self.clock = observer, reader_binding, clock_ns
        self.admitted, self.failed = {}, False

    def check_reader(self, *, deadline_ns):
        with bounded_observations(deadline_ns):
            self.reader_binding.verify()
        current = self.observer.calls.native(self.observer.calls.current())
        expected = self.reader_binding.runtime
        need(all(current[k] == expected[k] for k in ('pid', 'created', 'image')),
             'OBSERVER_MUST_EXECUTE_IN_ITS_INDEPENDENT_RETAINED_PROCESS')
        return identity(expected)

    def capture(self, binding, *, deadline_ns):
        need(not self.failed and type(binding) is RetainedLaunchBinding and self.clock() < deadline_ns,
             'ORIGINAL_LIVE_BINDING_FOR_CAPTURE')
        self.failed = True
        reader = self.check_reader(deadline_ns=deadline_ns)
        need(reader != identity(binding.runtime) and reader != identity(binding.parent),
             'OWNER_CANNOT_SELF_CERTIFY_INDEPENDENT_EVIDENCE')
        with bounded_observations(deadline_ns):
            binding.verify()
            row = self.observer.observe(binding.runtime_handle)
            parent = self.observer.observe(binding.parent_handle)
        need(row == binding.runtime and parent == binding.parent and row['parent_pid'] == parent['pid']
             and row['created'] >= parent['created'] and self.clock() < deadline_ns,
             'INDEPENDENT_RETAINED_NATIVE_CIM_ANCESTRY_CONFLICT')
        key = digest(row)
        need(key not in self.admitted, 'ONCE_ONLY_INDEPENDENT_ADMISSION')
        self.admitted[key] = (binding, copy.deepcopy(row), copy.deepcopy(parent), self.clock())
        self.failed = False
        return {'identity': identity(row), 'parent': identity(parent), 'observer': reader, 'at_ns': self.clock()}

    def read(self, *, deadline_ns):
        need(not self.failed and self.clock() < deadline_ns, 'BOUNDED_CURRENT_PROCESS_EVIDENCE')
        self.failed = True
        reader = self.check_reader(deadline_ns=deadline_ns)
        rows = []
        for binding, row, parent, admitted_ns in self.admitted.values():
            actual = self.observer.calls.native(binding.runtime_handle)
            life = self.observer.calls.lifecycle(binding.runtime_handle)
            need(all(actual[k] == row[k] for k in ('pid', 'created', 'image')),
                 'ORIGINAL_NATIVE_HANDLE_BIRTH_CHANGED')
            if not life['exited']:
                with bounded_observations(deadline_ns):
                    need(self.observer.observe(binding.runtime_handle) == row, 'CURRENT_CIM_IDENTITY_CHANGED')
            rows.append({'identity': identity(row), 'parent': identity(parent), 'command_line': row['command_line'],
                         'admitted_ns': admitted_ns, 'lifecycle': life})
        need(self.clock() < deadline_ns, 'PROCESS_OBSERVATION_DEADLINE')
        self.failed = False
        return {'observer': reader, 'rows': rows, 'complete': True, 'domain': DOMAIN}


class WindowsJobEvidence:
    def __init__(self, *, calls, job, expected, limits, clock_ns):
        self.calls, self.job, self.expected, self.limits, self.clock = calls, job, tuple(expected), copy.deepcopy(limits), clock_ns

    def read(self, *, deadline_ns):
        need(self.clock() < deadline_ns and self.job is not None and self.expected, 'ORIGINAL_BOUNDED_JOB_EVIDENCE')
        before = self.calls.members(self.job)
        need(self.calls.job_limits(self.job) == self.limits, 'JOB_LIMITS_CHANGED')
        rows = []
        for handle, original in self.expected:
            need(self.calls.native(handle) == original, 'JOB_RETAINED_PROCESS_IDENTITY_CHANGED')
            if not self.calls.lifecycle(handle)['exited']:
                need(self.calls.in_job(handle, self.job), 'PROCESS_OUTSIDE_ORIGINAL_JOB')
                rows.append(original['pid'])
        accounting = self.calls.job_accounting(self.job)
        after = self.calls.members(self.job)
        need(before == after == set(rows) and accounting['active'] == len(rows) <= LIMITS['processes']
             and self.clock() < deadline_ns, 'UNKNOWN_OR_MISSING_JOB_MEMBER')
        return {'members': sorted(after), 'accounting': accounting, 'complete': True}


class WindowsCapacityEvidence:
    """Actual kernel counters plus a separately reopened immutable ledger.

    A headroom number is not a load/capacity test. This reader only reports the
    measured counters; the F11 load producer is a separate mandatory binding.
    """
    def __init__(self, *, calls, job_reader, processes, parent_handle, ledger_reader, clock_ns):
        self.calls, self.jobs, self.processes, self.ledger, self.clock = calls, job_reader, tuple(processes), ledger_reader, clock_ns
        need(sum(h == parent_handle for h, _ in self.processes) == 1, 'EXPLICIT_CAPACITY_PARENT_HANDLE')
        self.parent_handle = parent_handle

    def read(self, *, deadline_ns):
        job = self.jobs.read(deadline_ns=deadline_ns)
        private, cpu, peak = 0, 0, 0
        for handle, expected in self.processes:
            need(self.calls.native(handle) == expected, 'CAPACITY_ORIGINAL_HANDLE_IDENTITY')
            memory, used = self.calls.usage(handle)
            need(type(memory) is int and type(used) is int and memory >= 0 and used >= 0, 'NATIVE_USAGE_COUNTERS')
            need(memory <= (LIMITS['private_bytes'] if handle == self.parent_handle else LIMITS['child_private_bytes']),
                 'PER_PROCESS_PRIVATE_MEMORY_LIMIT')
            private += memory; cpu += used; peak = max(peak, memory)
        account = job['accounting']
        cpu = max(cpu, account['user_ns'] + account['kernel_ns'])
        need(private <= LIMITS['private_bytes']
             and cpu <= LIMITS['cpu_ns'] and self.clock() < deadline_ns, 'NATIVE_CAPACITY_EXCEEDED')
        ledger = self.ledger.read(deadline_ns=deadline_ns)
        need(ledger['scope'] == SCOPE_HASH and ledger['unknown'] is False
             and ledger['entries'] <= LIMITS['entries'] and ledger['charged_bytes'] <= LIMITS['bytes'],
             'INDEPENDENT_LEDGER_CAPACITY_CONFLICT')
        return {'job': job, 'private_bytes': private, 'cpu_ns': cpu, 'ledger': ledger,
                'load_acceptance': False}


class ColdLedgerEvidence:
    """Read-only replay with an independently held head; never a new ledger."""
    def __init__(self, *, journal, expected_head, process_evidence, clock_ns):
        self.journal, self.head, self.processes, self.clock = journal, expected_head, process_evidence, clock_ns

    def read(self, *, deadline_ns):
        from scripts.observation_runtime.aip06_harness import SharedResources
        observer = self.processes.check_reader(deadline_ns=deadline_ns)
        need(self.clock() < deadline_ns and type(self.head) is str and len(self.head) == 64,
             'INDEPENDENT_REPLAY_HEAD_AND_DEADLINE')
        readback = SharedResources(self.journal, clock_ns=self.clock, expected_head=self.head).read()
        state = readback['state']
        need(self.clock() < deadline_ns and readback['head'] == self.head, 'LEDGER_CHANGED_DURING_REOPEN')
        return {'scope': SCOPE_HASH, 'observer': observer, 'head': self.head, 'unknown': False,
                'entries': state['entries'], 'charged_bytes': state['charged_bytes'],
                'unreleased': sorted(k for k, v in state['resources'].items() if not v['closed'])}


class BootstrapObjectEvidence:
    def __init__(self, *, sources, process_evidence, clock_ns):
        from scripts.observation_runtime.aip06_bootstrap_evidence import BootstrapObjects
        need(type(sources) is tuple and sources and all(type(s) is BootstrapObjects for s in sources),
             'ORIGINAL_BOOTSTRAP_OBJECT_CAPABILITIES_REQUIRED')
        self.sources, self.processes, self.clock = sources, process_evidence, clock_ns

    def read(self, *, deadline_ns):
        observer = self.processes.check_reader(deadline_ns=deadline_ns)
        rows = []
        for source in self.sources:
            need(self.clock() < deadline_ns and not source.failed and source.cut is not None,
                 'MISSING_OR_FAILED_ORIGINAL_OBJECT_CAPTURE')
            if source.released:
                need(source.terminal is not None and not source.live
                     and all(source.closed(source.descriptor['parent_owner'], k) for k in source.descriptor['slots']),
                     'INCOMPLETE_NATIVE_OBJECT_RELEASE_HISTORY')
            else:
                source.verify()  # CompareObjectHandles, native type and current Job evidence.
            rows.append({'nonce': source.binding.request.nonce, 'released': source.released,
                         'open_slots': sorted(source.live), 'financial_ack': False})
        return {'observer': observer, 'rows': rows, 'native_acceptance': False}


class RetainedFinancialEvidence:
    """Preserve ACK/readback provenance; cached replies are explicitly labelled.

    This adapter does not claim that a retained response performs a new cold
    financial reopen. The original StopVerification still owns full accounting
    and source/projection/report/global verification before native acceptance.
    """
    def __init__(self, *, reply, request, process_evidence, clock_ns):
        from scripts.observation_runtime.aip06_stop import RetainedFinancialReply
        need(type(reply) is RetainedFinancialReply, 'TYPED_ORIGINAL_FINANCIAL_REPLY_REQUIRED')
        self.reply, self.request, self.processes, self.clock = reply, copy.deepcopy(request), process_evidence, clock_ns

    def read(self, *, deadline_ns):
        observer = self.processes.check_reader(deadline_ns=deadline_ns)
        need(self.clock() < deadline_ns and identity(self.reply.observer_identity) == observer,
             'FINANCIAL_REPLY_INDEPENDENT_READER_CONFLICT')
        financial = self.reply.read_committed(self.request)
        need(self.clock() < deadline_ns, 'FINANCIAL_REPLY_DEADLINE')
        return {'observer': observer, 'request': copy.deepcopy(self.request), 'financial': financial,
                'readback_type': 'RETAINED_RESPONSE_NOT_NEW_COLD_REOPEN', 'native_acceptance': False}


class ColdArchiveEvidence:
    def __init__(self, *, archive, expected_head, process_evidence, clock_ns):
        from scripts.observation_runtime.aip06_outputs import EvidenceOutput
        need(type(archive) is EvidenceOutput, 'TYPED_COLD_ARCHIVE_REQUIRED')
        self.archive, self.head, self.processes, self.clock = archive, expected_head, process_evidence, clock_ns

    def read(self, *, deadline_ns):
        observer = self.processes.check_reader(deadline_ns=deadline_ns)
        need(self.clock() < deadline_ns and self.archive.sequence == 0, 'FRESH_COLD_ARCHIVE_REOPEN_REQUIRED')
        rows = self.archive.recover(expected_head=self.head)
        need(self.clock() < deadline_ns, 'COLD_ARCHIVE_REOPEN_DEADLINE')
        return {'observer': observer, 'head': self.head, 'records': rows, 'native_acceptance': False}


class WindowsReaderSet:
    """Concrete raw-source collection, deliberately not the old summary flags.

    Raw identity/Job/socket/financial results need typed policy projection and
    a separately admitted reader process before native grading. Returning a
    controller-authored summary as a provider is explicitly unsupported.
    """
    domain = DOMAIN

    def __init__(self, *, process_evidence, providers, clock_ns, output, manifest_sha256, socket_port, endpoints=()):
        need(type(process_evidence) is WindowsProcessEvidence and set(providers) == set(READERS)
             and len({id(p) for p in providers.values()}) == len(READERS), 'INDEPENDENT_CONCRETE_WINDOWS_READER_SET')
        expected = {'HANDLES':WindowsProcessEvidence,'JOB':WindowsJobEvidence,'LEDGER':WindowsCapacityEvidence,
                    'FINANCIAL':RetainedFinancialEvidence,'RESTART':ColdArchiveEvidence,'OBJECTS':BootstrapObjectEvidence,
                    'CIM':CimSockets,'IP_HELPER':TcpTables,'NETSTAT':GuardedNetstat,'PROCESS':StrictProcessCleanup}
        need(providers['HANDLES'] is process_evidence and all(type(providers[k]) is t for k,t in expected.items()),
             'OWNER_SUMMARIES_ARE_NOT_CONCRETE_INDEPENDENT_PROVIDERS')
        self.processes, self.providers, self.clock, self.output, self.pin = process_evidence, dict(providers), clock_ns, output, manifest_sha256
        self.socket_port, self.endpoints = socket_port, tuple(endpoints)
        self.sequence = 0
        self.failed = False

    def collect(self, request, *, deadline_ns):
        need(type(request) is dict and request.get('scope') == SCOPE_HASH and request.get('manifest') == self.pin
             and request.get('root') == ROOTS['E'], 'EXACT_WINDOWS_READER_REQUEST')
        need(not self.failed and self.sequence == 0,
             'WINDOWS_READER_ONCE_ONLY_COLLECTION_REQUIRED')
        self.failed = True
        observer = self.processes.check_reader(deadline_ns=deadline_ns)
        rows = []
        # Socket readers first; strict process snapshot LAST. No stale summary
        # can be accepted in place of invoking all complete native providers.
        def collect(name):
            start = self.clock(); need(start < deadline_ns, 'READER_DEADLINE')
            raw = self.providers[name].read(deadline_ns=deadline_ns)
            done = self.clock()
            need(start <= done < deadline_ns and done - start <= 2 * 10**9 and type(raw) is dict,
                 'BOUNDED_INDEPENDENT_READER_CUT')
            row = {'reader': name, 'observer': observer, 'request': digest(request), 'started_ns': start,
                   'finished_ns': done, 'raw': copy.deepcopy(raw), 'domain': DOMAIN}
            self.output.append(row); rows.append(row)
            return raw
        for name in READERS[:6]: collect(name)
        bundle = self
        class SocketProvider:
            def __init__(self, name): self.name = name
            def read(self, *, deadline_ns): return collect(self.name)
        socket_cut = ThreeReaderCleanup(readers={n: SocketProvider(n) for n in ('CIM','IP_HELPER','NETSTAT')},
            port=self.socket_port, output=self.output, clock_ns=self.clock, endpoints=self.endpoints).collect(
                started_ns=self.clock(), deadline_ns=deadline_ns)
        provider = bundle.providers['PROCESS']
        need(callable(getattr(provider, 'collect', None)), 'CONCRETE_STRICT_PROCESS_COLLECTOR_REQUIRED')
        cut = provider.collect(after_ns=socket_cut['at_ns'], deadline_ns=deadline_ns)
        need(type(cut) is dict and set(cut) >= {'scope', 'survivors', 'unknown', 'started_ns', 'at_ns'}
             and type(cut['survivors']) is list and type(cut['unknown']) is bool
             and type(cut['started_ns']) is int and type(cut['at_ns']) is int,
             'STRICT_PROCESS_CUT_FIELDS_REQUIRED')
        need(cut['scope'] == SCOPE_HASH and cut['survivors'] == [] and cut['unknown'] is False
             and socket_cut['at_ns'] <= cut['started_ns'] <= cut['at_ns'] <= self.clock() < deadline_ns,
             'STRICT_PROCESS_AFTER_SOCKET_CLEANUP_REQUIRED')
        need(cut['at_ns'] - cut['started_ns'] <= 2 * 10**9
             and self.processes.check_reader(deadline_ns=deadline_ns) == observer,
             'FINAL_PROCESS_CUT_FRESH_AND_SAME_INDEPENDENT_READER')
        row = {'reader':'PROCESS','observer':observer,'request':digest(request),'started_ns':cut['started_ns'],
               'finished_ns':cut['at_ns'],'raw':cut,'domain':DOMAIN}
        rows.append(row);self.output.append(row)
        self.sequence += 1
        self.failed = False
        return {'scope': SCOPE_HASH, 'manifest': self.pin, 'observer': observer, 'sequence': self.sequence,
                'cuts': rows, 'native_acceptance': False, 'domain': DOMAIN}


class WindowsAcceptanceOwner:
    """One create-new receipt and guarded controller session; no native grant.

    Construction is inert. Public launch refuses authority before effects;
    after admission the implementation uses only the existing suspended guard
    with an exact typed logical target and original fenced bootstrap command.
    """
    domain = DOMAIN

    def __init__(self, *, controller, guard, capacity, clock_ns, intent=None, precreation=None):
        self.controller, self.guard, self.capacity, self.clock = controller, guard, capacity, clock_ns
        self.reservations, self.failure = [], None
        self.intent = intent
        self.precreation = precreation if precreation is not None else getattr(controller, 'precreation_receipt', None)
        self.child = None

    def start(self, authorization=None):
        RefusalOnlyAuthorization().require(authorization,
            manifest_sha256=self.intent.sha256 if self.intent is not None else 'UNREDEEMABLE_WINDOWS_ADAPTER')

    def verify_current(self, *, deadline_ns):
        self.controller.require_ready(); self.guard.check()
        need(self.guard.processes is self.controller.process_port and self.clock() < deadline_ns,
             'EXACT_CURRENT_WINDOWS_OWNER_GUARD')
        native = self.controller.calls.native(self.controller.calls.current())
        owner = self.guard.resources.state['owners'][self.guard.owner]
        need(all(native[k] == owner[k] for k in ('pid', 'created', 'image')), 'WINDOWS_OWNER_IDENTITY_CHANGED')
        return self.capacity.read(deadline_ns=deadline_ns)

    def preflight(self, plan, *, manifest_sha256, deadline_ns):
        from scripts.observation_runtime.aip06_acceptance_plan import validate_plan
        from scripts.observation_runtime.aip06_launch_roles import launch_role
        validate_plan(plan)
        need(digest(plan) == manifest_sha256 and plan['executable'] == self.controller.profile['executable']
             and plan['source_pins'] == self.controller.profile['source_pins'], 'EXACT_WINDOWS_OWNER_MANIFEST_PROFILE')
        measured = self.verify_current(deadline_ns=deadline_ns)
        roots = {}
        self.guard.paths.parent()
        for alias, path in ROOTS.items():
            row = self.guard.io.inspect(path)
            if row is not None:
                need(alias in self.guard.paths.bound and self.guard.paths.bound[alias] == row,
                     'NO_EXISTING_NATIVE_FIXTURE_ADOPTION')
            roots[alias] = {'path': path, 'native': row, 'absent': row is None}
        from scripts.observation_runtime.aip06_controller_contract import ControllerIntent, PrecreationReceipt
        need(type(self.intent) is ControllerIntent and self.intent.plan() == plan
             and type(self.precreation) is PrecreationReceipt, 'MATCHED_CONTROLLER_PRECREATION_REQUIRED')
        self.precreation.bind(self.intent, guard=self.guard, clock_ns=self.clock, deadline_ns=deadline_ns)
        role = launch_role(self.intent.argv, self.controller.profile['targets'])
        return {'domain': DOMAIN, 'manifest': manifest_sha256, 'roots': roots, 'capacity': measured,
                'controller_role': role, 'required_role': 'acceptance_supervisor',
                'startup_status': 'SOURCE_CONTRACT_BOUND_NATIVE_AUTHORIZATION_PENDING',
                'native_acceptance': False}

    def reserve(self, limits, *, deadline_ns):
        need(limits == dict(LIMITS), 'EXACT_SHARED_OWNER_LIMITS')
        from scripts.observation_runtime.aip06_controller_contract import ControllerIntent, PrecreationReceipt
        need(type(self.intent) is ControllerIntent and type(self.precreation) is PrecreationReceipt,
             'CONTROLLER_BOOTSTRAP_ROLE_AND_SHARED_SESSION_BINDING_NOT_CONNECTED')
        self.verify_current(deadline_ns=deadline_ns)
        need(not self.reservations, 'ONE_OWNER_RESERVATION')
        self.precreation.bind(self.intent, guard=self.guard, clock_ns=self.clock, deadline_ns=deadline_ns)
        self.intent.declare(self.controller.process_port)
        cut = self.guard.resources.read()
        self.reservations.append({'head':cut['head'],'baseline':set(cut['state']['resources']),'lease':None})
        return {'held':True,'limits':dict(LIMITS),'includes_outer_owner':True,'stop_capacity_reserved':True,
                'head':cut['head'],'manifest':self.intent.sha256}

    def launch_controller(self, entry, executable, *, deadline_ns):
        # No grant is issued/redeemed here. Public native admission stays shut.
        self.start()
        return self._launch_reserved(entry, executable, deadline_ns=deadline_ns)

    def _launch_reserved(self, entry, executable, *, deadline_ns):
        """After admission only; tests inject Windows calls into the real guard."""
        from scripts.observation_runtime.aip06_acceptance_control import OwnerLaunch
        from scripts.observation_runtime.aip06_fixture_guard import current
        need(current() is self.guard, 'ORIGINAL_ROOT_GUARD_MUST_BE_INSTALLED')
        need(self.intent is not None and len(self.reservations) == 1 and self.child is None
             and not self.reservations[0].get('cancelled', False)
             and (entry,executable) == (self.intent.plan()['entry'],self.intent.plan()['executable'])
             and self.clock() < deadline_ns, 'ONE_RESERVED_EXACT_CONTROLLER_LAUNCH')
        # spawn performs the existing suspended creation, prospective native
        # reservations, Job assignment, original handle binding and guard ACK.
        with bounded_observations(deadline_ns):
            self.child = self.guard.spawn(self.intent.argv)
        lease = OwnerLaunch(self.child.child.binding,self.intent.sha256,self.child.child,self.intent)
        self.reservations[0]['lease'] = lease
        self.verify_controller(lease,deadline_ns=deadline_ns)
        return lease

    def cleanup(self, launch, *, deadline_ns):
        need(self.clock() < deadline_ns, 'OWNER_CLEANUP_DEADLINE')
        if launch is None:
            need(self.child is None, 'OWNED_CONTROLLER_REQUIRES_EXACT_LAUNCH_FOR_CLEANUP')
            if self.reservations:
                self.verify_released(deadline_ns=deadline_ns)
                self.reservations[0]['cancelled'] = True
            return True
        if self.child is not None and self.child.closed:
            need(self.reservations[0]['lease'] is launch, 'ORIGINAL_CONTROLLER_CLEANUP_IDENTITY')
            self.child.close()  # Existing idempotent native/ledger close checks.
            self.verify_released(deadline_ns=deadline_ns)
            return True
        self.verify_controller(launch,deadline_ns=deadline_ns)
        seconds = min(6,(deadline_ns-self.clock())/10**9)
        need(seconds > 0, 'CONTROLLER_CLEANUP_TIME_REMAINING')
        self.child.communicate(launch.preparation_packet(self.intent.plan(),self.intent.sha256),timeout=seconds)
        need(self.child.closed and self.clock() < deadline_ns, 'CONTROLLER_PREPARE_EXIT_AND_CLOSE_REQUIRED')
        self.verify_released(deadline_ns=deadline_ns)
        return True

    def verify_controller(self, launch, *, deadline_ns):
        need(self.clock() < deadline_ns, 'CONTROLLER_VERIFY_DEADLINE')
        from scripts.observation_runtime.aip06_controller_contract import ROLE, bootstrap_argv
        need(self.intent is not None and len(self.reservations) == 1
             and self.reservations[0]['lease'] is launch and self.child is not None
             and launch.session is self.child.child and launch.session in self.controller.process_port.sessions
             and launch.session.creation_attempted and type(launch.session.creation_native) is dict
             and all(launch.session.creation_native[k] == launch.binding.runtime[k] for k in ('pid','created','image'))
             and self.guard.ownership.bindings.get(ROLE) is launch.binding,
             'CONTROLLER_BOOTSTRAP_ROLE_AND_SHARED_SESSION_BINDING_NOT_CONNECTED')
        declared = self.controller.process_port.plans.get(launch.binding.request.nonce)
        need(declared is not None and declared['argv'] == self.intent.argv
             and declared['command'] == bootstrap_argv(self.intent.plan()['executable'],launch.binding.request.nonce),
             'CONTROLLER_ORIGINAL_CREATION_PLAN_REQUIRED')
        with bounded_observations(deadline_ns):
            launch.verify(self.intent.plan(),self.intent.sha256)

    def verify_released(self, *, deadline_ns):
        need(self.clock() < deadline_ns, 'OWNER_RESERVATIONS_OR_DEADLINE_UNRESOLVED')
        state = self.guard.resources.read()['state']
        baseline = self.reservations[0]['baseline'] if self.reservations else set()
        need(all(row['closed'] for key,row in state['resources'].items() if key not in baseline)
             and self.controller.process_port.all_members() == set() and self.clock() < deadline_ns,
             'OWNER_RESOURCE_OR_PROCESS_RELEASE_UNRESOLVED')
