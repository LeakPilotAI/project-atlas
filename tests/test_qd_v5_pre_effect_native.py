"""Actual V5, QD decision logic, SQL coordination and native FS2/FS3; synthetic trust."""
import copy
import hashlib

import pytest
import test_quality_dips_autonomous_binding as native_fixtures

system = native_fixtures.system


def capture(s):
    root = s.x.x.root
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


def frame(s):
    s.x.n.now[0] += 1
    return s.x.frame(1, 'entry')


def test_actual_v5_preview_reads_no_mutex_and_guarded_accept_is_one_effect(system, monkeypatch):
    s = system
    assert s.runtime.start(s.grant) == 'RUNNING'
    f = frame(s)
    before = capture(s)
    def forbidden(*args): raise AssertionError('Preview acquired writer mutex or published a latch')
    with monkeypatch.context() as changes:
        for resource in (s.x.x.store, s.x.x.archive):
            changes.setattr(resource.coordinator, 'wait', forbidden)
            changes.setattr(resource, '_latch', forbidden)
        preview = s.runtime.preview(f)
    assert capture(s) == before and not preview['authority_granted']
    result = s.runtime.accept(f, expected_command_digest=preview['decision']['command_digest'])
    assert result['filled'] and result['receipt'] == preview['decision']['receipt']
    assert s.financial.cut()['source_revision'] == 1
    assert s.runtime.accept(f, expected_command_digest=preview['decision']['command_digest']) == result
    assert s.financial.cut()['source_revision'] == 1


@pytest.mark.parametrize('changed', ['quote', 'clock'])
def test_changed_preview_refuses_before_both_financial_stores(changed, system):
    s = system
    s.runtime.start(s.grant)
    f = frame(s)
    preview = s.runtime.preview(f)
    f = copy.deepcopy(f)
    if changed == 'quote': f['request']['quotes'][0]['bid'] = '99.8'
    else: s.x.n.now[0] += 1
    result = s.runtime.accept(f, expected_command_digest=preview['decision']['command_digest'])
    assert not result['filled'] and result['reason'] == 'PREVIEW_COMMAND_CHANGED'
    assert s.financial.cut()['source_revision'] == 0
    assert s.x.n.ledger.snapshot()['revision'] == 0


def test_unacknowledged_native_effect_is_not_reapplied_by_preview(system, monkeypatch):
    s = system
    s.runtime.start(s.grant)
    f = frame(s)
    preview = s.runtime.preview(f)
    original = s.x.x.store.execute
    calls = []
    def lose_ack(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(result)
        raise OSError('SYNTHETIC_NATIVE_COMMIT_BEFORE_COORDINATION_ACK')
    monkeypatch.setattr(s.x.x.store, 'execute', lose_ack)
    with pytest.raises(ValueError): s.runtime.accept(f, expected_command_digest=preview['decision']['command_digest'])
    before = capture(s)
    with pytest.raises(ValueError): s.runtime.preview(f)
    assert capture(s) == before and len(calls) == 1


def test_existing_v5_ownership_refusal_precedes_preview(system):
    s = system
    s.runtime.start(s.grant)
    f = frame(s)
    s.f.o['writers'].pop('source')
    before = capture(s)
    with pytest.raises(ValueError): s.runtime.preview(f)
    assert capture(s) == before


def test_acknowledged_frame_cannot_accept_another_expected_command(system):
    s = system
    s.runtime.start(s.grant)
    f = frame(s)
    preview = s.runtime.preview(f)
    assert s.runtime.accept(f, expected_command_digest=preview['decision']['command_digest'])['filled']
    with pytest.raises(ValueError, match='EXPECTED_COMMAND'): s.runtime.accept(f, expected_command_digest='f' * 64)
    assert s.x.x.store.verified_cut()['state']['revision'] == 1


def test_new_preview_does_not_resume_stopped_v5(system):
    s = system
    s.runtime.start(s.grant)
    f = frame(s)
    assert s.runtime.stop() == 'STOPPED'
    before = capture(s)
    with pytest.raises(ValueError): s.runtime.preview(f)
    assert capture(s) == before
