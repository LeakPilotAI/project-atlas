"""Offline original case-context handoff checks; no native process launch."""
from types import SimpleNamespace
import pytest
from scripts.observation_runtime.aip06_scoped_context import CaseContext
from scripts.observation_runtime.aip06_fixture_guard import GuardedProcess
from scripts.observation_runtime import aip06_case_host_launch_intent as launch


def setup(monkeypatch):
    case = object.__new__(CaseContext)
    guard = SimpleNamespace()
    port = SimpleNamespace(sessions=[])
    guard.processes = port
    case.guard = guard
    case.reservation = {'held': True}
    monkeypatch.setattr(CaseContext, 'verify', lambda self, *, deadline_ns: None)
    sent = []
    port.deliver_case_host_input = lambda child, packet, *, deadline_ns: sent.append((child, packet, deadline_ns))
    port.guard = guard
    plan = {'name': 'case_host'}
    child = SimpleNamespace(name='case_host', plan=plan)
    port.sessions.append(child)
    process = GuardedProcess(guard, child, plan, (), ('python', '-B', 'host'))
    packet = {'schema': 'AIP06_PHYSICAL_CASE_HOST_HANDOFF_V1'}
    monkeypatch.setattr(launch, 'inspect_launch_intent', lambda *a, **kw: {
        'argv': process.argv, 'handoff': packet, 'native_acceptance': False,
        'execution_authorized': False})
    return case, process, port, sent


def test_existing_original_host_routes_handoff(monkeypatch):
    case, process, _, sent = setup(monkeypatch)
    case.deliver_physical_host_handoff(process, deadline_ns=200)
    assert len(sent) == 1 and sent[0][0] is process.child


@pytest.mark.parametrize('damage', ['foreign_guard', 'unregistered', 'closed', 'wrong_role', 'wrong_argv', 'unauthorized_intent', 'malformed_argv', 'nonstring_argv'])
def test_context_refuses_unowned_or_unqualified_handoff(monkeypatch, damage):
    case, process, port, sent = setup(monkeypatch)
    if damage == 'foreign_guard': process.guard = object()
    if damage == 'unregistered': port.sessions.clear()
    if damage == 'closed': process.closed = True
    if damage == 'wrong_role': process.plan['name'] = 'query'
    if damage == 'wrong_argv':
        process.argv = ('wrong', '-B', 'host')
        monkeypatch.setattr(launch, 'inspect_launch_intent', lambda *a, **kw: {
            'argv': ('python', '-B', 'host'), 'handoff': {},
            'native_acceptance': False, 'execution_authorized': False})
    if damage == 'malformed_argv': process.argv = None
    if damage == 'nonstring_argv': process.argv = ('python', '-B', 42)
    if damage == 'unauthorized_intent':
        monkeypatch.setattr(launch, 'inspect_launch_intent', lambda *a, **kw: {
            'argv': process.argv, 'handoff': {}, 'native_acceptance': False,
            'execution_authorized': True})
    with pytest.raises(ValueError):
        case.deliver_physical_host_handoff(process, deadline_ns=200)
    assert not sent
