"""No native effects: guarded preallocation case-host plan validation."""

from types import SimpleNamespace
import pytest

from scripts.observation_runtime.aip06_case_host_entry import HOST_ENTRY
from scripts.observation_runtime.aip06_case_host_launch_intent import verify_reserved_suspended_plan
from scripts.observation_runtime.aip06_harness import LIMITS
from scripts.observation_runtime.aip06_scoped_context import CaseContext


def fixture():
    executable = r'D:\reviewed\python.exe'
    argv = (executable, '-B', HOST_ENTRY)
    controller = SimpleNamespace(profile={'targets': {'case_host': HOST_ENTRY}})
    factory = SimpleNamespace(plan={'executable': executable})
    guard = SimpleNamespace(owner='original-owner')
    port = SimpleNamespace()
    guard.processes = port
    case = object.__new__(CaseContext)
    case.guard, case.factory, case.controller = guard, factory, controller
    case.reservation = {'held': True, 'stop_capacity_reserved': True}
    factory.pending = port.scoped_case = case
    plan = {'name': 'case_host', 'parent_owner': guard.owner,
            'resource_kinds': ('job', 'thread', 'image', 'pipe'),
            'job_limits': {**{k: LIMITS[k] for k in ('processes', 'private_bytes', 'child_private_bytes', 'cpu_ns')},
                           'kill_on_close': True}}
    return guard, argv, plan


def test_exact_owner_suspended_host_plan_is_data_only():
    guard, argv, plan = fixture()
    assert verify_reserved_suspended_plan(guard, argv, plan) is None


@pytest.mark.parametrize('damage', ['foreign_owner', 'wrong_role', 'missing_job', 'no_kill_on_close',
                                   'wrong_command', 'missing_case', 'foreign_guard', 'no_reservation'])
def test_suspended_host_plan_rejects_unowned_or_unescrowed_creation(damage):
    guard, argv, plan = fixture()
    case = guard.processes.scoped_case
    if damage == 'foreign_owner': plan['parent_owner'] = 'other'
    if damage == 'wrong_role': plan['name'] = 'acceptance_worker'
    if damage == 'missing_job': plan['resource_kinds'] = ('thread', 'image', 'pipe')
    if damage == 'no_kill_on_close': plan['job_limits']['kill_on_close'] = False
    if damage == 'wrong_command': argv = (*argv, '--extra')
    if damage == 'missing_case': guard.processes.scoped_case = None
    if damage == 'foreign_guard': case.guard = object()
    if damage == 'no_reservation': case.reservation = None
    with pytest.raises(ValueError):
        verify_reserved_suspended_plan(guard, argv, plan)
