"""Confined native high-water rollback fault tests; NOT trusted custody.

A separate native file is still controlled by the same test process. Caller-
held native pins cannot demonstrate independent non-rollbackable retention.
"""
import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from app.services.paper_financial_replay import body, strict
from app.services.quality_dips_autonomous_v4_retention_proposal import inspect_proposed_v4_retention
from test_quality_dips_autonomous_v4_highwater_proposal import sample


@pytest.fixture
def native_highwater():
    configured = os.environ.get('ATLAS_AUTO_ENROLLMENT_ROOT')
    if not configured:
        pytest.skip('NOT EXECUTED: confined native root required')
    repo = Path(__file__).resolve().parents[1]
    base = Path(configured)
    assert base.parent == repo / 'logs/diagnostics'
    assert base.name.startswith('qd-auto-enrollment-')
    root = base / 'v4-highwater-proposal' / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('v4_highwater_native',
        repo / 'scripts/volume_inspector/autonomous_enrollment_read.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    a, b = sample()
    output = module.s.w.WindowsOutput.create_root(str(root / 'source'))
    try:
        pins = {'anchor.json': output.write_bound('anchor.json', body(a).encode()),
                'candidate.json': output.write_bound('candidate.json', body(b).encode())}
        yield module, output, root, pins
    finally:
        output.close()


def read_docs(native):
    module, output, root, pins = native
    if {p.name for p in (root / 'source').iterdir()} != set(pins):
        raise ValueError('V4_HIGHWATER_NATIVE_ROSTER_MISMATCH')
    docs = {}
    for name, pin in pins.items():
        raw, _ = module.s.read_bound(output, name, pin)
        doc = strict(raw.decode('utf-8'))
        if type(doc) is not dict or body(doc).encode() != raw:
            raise ValueError('V4_HIGHWATER_NATIVE_CANONICAL_REQUIRED')
        docs[name] = doc
    return docs


class FixtureCustodian:
    """Test-only local reader; deliberately no independent custody claim."""
    def __init__(self, native):
        self.native = native
        self.calls = 0
    def read_anchor(self, account, epoch, now):
        self.calls += 1
        return read_docs(self.native)['anchor.json']
    def verify_anchor(self, anchor, now): return True
    def verify_candidate(self, candidate, now): return True


def verify_native_highwater(native, custodian=None):
    module, output, root, pins = native
    docs = read_docs(native)
    result = inspect_proposed_v4_retention(docs['anchor.json'], docs['candidate.json'],
                                           custodian or FixtureCustodian(native), 1000)
    if {p.name for p in (root / 'source').iterdir()} != set(pins):
        raise ValueError('V4_HIGHWATER_NATIVE_ROSTER_CHANGED')
    for name, pin in pins.items():
        module.s.read_bound(output, name, pin)
    return result


def test_confined_native_highwater_never_claims_independence(native_highwater):
    _, _, root, _ = native_highwater
    before = {p.name: p.read_bytes() for p in (root / 'source').iterdir()}
    result = verify_native_highwater(native_highwater)
    assert result['custodian_anchor_read_twice'] is True
    assert result['independent_retention_proven'] is False
    assert result['retention_independence_accepted'] is False
    assert result['paper_execution_authorized'] is False
    assert before == {p.name: p.read_bytes() for p in (root / 'source').iterdir()}


@pytest.mark.parametrize('damage', ['anchor_mutated', 'candidate_mutated', 'anchor_removed',
    'extra_file', 'wrong_anchor_identity', 'wrong_candidate_hash'])
def test_confined_native_highwater_refuses_storage_faults(native_highwater, damage):
    _, _, root, pins = native_highwater
    source = root / 'source'
    if damage == 'anchor_mutated': (source / 'anchor.json').write_bytes(b'{}')
    if damage == 'candidate_mutated': (source / 'candidate.json').write_bytes(b'{}')
    if damage == 'anchor_removed': (source / 'anchor.json').unlink()
    if damage == 'extra_file': (source / 'unexpected.json').write_bytes(b'{}')
    if damage == 'wrong_anchor_identity': pins['anchor.json']['id'] = [0, 0, 0]
    if damage == 'wrong_candidate_hash': pins['candidate.json']['sha256'] = 'f'*64
    with pytest.raises((ValueError, OSError)):
        verify_native_highwater(native_highwater)


@pytest.mark.parametrize('damage', ['anchor', 'candidate'])
def test_confined_native_highwater_refuses_mid_audit_change(native_highwater, damage):
    _, _, root, _ = native_highwater
    class MutatingCustodian(FixtureCustodian):
        def verify_candidate(self, candidate, now):
            (root / 'source' / f'{damage}.json').write_bytes(b'{}')
            return True
    with pytest.raises((ValueError, OSError)):
        verify_native_highwater(native_highwater, MutatingCustodian(native_highwater))