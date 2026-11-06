"""Scoped construction over existing guarded capabilities, never a launcher.

Case/reader declarations are not native attestations. They retain immutable
views of the original descriptor and one resource history. No guard, role map,
authorization, account or native process is created/reset by these factories.
"""
import copy
import ntpath
from dataclasses import dataclass

from app.services.paper_financial_replay import body, digest
from scripts.observation_runtime.aip06_acceptance_grade import READERS
from scripts.observation_runtime.aip06_controller_contract import ControllerContext
from scripts.observation_runtime.aip06_harness import LIMITS, ROOTS, SCOPE_HASH, need, path_for
from scripts.observation_runtime.aip06_native_scenario_bindings import bindings, contracts
from scripts.observation_runtime.aip06_outputs import EvidenceOutput
from scripts.observation_runtime.launch_ownership import identity

SOURCE = ntpath.join(ntpath.dirname(ntpath.dirname(__file__)), 'observation_runtime', 'aip06_scoped_context.py')
ACCOUNTS = (('QUALITY_DIPS', 'USD'), ('HYPERLIQUID', 'USDC'))
ACCESS = ('PROCESS_QUERY_LIMITED_INFORMATION', 'SYNCHRONIZE', 'JOB_OBJECT_QUERY',
          'FILE_READ_DATA', 'READ_CONTROL')
APIS = ('GetProcessTimes', 'QueryFullProcessImageNameW', 'QueryInformationJobObject',
        'GetExtendedTcpTable', 'ROOT/StandardCimv2', 'PINNED_NETSTAT', 'NATIVE_READONLY_FILE_ACL')


def token(value):
    need(type(value) is str and len(value) == 32 and set(value) <= set('0123456789abcdef'),
         'EXACT_UNIQUE_CONTEXT_ID')


def wire_identity(row):
    need(type(row) is dict and type(row.get('file_id')) in (list,tuple)
         and len(row['file_id']) == 3 and all(type(n) is int for n in row['file_id']),
         'EXACT_WIRE_IMAGE_FILE_ID')
    return identity({**row, 'file_id':tuple(row['file_id'])})


@dataclass(frozen=True)
class CaseIntent:
    scenario: str
    manifest: str
    case: str
    commands: tuple
    targets: tuple
    budget: tuple
    schedule: str
    root: str
    evidence: str
    accounts: tuple = ACCOUNTS


@dataclass(frozen=True)
class ReaderIntent:
    reader: str
    case: str
    manifest: str
    names: tuple = READERS
    access: tuple = ACCESS
    apis: tuple = APIS
    freshness_ns: int = 2 * 10**9


