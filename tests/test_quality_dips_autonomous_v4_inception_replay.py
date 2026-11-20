"""V4 inception financial replay source-only checks; no issuer or custody grants."""
import copy
import hashlib
import pytest
from app.services.paper_financial_replay import body, digest
from app.services.quality_dips_autonomous_v4_inception_replay import V4InceptionFinancialReplay
from test_quality_dips_autonomous_publication_binding import sample


def inception_case():
    e, p, cut, docs = sample()
    p['revision'] = 0
    p['source_files'] = ['inception.json']
    docs['source'] = {'inception.json': docs['source']['inception.json']}
    state = {'cash': '1000', 'positions': {}, 'gross': '0', 'costs': '0', 'net': '0', 'revision': 0}
    docs['projection']['projection.json']['revision'] = 0
    docs['projection']['projection.json']['state'] = state
    report = docs['report']['report.json']
    report['revision'] = 0
    report['head'] = digest(['QD_AUTO_NATIVE_INCEPTION_V4', digest(docs['source']['inception.json'])])
    report['status'] = 'COMPLETE'
    report['state_digest'] = digest(state)
    p['event_head'] = report['head']
    p['projection_digest'] = digest(state)
    p['report_digest'] = digest(report)
    for role in cut['resources']:
        cut['resources'][role] = {}
        for name, doc in docs[role].items():
            cut['resources'][role][name] = {'schema': 'QD_AUTO_NATIVE_FILE_V4',
                'native_id': [10, 20, 30], 'sha256': hashlib.sha256(body(doc).encode()).hexdigest(),
                'record_schema': doc['schema']}
    cut['scope'] = 'LOCAL_ENROLLED'
    return e, p, cut, docs


def test_v4_inception_replay_verifies_zero_event_financial_state():
    assert V4InceptionFinancialReplay().verify(*inception_case(), 1000, scope='LOCAL_ENROLLED') is True


@pytest.mark.parametrize('damage', ['nonzero', 'cash', 'positions', 'report_head',
    'report_status', 'bool_revision', 'extra_state', 'disposable_scope'])
def test_v4_inception_replay_refuses_unverified_financial_claims(damage):
    e, p, cut, docs = inception_case()
    if damage == 'nonzero': p['revision'] = 3
    if damage == 'cash': docs['projection']['projection.json']['state']['cash'] = '900'
    if damage == 'positions': docs['source']['inception.json']['positions'] = {'AAPL': '1'}
    if damage == 'report_head': docs['report']['report.json']['head'] = 'f' * 64
    if damage == 'report_status': docs['report']['report.json']['status'] = 'PENDING'
    if damage == 'bool_revision': docs['projection']['projection.json']['revision'] = False
    if damage == 'extra_state': docs['projection']['projection.json']['state']['fake'] = 1
    if damage == 'disposable_scope': cut['scope'] = 'DISPOSABLE_TEST'
    with pytest.raises(ValueError):
        V4InceptionFinancialReplay().verify(e, p, cut, docs, 1000, scope='LOCAL_ENROLLED')

def test_v4_inception_replay_is_used_by_publication_port():
    from contextlib import contextmanager
    from types import SimpleNamespace
    from app.services.quality_dips_autonomous_publication_port import BoundAutonomousFinancialPublication
    e, p, cut, docs = inception_case()

    class Port:
        def __init__(self, snapshot, check):
            self.snapshot, self.check = snapshot, check

        @contextmanager
        def lease(self, *args, **kwargs):
            yield SimpleNamespace(snapshot=copy.deepcopy(self.snapshot), check=self.check)

    class Replay(Port):
        verify = V4InceptionFinancialReplay().verify

    port = BoundAutonomousFinancialPublication(
        publication=Port(p, lambda snapshot, now: snapshot == p),
        custody_ack=Port(None, lambda ack_id, pub_digest, now:
            ack_id == p['ack_id'] and pub_digest == digest(p)),
        financial_replay=Replay(cut, lambda snapshot, now: snapshot == cut))
    current = {'scope': 'LOCAL_ENROLLED', 'financial_digest': digest(cut)}
    assert port.verify_cut(e, current, docs, 1000, scope='LOCAL_ENROLLED') is True
    docs['source']['inception.json']['opening_cash'] = '900'
    with pytest.raises(ValueError):
        port.verify_cut(e, current, docs, 1000, scope='LOCAL_ENROLLED')
