"""Publication-to-native-cut shape tests; no accepted native custody or grants."""
import copy
import hashlib
import pytest
from app.services.paper_financial_replay import body, digest
from app.services.quality_dips_autonomous_publication_binding import bind_financial_publication_to_native_cut
from test_quality_dips_autonomous_publication_contract import evidence


def sample():
    e, p = evidence(3)
    common = {'account_id': e['account_id'], 'epoch': e['epoch'], 'enrollment_digest': digest(e)}
    docs = {role: {} for role in e['resources']}
    docs['source']['inception.json'] = {'schema': 'QD_AUTO_NATIVE_INCEPTION_V4', **common,
        'inception_digest': e['inception_digest'], 'opening_cash': '1000', 'positions': {}, 'obligations': []}
    for i in range(1, 4):
        docs['source'][f'{i:04d}-event.json'] = {'schema': 'QD_AUTO_NATIVE_EVENT_V4', **common,
            'revision': i, 'record': {'sequence': i}}
    state = {'cash': '1010', 'positions': {}, 'revision': 3}
    docs['projection']['projection.json'] = {'schema': 'QD_AUTO_NATIVE_PROJECTION_V4',
        **common, 'revision': 3, 'state': state}
    p['projection_digest'] = digest(state)
    docs['report']['report.json'] = {'schema': 'QD_AUTO_NATIVE_REPORT_V4', **common,
        'revision': 3, 'head': p['event_head'], 'state_digest': p['projection_digest']}
    p['report_digest'] = digest(docs['report']['report.json'])
    cut = {'schema': 'QD_AUTO_NATIVE_RESOURCE_CUT_V4', 'enrollment_digest': digest(e),
           'scope': 'DISPOSABLE_TEST', 'resources': {role: {} for role in e['resources']}}
    for role, files in docs.items():
        for name, doc in files.items():
            cut['resources'][role][name] = {'schema': 'QD_AUTO_NATIVE_FILE_V4',
                'native_id': [10, 20, 30], 'sha256': hashlib.sha256(body(doc).encode('utf-8')).hexdigest(),
                'record_schema': doc['schema']}
    return e, p, cut, docs


def test_consistent_native_cut_metadata():
    assert bind_financial_publication_to_native_cut(*sample()) is True


@pytest.mark.parametrize('damage', ['missing_pin', 'extra_pin', 'missing_document', 'file_digest',
    'wrong_record_schema', 'foreign_enrollment', 'foreign_account', 'foreign_epoch',
    'wrong_projection', 'wrong_report', 'wrong_head', 'event_revision',
    'inception_digest', 'wrong_publication', 'bool_revision'])
def test_native_cut_binding_refuses(damage):
    e, p, cut, docs = sample()
    if damage == 'missing_pin': cut['resources']['source'].pop('0002-event.json')
    if damage == 'extra_pin': cut['resources']['source']['extra.json'] = {}
    if damage == 'missing_document': docs['source'].pop('0002-event.json')
    if damage == 'file_digest': cut['resources']['source']['0002-event.json']['sha256'] = 'f' * 64
    if damage == 'wrong_record_schema': cut['resources']['source']['0002-event.json']['record_schema'] = 'WRONG'
    if damage == 'foreign_enrollment': cut['enrollment_digest'] = 'f' * 64
    if damage == 'foreign_account': docs['projection']['projection.json']['account_id'] = 'OTHER'
    if damage == 'foreign_epoch': docs['report']['report.json']['epoch'] = 'OTHER'
    if damage == 'wrong_projection': p['projection_digest'] = 'f' * 64
    if damage == 'wrong_report': p['report_digest'] = 'f' * 64
    if damage == 'wrong_head': p['event_head'] = 'f' * 64
    if damage == 'event_revision': docs['source']['0002-event.json']['revision'] = 3
    if damage == 'inception_digest': docs['source']['inception.json']['inception_digest'] = 'f' * 64
    if damage == 'wrong_publication': p['source_files'].pop()
    if damage == 'bool_revision': docs['projection']['projection.json']['revision'] = True
    with pytest.raises(ValueError):
        bind_financial_publication_to_native_cut(e, p, cut, docs)


@pytest.mark.parametrize('bad_id', [None, 'fake', [10, 20], [10, 20, True], [-1, 20, 30], [10, 20, 30, 40]])
def test_native_publication_binding_rejects_untrusted_file_identity_shape(bad_id):
    e, p, cut, docs = sample()
    cut['resources']['source']['0002-event.json']['native_id'] = bad_id
    with pytest.raises(ValueError):
        bind_financial_publication_to_native_cut(e, p, cut, docs)


@pytest.mark.parametrize('bad_hash', ['F' * 64, 'g' * 64, 123, None])
def test_native_publication_binding_rejects_invalid_digest_format(bad_hash):
    e, p, cut, docs = sample()
    cut['resources']['source']['0002-event.json']['sha256'] = bad_hash
    with pytest.raises(ValueError):
        bind_financial_publication_to_native_cut(e, p, cut, docs)


def test_native_publication_binding_rejects_non_object_document():
    e, p, cut, docs = sample()
    docs['source']['0002-event.json'] = []
    with pytest.raises(ValueError):
        bind_financial_publication_to_native_cut(e, p, cut, docs)


@pytest.mark.parametrize('role,name', [('source', 'inception.json'),
    ('source', '0002-event.json'), ('projection', 'projection.json'),
    ('report', 'report.json')])
def test_publication_binding_rejects_non_v4_native_record_even_if_pin_matches(role, name):
    e, p, cut, docs = sample()
    doc = docs[role][name]
    doc['schema'] = 'QD_OP_MANUAL_OR_DISPOSABLE_V1'
    pin = cut['resources'][role][name]
    pin['record_schema'] = doc['schema']
    pin['sha256'] = hashlib.sha256(body(doc).encode('utf-8')).hexdigest()
    with pytest.raises(ValueError, match='AUTO_PUBLICATION_NATIVE_PIN_INVALID'):
        bind_financial_publication_to_native_cut(e, p, cut, docs)
