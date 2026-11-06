"""Original-owner case-host abort integration over injected native responses."""

from contextlib import nullcontext
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_aip06_harness import resources
from test_launch_ownership import setup as launch_fixture

from scripts.observation_runtime.aip06_fixture_guard import GuardedProcess
from scripts.observation_runtime.aip06_harness import WorkerOwnership
from scripts.observation_runtime.aip06_native_session import Session, WindowsSessionPort


def fixture(damage=None, *, exit_code=1):
    s = resources()
    api, request, ready = launch_fixture()
    request = replace(request, role='acceptance_supervisor')
    ready['role'] = request.role
    roster = WorkerOwnership(s.ledger, all_members=lambda: api.pids.copy())
    roster.prepare('case_host', request)
    roster.bind('case_host', api=api, request=request,
                parent_handle='parent', launch_handle='launch',
                runtime_handle='launch', ready=ready)
    bound = roster.bindings['case_host']
    slot = roster.prepared['case_host']['slots'][0]
    native_key = 'native-session-handle'
    s.ledger.reserve(s.controller, native_key, 'handle')

    events = []

    class Calls:
        def __init__(self):
            self.closed_handles = set()

        def lifecycle(self, handle):
            result = api.lifecycle(handle)
            if damage == 'malformed-receipt' and result['exited']:
                return {'pid': result['pid'], 'created': result['created'],
                        'exited': True, 'exit_code': True}
            if damage == 'identity-substitution' and result['exited']:
                result['created'] += 1
            return result

        def in_job(self, handle, job):
            return handle == 'launch' and job == 'job'

        def terminate_owned_job(self, job):
            events.append('terminate-job')
            api.exit_codes['launch'] = exit_code
            if damage != 'incomplete-job-drain':
                api.pids.clear()

        def wait(self, handle, deadline_ns):
            events.append('wait')
            if damage == 'parent-substitution':
                api.rows['parent']['created'] += 1

        def members(self, job):
            return api.pids.copy()

        def close(self, handle):
            events.append(('close', handle))
            if damage == 'incomplete-handle-close':
                return
            self.closed_handles.add(handle)

        def closed(self, handle):
            return handle in self.closed_handles

    calls = Calls()
    child = Session(
        name='case_host',
        plan={'name': 'case_host', 'request': request},
        permit={'slots': [slot]},
        keys=(native_key,),
        argv=(),
        options={},
        observer=None,
        native={native_key: {'kind': 'handle', 'handle': 'native-handle'}},
        job='job',
        launch_handle='launch',
        runtime_handle='launch',
        binding=bound,
        creation_native=dict(bound.launch),
    )
    guard = SimpleNamespace(owner=s.controller, ownership=roster, resources=s.ledger,
                            internal=lambda _mode: nullcontext())

    class Protocol:
        def close(self, session, *, deadline_ns):
            assert session is child and deadline_ns == 1000
            events.append('protocol-close')

    class Descendants:
        def release(self, session):
            assert session is child and session.binding.finished
            events.append('descendants-release')

    port = object.__new__(WindowsSessionPort)
    port.guard = guard
    guard.processes = port
    port.resources = s.ledger
    port.calls = calls
    port.protocol = Protocol()
    port.sessions = [child]
    port.closed_proofs = set()
    port.clock = lambda: 100
    port.aggregate = None
    port.descendant_gateway = Descendants()
    port.failed = False

    host = GuardedProcess(guard, child, child.plan,
                          (native_key, slot), ())
    return SimpleNamespace(
        s=s, api=api, roster=roster, bound=bound, slot=slot,
        native_key=native_key, child=child, guard=guard, port=port,
        host=host, events=events, calls=calls, damage=damage,
    )


@pytest.mark.parametrize('exit_code', [0, 1])
def test_abort_integrates_original_roster_native_close_ledger_and_wrapper(exit_code):
    f = fixture(exit_code=exit_code)

    receipt = f.host.abort_case_host(deadline_ns=1000)

    assert receipt == {'pid': f.bound.launch['pid'],
                       'created': f.bound.launch['created'],
                       'exited': True, 'exit_code': exit_code}
    assert f.roster.finished == {'case_host'} and f.bound.finished
    assert f.child.closed and f.host.closed
    assert f.port.resources_closed(f.child, f.host.keys)
    assert all(f.s.ledger.state['resources'][key]['closed']
               for key in f.host.keys)
    assert f.events.index('descendants-release') < f.events.index('protocol-close')
    assert f.events.index('wait') < f.events.index('protocol-close')
    assert f.port.all_members() == set()
    with pytest.raises(ValueError, match='ORIGINAL_GUARDED_CASE_HOST_ABORT_REQUIRED'):
        f.host.abort_case_host(deadline_ns=1000)


@pytest.mark.parametrize(
    'damage',
    ['malformed-receipt', 'identity-substitution', 'parent-substitution',
     'incomplete-job-drain'],
)
def test_abort_refuses_bad_terminal_or_ownership_evidence_without_closing(damage):
    f = fixture(damage)

    with pytest.raises(ValueError):
        f.host.abort_case_host(deadline_ns=1000)

    assert not f.host.closed
    assert not f.s.ledger.state['resources'][f.slot]['closed']
    assert f.events.count('protocol-close') == 0


@pytest.mark.parametrize('damage', ['incomplete-handle-close', 'ledger-conflict'])
def test_abort_refuses_incomplete_native_or_ledger_closure(damage):
    f = fixture(damage)
    if damage == 'ledger-conflict':
        original_closed = f.port.closed
        checks = {}

        def conflicting_closed(owner, key):
            if key == f.native_key:
                checks[key] = checks.get(key, 0) + 1
                return checks[key] == 1
            return original_closed(owner, key)

        f.port.closed = conflicting_closed

    with pytest.raises(ValueError):
        f.host.abort_case_host(deadline_ns=1000)

    assert f.bound.finished
    assert not f.host.closed
    assert not any(f.s.ledger.state['resources'][key]['closed']
                   for key in f.host.keys)


def test_failed_abort_transition_is_latched_against_receipt_replay():
    f = fixture()
    f.api.exit_codes['launch'] = 1
    f.api.pids.clear()
    malformed = {'pid': f.bound.launch['pid'],
                 'created': f.bound.launch['created'],
                 'exited': True, 'exit_code': True}
    with pytest.raises(ValueError):
        f.roster.abort_exit('case_host', malformed)
    with pytest.raises(ValueError, match='BOUND_CASE_HOST_ABORT_REQUIRED'):
        f.roster.abort_exit('case_host', {
            'pid': f.bound.launch['pid'],
            'created': f.bound.launch['created'],
            'exited': True, 'exit_code': 1,
        })

    assert f.roster.refused
    assert not f.bound.finished
    assert not f.s.ledger.state['resources'][f.slot]['closed']


def test_native_session_abort_attempt_cannot_be_replayed_after_receipt_failure():
    f = fixture('malformed-receipt')

    with pytest.raises(ValueError):
        f.host.abort_case_host(deadline_ns=1000)
    with pytest.raises(ValueError, match='ORIGINAL_SESSION_ABORT_REPLAY_REFUSED'):
        f.port.abort(f.child, deadline_ns=1000, ownership=f.roster)

    assert f.child.abort_attempted
    assert not f.host.closed
    assert not f.s.ledger.state['resources'][f.slot]['closed']
