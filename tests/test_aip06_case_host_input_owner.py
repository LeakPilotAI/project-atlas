"""Source-only adversarial owner INPUT tests; no native child launched."""
from types import SimpleNamespace
import pytest
from scripts.observation_runtime.aip06_scoped_context import CaseContext
from tests.test_aip06_case_host_release_gate import fixture


def setup(monkeypatch):
    port, child, case = fixture(monkeypatch)
    child.name = 'case_host'
    child.target_released = True
    child.channel = object()
    port.clock = lambda: 100
    port.failed = False
    sent = []
    port.protocol = SimpleNamespace(send_case_host_input=lambda *args, **kw: sent.append((args, kw)))
    packet = {'schema': 'AIP06_PHYSICAL_CASE_HOST_HANDOFF_V1', 'case': 'original'}
    monkeypatch.setattr(CaseContext, 'physical_host_handoff', lambda self, reservation, *, deadline_ns: dict(packet))
    return port, child, case, packet, sent


def test_one_shot_owner_send_and_replay_refused(monkeypatch):
    port, child, _, packet, sent = setup(monkeypatch)
    port.deliver_case_host_input(child, packet, deadline_ns=200)
    assert len(sent) == 1 and sent[0][0] == (child, packet)
    with pytest.raises(ValueError, match='CASE_HOST_INPUT_REPLAY_REFUSED'):
        port.deliver_case_host_input(child, packet, deadline_ns=200)
    assert len(sent) == 1


@pytest.mark.parametrize('damage', ['foreign_child', 'unreleased', 'foreign_binding', 'foreign_nonce',
    'expired', 'missing_stop', 'closed_directory', 'wrong_packet', 'closed_child'])
def test_refuses_damaged_original_owner(monkeypatch, damage):
    port, child, case, packet, sent = setup(monkeypatch)
    if damage == 'foreign_child': port.sessions.clear()
    if damage == 'unreleased': child.target_released = False
    if damage == 'foreign_binding': child.binding = object()
    if damage == 'foreign_nonce': child.receipt['nonce'] = 'b' * 32
    if damage == 'expired': port.clock = lambda: 200
    if damage == 'missing_stop': case.reservation['stop_capacity_reserved'] = False
    if damage == 'closed_directory': port.guard.ledger('read')['state']['resources']['directory-key']['closed'] = True
    if damage == 'wrong_packet': packet = {'schema': 'OTHER'}
    if damage == 'closed_child': child.closed = True
    with pytest.raises(ValueError):
        port.deliver_case_host_input(child, packet, deadline_ns=200)
    assert not sent


def test_send_failure_marks_child_failed_and_blocks_replay(monkeypatch):
    port, child, _, packet, _ = setup(monkeypatch)
    def fail(*args, **kwargs):
        raise OSError('channel closed')
    port.protocol.send_case_host_input = fail
    with pytest.raises(OSError, match='channel closed'):
        port.deliver_case_host_input(child, packet, deadline_ns=200)
    assert child.failed and port.failed and child.case_host_input_sent
    with pytest.raises(ValueError):
        port.deliver_case_host_input(child, packet, deadline_ns=200)