class ScopedContextFactory:
    def __init__(self, context):
        from scripts.observation_runtime.aip06_ipc import RemoteResources
        need(type(context) is ControllerContext and type(context.guard.resources) is RemoteResources,
             'ORIGINAL_INHERITED_CONTROLLER_CONTEXT')
        self.context = context
        self.guard = context.guard
        self.binding = copy.deepcopy(self.guard.resources.channel.binding)
        self.controller = getattr(getattr(self.guard.processes, 'port', self.guard.processes), 'controller', None)
        need(self.controller is not None and self.controller.process_port is self.guard.processes,
             'ORIGINAL_INHERITED_PROCESS_PORT')
        self.plan = context.intent.plan()
        need(SOURCE in self.plan['source_pins'], 'SCOPED_CONTEXT_SOURCE_PIN_REQUIRED')
        need(body(self.controller.profile['targets']) == body(self.guard.processes.runtime.descriptor['targets']),
             'ORIGINAL_PRIVATE_TARGET_DESCRIPTOR_REQUIRED')
        self.targets = body(self.controller.profile['targets'])
        self.cases, self.used, self.readers, self.reader_births = {}, set(), set(), set()
        self.pending, self.failed, self.cleanup_failure = None, False, None

    def verify(self, *, deadline_ns, cleanup=False):
        now = self.controller.clock()
        need(type(deadline_ns) is int and now < deadline_ns, 'SCOPED_CONTEXT_DEADLINE')
        need(cleanup or not self.failed, 'CONTEXT_FACTORY_FAILURE_LATCHED')
        if not cleanup:
            self.guard.check()
        # Original retained parent handles stay in the parent. Each RPC read
        # re-verifies the parent Broker's complete ownership graph; the child
        # independently verifies its inherited local handle/Job identity.
        current = self.guard.processes.runtime.identity.verify(self.binding)
        state = self.guard.ledger('read')['state']
        need(self.guard.resources.channel.binding == self.binding and current == self.binding['child']
             and self.guard.owner == digest(current)
             and self.context.root_owner == state['controller'] == digest(self.binding['parent'])
             and state['owners'].get(self.guard.owner) == current
             and wire_identity(self.binding['parent']) != wire_identity(current)
             and body(self.controller.profile['targets']) == self.targets
             and self.controller.profile['source_pins'] == self.plan['source_pins'],
             'CURRENT_CONTROLLER_GRAPH_AND_IMMUTABLE_DESCRIPTOR')
        need(self.controller.clock() < deadline_ns, 'SCOPED_CONTEXT_DEADLINE')

    def intent(self, scenario, case, commands):
        table = {c.id: c for c in contracts()}
        need(scenario in table, 'EXACT_SCENARIO_ID')
        token(case)
        contract = table[scenario]
        need(type(commands) is dict and set(commands) == set(contract.roles), 'EXACT_SCOPED_PROCESS_ROLES')
        return CaseIntent(scenario, self.context.intent.sha256, case,
            tuple((role, tuple(commands[role])) for role in contract.roles),
            tuple((role, self.controller.profile['targets'].get(role)) for role in contract.roles),
            tuple(sorted(LIMITS.items())), digest(vars(contract)), path_for('E', 'case-' + case),
            digest({'manifest': self.context.intent.sha256, 'case': case, 'owner': self.guard.owner}))

    def create(self, intent, *, deadline_ns):
        try:
            self.verify(deadline_ns=deadline_ns)
            need(type(intent) is CaseIntent, 'TYPED_CASE_INTENT')
            token(intent.case)
            contract = next((c for c in contracts() if c.id == intent.scenario), None)
            need(contract is not None and intent == self.intent(intent.scenario, intent.case, dict(intent.commands)),
                 'EXACT_CASE_MANIFEST_ROOT_BUDGET_AND_SCHEDULE')
            need(intent.case not in self.used and intent.scenario not in self.cases and self.pending is None,
                 'UNIQUE_SERIAL_CASE_CONTEXT')
            need(all(type(argv) is tuple and len(argv) >= 3 and all(type(v) is str for v in argv)
                     and argv[:2] == (self.plan['executable'], '-B')
                     and argv[2] == dict(intent.targets)[role] and argv[2] in self.plan['source_pins']
                     for role, argv in intent.commands), 'PINNED_IMMUTABLE_CASE_TARGET_VIEW')
            if intent.scenario == 'F04':
                need(len({argv for _, argv in intent.commands}) == 2, 'DISTINCT_RACE_CHILD_COMMANDS')
                # Original native config identity/operation checks remain at
                # declare_race_pair before any race child can be staged.
            self.used.add(intent.case)  # Burn before first reservation/effect.
            result = CaseContext(self, intent, contract, min(deadline_ns, self.controller.clock()+contract.seconds*10**9))
            self.cases[intent.scenario] = result
            result.verify(deadline_ns=deadline_ns)
            return result
        except BaseException:
            self.failed = True
            raise

    def as_bindings(self, *, fault_drivers=None):
        # A dispatcher snapshot must never publish a failed or foreign case.
        # This does not grant physical execution authority.
        try:
            need(not self.failed and all(type(case) is CaseContext
                 and case.factory is self and case.intent.scenario == scenario
                 and case.intent.case in self.used and not case.closed and not case.failed
                 for scenario, case in self.cases.items()),
                 'HEALTHY_ORIGINAL_SCOPED_BINDING_SNAPSHOT')
            self.verify(deadline_ns=self.controller.clock() + 10**9)
            return bindings(self.plan['source_pins'], contexts=dict(self.cases), fault_drivers=fault_drivers)
        except BaseException:
            self.failed = True
            raise

    def reader(self, case, intent, session, *, deadline_ns):
        result = None
        try:
            self.verify(deadline_ns=deadline_ns)
            need(type(case) is CaseContext and case.factory is self and self.pending is case,
                 'ORIGINAL_RESERVED_CASE_FOR_READER')
            need(type(intent) is ReaderIntent and intent.case == case.intent.case
                 and intent.manifest == case.intent.manifest and intent.names == READERS
                 and intent.access == ACCESS and intent.apis == APIS
                 and type(intent.freshness_ns) is int and intent.freshness_ns == 2*10**9,
                 'COMPLETE_TYPED_READER_SCOPE_ACCESS_AND_FRESHNESS')
            token(intent.reader)
            need(intent.reader not in self.readers and not case.reader, 'UNIQUE_INDEPENDENT_READER_CONTEXT')
            self.readers.add(intent.reader)
            result = ReaderContext(case, intent, session)
            result.verify(deadline_ns=deadline_ns)
            birth = identity(result.session.child.binding.runtime)
            need(birth not in self.reader_births, 'READER_PROCESS_IDENTITY_REUSED')
            self.reader_births.add(birth)
            case.reader = result
            return result
        except BaseException:
            self.failed = True
            # Borrowed handles are never closed or adopted on construction
            # failure; only this case's original guarded allocations release.
            if type(case) is CaseContext and case.factory is self and self.pending is case:
                try:
                    case.abort(case.reservation, deadline_ns=deadline_ns)
                except BaseException as exc:
                    self.cleanup_failure = str(exc)
            raise


