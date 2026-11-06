"""Injected release gate checks; never creates a native process."""
from types import SimpleNamespace
import pytest
from scripts.observation_runtime.aip06_native_session import WindowsSessionPort
from scripts.observation_runtime.aip06_scoped_context import CaseContext


def fixture(monkeypatch):
    case = object.__new__(CaseContext)
    guard = SimpleNamespace()
    factory = SimpleNamespace(pending=case)
    case.factory, case.guard = factory, guard
    case.closed = case.failed = False
    case.reservation = {'held': True, 'stop_capacity_reserved': True}
    monkeypatch.setattr(CaseContext, 'wire', lambda self: {'case': 'original'})
    nonce = 'a' * 32
    plan = {'request': SimpleNamespace(nonce=nonce)}
    argv = ('python', '-B', 'host.py')
    child = SimpleNamespace(plan=plan, argv=argv, closed=False, failed=False,
                            suspended=False, target_released=False)
    port = object.__new__(WindowsSessionPort)
    port.scoped_case, port.guard, port.sessions = case, guard, [child]
    port.plans = {nonce: {'plan': plan, 'argv': argv, 'case_scope': case.wire()}}
    return port, child, case


def test_original_release_scope(monkeypatch):
    port, child, _ = fixture(monkeypatch)
    assert port.verify_case_host_scope(child) is None


@pytest.mark.parametrize('damage', ['missing_case', 'foreign_case', 'closed_case', 'failed_case',
    'missing_reservation', 'missing_stop', 'foreign_plan', 'foreign_scope', 'foreign_argv',
    'replayed_release', 'still_suspended', 'unregistered_child'])
def test_release_gate_rejects_damaged_scope(monkeypatch, damage):
    port, child, case = fixture(monkeypatch)
    if damage == 'missing_case': port.scoped_case = None
    if damage == 'foreign_case': case.factory.pending = object()
    if damage == 'closed_case': case.closed = True
    if damage == 'failed_case': case.failed = True
    if damage == 'missing_reservation': case.reservation = None
    if damage == 'missing_stop': case.reservation['stop_capacity_reserved'] = False
    if damage == 'foreign_plan': port.plans['a'*32]['plan'] = {}
    if damage == 'foreign_scope': port.plans['a'*32]['case_scope'] = {}
    if damage == 'foreign_argv': port.plans['a'*32]['argv'] = ()
    if damage == 'replayed_release': child.target_released = True
    if damage == 'still_suspended': child.suspended = True
    if damage == 'unregistered_child': port.sessions.clear()
    with pytest.raises(ValueError):
        port.verify_case_host_scope(child)
