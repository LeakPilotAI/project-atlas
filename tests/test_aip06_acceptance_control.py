"""Control-plane qualification with memory files and injected process objects.

No native loader, subprocess, socket, fixture-root creation or grant is used.
"""

import copy
import hashlib
import ntpath
from subprocess import list2cmdline
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import body, digest
from scripts.observation_runtime.aip06_acceptance_control import (
    Deadline, Dispatcher, GuardedScenarioBridge, INJECTED, NS, OuterOwner,
    OwnerLaunch, scenarios,
)
from scripts.observation_runtime.aip06_acceptance_grade import IndependentGrader, READERS
from scripts.observation_runtime.aip06_acceptance_plan import ENTRY, REPO, RUNTIME, candidate_plan
from scripts.observation_runtime.aip06_harness import LIMITS, ROOTS, SCOPE_HASH
from scripts.observation_runtime.launch_ownership import LaunchRequest, RetainedLaunchBinding, identity


def sha(value): return hashlib.sha256(value).hexdigest()


class Clock:
    def __init__(self): self.value = 100 * NS
    def __call__(self): self.value += 1000; return self.value


class Files:
    def __init__(self):
        self.rows = {ENTRY: b'entry'}
        self.rows[ntpath.join(RUNTIME, 'python.exe')] = b'injected executable'
        dep = b'injected dependency'
        self.rows[ntpath.join(RUNTIME, 'python312.dll')] = dep
        records = [{'path': name, 'kind': 'file', 'links': 1, 'size': len(data), 'sha256': sha(data)}
                   for name, data in [('python.exe', b'injected executable'), ('python312.dll', dep)]]
        inventory = {'schema': 'AIP06_READONLY_RUNTIME_BYTES_V1', 'runtime': RUNTIME, 'records': records}
        self.inventory_path = ntpath.join(ntpath.dirname(ROOTS['E']), 'INJECTED-CONTROL-INVENTORY.json')
        raw = body(inventory).encode(); self.rows[self.inventory_path] = raw
        self.plan = candidate_plan(source_pins={ENTRY: sha(b'entry')}, runtime_inventory={
            'path': self.inventory_path, 'sha256': sha(raw), 'files': 2, 'directories': 0,
            'read_bytes': sum(r['size'] for r in records), 'native_identity_accepted': False,
            'complete_acl_accepted': False}, async_review={'compatible': False, 'native_execution': False})
        self.reads = []

    def read_bytes(self, path, *, maximum_bytes, deadline_ns):
        self.reads.append(path)
        return self.rows[path]


class Observer:
    def __init__(self, rows): self.rows = rows; self.job = {102}
    def observe(self, handle): return copy.deepcopy(self.rows[handle])
    def members(self): return set(self.job)


class Owner:
    domain = INJECTED
    def __init__(self, x): self.x = x; self.calls = []; self.closed = False; self.release_checked = False

    def preflight(self, plan, *, manifest_sha256, deadline_ns):
        self.calls.append('preflight')
        row = {'domain': INJECTED, 'manifest': manifest_sha256, 'roots': dict(ROOTS), 'roots_absent': True,
               'native_identity_and_acl_checks': True, 'async_socket_guard_compatible': True, 'network': plan['network']}
        if self.x.damage.startswith('preflight:'): row[self.x.damage.split(':')[1]] = False
        return row

    def reserve(self, limits, *, deadline_ns):
        self.calls.append('reserve')
        return {'held': True, 'limits': limits, 'includes_outer_owner': True, 'stop_capacity_reserved': True}

    def launch_controller(self, entry, executable, *, deadline_ns):
        self.calls.append('launch')
        x = self.x
        cmd = list2cmdline([executable, '-B', entry, '--role', 'controller', '--manifest',
            ntpath.join(REPO, 'docs', 'AIP_06_NATIVE_CANDIDATE_RUN_MANIFEST_2026-11-05.json'), '--manifest-sha256', x.pin])
        image = (executable, (1, 2, 3), sha(b'injected executable'))
        rows = {1: dict(pid=101, created=10, image=image[0], file_id=image[1], sha256=image[2],
                        command_line='original owner', parent_pid=99),
                2: dict(pid=102, created=20, image=image[0], file_id=image[1], sha256=image[2],
                        command_line=cmd, parent_pid=101)}
        x.observer = Observer(rows)
        request = LaunchRequest('acceptance_supervisor', 'a'*32, 'direct', image, image, cmd, cmd)
        binding = RetainedLaunchBinding(x.observer, request, 1, 2)
        binding.bind_runtime(2, {'pid': 102, 'nonce': 'a'*32, 'role': 'acceptance_supervisor'})
        x.launch = OwnerLaunch(binding, x.pin)
        return x.launch

    def verify_controller(self, first, *, deadline_ns):
        self.calls.append('verify'); first.verify(self.x.files.plan, self.x.pin)

    def cleanup(self, first, *, deadline_ns):
        self.calls.append('cleanup'); self.closed = True
        return self.x.damage != 'owner-cleanup'

    def verify_released(self, *, deadline_ns):
        self.calls.append('verify-released'); self.release_checked = True
        if self.x.damage == 'owner-release': raise ValueError('remaining original launch handle')


