"""Source-only synthetic native event-cut adapter tests."""
import copy
import pytest
from app.services.paper_financial_replay import digest
from app.services.paper_financial_audit import audit_financial_events
from app.services.quality_dips_autonomous_native_event_cut import DisposableNativeEventCutVerifier
from test_quality_dips_autonomous_financial_cut import sample
from test_quality_dips_autonomous_financial_reconciliation import case
from test_fs1_financial_replay import GOLDEN


def evidence(*, full_snapshot=False):
    e, _, _ = sample()
    manifest, records, state, pins = case()
    # The retained golden fixture epoch is explicitly bound to the synthetic enrollment.
    e['epoch'] = manifest['epoch']
    if full_snapshot:
        state = copy.deepcopy(GOLDEN[0]["snapshot"])
    revision = len(records)
    common = {'account_id': e['account_id'], 'epoch': e['epoch'],
              'enrollment_digest': digest(e), 'revision': revision}
    documents = {role: {} for role in e['resources']}
    documents['source']['manifest.json'] = {
        'schema': 'QD_AUTO_NATIVE_DISPOSABLE_MANIFEST_V1', **common, 'manifest': manifest}
    for i, record in enumerate(records, 1):
        documents['source'][f'{i:04d}-event.json'] = {
            'schema': 'QD_AUTO_NATIVE_DISPOSABLE_EVENT_V1', **common,
            'revision': i, 'record': record}
    documents['projection']['projection.json'] = {
        'schema': 'QD_AUTO_NATIVE_DISPOSABLE_PROJECTION_V1', **common, 'state': state}
    audit = audit_financial_events(manifest, records, state)
    documents['report']['report.json'] = {
        'schema': 'QD_AUTO_NATIVE_DISPOSABLE_REPORT_V1', **common,
        'head': pins['expected_head'], 'state_digest': pins['expected_state_digest'],
        'audit_digest': digest(audit)}
    return e, {'scope': 'DISPOSABLE_TEST', 'revision': revision}, documents


def test_three_revision_native_event_cut_reconciles():
    assert DisposableNativeEventCutVerifier().verify_cut(*evidence(), 1000,
                                                         scope='DISPOSABLE_TEST') is True


@pytest.mark.parametrize('damage', ['operational_scope', 'foreign_account', 'foreign_epoch',
    'wrong_manifest', 'missing_event', 'duplicate_event', 'event_revision', 'event_digest',
    'projection_cash', 'report_head', 'report_audit', 'extra_role_file', 'boolean_revision'])
def test_disposable_event_cut_refuses(damage):
    e, current, documents = evidence()
    if damage == 'operational_scope': current['scope'] = 'LOCAL_ENROLLED'
    if damage == 'foreign_account': documents['source']['0002-event.json']['account_id'] = 'FOREIGN'
    if damage == 'foreign_epoch': documents['report']['report.json']['epoch'] = 'FOREIGN'
    if damage == 'wrong_manifest': documents['source']['manifest.json']['manifest']['epoch'] = 'FOREIGN'
    if damage == 'missing_event': documents['source'].pop('0002-event.json')
    if damage == 'duplicate_event': documents['source']['0003-event.json']['record'] = copy.deepcopy(documents['source']['0001-event.json']['record'])
    if damage == 'event_revision': documents['source']['0002-event.json']['revision'] = 1
    if damage == 'event_digest': documents['source']['0002-event.json']['record']['digest'] = 'f' * 64
    if damage == 'projection_cash': documents['projection']['projection.json']['state']['cash'] = '999'
    if damage == 'report_head': documents['report']['report.json']['head'] = 'f' * 64
    if damage == 'report_audit': documents['report']['report.json']['audit_digest'] = 'f' * 64
    if damage == 'extra_role_file': documents['custody']['unexpected.json'] = {}
    if damage == 'boolean_revision': current['revision'] = True
    with pytest.raises((ValueError, KeyError)):
        DisposableNativeEventCutVerifier().verify_cut(e, current, documents, 1000,
                                                       scope='DISPOSABLE_TEST')


def test_native_event_cut_accepts_full_fs1_financial_snapshot():
    e, current, docs = evidence(full_snapshot=True)
    assert len(docs['projection']['projection.json']['state']) > len(case()[2])
    assert DisposableNativeEventCutVerifier().verify_cut(e, current, docs, 1000,
                                                        scope='DISPOSABLE_TEST') is True


@pytest.mark.parametrize('damage', ['clock', 'net_r', 'gross'])
def test_native_event_cut_rejects_corrupted_full_fs1_snapshot(damage):
    e, current, docs = evidence(full_snapshot=True)
    snapshot = docs['projection']['projection.json']['state']
    if damage == 'clock': snapshot['last_clock'] = -1
    if damage == 'net_r': snapshot['net_r'] = '999'
    if damage == 'gross': snapshot['gross'] = '999'
    with pytest.raises((ValueError, KeyError, TypeError)):
        DisposableNativeEventCutVerifier().verify_cut(e, current, docs, 1000,
                                                      scope='DISPOSABLE_TEST')
