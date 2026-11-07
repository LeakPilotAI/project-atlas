"""Synthetic policy obligations, not a production proof issuer or recovery API.

No Docker/process calls. A fixture isolation claim does not implement isolation.
No snapshot transition, uncertainty clearing or startup permission is provided.
"""
import copy
import importlib.util
import secrets
from pathlib import Path

spec = importlib.util.spec_from_file_location('policy_handoff', Path(__file__).with_name('manual_handoff.py'))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
s, Refused = h.s, h.Refused


class SyntheticEvidence:
    """Test facts only; even a perfectly formed instance is not real evidence."""
    def __init__(self, facts):
        self.facts = copy.deepcopy(facts)


class PolicyEvaluator:
    def __init__(self, handoff, output):
        if type(handoff) is not h.Handoff:
            raise Refused('Exact synthetic handoff required')
        self.handoff, self.output = handoff, output

    def evaluate_synthetic(self, evidence, now):
        if type(evidence) is not SyntheticEvidence or type(now) not in (int, float):
            raise Refused('Synthetic evidence and controlled clock only')
        facts = copy.deepcopy(evidence.facts)
        if len(s.encoded(facts)) > 16384:
            raise Refused('Bounded fixture evidence required')
        with self.handoff.store.guard():
            # Reads actual disposable native snapshot/witness/receipt identities.
            _, pin, _ = self.handoff._current()
            if pin != self.handoff.store.pin:
                raise Refused('Snapshot and durable pin disagree')
            state = self.handoff.store.snapshot()
            reasons = []
            def require(condition, code):
                if not condition:
                    reasons.append(code)
            required = {'binding', 'before', 'after', 'approval', 'writers', 'isolation', 'continuity', 'pending'}
            if not isinstance(facts, dict) or set(facts) != required:
                raise Refused('Complete policy facts required')
            binding = facts['binding']
            inspection = state['inspection']
            require(inspection is not None and state['startup'] is None, 'INSPECTION_STATE_UNPROVEN')
            require(s.encoded(binding) == s.encoded({'instance': state['instance'], 'revision': state['revision'],
                                'state_hash': s.sha(s.encoded(state)), 'inspection': inspection}), 'STALE_STATE_BINDING')
            require(facts['pending'] == 'NONE', 'PENDING_LIFECYCLE_OR_RECOVERY')
            observations = []
            for name in ('before', 'after'):
                observation = facts[name]
                schema = {'helper', 'operation', 'identity_verified', 'status', 'observed', 'source', 'facts_hash'}
                if not isinstance(observation, dict) or set(observation) != schema:
                    raise Refused('Complete observation required')
                require(inspection is not None and observation['helper'] == inspection['helper']
                        and observation['operation'] == inspection['operation'], 'EXACT_HELPER_UNPROVEN')
                require(observation['identity_verified'] is True and observation['status'] == 'EXITED', 'EXIT_UNPROVEN')
                require(observation['source'] == 'INDEPENDENT_FIXTURE_OBSERVER', 'SOURCE_UNPROVEN')
                require(type(observation['observed']) in (int, float)
                        and 0 <= now-observation['observed'] <= 5, 'OBSERVATION_STALE')
                require(isinstance(observation['facts_hash'], str) and len(observation['facts_hash']) == 64
                        and all(c in '0123456789abcdef' for c in observation['facts_hash']), 'EXIT_FACTS_UNPROVEN')
                observations.append(observation)
            require({k:v for k,v in observations[0].items() if k != 'observed'} ==
                    {k:v for k,v in observations[1].items() if k != 'observed'}, 'CONTRADICTORY_OBSERVATIONS')
            approval = facts['approval']
            if not isinstance(approval, dict) or set(approval) != {'binding', 'operator', 'explicit', 'issued', 'nonce'}:
                raise Refused('Complete approval required')
            require(s.encoded(approval['binding']) == s.encoded(binding) and approval['operator'] == 'SYNTHETIC_EXPECTED_OPERATOR'
                    and approval['explicit'] is True, 'APPROVAL_UNPROVEN')
            require(type(approval['issued']) in (int, float) and 0 <= now-approval['issued'] <= 45, 'APPROVAL_STALE')
            require(type(approval['issued']) in (int, float) and observations[0]['observed'] <= approval['issued']
                    <= observations[1]['observed'] <= now, 'APPROVAL_NOT_BRACKETED')
            nonce = approval['nonce']
            if not isinstance(nonce, str) or len(nonce) != 32 or any(c not in '0123456789abcdef' for c in nonce):
                raise Refused('Invalid approval identity')
            require(facts['writers'] == 'INDEPENDENTLY_VERIFIED_NONE', 'WRITER_EXCLUSION_UNPROVEN')
            # Continuity alone never excludes writers; a click/window assertion is not custody.
            isolation = facts['isolation']
            expected = {'kind': 'INDEPENDENT_ALL_WRITER_CUSTODY', 'binding': binding,
                        'helper_quiescent': True, 'external_writers_excluded': True,
                        'atlas_startup_excluded': True, 'backend_restart_cannot_resume_writer': True,
                        'held_from': 995, 'held_until': 1010, 'authority': 'SYNTHETIC_TECHNICAL_ISOLATOR'}
            # Exact bounded fixture interval; no collector/enforcer exists in production.
            require(s.encoded(isolation) == s.encoded(expected) and 995 <= observations[0]['observed'] <= now < 1010,
                    'INDEPENDENT_CUSTODY_UNPROVEN')
            require(facts['continuity'] in ('PROVEN_SYNTHETIC', 'UNPROVEN'), 'CONTINUITY_CONTRADICTORY')
            model_ok = not reasons
            if model_ok:
                # An exclusive durable reservation prevents replay even after interruption/restart.
                self.output._write(self.output.root_handle, 'attempt-'+nonce+'.json',
                                   s.encoded({'binding': binding, 'scope': 'MODEL_ONLY', 'nonce': nonce}))
            result = {'scope': 'SYNTHETIC_POLICY_ONLY', 'model_conditions_satisfied': model_ok,
                      'recovery_authorized': False, 'startup_authorized': False,
                      'reasons': reasons, 'real_isolation_implemented': False,
                      'state_revision': state['revision'], 'evidence_hash': s.sha(s.encoded(facts))}
            self.output._write(self.output.root_handle, 'decision-'+secrets.token_hex(16)+'.json', s.encoded(result))
            return result

    def production_recovery(self):
        raise Refused('Independent production isolation/exit proof absent; recovery BLOCKED')
