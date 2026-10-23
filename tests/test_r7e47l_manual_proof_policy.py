"""Native disposable state with explicit synthetic technical-isolation facts."""
import copy
import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Native Windows required')
spec = importlib.util.spec_from_file_location('policy_test', ROOT/'scripts/volume_inspector/manual_proof_policy.py')
m = importlib.util.module_from_spec(spec)
if os.name == 'nt': spec.loader.exec_module(m)


@pytest.fixture
def policy(tmp_path):
    store = m.s.SnapshotStore.provision_synthetic(str(tmp_path/'state'), str(tmp_path/'witness'))
    handoff = m.h.Handoff.provision_synthetic(store, str(tmp_path/'handoff'), m.h.ManualFixtureAuthority())
    state = handoff.inspect_synthetic('inspection-one', 'c'*64, approved=True)
    output = m.s.w.WindowsOutput.create_root(str(tmp_path/'policy'))
    evaluator = m.PolicyEvaluator(handoff, output)
    binding = {'instance': state['instance'], 'revision': state['revision'], 'state_hash': m.s.sha(m.s.encoded(state)),
               'inspection': state['inspection']}
    before = {'helper': 'c'*64, 'operation': 'inspection-one', 'identity_verified': True, 'status': 'EXITED',
              'observed': 999, 'source': 'INDEPENDENT_FIXTURE_OBSERVER', 'facts_hash': 'd'*64}
    facts = {'binding': binding, 'before': before, 'after': {**before, 'observed': 1001},
             'approval': {'binding': binding, 'operator': 'SYNTHETIC_EXPECTED_OPERATOR', 'explicit': True, 'issued': 1000, 'nonce': 'a'*32},
             'writers': 'INDEPENDENTLY_VERIFIED_NONE', 'continuity': 'UNPROVEN', 'pending': 'NONE',
             'isolation': {'kind': 'INDEPENDENT_ALL_WRITER_CUSTODY', 'binding': binding, 'helper_quiescent': True,
                           'external_writers_excluded': True, 'atlas_startup_excluded': True,
                           'backend_restart_cannot_resume_writer': True, 'held_from': 995, 'held_until': 1010,
                           'authority': 'SYNTHETIC_TECHNICAL_ISOLATOR'}}
    try: yield evaluator, facts
    finally:
        output.close()
        handoff.close()


def test_full_model_is_not_real_authority_and_does_not_clear_state(policy):
    evaluator, facts = policy
    result = evaluator.evaluate_synthetic(m.SyntheticEvidence(facts), 1002)
    assert result['model_conditions_satisfied'] is True
    assert result['recovery_authorized'] is False and result['startup_authorized'] is False
    assert evaluator.handoff.store.snapshot()['inspection'] is not None
    with pytest.raises(m.Refused): evaluator.production_recovery()


@pytest.mark.parametrize('case', ['running', 'missing', 'replaced', 'docker-unavailable', 'restart-ambiguity',
    'contradiction', 'stale', 'future', 'writer-active', 'writer-unknown', 'wrong-operator', 'declined',
    'old-approval', 'wrong-revision', 'unbracketed', 'pending', 'external-clients', 'restart-writer',
    'operator-asserted-isolation', 'exit-alone', 'unchanged-engine-alone', 'timeout-alone'])
def test_unproven_conditions_refuse(policy, case):
    evaluator, facts = policy
    if case in ('running', 'missing', 'replaced', 'docker-unavailable'):
        facts['after']['status'] = {'running':'RUNNING', 'missing':'MISSING', 'replaced':'REPLACED', 'docker-unavailable':'UNKNOWN'}[case]
    elif case == 'restart-ambiguity': facts['isolation'] = None
    elif case == 'contradiction': facts['after']['facts_hash'] = 'e'*64
    elif case == 'stale': facts['before']['observed'] = 900
    elif case == 'future': facts['after']['observed'] = 1003
    elif case.startswith('writer-'): facts['writers'] = case
    elif case == 'wrong-operator': facts['approval']['operator'] = 'someone-else'
    elif case == 'declined': facts['approval']['explicit'] = False
    elif case == 'old-approval': facts['approval']['issued'] = 900
    elif case == 'wrong-revision': facts['binding'] = {**facts['binding'], 'revision': 99}
    elif case == 'unbracketed': facts['approval']['issued'] = 1002
    elif case == 'pending': facts['pending'] = 'STARTUP'
    elif case == 'external-clients': facts['isolation']['external_writers_excluded'] = False
    elif case == 'restart-writer': facts['isolation']['backend_restart_cannot_resume_writer'] = False
    else:
        facts['isolation'] = {'operator_says_safe': True}
        if case == 'unchanged-engine-alone': facts['continuity'] = 'PROVEN_SYNTHETIC'
    result = evaluator.evaluate_synthetic(m.SyntheticEvidence(facts), 1002)
    assert not result['model_conditions_satisfied'] and not result['recovery_authorized']


