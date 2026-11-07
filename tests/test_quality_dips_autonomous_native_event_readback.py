"""Confined Windows bound-native readback of disposable QD event histories."""
import copy
import importlib.util
import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, digest
from app.services.quality_dips_autonomous_native_event_cut import DisposableNativeEventCutVerifier
from test_quality_dips_autonomous_native_event_cut import evidence


@pytest.fixture
def native_event_cut():
    value = os.environ.get('ATLAS_AUTO_ENROLLMENT_ROOT')
    if not value:
        pytest.skip('NOT EXECUTED: confined native enrollment root required')
    repo = Path(__file__).resolve().parents[1]
    root = Path(value)
    assert root.parent == repo / 'logs/diagnostics'
    assert root.name.startswith('qd-auto-enrollment-')
    root = root / 'event-financial' / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('native_event_cut_read',
        repo / 'scripts/volume_inspector/autonomous_enrollment_read.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    enrollment, current, docs = evidence()
    outputs, resources = {}, {}
    try:
        for role in enrollment['resources']:
            out = module.s.w.WindowsOutput.create_root(str(root / role))
            outputs[role] = out
            enrollment['resources'][role]['path'] = str(out.root)
            enrollment['resources'][role]['native_id'] = module.s.native.file_identity(out.root_handle)
            resources[role] = {}
        common = {'account_id': enrollment['account_id'], 'epoch': enrollment['epoch'],
                  'enrollment_digest': digest(enrollment)}
        for role in ('source', 'projection', 'report'):
            for doc in docs[role].values():
                doc.update(common)
        for role, files in docs.items():
            for name, doc in files.items():
                pin = outputs[role].write_bound(name, body(doc).encode('utf-8'))
                resources[role][name] = {'schema': 'QD_AUTO_NATIVE_FILE_V4',
                    'native_id': pin['id'], 'sha256': pin['sha256'], 'record_schema': doc['schema']}
        cut = {'schema': 'QD_AUTO_NATIVE_RESOURCE_CUT_V4',
               'enrollment_digest': digest(enrollment), 'scope': 'DISPOSABLE_TEST',
               'resources': resources}
        class Cuts:
            @contextmanager
            def lease(self, e, c, now, *, scope):
                assert scope == 'DISPOSABLE_TEST'
                yield SimpleNamespace(snapshot=copy.deepcopy(cut), check=lambda v, t: v == cut)
        current['financial_digest'] = digest(cut)
        port = module.BoundNativeEnrollmentEvidence(cuts=Cuts(),
            financial=DisposableNativeEventCutVerifier())
        yield SimpleNamespace(**locals())
    finally:
        for out in outputs.values():
            out.close()


def test_three_event_native_bound_readback_preserves_bytes(native_event_cut):
    s = native_event_cut
    before = {p: p.read_bytes() for p in s.root.rglob('*.json')}
    assert s.port.verify(s.enrollment, s.current, 1000, scope='DISPOSABLE_TEST') is True
    assert before == {p: p.read_bytes() for p in s.root.rglob('*.json')}


@pytest.mark.parametrize('damage', ['event_bytes', 'event_missing', 'event_added',
    'projection_bytes', 'report_bytes', 'foreign_root', 'wrong_cut_digest', 'operational_scope'])
def test_native_bound_event_cut_refuses(damage, native_event_cut):
    s = native_event_cut
    if damage == 'event_bytes':
        (s.root / 'source/0002-event.json').write_bytes(b'{}')
    if damage == 'event_missing':
        (s.root / 'source/0002-event.json').unlink()
    if damage == 'event_added':
        (s.root / 'source/unexpected.json').write_bytes(b'{}')
    if damage == 'projection_bytes':
        (s.root / 'projection/projection.json').write_bytes(b'{}')
    if damage == 'report_bytes':
        (s.root / 'report/report.json').write_bytes(b'{}')
    if damage == 'foreign_root':
        s.enrollment['resources']['source']['native_id'][1] += 1
    if damage == 'wrong_cut_digest':
        s.current['financial_digest'] = 'f' * 64
    if damage == 'operational_scope':
        s.current['scope'] = 'LOCAL_ENROLLED'
    with pytest.raises((ValueError, OSError)):
        s.port.verify(s.enrollment, s.current, 1000, scope='DISPOSABLE_TEST')