class CaseContext:
    def __init__(self, factory, intent, contract, deadline):
        self.factory, self.intent, self.contract = factory, intent, contract
        self.guard, self.controller, self.roles = factory.guard, factory.controller, contract.roles
        self.deadline, self.reservation, self.reader, self.output = deadline, None, None, None
        self.baseline, self.closed, self.failed = None, False, False

    def verify(self, *, deadline_ns):
        self.factory.verify(deadline_ns=min(deadline_ns, self.deadline))
        need(not self.closed and not self.failed and self.factory.cases.get(self.contract.id) is self
             and self.intent == self.factory.intent(self.contract.id, self.intent.case, dict(self.intent.commands)),
             'CURRENT_ORIGINAL_CASE_CONTEXT')

    def reserve(self, *, deadline_ns):
        self.verify(deadline_ns=deadline_ns)
        need(self.reservation is None and self.factory.pending is None, 'SERIAL_RESERVATION_ONCE_ONLY')
        port = getattr(self.guard.processes, 'port', self.guard.processes)
        need(getattr(port, 'scoped_case', None) is None, 'NO_OVERLAPPING_CASE_AUTHORITY')
        self.factory.pending = self  # Capture partial construction before IO.
        port.scoped_case = self
        try:
            self.baseline = set(self.guard.ledger('read')['state']['resources'])
            key = self.guard.mkdir(self.intent.root, hold=True)
            self.output = EvidenceOutput(self.guard, directory=self.intent.root, producer={
                'session': self.factory.context.nonce, 'owner': self.guard.owner,
                'role': 'SCOPED_CASE_SOURCE_CONTEXT', 'source_pins': self.factory.plan['source_pins']})
            self.output.append({'schema': 'AIP06_CASE_CONTEXT_V1', 'intent': vars(self.intent),
                                'identity': self.intent.evidence, 'native_acceptance': False})
            state = self.guard.ledger('read')['state']
            need(state['mode'] == 'WORK' and state['entries'] <= LIMITS['entries']-LIMITS['stop_entries']
                 and state['charged_bytes'] <= LIMITS['bytes']-LIMITS['stop_bytes'],
                 'ORIGINAL_RESERVED_STOP_CAPACITY_REQUIRED')
            self.reservation = {'scenario': self.contract.id, 'root': ROOTS['E'], 'roles': self.roles,
                'held': True, 'stop_capacity_reserved': True, 'key': key, 'commands': dict(self.intent.commands),
                'controller_command': self.factory.binding['launch']['command'],
                'case': self.intent.case, 'manifest': self.intent.manifest, 'evidence': self.intent.evidence}
            self.verify(deadline_ns=deadline_ns)
            return copy.deepcopy(self.reservation)
        except BaseException:
            self.failed = self.factory.failed = True
            try:
                self.abort(self.reservation, deadline_ns=deadline_ns)
            except BaseException as exc:
                self.factory.cleanup_failure = str(exc)
            raise

    def release(self, reservation, evidence, *, deadline_ns):
        try:
            need(not self.closed and not self.failed and reservation == self.reservation
                 and self.reader is not None and evidence is self.reader.result,
                 'ORIGINAL_INDEPENDENT_CONTEXT_OBSERVATION_FOR_RELEASE')
            self.reader.verify(deadline_ns=deadline_ns)
            need(digest(evidence) == self.reader.result_hash, 'READER_RESULT_CHANGED_AFTER_PRIVATE_RECEIPT')
            return self._close(deadline_ns)
        except BaseException:
            self.failed = self.factory.failed = True
            raise

    def admit(self, argv):
        self.verify(deadline_ns=self.deadline)
        commands = dict(self.intent.commands)
        reader = (self.factory.plan['executable'], '-B', READER_ENTRY)
        from scripts.observation_runtime.aip06_case_host_entry import HOST_ENTRY
        host = (self.factory.plan['executable'], '-B', HOST_ENTRY)
        if tuple(argv) == host:
            # The original guarded spawn path invokes admit before any native
            # allocation. This is validation only, never execution authority.
            from scripts.observation_runtime.aip06_case_host_launch_intent import inspect_launch_intent
            inspect_launch_intent(self, self.reservation, deadline_ns=self.deadline)
            return
        need(tuple(argv) in tuple(commands.values()) or
             (tuple(argv) == reader and self.controller.profile['targets'].get('readonly_reader') == READER_ENTRY),
             'EXACT_SCOPED_COMMAND_BEFORE_GUARDED_CREATION')

    def wire(self):
        return {'schema':'AIP06_IMMUTABLE_CASE_VIEW_V1', 'owner':self.guard.owner,
                'owners':[self.guard.owner], 'source_pins':digest(self.factory.plan['source_pins']),
                'intent':copy.deepcopy(vars(self.intent))}

    def deliver_physical_host_handoff(self, process, *, deadline_ns):
        """Connect a pre-existing original guarded host to its pinned INPUT.

        No process is created here, and this does not authorize execution.
        """
        self.verify(deadline_ns=deadline_ns)
        from scripts.observation_runtime.aip06_fixture_guard import GuardedProcess
        from scripts.observation_runtime.aip06_case_host_launch_intent import inspect_launch_intent
        need(type(process) is GuardedProcess and process.guard is self.guard
             and process.plan['name'] == 'case_host'
             and any(session is process.child for session in
                     getattr(self.guard.processes, 'sessions', ()))
             and not process.closed,
             'ORIGINAL_EXISTING_GUARDED_CASE_HOST_REQUIRED')
        intent = inspect_launch_intent(self, self.reservation, deadline_ns=deadline_ns)
        need(tuple(process.argv) == intent['argv']
             and intent['native_acceptance'] is False
             and intent['execution_authorized'] is False,
             'EXACT_PINNED_CASE_HOST_HANDOFF_INTENT_REQUIRED')
        return process.send_case_host_handoff(intent['handoff'], deadline_ns=deadline_ns)

    def physical_host_handoff(self, reservation, *, deadline_ns):
        """Data-only handoff for a separately guarded case host; never authority."""
        self.verify(deadline_ns=deadline_ns)
        need(self.factory.pending is self and self.reservation is not None
             and type(reservation) is dict and reservation == self.reservation
             and reservation.get('held') is True
             and reservation.get('stop_capacity_reserved') is True,
             'ORIGINAL_RESERVED_CASE_FOR_PHYSICAL_HOST_HANDOFF')
        state = self.guard.ledger('read')['state']
        need(state['resources'].get(self.reservation['key']) ==
             {'owner': self.guard.owner, 'kind': 'directory', 'closed': False},
             'ORIGINAL_PHYSICAL_HANDOFF_RESERVATION_STILL_HELD')
        observed = self.guard.paths.port.inspect(self.intent.root)
        need(observed is not None and self.guard.file_identities.get(self.intent.root) == observed['id'],
             'ORIGINAL_CASE_DIRECTORY_IDENTITY_REQUIRED')
        packet = {'schema': 'AIP06_PHYSICAL_CASE_HOST_HANDOFF_V1',
                  'case': self.wire(), 'reservation': self.reservation,
                  'native_acceptance': False}
        packet['integrity'] = digest(packet)
        return copy.deepcopy(packet)

    def require_execution(self):
        # Construction and an immutable view are NOT a physical case host.
        # The historical cases install their own guards/Stop lifetimes; they
        # must not be run inside the live controller's interpreter/authority.
        raise ValueError('SEPARATELY_GUARDED_PHYSICAL_CASE_HOST_BINDING_REQUIRED')

    def _close(self, deadline_ns):
        self.factory.verify(deadline_ns=deadline_ns, cleanup=True)
        need(self.baseline is not None and self.factory.pending is self, 'ORIGINAL_PARTIAL_CASE_CLEANUP')
        port = getattr(self.guard.processes, 'port', self.guard.processes)
        need(getattr(port, 'scoped_case', None) is self and self.factory.pending is self,
             'ORIGINAL_SCOPED_CASE_RELEASE_ORDER')
        state = self.guard.ledger('read')['state']
        keys = set(state['resources']) - self.baseline
        # Files/metadata use NativeIO's original completion proofs. Process,
        # pipe, Job and other allocations must already have closed via their
        # original retained owner; this context cannot manufacture those proofs.
        for key in keys:
            row = state['resources'][key]
            need(row['closed'] or (row['owner'] == self.guard.owner and row['kind'] in ('file', 'directory')
                                  and self.guard.io.closed(self.guard.owner, key) is True),
                 'INCOMPLETE_CONTEXT_NATIVE_RESOURCE_RELEASE')
        for key in sorted(keys):
            if not state['resources'][key]['closed']:
                self.guard.release(key)
        need(all(self.guard.ledger('read')['state']['resources'][k]['closed'] for k in keys)
             and self.controller.clock() < deadline_ns, 'AGGREGATE_CONTEXT_RELEASE_UNRESOLVED')
        port = getattr(self.guard.processes, 'port', self.guard.processes)
        need(getattr(port, 'scoped_case', None) is self and self.factory.pending is self,
             'ORIGINAL_SCOPED_CASE_RELEASE_ORDER')
        port.scoped_case = None
        self.factory.pending = None
        self.closed = True
        return True

    def abort(self, reservation, *, deadline_ns):
        self.failed = self.factory.failed = True
        need(reservation is None or reservation == self.reservation, 'ORIGINAL_CASE_ABORT_TICKET')
        if self.closed:
            return True
        if self.baseline is None:
            # Reservation failed before the resource snapshot. Release only
            # the scope marker installed by this case; no resource keys can
            # safely be inferred without the original ledger baseline.
            port = getattr(self.guard.processes, 'port', self.guard.processes)
            need(self.factory.pending is self and getattr(port, 'scoped_case', None) is self,
                 'ORIGINAL_PARTIAL_SCOPE_OWNER_REQUIRED')
            port.scoped_case = None
            self.factory.pending = None
            self.closed = True
            return True
        return self._close(deadline_ns)