class Adapter:
    domain = INJECTED
    def __init__(self, x):
        self.x = x; self.owner_launch = x.launch; self.events = []; self.released = False

    def check(self, scenario, *, deadline_ns):
        self.events.append(('check', scenario.id))
        if self.x.damage == 'unbound-case' and scenario.id == 'F11': raise ValueError('missing capacity binding')

    def reserve(self, scenario, *, deadline_ns):
        self.events.append(('reserve', scenario.id)); self.released = False
        if self.x.damage == 'interrupted-reserve': raise ValueError('interrupted reservation')
        row = {'scenario': scenario.id, 'roles': scenario.roles, 'held': True, 'stop_capacity_reserved': True,
               'key': 'reserved:' + scenario.id, 'root': ROOTS['E'], 'controller_command': self.x.launch.binding.runtime['command_line'],
               'commands': {r: (self.x.files.plan['executable'], '-B', ENTRY, '--injected-role', r) for r in scenario.roles},
               'endpoints': (('127.0.0.1', 50001),)}
        if self.x.damage == 'no-reservation': row['held'] = False
        if self.x.damage == 'wrong-role': row['roles'] = ('query',)
        if self.x.damage == 'reused-ticket': row['key'] = 'one-ticket'
        if self.x.damage == 'wrong-reservation-root': row['root'] = r'D:\AtlasRuntime'
        self.x.reservation = row
        return row

    def execute(self, scenario, reservation, *, deadline_ns):
        self.events.append(('execute', scenario.id)); self.x.scenario = scenario
        if self.x.damage == 'execution': raise ValueError('scenario fault')
        row = {'domain': INJECTED, 'native_acceptance': False, 'scenario': scenario.id, 'reservation': reservation['key']}
        if scenario.sample is not None:
            row.update(sample=scenario.sample, stop_started_ns=self.x.clock(), stop_finished_ns=self.x.clock())
            if self.x.damage == 'late-stop': self.x.clock.value += 8 * NS
        if self.x.damage == 'fake-native': row.update(domain='NATIVE', native_acceptance=True)
        return row

    def release(self, scenario, reservation, evidence, *, deadline_ns):
        self.events.append(('release', scenario.id)); self.released = True
        if self.x.damage == 'late-release' and scenario.sample: self.x.clock.value += 8 * NS
        return self.x.damage != 'failed-release'

    def abort(self, scenario, reservation, *, deadline_ns):
        self.events.append(('abort', scenario.id))
        return self.x.damage != 'failed-abort'


