"""Equal-value foreign session objects must not pass original-owner checks."""
import copy
import pytest
from tests.test_aip06_case_host_input_owner import setup as owner_setup
from tests.test_aip06_case_host_context_delivery import setup as context_setup


def test_owner_refuses_equal_value_foreign_child(monkeypatch):
    port, child, _, packet, sent = owner_setup(monkeypatch)
    foreign = copy.copy(child)
    assert foreign == child and foreign is not child
    with pytest.raises(ValueError, match='RELEASED_ORIGINAL_CASE_HOST_INPUT_CHILD_REQUIRED'):
        port.deliver_case_host_input(foreign, packet, deadline_ns=200)
    assert not sent


def test_context_refuses_equal_value_foreign_child(monkeypatch):
    case, process, _, sent = context_setup(monkeypatch)
    foreign = copy.copy(process.child)
    assert foreign == process.child and foreign is not process.child
    process.child = foreign
    with pytest.raises(ValueError, match='ORIGINAL_EXISTING_GUARDED_CASE_HOST_REQUIRED'):
        case.deliver_physical_host_handoff(process, deadline_ns=200)
    assert not sent
