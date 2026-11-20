"""Proposed V4 publication/ack consistency is NOT independent authority."""
import copy
import pytest
from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_v4_native_envelope_proposal import verify_proposed_v4_native_envelopes
from app.services.quality_dips_autonomous_v4_publication_proposal import inspect_proposed_v4_publication
from test_quality_dips_autonomous_v4_native_envelope_proposal import sample


def publication_case():
    enrollment, envelopes, assertion = sample()
    audit = verify_proposed_v4_native_envelopes(enrollment, envelopes, assertion)
    publication = {'schema': 'QD_AUTO_V4_PUBLICATION_PROPOSAL_V1',
                   **enrollment, 'revision': audit['revision'], 'head': audit['head'],
                   'receipts_digest': audit['receipts_digest'],
                   'assertion_digest': digest(assertion), 'publication_id': 'PAPER-PUB-1'}
    ack = {'schema': 'QD_AUTO_V4_CUSTODY_ACK_PROPOSAL_V1',
           'publication_id': publication['publication_id'],
           'publication_digest': digest(publication), 'ack_id': 'PAPER-ACK-1',
           'status': 'ACKNOWLEDGED'}
    return enrollment, envelopes, assertion, publication, ack


def test_proposed_publication_ack_consistency_never_grants_authority():
    result = inspect_proposed_v4_publication(*publication_case())
    assert result['revision'] == 3
    assert result['internal_consistency_verified'] is True
    assert result['independent_custody_verified'] is False
    assert result['independent_publication_verified'] is False
    assert result['operational_authority_accepted'] is False
    assert result['paper_execution_authorized'] is False
    assert result['live_order_authorized'] is False


@pytest.mark.parametrize('damage', ['foreign_account', 'foreign_epoch', 'foreign_enrollment',
    'revision', 'bool_revision', 'head', 'receipts', 'assertion', 'publication_id',
    'publication_extra', 'ack_digest', 'ack_id', 'ack_status', 'ack_publication',
    'ack_extra', 'event', 'financial_state'])
def test_proposed_publication_ack_refuses_mismatch(damage):
    e, events, assertion, pub, ack = publication_case()
    if damage == 'foreign_account': pub['account_id'] = 'FOREIGN'
    if damage == 'foreign_epoch': pub['epoch'] = 'FOREIGN'
    if damage == 'foreign_enrollment': pub['enrollment_digest'] = 'f' * 64
    if damage == 'revision': pub['revision'] = 2
    if damage == 'bool_revision': pub['revision'] = True
    if damage == 'head': pub['head'] = 'f' * 64
    if damage == 'receipts': pub['receipts_digest'] = 'f' * 64
    if damage == 'assertion': pub['assertion_digest'] = 'f' * 64
    if damage == 'publication_id': pub['publication_id'] = ''
    if damage == 'publication_extra': pub['authority_granted'] = True
    if damage == 'ack_digest': ack['publication_digest'] = 'f' * 64
    if damage == 'ack_id': ack['ack_id'] = ''
    if damage == 'ack_status': ack['status'] = 'PENDING'
    if damage == 'ack_publication': ack['publication_id'] = 'OTHER'
    if damage == 'ack_extra': ack['authority_granted'] = True
    if damage == 'event': events[1]['record']['price'] = '111'
    if damage == 'financial_state': assertion['state']['cash'] = '999'
    with pytest.raises(ValueError):
        inspect_proposed_v4_publication(e, events, assertion, pub, ack)


def test_proposed_publication_ack_inspection_does_not_mutate_inputs():
    inputs = publication_case()
    before = copy.deepcopy(inputs)
    inspect_proposed_v4_publication(*inputs)
    assert inputs == before