class Reader:
    domain = INJECTED
    source_path = ENTRY
    source_sha256 = sha(b'entry')
    def __init__(self, name, x): self.name, self.x, self.sequence = name, x, 0
    def read(self, request, *, deadline_ns):
        x = self.x; self.sequence += 1
        x.read_order.append((request['scenario'], self.name))
        cut = {'reader': self.name, 'domain': INJECTED, 'request': digest(request), 'sequence': self.sequence,
               'started_ns': x.clock(), 'finished_ns': x.clock(), 'complete': True, 'error': None,
               'payload': self.payload()}
        if x.damage == 'stale-cut': cut['started_ns'] -= 3 * NS
        if x.damage == 'incomplete-cut': cut['complete'] = False
        if x.damage == 'conflicting-request': cut['request'] = 'f'*64
        if x.damage == 'replayed-cut': cut['sequence'] = 0
        if x.damage == 'native-flag': cut['domain'] = 'NATIVE'
        return cut

    def payload(self):
        x = self.x; damage = x.damage; reservation = x.reservation; scenario = x.scenario
        parent = x.launch.binding.parent; controller = x.launch.binding.runtime
        if self.name == 'HANDLES':
            descendants = []
            for i, role in enumerate(scenario.roles):
                native = {**controller, 'pid': 103+i, 'created': 30+i, 'parent_pid': controller['pid'],
                          'command_line': list2cmdline(list(reservation['commands'][role]))}
                descendants.append({'role': role, 'current': native, 'launched': copy.deepcopy(native),
                    'parent': identity(controller), 'original_handle_retained': True, 'exited_normally': True,
                    'command': reservation['commands'][role]})
            row = {'owner': copy.deepcopy(parent), 'controller': copy.deepcopy(controller),
                'controller_parent': identity(parent), 'original_launch_handle_retained': True,
                'controller_command': reservation['controller_command'], 'descendants': descendants}
            if damage == 'missing-identity': del row['controller']['file_id']
            if damage == 'wrong-ancestry': descendants[0]['parent'] = identity(parent)
            if damage == 'wrong-command': descendants[0]['command'] = ('another command',)
            if damage == 'stale-identity': descendants[0]['current']['created'] += 1
            if damage == 'unknown-descendant': descendants.append({**descendants[0], 'role': 'unregistered'})
            if damage == 'missing-handle': descendants[0]['original_handle_retained'] = False
            if damage == 'observed-command': descendants[0]['current']['command_line'] = 'wrong command'
            if damage == 'observed-parent': descendants[0]['current']['parent_pid'] = 999
            if damage == 'observed-executable': descendants[0]['current']['image'] = r'D:\foreign.exe'
            if damage == 'pid-reuse': descendants[0]['current']['pid'] = controller['pid']; descendants[0]['launched']['pid'] = controller['pid']
            return row
        if self.name == 'JOB':
            workers = [identity({**controller, 'pid': 103+i, 'created': 30+i}) for i in range(len(scenario.roles))]
            row = {'unknown': False, 'admitted': [identity(parent), identity(controller)] + workers,
                   'members': [identity(parent), identity(controller)], 'unexpected': [], 'retained_job_handle': True}
            if damage == 'missing-job': row['admitted'].pop()
            if damage == 'unexpected-job': row['unexpected'] = [999]
            return row
        if self.name == 'LEDGER':
            row = {'reservation': reservation['key'], 'stop_reserved': True, 'unreleased': [], 'unknown': False,
                   'reservation_released': x.adapter.released,
                   'peaks': {k: 1 for k in ('processes', 'private_bytes', 'child_private_bytes', 'cpu_ns', 'entries', 'bytes')}}
            if damage == 'resource-leak': row['unreleased'] = ['original ticket']
            if damage == 'over-capacity': row['peaks']['processes'] = 9
            if damage == 'release-not-observed': row['reservation_released'] = False
            return row
        if self.name == 'FINANCIAL':
            ack = {'scope': SCOPE_HASH, 'reservation': reservation['key'], 'operation': scenario.id}
            row = {'scenario': scenario.id, 'proof': scenario.proof, 'ack': ack, 'committed': copy.deepcopy(ack),
                   'drain_request': copy.deepcopy(ack), 'pending': 0, 'unknown': False,
                   'accounts': {'QUALITY_DIPS': 'USD', 'HYPERLIQUID': 'USDC'},
                   'account_ids': {'QUALITY_DIPS': 'QD-fixture', 'HYPERLIQUID': 'HL-fixture'}, 'cash': '1015.9136', 'revision': 3}
            if damage == 'missing-ack': row['ack'] = None
            if damage == 'incomplete-drain': row['pending'] = 1
            if damage == 'currency-alias': row['accounts']['HYPERLIQUID'] = 'USD'
            return row
        if self.name == 'RESTART':
            return {'scenario': scenario.id, 'before_hashes': {'journal': 'a'*64},
                    'after_hashes': {'journal': ('b' if damage == 'restart-conflict' else 'a')*64}, 'reapplied': 0, 'unknown': False}
        if self.name == 'OBJECTS':
            return {'unknown': False, 'open_descendant_handles': [1] if damage == 'open-handle' else [],
                    'unreleased_objects': [], 'unexpected': [], 'retained_identity_verified_before_close': True}
        if self.name == 'PROCESS':
            return {'survivors': [999] if damage == 'survivor' else [], 'unknown': False,
                    'controller': identity(controller), 'owner': identity(parent)}
        state = {'state-zero': 0, 'pid-zero-listener': 2, 'listener': 2, 'disagreement': 11}.get(damage)
        rows = []
        if state is not None and (damage != 'disagreement' or self.name == 'CIM'):
            rows = [{'protocol': 'TCP', 'family': 4, 'local_address': '127.0.0.1', 'local_port': 50001,
                     'remote_address': '0.0.0.0', 'remote_port': 0, 'state': state,
                     'owner_present': True, 'owner_pid': 0 if damage in ('pid-zero-listener', 'state-zero') else 103}]
        return {'rows': rows}


