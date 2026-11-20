"""Confined Windows native readback of PROPOSED V4 financial events only.

This test harness is not the accepted V4 operational native read port.
"""
import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from app.services.paper_financial_replay import body, strict
from app.services.quality_dips_autonomous_v4_native_envelope_proposal import verify_proposed_v4_native_envelopes
from test_quality_dips_autonomous_v4_native_envelope_proposal import sample


@pytest.fixture
def native_proposal():
    value = os.environ.get('ATLAS_AUTO_ENROLLMENT_ROOT')
    if not value:
        pytest.skip('NOT EXECUTED: confined Windows native enrollment root required')
    repo = Path(__file__).resolve().parents[1]
    root = Path(value)
    assert root.parent == repo / 'logs/diagnostics'
    assert root.name.startswith('qd-auto-enrollment-')
    root = root / 'v4-event-proposal' / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('v4_event_proposal_reader',
        repo / 'scripts/volume_inspector/autonomous_enrollment_read.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    enrollment, envelopes, assertion = sample()
    output = module.s.w.WindowsOutput.create_root(str(root / 'source'))
    try:
        pins = {}
        for i, envelope in enumerate(envelopes, 1):
            name = f'{i:04d}-event.json'
            pins[name] = output.write_bound(name, body(envelope).encode('utf-8'))
        pins['assertion.json'] = output.write_bound('assertion.json', body(assertion).encode('utf-8'))
        yield (module, output, root, pins, enrollment)
    finally:
        output.close()


def verify_native_proposal(sample_native):
    module, output, root, pins, enrollment = sample_native
    expected_names = set(pins)
    if {p.name for p in (root / 'source').iterdir()} != expected_names:
        raise ValueError('V4_PROPOSAL_NATIVE_ROSTER_MISMATCH')
    docs = {}
    for name, pin in pins.items():
        raw, _ = module.s.read_bound(output, name, pin)
        value = strict(raw.decode('utf-8'))
        if type(value) is not dict or body(value).encode('utf-8') != raw:
            raise ValueError('V4_PROPOSAL_NATIVE_CANONICAL_RECORD_REQUIRED')
        docs[name] = value
    envelopes = [docs[f'{i:04d}-event.json'] for i in range(1, len(pins))]
    result = verify_proposed_v4_native_envelopes(enrollment, envelopes, docs['assertion.json'])
    if {p.name for p in (root / 'source').iterdir()} != expected_names:
        raise ValueError('V4_PROPOSAL_NATIVE_ROSTER_CHANGED')
    for name, pin in pins.items():
        module.s.read_bound(output, name, pin)
    return result


def test_confined_native_proposed_event_receipts_reconcile_without_writing(native_proposal):
    _, _, root, _, _ = native_proposal
    before = {p.name: p.read_bytes() for p in (root / 'source').iterdir()}
    result = verify_native_proposal(native_proposal)
    assert result['revision'] == 3
    assert result['operational_authority_accepted'] is False
    assert result['paper_execution_authorized'] is False
    assert before == {p.name: p.read_bytes() for p in (root / 'source').iterdir()}


@pytest.mark.parametrize('damage', ['event_bytes', 'event_removed', 'event_added', 'assertion_bytes'])
def test_confined_native_proposal_refuses_mutated_files(damage, native_proposal):
    _, _, root, _, _ = native_proposal
    source = root / 'source'
    if damage == 'event_bytes': (source / '0002-event.json').write_bytes(b'{}')
    if damage == 'event_removed': (source / '0002-event.json').unlink()
    if damage == 'event_added': (source / 'unexpected.json').write_bytes(b'{}')
    if damage == 'assertion_bytes': (source / 'assertion.json').write_bytes(b'{}')
    with pytest.raises((ValueError, OSError)):
        verify_native_proposal(native_proposal)


@pytest.mark.parametrize('damage', ['event', 'assertion'])
def test_confined_native_proposal_refuses_post_audit_mutation(damage, native_proposal, monkeypatch):
    module, _, root, _, _ = native_proposal
    original = verify_proposed_v4_native_envelopes

    def audit_then_mutate(*args):
        result = original(*args)
        name = '0002-event.json' if damage == 'event' else 'assertion.json'
        (root / 'source' / name).write_bytes(b'{}')
        return result

    monkeypatch.setattr(__import__(__name__), 'verify_proposed_v4_native_envelopes', audit_then_mutate)
    with pytest.raises((ValueError, OSError)):
        verify_native_proposal(native_proposal)