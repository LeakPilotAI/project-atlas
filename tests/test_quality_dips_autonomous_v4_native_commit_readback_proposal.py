"""Confined Windows native readback for proposed V4 commit evidence.

Test-only; native identity/hash pins supplied by the fixture are NOT an
independently retained custody high-water mark or an operational authority.
"""
import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from app.services.paper_financial_replay import body, strict
from app.services.quality_dips_autonomous_v4_recovery_proposal import reconcile_proposed_v4_uncertain
from test_quality_dips_autonomous_v4_recovery_proposal import sample


@pytest.fixture
def confined_commit():
    value = os.environ.get('ATLAS_AUTO_ENROLLMENT_ROOT')
    if not value:
        pytest.skip('NOT EXECUTED: confined Windows native enrollment root required')
    repo = Path(__file__).resolve().parents[1]
    base = Path(value)
    assert base.parent == repo / 'logs/diagnostics'
    assert base.name.startswith('qd-auto-enrollment-')
    root = base / 'v4-commit-proposal' / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('v4_commit_proposal_native',
        repo / 'scripts/volume_inspector/autonomous_enrollment_read.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    state, evidence = sample()
    output = module.s.w.WindowsOutput.create_root(str(root / 'source'))
    try:
        pins = {
            'pending.json': output.write_bound('pending.json', body(state).encode()),
            'commit.json': output.write_bound('commit.json', body(evidence).encode())}
        yield module, output, root, pins
    finally:
        output.close()


def verify_confined_commit(native, verifier):
    module, output, root, pins = native
    if {p.name for p in (root / 'source').iterdir()} != set(pins):
        raise ValueError('V4_COMMIT_NATIVE_ROSTER_MISMATCH')
    docs = {}
    for name, pin in pins.items():
        raw, _ = module.s.read_bound(output, name, pin)
        doc = strict(raw.decode('utf-8'))
        if type(doc) is not dict or body(doc).encode() != raw:
            raise ValueError('V4_COMMIT_NATIVE_CANONICAL_REQUIRED')
        docs[name] = doc
    result = reconcile_proposed_v4_uncertain(docs['pending.json'], docs['commit.json'], verifier, 1000)
    if {p.name for p in (root / 'source').iterdir()} != set(pins):
        raise ValueError('V4_COMMIT_NATIVE_ROSTER_CHANGED')
    for name, pin in pins.items():
        module.s.read_bound(output, name, pin)
    return result


class TestVerifier:
    __test__ = False
    def __init__(self): self.calls = 0
    def verify_commit(self, evidence, now):
        self.calls += 1
        return True


def test_native_commit_readback_never_unfences_journal(confined_commit):
    _, _, root, _ = confined_commit
    before = {p.name: p.read_bytes() for p in (root / 'source').iterdir()}
    verifier = TestVerifier()
    result = verify_confined_commit(confined_commit, verifier)
    assert verifier.calls == 2
    assert result['journal_status'] == 'UNCERTAIN'
    assert result['independent_custody_accepted'] is False
    assert result['paper_execution_authorized'] is False
    assert before == {p.name: p.read_bytes() for p in (root / 'source').iterdir()}


@pytest.mark.parametrize('damage', ['commit_bytes', 'pending_bytes', 'missing_commit', 'extra_file',
                                    'wrong_identity_pin', 'wrong_hash_pin'])
def test_native_commit_readback_refuses_corruption(damage, confined_commit):
    _, _, root, pins = confined_commit
    source = root / 'source'
    if damage == 'commit_bytes': (source / 'commit.json').write_bytes(b'{}')
    if damage == 'pending_bytes': (source / 'pending.json').write_bytes(b'{}')
    if damage == 'missing_commit': (source / 'commit.json').unlink()
    if damage == 'extra_file': (source / 'unexpected.json').write_bytes(b'{}')
    if damage == 'wrong_identity_pin': pins['commit.json']['id'] = [0, 0, 0]
    if damage == 'wrong_hash_pin': pins['commit.json']['sha256'] = 'f' * 64
    with pytest.raises((ValueError, OSError)):
        verify_confined_commit(confined_commit, TestVerifier())


@pytest.mark.parametrize('damage', ['commit', 'pending'])
def test_native_commit_readback_refuses_post_audit_mutation(damage, confined_commit):
    _, _, root, _ = confined_commit
    source = root / 'source'
    class MutatingVerifier(TestVerifier):
        def verify_commit(self, evidence, now):
            self.calls += 1
            if self.calls == 1:
                (source / f'{damage}.json').write_bytes(b'{}')
            return True
    with pytest.raises((ValueError, OSError)):
        verify_confined_commit(confined_commit, MutatingVerifier())