def fixture(damage=''):
    x = SimpleNamespace(clock=Clock(), files=Files(), damage=damage, read_order=[], output=[])
    x.raw = body(x.files.plan).encode(); x.pin = sha(x.raw); x.owner = Owner(x)
    def dispatcher(clock):
        x.adapter = Adapter(x)
        readers = {n: Reader(n, x) for n in READERS}
        if damage == 'missing-reader': del readers['NETSTAT']
        x.grader = IndependentGrader(plan=x.files.plan, manifest_sha256=x.pin, readers=readers,
            clock_ns=x.clock, output=x.output, owner_launch=x.launch)
        x.dispatcher = Dispatcher(adapter=x.adapter, grader=x.grader, deadline=clock)
        return x.dispatcher
    x.control = OuterOwner(x.raw, x.pin, clock_ns=x.clock, files=x.files, owner=x.owner, dispatcher_factory=dispatcher)
    return x


def test_full_serial_source_matrix_includes_three_stop_samples_and_never_native_pass():
    x = fixture(); result = x.control.qualify_offline()
    assert result['status'] == 'SOURCE_CONTROL_PLANE_QUALIFIED' and result['native_acceptance'] is False
    assert [r['scenario'] for r in result['scenarios']] == [s.id for s in scenarios()]
    assert all(r['aggregate_released'] for r in result['scenarios'])
    assert x.owner.closed and x.owner.release_checked
    assert [v for k, v in x.adapter.events if k == 'execute'] == [s.id for s in scenarios()]
    for scenario in scenarios():
        order = [n for s, n in x.read_order if s == scenario.id]
        assert order[6:10] == ['CIM', 'IP_HELPER', 'NETSTAT', 'PROCESS']
    with pytest.raises(ValueError, match='ONCE_ONLY'): x.control.qualify_offline()
    with pytest.raises(ValueError, match='NOT_QUALIFIED'): x.grader.grade_native(result)


@pytest.mark.parametrize('grant,reason', [(None, 'FRESH_SCOPED'), ({'consumed': True}, 'REUSED'),
    ({'consumed': False, 'scope': SCOPE_HASH, 'native': True}, 'NOT_BOUND')])
def test_authorization_gate_never_reads_or_launches_or_consumes(grant, reason):
    x = fixture(); before = copy.deepcopy(grant)
    with pytest.raises(ValueError, match=reason): x.control.start(grant)
    assert not x.files.reads and not x.owner.calls and grant == before


@pytest.mark.parametrize('damage', ['wrong-role', 'wrong-reservation-root', 'no-reservation', 'unbound-case',
    'interrupted-reserve', 'execution', 'fake-native', 'missing-identity', 'wrong-ancestry', 'wrong-command',
    'stale-identity', 'unknown-descendant', 'missing-handle', 'observed-command', 'observed-parent',
    'observed-executable', 'pid-reuse', 'missing-job', 'unexpected-job',
    'resource-leak', 'over-capacity', 'missing-ack', 'incomplete-drain', 'currency-alias', 'restart-conflict',
    'open-handle', 'survivor', 'state-zero', 'pid-zero-listener', 'listener', 'disagreement', 'missing-reader',
    'stale-cut', 'incomplete-cut', 'conflicting-request', 'replayed-cut', 'native-flag', 'failed-release',
    'release-not-observed', 'late-stop', 'late-release', 'reused-ticket', 'owner-cleanup', 'owner-release'])
def test_adversarial_evidence_fails_closed_and_owned_cleanup_is_always_attempted(damage):
    x = fixture(damage)
    with pytest.raises((ValueError, KeyError)): x.control.qualify_offline()
    assert x.control.failed and x.owner.closed
    if hasattr(x, 'dispatcher'):
        assert len(x.dispatcher.completed) < len(scenarios()) or x.control.cleanup_failure
        if x.dispatcher.pending: assert x.adapter.events[-1][0] == 'abort'
    with pytest.raises(ValueError, match='ONCE_ONLY'): x.control.qualify_offline()


@pytest.mark.parametrize('field', ['roots', 'roots_absent', 'native_identity_and_acl_checks',
                                  'async_socket_guard_compatible', 'manifest', 'network'])
