"""Fail-closed proposed V4 recovery from uncertain publication."""
import copy
import pytest
from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_v4_publication_journal_proposal import (
    SCHEMA, initial_publication_journal, transition_publication_journal)
from app.services.quality_dips_autonomous_v4_recovery_proposal import reconcile_proposed_v4_uncertain


def sample():
    pending = transition_publication_journal(initial_publication_journal(), 'RESERVE',
        {'publication_digest': 'a'*64, 'publication_id': 'PUB-1'})
    state = transition_publication_journal(pending, 'RESTART')
    p = state['pending']
    evidence = {'schema': 'QD_AUTO_V4_NATIVE_COMMIT_EVIDENCE_PROPOSAL_V1',
                'revision': p['revision'], 'previous': p['previous'],
                **p['record'], 'committed_head': digest([SCHEMA, p]), 'commit_pin': 'b'*64}
    return state, evidence


class Verifier:
    def __init__(self): self.calls = 0
    def verify_commit(self, evidence, now):
        self.calls += 1
        return True


def test_proposed_recovery_checks_commit_without_unfencing_journal():
    state, evidence = sample()
    before = copy.deepcopy((state, evidence))
    v = Verifier()
    result = reconcile_proposed_v4_uncertain(state, evidence, v, 100)
    assert v.calls == 2 and result['external_commit_checks_passed'] is True
    assert result['journal_status'] == 'UNCERTAIN'
    assert result['independent_custody_accepted'] is False
    assert result['paper_execution_authorized'] is False
    assert (state, evidence) == before


@pytest.mark.parametrize('damage', ['revision', 'bool_revision', 'parent', 'publication', 'id',
    'head', 'pin', 'schema', 'extra', 'not_uncertain', 'bad_clock', 'no_verifier',
    'denied', 'revoked', 'mutated', 'bad_pending'])
def test_proposed_recovery_refuses_unverified_or_corrupt_commit(damage):
    state, evidence = sample()
    v = Verifier()
    if damage == 'revision': evidence['revision'] = 2
    if damage == 'bool_revision': evidence['revision'] = True
    if damage == 'parent': evidence['previous'] = 'c'*64
    if damage == 'publication': evidence['publication_digest'] = 'c'*64
    if damage == 'id': evidence['publication_id'] = 'WRONG'
    if damage == 'head': evidence['committed_head'] = 'c'*64
    if damage == 'pin': evidence['commit_pin'] = ''
    if damage == 'schema': evidence['schema'] = 'WRONG'
    if damage == 'extra': evidence['approved'] = True
    if damage == 'not_uncertain': state['status'] = 'RESERVED'
    if damage == 'denied': v.verify_commit = lambda *args: False
    if damage == 'revoked':
        v.verify_commit = lambda *args: setattr(v, 'calls', v.calls + 1) or v.calls == 1
    if damage == 'mutated':
        def mutate(e, now):
            e['commit_pin'] = 'c'*64
            return True
        v.verify_commit = mutate
    if damage == 'bad_pending': state['pending']['revision'] = 7
    with pytest.raises(ValueError):
        reconcile_proposed_v4_uncertain(state, evidence,
            None if damage == 'no_verifier' else v,
            False if damage == 'bad_clock' else 100)