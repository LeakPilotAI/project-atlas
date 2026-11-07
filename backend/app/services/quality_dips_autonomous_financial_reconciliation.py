"""Source-only financial replay/report reconciliation of an already authenticated cut.

This consumes FS1 event envelopes and the independent financial audit. It does
not authenticate native custody, convert fixture events to V4 operational records,
write records, or authorize an account or runtime.
"""
from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import body, digest, replay_verified_events, validate_manifest


def reconcile_authenticated_financial_cut(manifest, records, snapshot, *, expected_epoch,
                                         expected_revision, expected_head, expected_state_digest):
    """Reject stale, omitted, duplicated or arithmetically inconsistent cuts."""
    if (type(manifest) is not dict or type(records) is not list or type(snapshot) is not dict
            or type(expected_epoch) is not str or not expected_epoch
            or type(expected_revision) is not int or expected_revision < 0
            or type(expected_head) is not str or len(expected_head) != 64
            or type(expected_state_digest) is not str or len(expected_state_digest) != 64):
        raise ValueError('AUTO_FINANCIAL_EXPLICIT_CUT_REQUIRED')
    validate_manifest(manifest)
    if manifest['strategy'] != 'QUALITY_DIPS' or manifest['epoch'] != expected_epoch:
        raise ValueError('AUTO_FINANCIAL_FOREIGN_EPOCH_OR_STRATEGY')
    if len(records) != expected_revision or snapshot.get('revision') != expected_revision:
        raise ValueError('AUTO_FINANCIAL_INCOMPLETE_CUT')
    state, head, operations = replay_verified_events(manifest, records)
    if (head != expected_head or digest(state) != expected_state_digest
            or body(snapshot) != body(state) or len(operations) != expected_revision):
        raise ValueError('AUTO_FINANCIAL_REPLAY_OR_PROJECTION_MISMATCH')
    audit = audit_financial_events(manifest, records, snapshot)
    if (type(audit) is not dict or audit.get('source_revision') != expected_revision
            or audit.get('startup_authorized') is not False
            or audit.get('production_authorized') is not False):
        raise ValueError('AUTO_FINANCIAL_INDEPENDENT_AUDIT_REFUSED')
    return {'schema': 'QD_AUTO_FINANCIAL_RECONCILIATION_SOURCE_ONLY_V1',
            'epoch': expected_epoch, 'revision': expected_revision,
            'head': head, 'state_digest': digest(state), 'audit_digest': digest(audit),
            'startup_authorized': False, 'production_authorized': False}
