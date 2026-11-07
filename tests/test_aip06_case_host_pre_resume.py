"""Injected pre-resume original handle and Job receipt refusal tests."""
from types import SimpleNamespace
import pytest
from scripts.observation_runtime.aip06_case_host_launch_intent import verify_suspended_host_before_resume
from scripts.observation_runtime.aip06_harness import LIMITS
from scripts.observation_runtime.aip06_native_session import Session


def setup():
    limits = {k: LIMITS[k] for k in ('processes', 'private_bytes', 'child_private_bytes', 'cpu_ns')}
    limits['kill_on_close'] = True
    session = Session(name='case_host', permit={}, keys=(), argv=(), options={},
        observer=None, plan={'parent_owner': 'original',
        'job_limits': limits, 'request': SimpleNamespace(nonce='a'*32, launch_command='pinned-command')},
        creation_attempted=True, launch_handle=101, runtime_handle=101,
        parent_handle=100, thread=102, job=103,
        creation_native={'pid': 555, 'created': 12345, 'image': 'pinned-image'})
    observed = {'limits': dict(limits), 'members': [555], 'suspended': True, 'handle': 103}
    guard = SimpleNamespace(owner='original', resources=SimpleNamespace(
        state={'owners': {'original': {'pid': 77}}}))
    child = {'pid': 555, 'created': 12345, 'image': 'pinned-image',
             'parent_pid': 77, 'command_line': 'pinned-command'}
    parent = {'pid': 77}
    session.observer = SimpleNamespace(observe=lambda handle: child if handle == 101 else parent,
                                       members=lambda: {555})
    session.observer.parent = session.parent_handle
    session.observer.job = session.job
    session.plan['api'] = session.observer
    port = SimpleNamespace(sessions=[session], plans={'a'*32: {
        'plan': session.plan, 'argv': tuple(session.argv)}})
    guard.processes = SimpleNamespace(port=port)
    return session, observed, guard


def test_original_retained_suspended_receipts_are_data_only():
    s, job, guard = setup()
    assert verify_suspended_host_before_resume(s, job, guard) is None


@pytest.mark.parametrize('damage', ['resumed', 'failed', 'no_creation', 'foreign_parent',
    'foreign_handle', 'missing_thread', 'missing_job', 'missing_native', 'wrong_pid',
    'wrong_member', 'extra_member', 'wrong_job', 'wrong_limits', 'not_suspended',
    'kill_on_close_disabled', 'retired_nonce', 'observer_wrong_pid',
    'observer_wrong_parent', 'observer_wrong_command', 'observer_extra_member',
    'observer_wrong_creation', 'observer_wrong_image', 'foreign_observer',
    'observer_foreign_parent_handle', 'observer_foreign_job_handle',
    'unregistered_session', 'foreign_plan', 'foreign_argv'])
def test_case_host_refuses_invalid_pre_resume_receipt(damage):
    s, job, guard = setup()
    if damage == 'resumed': s.suspended = False
    if damage == 'failed': s.failed = True
    if damage == 'no_creation': s.creation_attempted = False
    if damage == 'foreign_parent': s.plan['parent_owner'] = 'foreign'
    if damage == 'foreign_observer': s.plan['api'] = object()
    if damage == 'unregistered_session': guard.processes.port.sessions.clear()
    if damage == 'foreign_plan': guard.processes.port.plans['a'*32]['plan'] = {}
    if damage == 'foreign_argv': guard.processes.port.plans['a'*32]['argv'] = ('foreign',)
    if damage == 'observer_foreign_parent_handle': s.observer.parent = 999
    if damage == 'observer_foreign_job_handle': s.observer.job = 999
    if damage == 'foreign_handle': s.runtime_handle = 104
    if damage == 'missing_thread': s.thread = None
    if damage == 'missing_job': s.job = None
    if damage == 'missing_native': s.creation_native = None
    if damage == 'wrong_pid': s.creation_native['pid'] = 4
    if damage == 'wrong_member': job['members'] = [556]
    if damage == 'extra_member': job['members'] = [555, 556]
    if damage == 'wrong_job': job['handle'] = 104
    if damage == 'wrong_limits': job['limits']['cpu_ns'] += 1
    if damage == 'not_suspended': job['suspended'] = False
    if damage == 'kill_on_close_disabled': s.plan['job_limits']['kill_on_close'] = False
    if damage == 'retired_nonce': guard.retired_launch_nonces = {'a'*32}
    if damage.startswith('observer_'):
        child = dict(s.observer.observe(101))
        if damage == 'observer_wrong_pid': child['pid'] = 556
        if damage == 'observer_wrong_parent': child['parent_pid'] = 78
        if damage == 'observer_wrong_command': child['command_line'] = 'other'
        if damage == 'observer_wrong_creation': child['created'] = 12346
        if damage == 'observer_wrong_image': child['image'] = 'other'
        members = {555, 556} if damage == 'observer_extra_member' else {555}
        s.observer.observe = lambda handle: child if handle == 101 else {'pid': 77}
        s.observer.members = lambda: members
    with pytest.raises(ValueError):
        verify_suspended_host_before_resume(s, job, guard)


def test_equal_but_unretained_session_cannot_authorize_resume():
    from copy import copy
    session, job, guard = setup()
    substituted = copy(session)
    assert substituted == session and substituted is not session
    guard.processes.port.sessions[:] = [substituted]
    with pytest.raises(ValueError, match="ORIGINAL_RETAINED_CASE_HOST_SESSION_REQUIRED"):
        verify_suspended_host_before_resume(session, job, guard)

@pytest.mark.parametrize("damage", ["missing_plan", "missing_request", "missing_job_receipt"])
def test_malformed_pre_resume_receipts_fail_closed_before_observation(damage):
    session, job, guard = setup()
    if damage == "missing_plan": session.plan = None
    if damage == "missing_request": session.plan["request"] = None
    if damage == "missing_job_receipt": job = None
    with pytest.raises(ValueError, match="TYPED_SUSPENDED_CASE_HOST_RECEIPT_REQUIRED"):
        verify_suspended_host_before_resume(session, job, guard)
