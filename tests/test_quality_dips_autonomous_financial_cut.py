"""Source-only synthetic contract checks; no native execution or acceptance."""
import copy
import pytest
from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_financial_cut import AutonomousInceptionFinancialVerifier
from app.services.quality_dips_autonomous_enrollment import publication_intent
from test_quality_dips_autonomous_enrollment import fixture


def sample():
    f = fixture()
    e = f.e
    intent = publication_intent(e)
    current = {'scope': 'DISPOSABLE_TEST', 'revision': 0, 'acknowledged_revision': 0,
               'high_water': 0, 'status': 'ACKNOWLEDGED', 'publication_ack': 'SYNTHETIC-ACK',
               'publication': {'intent_digest': digest(intent), 'operation_id': intent['operation_id'],
                               'status': 'ACKNOWLEDGED', 'ack_id': 'SYNTHETIC-ACK'}}
    state = {'cash': '1000', 'positions': {}, 'gross': '0', 'costs': '0', 'net': '0', 'revision': 0}
    docs = {role: {} for role in e['resources']}
    common = {'account_id': e['account_id'], 'epoch': e['epoch'], 'enrollment_digest': digest(e)}
    docs['source']['inception.json'] = {'schema': 'QD_AUTO_NATIVE_INCEPTION_V4', **common,
        'inception_digest': e['inception_digest'], 'opening_cash': '1000', 'positions': {}, 'obligations': []}
    docs['projection']['projection.json'] = {'schema': 'QD_AUTO_NATIVE_PROJECTION_V4', **common,
        'revision': 0, 'state': state}
    docs['report']['report.json'] = {'schema': 'QD_AUTO_NATIVE_REPORT_V4', **common,
        'revision': 0, 'state_digest': digest(state), 'status': 'COMPLETE'}
    return e, current, docs


def test_consistent_inception_cut():
    assert AutonomousInceptionFinancialVerifier().verify_cut(*sample(), 1000, scope='DISPOSABLE_TEST') is True


@pytest.mark.parametrize('damage', ['foreign_account', 'foreign_epoch', 'cash', 'position', 'obligation',
    'revision', 'foreign_publication', 'unacknowledged', 'projection', 'report', 'missing_role', 'extra_file', 'unknown_scope'])
def test_inconsistent_cut_refuses(damage):
    e, current, docs = sample()
    if damage == 'foreign_account': docs['source']['inception.json']['account_id'] = 'OTHER'
    if damage == 'foreign_epoch': docs['report']['report.json']['epoch'] = 'OTHER'
    if damage == 'cash': docs['source']['inception.json']['opening_cash'] = '999'
    if damage == 'position': docs['source']['inception.json']['positions'] = {'X': '1'}
    if damage == 'obligation': docs['source']['inception.json']['obligations'] = ['X']
    if damage == 'revision': current['revision'] = 1
    if damage == 'foreign_publication': current['publication']['intent_digest'] = 'f' * 64
    if damage == 'unacknowledged': current['status'] = 'PENDING'
    if damage == 'projection': docs['projection']['projection.json']['state']['cash'] = '900'
    if damage == 'report': docs['report']['report.json']['state_digest'] = 'f' * 64
    if damage == 'missing_role': docs.pop('custody')
    if damage == 'extra_file': docs['control']['extra.json'] = {}
    if damage == 'unknown_scope': current['scope'] = 'LOCAL_ENROLLED'
    with pytest.raises(ValueError):
        AutonomousInceptionFinancialVerifier().verify_cut(e, current, docs, 1000, scope='DISPOSABLE_TEST')
