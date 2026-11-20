"""Non-authorizing V4 custody high-water continuity inspection.

Trusted anchors must originate outside the mutable publisher state. This
source-only inspector cannot establish independent retention or authenticity.
"""
from app.services.paper_financial_replay import digest

SCHEMA = 'QD_AUTO_V4_CUSTODY_HIGHWATER_PROPOSAL_V1'


def inspect_proposed_v4_highwater(anchor, candidate, verifier, now):
    if (type(now) is not int or now <= 0
            or not callable(getattr(verifier, 'verify_anchor', None))
            or not callable(getattr(verifier, 'verify_candidate', None))):
        raise ValueError('V4_HIGHWATER_TRUST_BOUNDARY_REQUIRED')
    for entry in (anchor, candidate):
        if (type(entry) is not dict or set(entry) != {
                'schema', 'account_id', 'epoch', 'revision', 'head', 'parent', 'commit_pin'}
                or entry['schema'] != SCHEMA
                or type(entry['account_id']) is not str or not entry['account_id']
                or type(entry['epoch']) is not str or not entry['epoch']
                or type(entry['revision']) is not int or not 0 <= entry['revision'] <= 128
                or type(entry['head']) is not str or len(entry['head']) != 64
                or type(entry['commit_pin']) is not str or len(entry['commit_pin']) != 64
                or (entry['revision'] == 0 and entry['parent'] is not None)
                or (entry['revision'] > 0 and entry['parent'] is not None
                    and (type(entry['parent']) is not str or len(entry['parent']) != 64))):
            raise ValueError('V4_HIGHWATER_SCHEMA_INVALID')
    if (anchor['account_id'] != candidate['account_id']
            or anchor['epoch'] != candidate['epoch']
            or candidate['revision'] != anchor['revision'] + 1
            or candidate['parent'] != anchor['head']
            or candidate['head'] == anchor['head']):
        raise ValueError('V4_HIGHWATER_ROLLBACK_OR_FORK')
    original_anchor, original_candidate = digest(anchor), digest(candidate)
    for _ in range(2):
        if verifier.verify_anchor(anchor, now) is not True:
            raise ValueError('V4_HIGHWATER_ANCHOR_UNVERIFIED')
        if verifier.verify_candidate(candidate, now) is not True:
            raise ValueError('V4_HIGHWATER_CANDIDATE_UNVERIFIED')
        if digest(anchor) != original_anchor or digest(candidate) != original_candidate:
            raise ValueError('V4_HIGHWATER_MUTATED_DURING_VERIFICATION')
    return {'schema': 'QD_AUTO_V4_HIGHWATER_INSPECTION_PROPOSAL_V1',
            'candidate_revision': candidate['revision'],
            'candidate_digest': original_candidate,
            'external_checks_passed': True,
            'independent_retention_proven': False,
            'rollback_resistance_accepted': False,
            'operational_authority_accepted': False,
            'paper_execution_authorized': False, 'live_order_authorized': False}