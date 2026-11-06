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
    case.reservation = {'held': True, 'stop_capacity_reserved': True, 'key': 'directory-key'}
    ledger = {'resources': {'directory-key': {'owner': 'original', 'kind': 'directory', 'closed': False}}}
    guard.ledger = lambda mode: {'state': ledger}
    monkeypatch.setattr(CaseContext, 'wire', lambda self: {'case': 'original'})
    nonce = 'a' * 32
    plan = {'request': SimpleNamespace(nonce=nonce)}
    argv = ('python', '-B', 'host.py')
    binding = SimpleNamespace(request=plan['request'], runtime={'pid': 555})
    child = SimpleNamespace(plan=plan, argv=argv, closed=False, failed=False,
                            suspended=False, target_released=False, binding=binding)
    guard.ownership = SimpleNamespace(bindings={'case_host': binding})
    from scripts.observation_runtime.aip06_native_session import digest
    child.receipt = {'guarded': True, 'nonce': nonce, 'owner': digest(binding.runtime)}
    port = object.__new__(WindowsSessionPort)
    port.scoped_case, port.guard, port.sessions = case, guard, [child]
    port.resources = SimpleNamespace(state={'owners': {'original': {'pid': 77}}})
    guard.owner = 'original'
    port.plans = {nonce: {'plan': plan, 'argv': argv, 'case_scope': case.wire(),
                          'parent': {'pid': 77}}}
    return port, child, case


def test_original_release_scope(monkeypatch):
    port, child, _ = fixture(monkeypatch)
    assert port.verify_case_host_scope(child) is None


@pytest.mark.parametrize('damage', ['missing_case', 'foreign_case', 'closed_case', 'failed_case',
    'missing_reservation', 'missing_stop', 'foreign_plan', 'foreign_scope', 'foreign_argv',
    'replayed_release', 'still_suspended', 'unregistered_child', 'foreign_parent',
    'closed_directory', 'foreign_directory', 'missing_directory',
    'foreign_binding', 'foreign_request', 'missing_receipt', 'wrong_nonce', 'wrong_owner', 'unguarded'])
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
    if damage == 'foreign_parent': port.plans['a'*32]['parent'] = {'pid': 88}
    if damage == 'closed_directory': port.guard.ledger('read')['state']['resources']['directory-key']['closed'] = True
    if damage == 'foreign_directory': port.guard.ledger('read')['state']['resources']['directory-key']['owner'] = 'foreign'
    if damage == 'missing_directory': port.guard.ledger('read')['state']['resources'].clear()
    if damage == 'foreign_binding': child.binding = SimpleNamespace(request=child.plan['request'], runtime={'pid': 555})
    if damage == 'foreign_request': child.binding.request = object()
    if damage == 'missing_receipt': child.receipt = None
    if damage == 'wrong_nonce': child.receipt['nonce'] = 'b'*32
    if damage == 'wrong_owner': child.receipt['owner'] = 'other'
    if damage == 'unguarded': child.receipt['guarded'] = False
    with pytest.raises(ValueError):
        port.verify_case_host_scope(child)