class ReaderContext:
    """Parent-side lease for an ORIGINAL guarded reader, never its observer."""
    def __init__(self, case, intent, session):
        self.case, self.intent, self.session = case, intent, session
        self.result, self.failed = None, False
        self.result_hash = None
        self.prepared = None

    def verify(self, *, deadline_ns):
        from scripts.observation_runtime.aip06_fixture_guard import GuardedProcess
        from scripts.observation_runtime.aip06_native_session import Session
        f = self.case.factory
        f.verify(deadline_ns=deadline_ns)
        port = getattr(f.guard.processes, 'port', f.guard.processes)
        need(not self.failed and type(self.session) is GuardedProcess and self.session.guard is f.guard
             and type(self.session.child) is Session
             and any(retained is self.session.child for retained in port.sessions)
             and self.session.child.name == 'readonly_reader'
             and self.session.child.binding is f.guard.ownership.bindings.get('readonly_reader')
             and self.session.child.creation_attempted and self.session.child.target_released
             and self.session.keys == self.session.child.keys and bool(self.session.keys)
             and self.session.child.plan['request'] is self.session.child.binding.request
             and self.session.child.receipt is not None and self.session.child.receipt.get('guarded') is True
             and self.session.child.receipt.get('scope') == SCOPE_HASH
             and self.session.child.receipt.get('nonce') == self.session.child.plan['request'].nonce
             and self.session.child.receipt.get('owner') == digest(self.session.child.binding.runtime)
             and all(self.session.child.creation_native.get(k) == self.session.child.binding.runtime[k]
                     for k in ('pid','created','image')),
             'ORIGINAL_GUARDED_READER_SESSION_REQUIRED')
        binding = self.session.child.binding
        if self.session.closed:
            need(self.session.child.closed and port.resources_closed(self.session.child, self.session.keys),
                 'ORIGINAL_READER_TERMINAL_RELEASE_PROOF')
        else:
            binding.verify()  # Original local parent handles; NOT current reader PID.
        need(body(binding.parent) == body(f.binding['child'])
             and identity(binding.runtime) not in (wire_identity(f.binding['parent']), wire_identity(f.binding['child']))
             and self.session.argv == self.session.child.argv == (f.plan['executable'], '-B', READER_ENTRY),
             'EXACT_INDEPENDENT_READER_ANCESTRY_AND_ENTRY')
        state = f.guard.ledger('read')['state']; owner = digest(binding.runtime)
        need(body(state['owners'].get(owner)) == body(binding.runtime)
             and any(k in self.session.keys and row['owner'] == owner and row['kind'] == 'process'
                     and row['closed'] is self.session.closed for k,row in state['resources'].items()),
             'ORIGINAL_READER_SHARED_PROCESS_RESERVATION')
        need(f.controller.clock() < deadline_ns, 'READER_CONTEXT_DEADLINE')

    def prepare(self, request, *, deadline_ns):
        try:
            return self._prepare(request, deadline_ns=deadline_ns)
        except BaseException:
            self.failed = self.case.factory.failed = True
            raise

    def _prepare(self, request, *, deadline_ns):
        need(self.prepared is None and self.result is None and not self.failed, 'READER_PREPARATION_ONCE_ONLY')
        self.verify(deadline_ns=deadline_ns)
        case = self.case
        expected = {'scope': SCOPE_HASH, 'manifest': case.intent.manifest, 'scenario': case.contract.id,
                    'reservation': case.reservation['key'], 'root': ROOTS['E']}
        need(request == expected and case.factory.pending is case, 'EXACT_SCOPED_READER_REQUEST')
        start = case.controller.clock(); end = min(deadline_ns, start + 6*10**9)
        packet = {'schema':'AIP06_SCOPED_READER_INPUT_V1','raw':case.factory.context.intent.raw.decode(),
                'manifest':case.intent.manifest,'case':vars(case.intent),'reader':vars(self.intent),
                'request':request,'nonce':self.session.child.plan['request'].nonce,
                'owner':digest(self.session.child.binding.runtime),'parent_owner':case.guard.owner}
        need(len(body(packet).encode()) <= 65536, 'READER_INPUT_WITHIN_ORIGINAL_IPC_CAP')
        self.prepared = (copy.deepcopy(request), copy.deepcopy(packet), start, end)
        return copy.deepcopy(packet)

    def collect(self, request, *, deadline_ns):
        try:
            need(self.result is None and not self.failed, 'READER_CONTEXT_ONCE_ONLY')
            if self.prepared is None:
                self.prepare(request, deadline_ns=deadline_ns)
            expected, packet, start, limit = self.prepared
            end = min(deadline_ns, limit)
            case = self.case
            self.verify(deadline_ns=end)
            need(request == expected, 'ORIGINAL_PREPARED_READER_REQUEST')
            remaining = end-case.controller.clock()
            need(remaining > 0, 'READER_PREPARED_DEADLINE')
            self.session.communicate(packet, timeout=remaining/10**9)
            need(self.session.closed, 'READER_ORIGINAL_EXIT_AND_HANDLE_RELEASE_REQUIRED')
            rows = [r['payload'] for r in self.session.child.channel.saved_outputs
                    if type(r['payload']) is dict and r['payload'].get('schema') == 'AIP06_SCOPED_READER_REPLY_V1']
            need(len(rows) == 1, 'ONE_AUTHENTICATED_SCOPED_READER_REPLY')
            reply = rows[0]
            need(set(reply) == {'schema','case','reader','request','nonce','owner','raw','native_acceptance'}
                 and reply['case'] == case.intent.case and reply['reader'] == self.intent.reader
                 and reply['request'] == digest(request) and reply['nonce'] == packet['nonce']
                 and reply['owner'] == packet['owner'] and reply['native_acceptance'] is False,
                 'ORIGINAL_PRIVATE_READER_REPLY_CORRELATION')
            raw = reply['raw']
            need(type(raw) is dict and raw.get('native_acceptance') is False
                 and type(raw.get('cuts')) is list and len(raw['cuts']) == len(READERS)
                 and all(type(c) is dict and type(c.get('reader')) is str
                         and type(c.get('started_ns')) is int and type(c.get('finished_ns')) is int
                         for c in raw['cuts']), 'CLOSED_TYPED_INDEPENDENT_READER_CUTS')
            now = case.controller.clock()
            need(body(raw.get('observer')) == body(identity(self.session.child.binding.runtime))
                 and tuple(c['reader'] for c in raw['cuts']) == READERS
                 and all(start <= c['started_ns'] <= c['finished_ns'] <= now < end
                         and c['finished_ns']-c['started_ns'] <= self.intent.freshness_ns
                         and now-c['finished_ns'] <= self.intent.freshness_ns for c in raw['cuts']),
                 'SCOPED_READER_FRESHNESS_OR_IDENTITY_CONFLICT')
            case.output.append({'schema': 'AIP06_SCOPED_RAW_READER_V1', 'case': case.intent.case,
                                'reader': self.intent.reader, 'request': request, 'raw': raw,
                                'native_acceptance': False})
            self.result = raw
            self.result_hash = digest(raw)
            return raw
        except BaseException:
            self.failed = True
            self.case.factory.failed = True
            raise


