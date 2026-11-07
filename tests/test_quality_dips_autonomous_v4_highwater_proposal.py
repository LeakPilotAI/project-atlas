"""V4 proposed high-water source-only fail-closed contract."""
import copy
import pytest
from app.services.quality_dips_autonomous_v4_highwater_proposal import inspect_proposed_v4_highwater, SCHEMA


def sample():
    a = {'schema': SCHEMA, 'account_id': 'PAPER', 'epoch': 'E1', 'revision': 1,
         'head': 'a'*64, 'parent': None, 'commit_pin': 'c'*64}
    b = {**a, 'revision': 2, 'head': 'b'*64, 'parent': a['head'], 'commit_pin': 'd'*64}
    return a, b


class Witness:
    def __init__(self): self.calls = 0
    def verify_anchor(self, anchor, now):
        self.calls += 1
        return True
    def verify_candidate(self, candidate, now):
        self.calls += 1
        return True


def test_highwater_source_inspection_never_grants_custody():
    a, b = sample()
    before = copy.deepcopy((a, b))
    w = Witness()
    result = inspect_proposed_v4_highwater(a, b, w, 1000)
    assert w.calls == 4
    assert result['external_checks_passed'] is True
    assert result['independent_retention_proven'] is False
    assert result['rollback_resistance_accepted'] is False
    assert result['paper_execution_authorized'] is False
    assert (a, b) == before


@pytest.mark.parametrize('damage', ['rollback', 'gap', 'fork', 'epoch', 'account', 'same_head',
    'bad_pin', 'bad_parent', 'extra', 'bool_revision', 'bad_clock', 'no_witness',
    'anchor_denied', 'candidate_denied', 'anchor_revoked', 'candidate_revoked',
    'anchor_mutated', 'candidate_mutated'])
def test_highwater_refuses_bad_evidence(damage):
    a, b = sample()
    w = Witness()
    if damage == 'rollback': b['revision'] = 0
    if damage == 'gap': b['revision'] = 4
    if damage == 'fork': b['parent'] = 'f'*64
    if damage == 'epoch': b['epoch'] = 'E2'
    if damage == 'account': b['account_id'] = 'OTHER'
    if damage == 'same_head': b['head'] = a['head']
    if damage == 'bad_pin': b['commit_pin'] = ''
    if damage == 'bad_parent': b['parent'] = 1
    if damage == 'extra': b['approved'] = True
    if damage == 'bool_revision': b['revision'] = True
    if damage == 'anchor_denied': w.verify_anchor = lambda *args: False
    if damage == 'candidate_denied': w.verify_candidate = lambda *args: False
    if damage == 'anchor_revoked':
        def revoked_anchor(*args):
            w.calls += 1
            return w.calls == 1
        w.verify_anchor = revoked_anchor
    if damage == 'candidate_revoked':
        def revoked_candidate(*args):
            w.calls += 1
            return w.calls == 2
        w.verify_candidate = revoked_candidate
    if damage == 'anchor_mutated':
        def mutate_anchor(*args):
            a['head'] = 'f'*64
            return True
        w.verify_anchor = mutate_anchor
    if damage == 'candidate_mutated':
        def mutate_candidate(*args):
            b['commit_pin'] = 'f'*64
            return True
        w.verify_candidate = mutate_candidate
    with pytest.raises(ValueError):
        inspect_proposed_v4_highwater(a, b, None if damage == 'no_witness' else w,
                                      False if damage == 'bad_clock' else 1000)