def test_preflight_refusals_do_not_launch(field):
    x = fixture('preflight:' + field)
    with pytest.raises(ValueError, match='PREFLIGHT'): x.control.qualify_offline()
    assert 'launch' not in x.owner.calls and x.owner.closed


@pytest.mark.parametrize('path', [ENTRY, ntpath.join(RUNTIME, 'python.exe'), ntpath.join(RUNTIME, 'python312.dll')])
def test_changed_source_executable_or_dependency_refuses_before_launch(path):
    x = fixture(); x.files.rows[path] = b'wrong'
    with pytest.raises(ValueError, match='HASH_MISMATCH'): x.control.qualify_offline()
    assert 'launch' not in x.owner.calls


def test_wrong_manifest_refuses_in_inert_constructor():
    x = fixture()
    with pytest.raises(ValueError, match='PIN_MISMATCH'):
        OuterOwner(x.raw, 'f'*64, clock_ns=x.clock, files=x.files, owner=x.owner, dispatcher_factory=None)
    assert not x.owner.calls and not x.files.reads


def test_incomplete_matrix_cannot_be_graded_as_complete():
    x = fixture(); result = x.control.qualify_offline()
    with pytest.raises(ValueError, match='ALL_FINANCIAL'): x.grader.finish(result['scenarios'][:-1])


def test_deadline_is_monotonic_bounded_and_cannot_omit_cleanup_time():
    clock = Clock(); deadline = Deadline(clock)
    clock.value -= NS
    with pytest.raises(ValueError, match='MONOTONIC'): deadline.now(deadline.work)


def test_guarded_bridge_has_no_binding_or_raw_spawn_fallback():
    guard = SimpleNamespace(processes=object(), check=lambda: None)
    bridge = GuardedScenarioBridge(SimpleNamespace(process_port=guard.processes), guard, {})
    with pytest.raises(ValueError, match='BINDING_MISSING'): bridge.reserve(scenarios()[0], deadline_ns=1)


def test_unbound_case_prevents_all_reservations_not_just_the_late_case():
    x = fixture('unbound-case')
    with pytest.raises(ValueError): x.control.qualify_offline()
    assert not any(e[0] == 'reserve' for e in x.adapter.events)


def test_partial_reservation_is_retained_for_abort_even_without_receipt():
    x = fixture('interrupted-reserve')
    with pytest.raises(ValueError, match='interrupted reservation'): x.control.qualify_offline()
    assert x.dispatcher.pending == (scenarios()[0], None) and x.adapter.events[-1] == ('abort', 'F01')


def test_constructor_and_controller_factory_are_inert():
    from scripts.observation_runtime.aip06_acceptance_controller import control_plane
    x = fixture()
    other = control_plane(x.raw, x.pin, clock_ns=x.clock, files=x.files, owner=x.owner, dispatcher_factory=None)
    assert not other.started and not x.owner.calls and not x.files.reads


def test_schedule_keeps_original_budgets_race_roles_and_three_cold_samples():
    rows = scenarios()
    assert len(rows) == 17 and sum(s.seconds for s in rows) == 464
    assert next(s for s in rows if s.id == 'F04').roles == ('race_one', 'race_two')
    assert [s.sample for s in rows if s.sample] == [1, 2, 3]
    assert 464 + 60 + 16 == LIMITS['work_seconds'] and LIMITS['seconds'] == 600


def test_bridge_routes_exact_race_pair_through_existing_guarded_injected_windows_path():
    from test_aip06_native_prerequisites import pair
    x = pair(); x.controller.process_port = x.port
    scenario = next(s for s in scenarios() if s.id == 'F04')
    class Binding:
        roles = scenario.roles
        source_pins = x.controller.profile['source_pins']
        def check(self, controller, guard, *, deadline_ns):
            assert controller is x.controller and guard is x.guard and not x.calls.handles
        def reserve(self, guard, *, deadline_ns):
            return x.port.declare_race_pair(x.commands)
        def execute(self, controller, guard, reservation, *, deadline_ns):
            children = [guard.spawn(command) for command in x.commands]
            assert [c.plan['name'] for c in children] == list(scenario.roles)
            assert len({c.child.binding.runtime_handle for c in children}) == 2
            for child in children: child.communicate()
            return reservation
        def release(self, guard, reservation, evidence, *, deadline_ns):
            return not x.calls.handles and x.port.all_members() == set()
    bridge = GuardedScenarioBridge(x.controller, x.guard, {'F04': Binding()})
    with x.guard.installed():
        reservation = bridge.reserve(scenario, deadline_ns=1)
        result = bridge.execute(scenario, reservation, deadline_ns=1)
        assert bridge.release(scenario, reservation, result, deadline_ns=1)
        assert all(r['closed'] for r in x.ledger.state['resources'].values())


