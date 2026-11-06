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


@pytest.mark.parametrize('damage', ['unretained_equal', 'unreleased', 'suspended', 'closed', 'failed'])
def test_direct_post_release_binding_rejects_unretained_or_invalid_child(monkeypatch, damage):
    from copy import copy
    port, child, _, _, _ = setup(monkeypatch)
    if damage == 'unretained_equal':
        duplicate = copy(child)
        assert duplicate == child and duplicate is not child
        port.sessions[:] = [duplicate]
    if damage == 'unreleased': child.target_released = False
    if damage == 'suspended': child.suspended = True
    if damage == 'closed': child.closed = True
    if damage == 'failed': child.failed = True
    with pytest.raises(ValueError, match='ORIGINAL_RELEASED_CASE_HOST_SESSION_REQUIRED'):
        port.verify_case_host_scope_after_release(child)


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
