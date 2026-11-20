"""Confined native readback of V4 inception financial documents, never authority."""
import copy
import importlib.util
import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, digest
from app.services.quality_dips_autonomous_financial_cut import AutonomousInceptionFinancialVerifier
from test_quality_dips_autonomous_financial_cut import sample
from app.services.quality_dips_autonomous_enrollment import publication_intent


@pytest.fixture
def native_cut(tmp_path):
    root_value = os.environ.get('ATLAS_AUTO_ENROLLMENT_ROOT')
    if not root_value:
        pytest.skip('NOT EXECUTED: confined native enrollment root required')
    repo = Path(__file__).resolve().parents[1]
    root = Path(root_value)
    assert root.parent == repo / 'logs/diagnostics'
    assert root.name.startswith('qd-auto-enrollment-')
    root = root / 'financial' / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('native_financial_cut_read',
        repo / 'scripts/volume_inspector/autonomous_enrollment_read.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    enrollment, current, docs = sample()
    outputs, resources = {}, {}
    try:
        for role in enrollment['resources']:
            out = module.s.w.WindowsOutput.create_root(str(root / role))
            outputs[role] = out
            enrollment['resources'][role]['path'] = str(out.root)
            enrollment['resources'][role]['native_id'] = module.s.native.file_identity(out.root_handle)
            resources[role] = {}
        intent = publication_intent(enrollment)
        current['publication']['intent_digest'] = digest(intent)
        current['publication']['operation_id'] = intent['operation_id']
        # Source enrollment digest is bound to the actual native resource IDs.
        common = {'account_id': enrollment['account_id'], 'epoch': enrollment['epoch'],
                  'enrollment_digest': digest(enrollment)}
        for role in ('source', 'projection', 'report'):
            for document in docs[role].values():
                document.update(common)
        docs['report']['report.json']['state_digest'] = digest(docs['projection']['projection.json']['state'])
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
            financial=AutonomousInceptionFinancialVerifier())
        yield SimpleNamespace(**locals())
    finally:
        for out in outputs.values():
            out.close()


def test_native_financial_cut_readback_is_read_only(native_cut):
    s = native_cut
    before = {p: p.read_bytes() for p in s.root.rglob('*.json')}
    assert s.port.verify(s.enrollment, s.current, 1000, scope='DISPOSABLE_TEST') is True
    assert before == {p: p.read_bytes() for p in s.root.rglob('*.json')}


@pytest.mark.parametrize('damage', ['account', 'projection', 'report', 'missing', 'foreign_root'])
def test_native_financial_cut_tamper_refused(native_cut, damage):
    s = native_cut
    if damage == 'account':
        s.enrollment['account_id'] = 'FOREIGN'
    elif damage == 'projection':
        (s.root / 'projection/projection.json').write_bytes(b'{"schema":"changed"}')
    elif damage == 'report':
        (s.root / 'report/report.json').write_bytes(b'{"schema":"changed"}')
    elif damage == 'missing':
        s.cut['resources']['source'].clear()
        s.current['financial_digest'] = digest(s.cut)
    elif damage == 'foreign_root':
        s.enrollment['resources']['source']['native_id'][1] += 1
    with pytest.raises((ValueError, OSError)):
        s.port.verify(s.enrollment, s.current, 1000, scope='DISPOSABLE_TEST')
