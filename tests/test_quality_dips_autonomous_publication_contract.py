"""V4 publication shape is source-only, never a trusted custody assertion."""
import copy
import pytest
from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_enrollment import publication_intent
from app.services.quality_dips_autonomous_publication_contract import validate_financial_publication
from test_quality_dips_autonomous_financial_cut import sample


def evidence(revision=3):
    e, _, _ = sample()
    p = {'schema': 'QD_AUTO_NATIVE_FINANCIAL_PUBLICATION_V4',
         'account_id': e['account_id'], 'epoch': e['epoch'],
         'enrollment_digest': digest(e),
         'inception_intent_digest': digest(publication_intent(e)),
         'revision': revision, 'event_head': 'a' * 64,
         'projection_digest': 'b' * 64, 'report_digest': 'c' * 64,
         'source_files': ['inception.json', *(f'{i:04d}-event.json' for i in range(1, revision + 1))],
         'projection_file': 'projection.json', 'report_file': 'report.json',
         'status': 'ACKNOWLEDGED', 'ack_id': 'SYNTHETIC-NOT-AUTHORITY'}
    return e, p


@pytest.mark.parametrize('revision', [0, 1, 3, 128])
def test_complete_versioned_publication_shape(revision):
    e, p = evidence(revision)
    assert validate_financial_publication(e, p) == p


@pytest.mark.parametrize('damage', ['foreign_account', 'foreign_epoch', 'foreign_enrollment',
    'foreign_intent', 'missing_event', 'duplicate_event', 'reordered_event', 'extra_event',
    'bool_revision', 'negative_revision', 'overflow_revision', 'nonhex_digest',
    'unacknowledged', 'empty_ack', 'extra_field', 'wrong_report_file'])
def test_publication_shape_refuses(damage):
    e, p = evidence()
    if damage == 'foreign_account': p['account_id'] = 'OTHER'
    if damage == 'foreign_epoch': p['epoch'] = 'OTHER'
    if damage == 'foreign_enrollment': p['enrollment_digest'] = 'f' * 64
    if damage == 'foreign_intent': p['inception_intent_digest'] = 'f' * 64
    if damage == 'missing_event': p['source_files'].pop(2)
    if damage == 'duplicate_event': p['source_files'][2] = p['source_files'][1]
    if damage == 'reordered_event': p['source_files'][1], p['source_files'][2] = p['source_files'][2], p['source_files'][1]
    if damage == 'extra_event': p['source_files'].append('0004-event.json')
    if damage == 'bool_revision': p['revision'] = True
    if damage == 'negative_revision': p['revision'] = -1
    if damage == 'overflow_revision': p['revision'] = 129
    if damage == 'nonhex_digest': p['report_digest'] = 'z' * 64
    if damage == 'unacknowledged': p['status'] = 'PENDING'
    if damage == 'empty_ack': p['ack_id'] = ''
    if damage == 'extra_field': p['startup_authorized'] = True
    if damage == 'wrong_report_file': p['report_file'] = 'other.json'
    with pytest.raises(ValueError):
        validate_financial_publication(e, p)
