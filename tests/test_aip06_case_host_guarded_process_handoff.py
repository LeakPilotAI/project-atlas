"""Offline original GuardedProcess-to-owner INPUT boundary checks."""
from types import SimpleNamespace
import pytest
from scripts.observation_runtime.aip06_fixture_guard import GuardedProcess


def setup():
    calls = []
    port = SimpleNamespace(guard=None)
    port.deliver_case_host_input = lambda child, packet, *, deadline_ns: calls.append((child, packet, deadline_ns))
    guard = SimpleNamespace(processes=port)
    port.guard = guard
    plan = {'name': 'case_host'}
    child = SimpleNamespace(name='case_host', plan=plan)
    process = GuardedProcess(guard, child, plan, (), ('python', '-B', 'host'))
    return process, port, calls


def test_explicit_original_process_routes_once_to_original_owner():
    process, _, calls = setup()
    packet = {'schema': 'AIP06_PHYSICAL_CASE_HOST_HANDOFF_V1'}
    assert process.send_case_host_handoff(packet, deadline_ns=123) is None
    assert calls == [(process.child, packet, 123)]


@pytest.mark.parametrize('damage', ['closed', 'foreign_role', 'foreign_child', 'foreign_plan', 'foreign_guard'])
def test_guarded_process_rejects_foreign_or_closed_handoff(damage):
    process, port, calls = setup()
    if damage == 'closed': process.closed = True
    if damage == 'foreign_role': process.plan['name'] = 'query'
    if damage == 'foreign_child': process.child.name = 'reader'
    if damage == 'foreign_plan': process.child.plan = {}
    if damage == 'foreign_guard': port.guard = object()
    with pytest.raises(ValueError, match='ORIGINAL_GUARDED_CASE_HOST_PROCESS_REQUIRED'):
        process.send_case_host_handoff({}, deadline_ns=123)
    assert not calls