def test_replayed_approval_and_restart_refuse(policy):
    evaluator, facts = policy
    evaluator.evaluate_synthetic(m.SyntheticEvidence(facts), 1002)
    with pytest.raises(FileExistsError): evaluator.evaluate_synthetic(m.SyntheticEvidence(facts), 1002)
    with m.s.w.WindowsOutput(evaluator.output.root) as reopened:
        again = m.PolicyEvaluator(evaluator.handoff, reopened)
        with pytest.raises(FileExistsError): again.evaluate_synthetic(m.SyntheticEvidence(facts), 1002)


def test_interrupted_decision_cannot_reuse_reserved_approval(policy, monkeypatch):
    evaluator, facts = policy
    original = evaluator.output._write
    def interrupted(handle, name, data):
        if name.startswith('decision-'): raise OSError('Synthetic interruption')
        return original(handle, name, data)
    monkeypatch.setattr(evaluator.output, '_write', interrupted)
    with pytest.raises(OSError): evaluator.evaluate_synthetic(m.SyntheticEvidence(facts), 1002)
    monkeypatch.setattr(evaluator.output, '_write', original)
    with pytest.raises(FileExistsError): evaluator.evaluate_synthetic(m.SyntheticEvidence(facts), 1002)


@pytest.mark.parametrize('surface', ['snapshot', 'witness'])
def test_corrupt_native_state_refuses_before_decision(policy, surface):
    evaluator, facts = policy
    store = evaluator.handoff.store
    target = store.output if surface == 'snapshot' else store.witness
    # Native handle identity remains; same-owner corruption must still fail hash verification.
    prefix = 'snapshot' if surface == 'snapshot' else 'commit'
    (Path(target.root)/f'{prefix}-{store.pin["revision"]:08d}.json').write_bytes(b'{}')
    with pytest.raises((m.Refused, ValueError, OSError)):
        evaluator.evaluate_synthetic(m.SyntheticEvidence(facts), 1002)


def test_concurrent_startup_inspection_and_replay_remain_closed(policy):
    evaluator, facts = policy
    def attempt(kind):
        try:
            if kind == 'startup': evaluator.handoff.start_synthetic('start-two', {'pid': 1, 'created': 1, 'exe': 'a'*64, 'command': 'b'*64})
            elif kind == 'inspection': evaluator.handoff.inspect_synthetic('inspection-two', 'e'*64, approved=True)
            else: return evaluator.evaluate_synthetic(m.SyntheticEvidence(copy.deepcopy(facts)), 1002)['model_conditions_satisfied']
        except (m.Refused, FileExistsError): return False
        raise AssertionError('Unexpected admission')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, ['startup', 'inspection', 'policy', 'policy']))
    # A competing refused start may leave a durable unresolved intent; all-refuse is safe.
    assert sum(results) <= 1 and evaluator.handoff.store.snapshot()['startup'] is None


def test_raw_live_evidence_not_accepted(policy):
    evaluator, facts = policy
    with pytest.raises(m.Refused): evaluator.evaluate_synthetic(facts, 1002)


def test_integer_cannot_substitute_for_isolation_boolean(policy):
    evaluator, facts = policy
    facts['isolation']['external_writers_excluded'] = 1
    assert not evaluator.evaluate_synthetic(m.SyntheticEvidence(facts), 1002)['model_conditions_satisfied']


def test_true_cannot_substitute_for_revision_one(policy):
    evaluator, facts = policy
    facts['binding']['revision'] = True
    assert not evaluator.evaluate_synthetic(m.SyntheticEvidence(facts), 1002)['model_conditions_satisfied']
