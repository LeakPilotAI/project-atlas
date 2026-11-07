"""Source-only proposed high-water retention protocol and adversarial rollback fence.

Injected custodian is NOT independently governed merely by implementing these
methods. No storage, signing, grant or operational activation occurs here.
"""
from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_v4_highwater_proposal import inspect_proposed_v4_highwater


def inspect_proposed_v4_retention(anchor, candidate, custodian, now):
    required = ('read_anchor', 'verify_anchor', 'verify_candidate')
    if custodian is None or any(not callable(getattr(custodian, k, None)) for k in required):
        raise ValueError('V4_RETENTION_SEPARATE_CUSTODIAN_REQUIRED')
    # Require the custodian's own retained anchor; publisher-supplied anchor
    # alone cannot establish a durable high-water floor.
    retained = custodian.read_anchor(candidate['account_id'], candidate['epoch'], now)
    if type(retained) is not dict or retained != anchor:
        raise ValueError('V4_RETENTION_ANCHOR_MISMATCH')
    original_anchor, original_candidate = digest(anchor), digest(candidate)
    result = inspect_proposed_v4_highwater(anchor, candidate, custodian, now)
    # Read the custodian again after external verification. A concurrent
    # advance, disappearance, or mutation refuses instead of resetting.
    again = custodian.read_anchor(candidate['account_id'], candidate['epoch'], now)
    if (type(again) is not dict or again != anchor
            or digest(anchor) != original_anchor or digest(candidate) != original_candidate):
        raise ValueError('V4_RETENTION_ANCHOR_CHANGED')
    return {**result, 'custodian_anchor_read_twice': True,
            'retention_independence_accepted': False,
            'rollback_resistance_accepted': False,
            'operational_authority_accepted': False,
            'paper_execution_authorized': False, 'live_order_authorized': False}