@pytest.mark.parametrize('damage', ['role', 'pins', 'port'])
def test_bridge_refuses_unreviewed_bindings_and_foreign_process_ports(damage):
    port = object(); guard = SimpleNamespace(processes=port, check=lambda: None)
    pins = {ENTRY: 'a'*64}
    binding = SimpleNamespace(roles=scenarios()[0].roles, source_pins=pins)
    controller = SimpleNamespace(process_port=port, profile={'source_pins': pins})
    if damage == 'role': binding.roles = ('race_two',)
    if damage == 'pins': binding.source_pins = {ENTRY: 'b'*64}
    if damage == 'port': controller.process_port = object()
    bridge = GuardedScenarioBridge(controller, guard, {'F01': binding})
    with pytest.raises(ValueError): bridge.reserve(scenarios()[0], deadline_ns=1)


def test_plan_cannot_be_changed_after_inert_construction():
    x = fixture(); x.control.plan['roots']['E'] = r'D:\AtlasRuntime'
    with pytest.raises(ValueError, match='PLAN_MUTATED'): x.control.qualify_offline()
    assert not x.files.reads and 'launch' not in x.owner.calls


def test_unapproved_fixture_root_is_rejected_by_manifest_contract():
    x = fixture(); plan = copy.deepcopy(x.files.plan); plan['roots']['E'] = r'D:\AtlasRuntime'
    raw = body(plan).encode()
    with pytest.raises(ValueError, match='PATHS_AND_LIMITS'):
        OuterOwner(raw, sha(raw), clock_ns=x.clock, files=x.files, owner=x.owner, dispatcher_factory=None)
    assert not x.owner.calls


@pytest.mark.parametrize('damage', ['duplicate', 'native', 'unpinned'])
def test_reader_registration_requires_distinct_pinned_offline_ports(damage):
    x = fixture(); readers = {n: Reader(n, x) for n in READERS}
    if damage == 'duplicate': readers['JOB'] = readers['HANDLES']
    elif damage == 'native': readers['JOB'].domain = 'NATIVE'
    else: readers['JOB'].source_sha256 = 'b'*64
    with pytest.raises(ValueError):
        IndependentGrader(plan=x.files.plan, manifest_sha256=x.pin, readers=readers, clock_ns=x.clock,
                          output=x.output, owner_launch=None)


def test_preflight_and_pin_read_have_original_sixty_second_bound():
    x = fixture(); read = x.files.read_bytes
    def slow(*args, **kwargs): x.clock.value += 61 * NS; return read(*args, **kwargs)
    x.files.read_bytes = slow
    with pytest.raises(ValueError, match='DEADLINE'): x.control.qualify_offline()
    assert 'launch' not in x.owner.calls and x.owner.closed


def test_first_failure_is_preserved_when_owned_cleanup_also_fails():
    x = fixture('execution'); cleanup = x.owner.cleanup
    def failed(first, *, deadline_ns): cleanup(first, deadline_ns=deadline_ns); return False
    x.owner.cleanup = failed
    with pytest.raises(ValueError, match='scenario fault'): x.control.qualify_offline()
    assert x.control.failure == 'scenario fault' and x.control.cleanup_failure == 'OUTER_OWNER_CLEANUP_INCOMPLETE'


def test_retained_controller_birth_cannot_be_replaced_even_with_same_pid():
    x = fixture(); verify = x.owner.verify_controller
    def replaced(first, *, deadline_ns):
        x.observer.rows[2]['created'] += 1
        verify(first, deadline_ns=deadline_ns)
    x.owner.verify_controller = replaced
    with pytest.raises(ValueError, match='LIFETIME_CHANGED'): x.control.qualify_offline()
    assert x.owner.closed


def test_failed_abort_remains_explicit_and_does_not_replace_first_failure():
    x = fixture('execution')
    create = x.control.dispatcher_factory
    def dispatcher(clock):
        result = create(clock); result.adapter.abort = lambda *a, **k: False; return result
    x.control.dispatcher_factory = dispatcher
    with pytest.raises(ValueError, match='scenario fault'): x.control.qualify_offline()
    assert x.dispatcher.failure == 'scenario fault'
    assert x.dispatcher.cleanup_failure == 'DISPATCH_OWNED_ABORT_INCOMPLETE'
