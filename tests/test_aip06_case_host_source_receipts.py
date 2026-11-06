"""Isolated owner-side source receipt checks; no process or filesystem effects."""

from types import SimpleNamespace
import pytest

from scripts.observation_runtime.aip06_case_host_entry import HOST_ENTRY
from scripts.observation_runtime.aip06_case_host_launch_intent import PREFLIGHT, inspect_launch_intent
from scripts.observation_runtime.aip06_scoped_context import CaseContext


@pytest.mark.parametrize('damage', ['wrong_digest', 'open_handle', 'wrong_path', 'missing_receipt', 'source_error', None])
def test_case_host_requires_two_closed_original_source_receipts_before_handoff(monkeypatch, damage):
    events = []
    pins = {HOST_ENTRY: 'a'*64, PREFLIGHT: 'b'*64}
    ticket = {'held': True, 'stop_capacity_reserved': True}
    guard = SimpleNamespace()
    controller = SimpleNamespace(profile={'source_pins': pins, 'targets': {'case_host': HOST_ENTRY}})
    guard.processes = port = object()
    controller.process_port = port
    plan = {'source_pins': pins, 'executable': r'D:\reviewed\python.exe'}
    factory = SimpleNamespace(plan=plan, guard=guard, controller=controller)
    case = object.__new__(CaseContext)
    case.factory, case.controller, case.guard, case.reservation = factory, controller, guard, ticket
    factory.pending = case
    monkeypatch.setattr(CaseContext, 'verify', lambda self, **kw: events.append('verified'))
    def handoff(self, reservation, *, deadline_ns):
        events.append('handoff')
        return {'schema': 'test-data-only'}
    monkeypatch.setattr(CaseContext, 'physical_host_handoff', handoff)
    def verify_source(path):
        events.append(path)
        if damage == 'source_error' and path == PREFLIGHT:
            raise ValueError('SOURCE_PIN_OR_NATIVE_IDENTITY_MISMATCH')
        if damage == 'missing_receipt' and path == PREFLIGHT:
            return None
        return {'path': HOST_ENTRY if damage == 'wrong_path' and path == PREFLIGHT else path,
                'sha256': '0'*64 if damage == 'wrong_digest' and path == PREFLIGHT else pins[path],
                'closed': False if damage == 'open_handle' and path == PREFLIGHT else True}
    controller.verify_source = verify_source
    if damage is not None:
        with pytest.raises(ValueError):
            inspect_launch_intent(case, ticket, deadline_ns=10**9)
        assert 'handoff' not in events
    else:
        result = inspect_launch_intent(case, ticket, deadline_ns=10**9)
        assert result['execution_authorized'] is False
        assert result['native_acceptance'] is False
        assert result['argv'] == (plan['executable'], '-B', HOST_ENTRY)
        assert events == ['verified', HOST_ENTRY, PREFLIGHT, 'handoff']
