"""Actual Windows native readback + V4 publication adapter integration; fake leases only."""
import copy
import importlib.util
import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, digest
from app.services.quality_dips_autonomous_enrollment import publication_intent
from app.services.quality_dips_autonomous_publication_port import BoundAutonomousFinancialPublication
from app.services.quality_dips_autonomous_v4_inception_replay import V4InceptionFinancialReplay
from test_quality_dips_autonomous_v4_inception_replay import inception_case
from test_quality_dips_autonomous_publication_binding import sample


@pytest.fixture
def native_v4_publication(request):
    value = os.environ.get('ATLAS_AUTO_ENROLLMENT_ROOT')
    if not value:
        pytest.skip('NOT EXECUTED: confined native enrollment root required')
    repo = Path(__file__).resolve().parents[1]
    root = Path(value)
    assert root.parent == repo / 'logs/diagnostics'
    assert root.name.startswith('qd-auto-enrollment-')
    root = root / 'v4-publication' / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('v4_native_publication_reader',
        repo / 'scripts/volume_inspector/autonomous_enrollment_read.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    e, p, cut, docs = inception_case() if request.param == "inception" else sample()
    outputs = {}
    try:
        for role in e['resources']:
            out = module.s.w.WindowsOutput.create_root(str(root / role))
            outputs[role] = out
            e['resources'][role]['path'] = str(out.root)
            e['resources'][role]['native_id'] = module.s.native.file_identity(out.root_handle)
        common = {'account_id': e['account_id'], 'epoch': e['epoch'],
                  'enrollment_digest': digest(e)}
        for role in ('source', 'projection', 'report'):
            for doc in docs[role].values():
                doc.update(common)
        if request.param == 'inception':
            head = digest(['QD_AUTO_NATIVE_INCEPTION_V4', digest(docs['source']['inception.json'])])
            docs['report']['report.json']['head'] = head
            p['event_head'] = head
        p['enrollment_digest'] = digest(e)
        p['inception_intent_digest'] = digest(publication_intent(e))
        p['projection_digest'] = digest(docs['projection']['projection.json']['state'])
        docs['report']['report.json']['state_digest'] = p['projection_digest']
        p['report_digest'] = digest(docs['report']['report.json'])
        cut['enrollment_digest'] = digest(e)
        cut['scope'] = 'LOCAL_ENROLLED'
        for role, files in docs.items():
            for name, doc in files.items():
                pin = outputs[role].write_bound(name, body(doc).encode('utf-8'))
                cut['resources'][role][name] = {'schema': 'QD_AUTO_NATIVE_FILE_V4',
                    'native_id': pin['id'], 'sha256': pin['sha256'], 'record_schema': doc['schema']}
        current = {'scope': 'LOCAL_ENROLLED', 'financial_digest': digest(cut)}

        class Cuts:
            @contextmanager
            def lease(self, enrollment, current, now, *, scope):
                yield SimpleNamespace(snapshot=copy.deepcopy(cut),
                    check=lambda snapshot, now: snapshot == cut)

        class Port:
            def __init__(self, snapshot, check):
                self.snapshot, self.check = snapshot, check

            @contextmanager
            def lease(self, *args, **kwargs):
                yield SimpleNamespace(snapshot=copy.deepcopy(self.snapshot), check=self.check)

        publisher = Port(p, lambda snapshot, now: snapshot == p)
        ack = Port(None, lambda ack_id, publication_digest, now:
            ack_id == p['ack_id'] and publication_digest == digest(p))

        class Replay(Port):
            def verify(self, enrollment, publication, cut, documents, now, *, scope):
                # No fake financial replay success for nonzero operational cuts.
                return V4InceptionFinancialReplay().verify(
                    enrollment, publication, cut, documents, now, scope=scope)

        replay = Replay(cut, lambda snapshot, now: snapshot == cut)
        financial = BoundAutonomousFinancialPublication(
            publication=publisher, custody_ack=ack, financial_replay=replay)
        reader = module.BoundNativeEnrollmentEvidence(cuts=Cuts(), financial=financial)
        yield SimpleNamespace(**locals())
    finally:
        for out in outputs.values():
            out.close()


@pytest.mark.parametrize("native_v4_publication", ["inception"], indirect=True)
def test_v4_publication_adapter_is_called_from_real_native_readback(native_v4_publication):
    s = native_v4_publication
    before = {p: p.read_bytes() for p in s.root.rglob('*.json')}
    assert s.reader.verify(s.e, s.current, 1000, scope='LOCAL_ENROLLED') is True
    assert before == {p: p.read_bytes() for p in s.root.rglob('*.json')}


@pytest.mark.parametrize('native_v4_publication', ['three_event'], indirect=True)
def test_nonzero_native_v4_publication_fails_closed_without_event_replay_protocol(native_v4_publication):
    s = native_v4_publication
    with pytest.raises(ValueError, match='AUTO_V4_REPLAY_NONZERO_PROTOCOL_NOT_ACCEPTED'):
        s.reader.verify(s.e, s.current, 1000, scope='LOCAL_ENROLLED')

@pytest.mark.parametrize('native_v4_publication', ['three_event'], indirect=True)
@pytest.mark.parametrize('damage', ['event_bytes', 'publisher', 'ack', 'replay', 'scope'])
def test_v4_native_publication_integration_refuses_tampering(damage, native_v4_publication):
    s = native_v4_publication
    if damage == 'event_bytes':
        (s.root / 'source/0002-event.json').write_bytes(b'{}')
    if damage == 'publisher': s.publisher.check = lambda *a: False
    if damage == 'ack': s.ack.check = lambda *a: False
    if damage == 'replay': s.replay.verify = lambda *a, **kw: False
    if damage == 'scope': s.current['scope'] = 'DISPOSABLE_TEST'
    with pytest.raises((ValueError, OSError)):
        s.reader.verify(s.e, s.current, 1000, scope='LOCAL_ENROLLED')

@pytest.mark.parametrize('damage', ['inception_bytes', 'projection_bytes', 'report_bytes',
    'publisher', 'ack', 'replay', 'scope'])
@pytest.mark.parametrize('native_v4_publication', ['inception'], indirect=True)
def test_real_native_v4_inception_financial_replay_refuses_tampering(damage, native_v4_publication):
    s = native_v4_publication
    if damage == 'inception_bytes': (s.root / 'source/inception.json').write_bytes(b'{}')
    if damage == 'projection_bytes': (s.root / 'projection/projection.json').write_bytes(b'{}')
    if damage == 'report_bytes': (s.root / 'report/report.json').write_bytes(b'{}')
    if damage == 'publisher': s.publisher.check = lambda *a: False
    if damage == 'ack': s.ack.check = lambda *a: False
    if damage == 'replay': s.replay.verify = lambda *a, **kw: False
    if damage == 'scope': s.current['scope'] = 'DISPOSABLE_TEST'
    with pytest.raises((ValueError, OSError)):
        s.reader.verify(s.e, s.current, 1000, scope='LOCAL_ENROLLED')


@pytest.mark.parametrize('damage', ['inception_bytes', 'projection_bytes', 'report_bytes'])
@pytest.mark.parametrize('native_v4_publication', ['inception'], indirect=True)
def test_real_inception_replay_refuses_native_file_changed_after_financial_audit(damage, native_v4_publication):
    s = native_v4_publication
    original = s.replay.verify
    targets = {'inception_bytes': 'source/inception.json',
               'projection_bytes': 'projection/projection.json',
               'report_bytes': 'report/report.json'}

    def audit_then_mutate(*args, **kwargs):
        assert original(*args, **kwargs) is True
        (s.root / targets[damage]).write_bytes(b'{}')
        return True

    s.replay.verify = audit_then_mutate
    with pytest.raises((ValueError, OSError)):
        s.reader.verify(s.e, s.current, 1000, scope='LOCAL_ENROLLED')
