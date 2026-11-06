"""Injected pre-resume original handle and Job receipt refusal tests."""
from types import SimpleNamespace
import pytest
from scripts.observation_runtime.aip06_case_host_launch_intent import verify_suspended_host_before_resume
from scripts.observation_runtime.aip06_harness import LIMITS


def setup():
    limits = {k: LIMITS[k] for k in ('processes', 'private_bytes', 'child_private_bytes', 'cpu_ns')}
    limits['kill_on_close'] = True
    session = SimpleNamespace(name='case_host', suspended=True, failed=False,
        creation_attempted=True, plan={'parent_owner': 'original',
        'job_limits': limits, 'request': SimpleNamespace(nonce='a'*32)},
        launch_handle=101, runtime_handle=101, thread=102, job=103,
        creation_native={'pid': 555})
    observed = {'limits': dict(limits), 'members': [555], 'suspended': True, 'handle': 103}
    guard = SimpleNamespace(owner='original')
    return session, observed, guard


def test_original_retained_suspended_receipts_are_data_only():
    s, job, guard = setup()
    assert verify_suspended_host_before_resume(s, job, guard) is None


@pytest.mark.parametrize('damage', ['resumed', 'failed', 'no_creation', 'foreign_parent',
    'foreign_handle', 'missing_thread', 'missing_job', 'missing_native', 'wrong_pid',
    'wrong_member', 'extra_member', 'wrong_job', 'wrong_limits', 'not_suspended',
    'kill_on_close_disabled', 'retired_nonce'])
def test_case_host_refuses_invalid_pre_resume_receipt(damage):
    s, job, guard = setup()
    if damage == 'resumed': s.suspended = False
    if damage == 'failed': s.failed = True
    if damage == 'no_creation': s.creation_attempted = False
    if damage == 'foreign_parent': s.plan['parent_owner'] = 'foreign'
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
    with pytest.raises(ValueError):
        verify_suspended_host_before_resume(s, job, guard)