READER_ENTRY = ntpath.join(ntpath.dirname(__file__), 'aip06_reader_context_entry.py')


def verify_inherited_scope(value, descriptor):
    """Private descriptor restriction only. Never adds roles or launch rights."""
    need(type(value) is dict and set(value) == {'schema','owner','owners','source_pins','intent'}
         and value['schema'] == 'AIP06_IMMUTABLE_CASE_VIEW_V1'
         and value['owner'] == digest(descriptor['binding']['parent'])
         and value['source_pins'] == digest(descriptor['source_pins']), 'PRIVATE_CASE_VIEW_PROVENANCE')
    need(type(value['owners']) in (list,tuple) and 0 < len(value['owners']) <= LIMITS['processes']
         and value['owners'][-1] == value['owner'] and len(set(value['owners'])) == len(value['owners']),
         'BOUNDED_CASE_ANCESTRY_CONTINUITY')
    c = value['intent']
    need(type(c) is dict and set(c) == set(CaseIntent.__dataclass_fields__), 'CLOSED_INHERITED_CASE_VIEW')
    token(c['case'])
    contract = next((v for v in contracts() if v.id == c['scenario']), None)
    need(contract is not None and c['root'] == path_for('E','case-'+c['case'])
         and c['schedule'] == digest(vars(contract)) and body(c['budget']) == body(tuple(sorted(LIMITS.items())))
         and body(c['accounts']) == body(ACCOUNTS)
         and type(c['manifest']) is str and len(c['manifest']) == 64
         and set(c['manifest']) <= set('0123456789abcdef')
         and c['evidence'] == digest({'manifest':c['manifest'],'case':c['case'],'owner':value['owners'][0]}),
         'EXACT_INHERITED_CASE_BUDGET_AND_SCOPE')
    commands, targets = dict(c['commands']), dict(c['targets'])
    need(tuple(commands) == contract.roles and tuple(targets) == contract.roles
         and len(c['commands']) == len(c['targets']) == len(contract.roles)
         and all(descriptor['targets'].get(role) == targets[role] == cmd[2]
                 and cmd[0] == descriptor['argv'][0] and cmd[1] == '-B'
                 and cmd[2] in descriptor['source_pins'] for role,cmd in commands.items()),
         'EXACT_INHERITED_ROLE_TARGET_VIEW')
    allowed = tuple(tuple(cmd) for cmd in commands.values())
    if descriptor['targets'].get('readonly_reader') == READER_ENTRY:
        allowed += ((descriptor['argv'][0],'-B',READER_ENTRY),)
    from scripts.observation_runtime.aip06_case_host_entry import HOST_ENTRY
    if descriptor['targets'].get('case_host') == HOST_ENTRY and HOST_ENTRY in descriptor['source_pins']:
        allowed += ((descriptor['argv'][0], '-B', HOST_ENTRY),)
    need(tuple(descriptor['argv']) in allowed, 'INHERITED_CASE_COMMAND_MISMATCH')
    return copy.deepcopy(value)


