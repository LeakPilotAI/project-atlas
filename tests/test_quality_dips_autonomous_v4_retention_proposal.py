"""Adversarial rollback tests for the proposed retained custody anchor."""
import copy
import pytest
from app.services.quality_dips_autonomous_v4_retention_proposal import inspect_proposed_v4_retention
from test_quality_dips_autonomous_v4_highwater_proposal import sample


class Custodian:
    def __init__(self, anchor):
        self.anchor = copy.deepcopy(anchor)
        self.reads = 0
        self.checks = 0
    def read_anchor(self, account, epoch, now):
        self.reads += 1
        return copy.deepcopy(self.anchor)
    def verify_anchor(self, anchor, now):
        self.checks += 1
        return True
    def verify_candidate(self, candidate, now):
        self.checks += 1
        return True


def test_proposed_retention_reads_twice_but_never_accepts_independence():
    a, b = sample()
    c = Custodian(a)
    before = copy.deepcopy((a, b))
    result = inspect_proposed_v4_retention(a, b, c, 100)
    assert c.reads == 2 and c.checks == 4
    assert result['custodian_anchor_read_twice'] is True
    assert result['retention_independence_accepted'] is False
    assert result['rollback_resistance_accepted'] is False
    assert result['paper_execution_authorized'] is False
    assert (a, b) == before


@pytest.mark.parametrize('attack', ['missing_custodian', 'missing_method', 'retained_rollback',
    'retained_fork', 'retained_missing', 'retained_foreign_epoch', 'candidate_rollback',
    'candidate_gap', 'candidate_fork', 'candidate_foreign_account', 'read_advance',
    'read_disappear', 'read_mutate_anchor', 'verifier_mutates_candidate',
    'verifier_revokes', 'verifier_denies'])
def test_proposed_retention_refuses_adversarial_cases(attack):
    a, b = sample()
    c = Custodian(a)
    if attack == 'missing_custodian': c = None
    if attack == 'missing_method': c.verify_anchor = None
    if attack == 'retained_rollback': c.anchor['revision'] = 0
    if attack == 'retained_fork': c.anchor['head'] = 'f'*64
    if attack == 'retained_missing': c.anchor = None
    if attack == 'retained_foreign_epoch': c.anchor['epoch'] = 'OTHER'
    if attack == 'candidate_rollback': b['revision'] = 1
    if attack == 'candidate_gap': b['revision'] = 4
    if attack == 'candidate_fork': b['parent'] = 'f'*64
    if attack == 'candidate_foreign_account': b['account_id'] = 'OTHER'
    if attack in ('read_advance', 'read_disappear', 'read_mutate_anchor'):
        original = c.read_anchor
        def read(*args):
            if c.reads == 1:
                if attack == 'read_advance': c.anchor['revision'] += 1
                if attack == 'read_disappear': c.anchor = None
                if attack == 'read_mutate_anchor': a['head'] = 'f'*64
            return original(*args)
        c.read_anchor = read
    if attack == 'verifier_mutates_candidate':
        def mutate(*args):
            b['head'] = 'f'*64
            return True
        c.verify_candidate = mutate
    if attack == 'verifier_revokes':
        def revoke(*args):
            c.checks += 1
            return c.checks == 1
        c.verify_anchor = revoke
    if attack == 'verifier_denies': c.verify_candidate = lambda *args: False
    with pytest.raises((ValueError, TypeError)):
        inspect_proposed_v4_retention(a, b, c, 100)