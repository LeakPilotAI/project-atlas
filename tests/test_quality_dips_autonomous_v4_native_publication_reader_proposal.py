"""Confined Windows native proposed V4 history/publication binding tests."""
import copy
import pytest
from app.services.quality_dips_autonomous_v4_native_publication_reader_proposal import inspect_proposed_v4_native_publication
from test_quality_dips_autonomous_v4_native_history_reader_proposal import ConfinedReader, native_proposal
from test_quality_dips_autonomous_v4_publication_proposal import publication_case


def inspect(fixture, pub=None, ack=None, reader=None):
    _, _, _, _, enrollment = fixture
    _, _, _, publication, acknowledgment = publication_case()
    return inspect_proposed_v4_native_publication(reader or ConfinedReader(fixture),
        fixture[3], enrollment, pub if pub is not None else publication,
        ack if ack is not None else acknowledgment)


def test_native_history_publication_binds_three_nonzero_events(native_proposal):
    result = inspect(native_proposal)
    assert result['revision'] == 3
    assert result['native_history_publication_binding_checked'] is True
    assert result['independent_custody_verified'] is False
    assert result['operational_authority_accepted'] is False
    assert result['paper_execution_authorized'] is False


@pytest.mark.parametrize('damage', ['publication_head', 'publication_receipts',
    'publication_revision', 'publication_account', 'ack_digest', 'ack_status',
    'event_changed', 'assertion_changed', 'post_history_event', 'post_publication_assertion'])
def test_native_history_publication_refuses_bad_binding(native_proposal, damage):
    _, _, _, publication, acknowledgment = publication_case()
    reader = ConfinedReader(native_proposal)
    source = reader.root / 'source'
    if damage == 'publication_head': publication['head'] = 'f'*64
    if damage == 'publication_receipts': publication['receipts_digest'] = 'f'*64
    if damage == 'publication_revision': publication['revision'] = 2
    if damage == 'publication_account': publication['account_id'] = 'FOREIGN'
    if damage == 'ack_digest': acknowledgment['publication_digest'] = 'f'*64
    if damage == 'ack_status': acknowledgment['status'] = 'PENDING'
    if damage == 'event_changed': (source / '0002-event.json').write_bytes(b'{}')
    if damage == 'assertion_changed': (source / 'assertion.json').write_bytes(b'{}')
    if damage.startswith('post_'):
        original = reader.read_bound
        def mutate(name, pin):
            raw = original(name, pin)
            if reader.reads == (8 if damage == 'post_history_event' else 12):
                target = '0002-event.json' if damage == 'post_history_event' else 'assertion.json'
                (source / target).write_bytes(b'{}')
            return raw
        reader.read_bound = mutate
    with pytest.raises((ValueError, OSError)):
        inspect(native_proposal, publication, acknowledgment, reader)


def test_native_publication_claims_are_not_modified(native_proposal):
    _, _, _, publication, acknowledgment = publication_case()
    before = copy.deepcopy((publication, acknowledgment))
    inspect(native_proposal, publication, acknowledgment)
    assert (publication, acknowledgment) == before