def verify_physical_host_handoff(packet, descriptor, guard):
    """Check private host handoff against inherited scope and original ledger.

    A valid packet is only data: it cannot authorize execution or attest native IO.
    """
    need(type(packet) is dict and set(packet) ==
         {'schema', 'case', 'reservation', 'native_acceptance', 'integrity'}
         and packet['schema'] == 'AIP06_PHYSICAL_CASE_HOST_HANDOFF_V1'
         and packet['native_acceptance'] is False
         and packet['integrity'] == digest({k: v for k, v in packet.items() if k != 'integrity'}),
         'CLOSED_INTEGRITY_BOUND_PHYSICAL_HOST_HANDOFF')
    view = verify_inherited_scope(packet['case'], descriptor)
    ticket = packet['reservation']
    contract = next((c for c in contracts() if c.id == view['intent']['scenario']), None)
    need(type(ticket) is dict and set(ticket) ==
         {'scenario', 'root', 'roles', 'held', 'stop_capacity_reserved', 'key',
          'commands', 'controller_command', 'case', 'manifest', 'evidence'}
         and contract is not None
         and body(ticket['commands']) == body(dict(view['intent']['commands']))
         and ticket.get('scenario') == view['intent']['scenario']
         and ticket.get('case') == view['intent']['case']
         and ticket.get('manifest') == view['intent']['manifest']
         and ticket.get('evidence') == view['intent']['evidence']
         and ticket.get('roles') == contract.roles
         and ticket.get('root') == ROOTS['E'] and ticket.get('held') is True
         and type(ticket.get('key')) is str and bool(ticket['key'])
         and ticket.get('stop_capacity_reserved') is True
         and ticket.get('controller_command') == guard.resources.channel.binding['launch']['command'],
         'EXACT_PHYSICAL_HOST_RESERVATION_SCOPE')
    need(guard.owner == view['owner'], 'ORIGINAL_PHYSICAL_HOST_GUARD_OWNER_REQUIRED')
    guard.check()
    state = guard.ledger('read')['state']
    need(state['resources'].get(ticket.get('key')) ==
         {'owner': view['owner'], 'kind': 'directory', 'closed': False},
         'ORIGINAL_PHYSICAL_HOST_RESERVATION_STILL_HELD')
    path = view['intent']['root']
    observed = guard.paths.port.inspect(path)
    need(observed is not None and guard.file_identities.get(path) == observed['id'],
         'ORIGINAL_PHYSICAL_HOST_DIRECTORY_IDENTITY_STILL_BOUND')
    return copy.deepcopy(packet)


