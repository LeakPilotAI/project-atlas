"""Proposed V4 crash reconciliation against independently supplied commit evidence.

No native writer, custody principal, high-water authority or operational grant is
installed. A caller-supplied verifier is only a source-contract dependency.
"""
from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_v4_publication_journal_proposal import (
    SCHEMA, transition_publication_journal)


def reconcile_proposed_v4_uncertain(state, evidence, verifier, now):
    if (type(state) is not dict or state.get('status') != 'UNCERTAIN'
            or type(now) is not int or now <= 0
            or not callable(getattr(verifier, 'verify_commit', None))):
        raise ValueError('V4_RECOVERY_BOUNDARY_REQUIRED')
    # Existing transition validates all shared state fields without changing
    # an uncertain journal. Never infer a commit from local state alone.
    if transition_publication_journal(state, 'RESTART') != state:
        raise ValueError('V4_RECOVERY_STATE_INVALID')
    pending = state['pending']
    if (type(pending) is not dict or set(pending) != {'revision', 'previous', 'record'}
            or type(pending['revision']) is not int
            or pending['revision'] != state['revision'] + 1
            or pending['previous'] != state['head']
            or type(pending['record']) is not dict
            or set(pending['record']) != {'publication_digest', 'publication_id'}
            or type(pending['record']['publication_digest']) is not str
            or len(pending['record']['publication_digest']) != 64
            or type(pending['record']['publication_id']) is not str
            or not 1 <= len(pending['record']['publication_id']) <= 128):
        raise ValueError('V4_RECOVERY_PENDING_INVALID')
    expected_head = digest([SCHEMA, pending])
    if (type(evidence) is not dict or set(evidence) != {
            'schema', 'revision', 'previous', 'publication_digest',
            'publication_id', 'committed_head', 'commit_pin'}
            or evidence['schema'] != 'QD_AUTO_V4_NATIVE_COMMIT_EVIDENCE_PROPOSAL_V1'
            or type(evidence['revision']) is not int
            or evidence['revision'] != pending['revision']
            or evidence['previous'] != pending['previous']
            or evidence['publication_digest'] != pending['record']['publication_digest']
            or evidence['publication_id'] != pending['record']['publication_id']
            or evidence['committed_head'] != expected_head
            or type(evidence['commit_pin']) is not str
            or len(evidence['commit_pin']) != 64):
        raise ValueError('V4_RECOVERY_COMMIT_EVIDENCE_MISMATCH')
    original_state = digest(state)
    original_evidence = digest(evidence)
    if verifier.verify_commit(evidence, now) is not True:
        raise ValueError('V4_RECOVERY_COMMIT_NOT_INDEPENDENTLY_VERIFIED')
    if digest(state) != original_state or digest(evidence) != original_evidence:
        raise ValueError('V4_RECOVERY_EVIDENCE_CHANGED')
    if verifier.verify_commit(evidence, now) is not True:
        raise ValueError('V4_RECOVERY_COMMIT_REVOKED')
    if digest(state) != original_state or digest(evidence) != original_evidence:
        raise ValueError('V4_RECOVERY_EVIDENCE_CHANGED')
    # Even with a caller-supplied verified commit, preserve the UNCERTAIN
    # journal until independent high-water custody and native replay are accepted.
    return {'schema': 'QD_AUTO_V4_RECOVERY_INSPECTION_PROPOSAL_V1',
            'expected_head': expected_head, 'revision': pending['revision'],
            'external_commit_checks_passed': True, 'journal_status': 'UNCERTAIN',
            'independent_custody_accepted': False,
            'operational_authority_accepted': False,
            'paper_execution_authorized': False, 'live_order_authorized': False}