def forward_scope(value, guard):
    guard.check(); state = guard.ledger('read')['state']
    current, prior = state['owners'].get(guard.owner), state['owners'].get(value['owner'])
    need(current is not None and prior is not None and current['parent_pid'] == prior['pid']
         and current['created'] >= prior['created'] and guard.owner not in value['owners'],
         'CASE_FORWARD_CURRENT_DESCENDANT_ANCESTRY')
    result = copy.deepcopy(value)
    result['owner'] = guard.owner
    result['owners'] = [*value['owners'], guard.owner]
    return result


class ReaderExecutionContext:
    """Construct ONLY in the independent reader's inherited guarded context.

    Native provider construction remains injected, not an automatic OS loader.
    Parent handles and controller Python objects never cross this boundary.
    """
    def __init__(self, guard, packet, adapters, acl_reader):
        from scripts.observation_runtime.aip06_ipc import RemoteResources
        from scripts.observation_runtime.aip06_windows_acceptance_adapters import WindowsReaderSet, PinnedWindowsRead
        from scripts.observation_runtime.aip06_controller_contract import ControllerIntent
        need(type(guard.resources) is RemoteResources and type(packet) is dict
             and set(packet) == {'schema','raw','manifest','case','reader','request','nonce','owner','parent_owner'}
             and packet['schema'] == 'AIP06_SCOPED_READER_INPUT_V1'
             and len(body(packet).encode()) <= 65536, 'CLOSED_PRIVATE_READER_INPUT')
        self.guard, self.packet, self.adapters, self.acl_reader = guard, copy.deepcopy(packet), adapters, acl_reader
        intent = ControllerIntent(packet['raw'].encode(), packet['manifest']); self.plan = intent.plan()
        need(SOURCE in self.plan['source_pins'] and READER_ENTRY in self.plan['source_pins'], 'READER_CONTEXT_PINNED_SOURCES')
        self.binding = copy.deepcopy(guard.resources.channel.binding)
        self.result, self.failed = None, False
        need(type(adapters) is WindowsReaderSet and type(acl_reader) is PinnedWindowsRead,
             'CONCRETE_INDEPENDENT_PROVIDERS_AND_ACL_READER_REQUIRED')

    def verify(self, *, deadline_ns):
        from scripts.observation_runtime.aip06_acceptance_plan import decode_plan
        guard, p = self.guard, self.packet
        guard.check()
        need(not self.failed and self.binding == guard.resources.channel.binding
             and guard.processes.runtime.identity.verify(self.binding) == self.binding['child']
             and guard.clock() < deadline_ns, 'CURRENT_INDEPENDENT_READER_CONTEXT')
        need(decode_plan(p['raw'].encode(), p['manifest']) == self.plan
             and p['nonce'] == self.binding['nonce'] and p['owner'] == guard.owner == digest(self.binding['child'])
             and p['parent_owner'] == digest(self.binding['parent'])
             and guard.processes.runtime.descriptor['argv'] == [self.plan['executable'], '-B', READER_ENTRY]
             and guard.processes.runtime.descriptor['source_pins'] == self.plan['source_pins'],
             'PRIVATE_READER_NONCE_SOURCE_AND_ANCESTRY_CORRELATION')
        c, r = p['case'], p['reader']; token(c['case']); token(r['reader'])
        descriptor = guard.processes.runtime.descriptor
        private_view = verify_inherited_scope(descriptor.get('case_scope'), descriptor)
        need(body(private_view['intent']) == body(c), 'READER_PRIVATE_CASE_VIEW_MISMATCH')
        contract = next((v for v in contracts() if v.id == c['scenario']), None)
        need(contract is not None and set(c) == set(CaseIntent.__dataclass_fields__)
             and set(r) == set(ReaderIntent.__dataclass_fields__)
             and c['manifest'] == r['manifest'] == p['manifest'] and c['case'] == r['case']
             and c['root'] == path_for('E','case-'+c['case']) and c['schedule'] == digest(vars(contract))
             and body(c['budget']) == body(tuple(sorted(LIMITS.items()))) and body(c['accounts']) == body(ACCOUNTS)
             and body(r['names']) == body(READERS) and body(r['access']) == body(ACCESS)
             and body(r['apis']) == body(APIS) and r['freshness_ns'] == 2*10**9,
             'EXACT_READER_CASE_SCOPE_ACL_AND_SCHEDULE')
        request = p['request']; state = guard.ledger('read')['state']
        need(set(request) == {'scope','manifest','scenario','reservation','root'}
             and request['scope'] == SCOPE_HASH and request['manifest'] == p['manifest']
             and request['scenario'] == c['scenario'] and request['root'] == ROOTS['E']
             and state['resources'].get(request['reservation']) ==
                 {'owner':p['parent_owner'],'kind':'directory','closed':False}
             and state['owners'].get(guard.owner) == self.binding['child'], 'CURRENT_SHARED_READER_RESERVATION')
        observed = self.adapters.processes.check_reader(deadline_ns=deadline_ns)
        need(observed == wire_identity(self.binding['child']) and observed != wire_identity(self.binding['parent'])
             and body(self.adapters.processes.reader_binding.runtime) == body(self.binding['child'])
             and body(self.adapters.processes.reader_binding.parent) == body(self.binding['parent'])
             and self.adapters.pin == p['manifest']
             and any(row['owner'] == guard.owner and row['kind'] == 'process' and not row['closed']
                     for row in state['resources'].values()), 'OWNER_CANNOT_SELF_CERTIFY_READER_CUT')
        path, fid, sha = self.adapters.processes.reader_binding.request.runtime_image
        need(self.acl_reader.pins.get(path) == {'file_id':list(fid),'sha256':sha}, 'EXACT_READER_ACL_IMAGE_PIN')
        need(self.acl_reader.allocations.resources is guard.resources and self.acl_reader.allocations.owner == guard.owner,
             'READER_ACL_RESERVATIONS_IN_SAME_SHARED_LEDGER')
        self.acl_reader.read_bytes(path, maximum_bytes=32*1024**2, deadline_ns=deadline_ns)

    def collect(self, request, *, deadline_ns):
        try:
            need(self.result is None and request == self.packet['request'], 'SCOPED_READER_ONCE_ONLY_REQUEST')
            self.verify(deadline_ns=deadline_ns)
            start = self.guard.clock()
            raw = self.adapters.collect(request, deadline_ns=deadline_ns)
            need(raw['native_acceptance'] is False and body(raw['observer']) == body(wire_identity(self.binding['child']))
                 and tuple(c['reader'] for c in raw['cuts']) == READERS
                 and all(start <= c['started_ns'] <= c['finished_ns'] <= self.guard.clock() < deadline_ns
                         and c['finished_ns']-c['started_ns'] <= 2*10**9 for c in raw['cuts']),
                 'INDEPENDENT_RAW_CUT_FRESHNESS_AND_COMPLETENESS')
            self.verify(deadline_ns=deadline_ns)
            self.result = raw
            self.guard.processes.emit_output({'schema':'AIP06_SCOPED_READER_REPLY_V1',
                'case':self.packet['case']['case'],'reader':self.packet['reader']['reader'],
                'request':digest(request),'nonce':self.packet['nonce'],'owner':self.guard.owner,
                'raw':raw,'native_acceptance':False})
            return raw
        except BaseException:
            self.failed = True
            raise
