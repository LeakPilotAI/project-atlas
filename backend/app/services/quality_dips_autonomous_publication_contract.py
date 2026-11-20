"""Pure V4 operational financial publication contract, never an authority grant.

This validates a proposed immutable publication envelope; accepted custody,
writer ownership, provider rights, native file identity and runtime grants are
independent and deliberately not installed by this module.
"""
from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_autonomous_enrollment import publication_intent, validate_enrollment


SCHEMA = 'QD_AUTO_NATIVE_FINANCIAL_PUBLICATION_V4'


def validate_financial_publication(enrollment, publication):
    """Require complete versioned, contiguous, account-bound publication metadata."""
    e = validate_enrollment(enrollment)
    p = strict(body(publication))
    required = {'schema', 'account_id', 'epoch', 'enrollment_digest', 'inception_intent_digest',
                'revision', 'event_head', 'projection_digest', 'report_digest', 'source_files',
                'projection_file', 'report_file', 'status', 'ack_id'}
    if type(p) is not dict or set(p) != required or p['schema'] != SCHEMA:
        raise ValueError('AUTO_PUBLICATION_EXACT_V4_SCHEMA_REQUIRED')
    if (p['account_id'] != e['account_id'] or p['epoch'] != e['epoch']
            or p['enrollment_digest'] != digest(e)
            or p['inception_intent_digest'] != digest(publication_intent(e))):
        raise ValueError('AUTO_PUBLICATION_ACCOUNT_EPOCH_INCEPTION_MISMATCH')
    revision = p['revision']
    if type(revision) is not int or not 0 <= revision <= 128:
        raise ValueError('AUTO_PUBLICATION_BOUNDED_REVISION_REQUIRED')
    for field in ('event_head', 'projection_digest', 'report_digest'):
        value = p[field]
        if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('AUTO_PUBLICATION_DIGEST_REQUIRED')
    names = ['inception.json', *(f'{i:04d}-event.json' for i in range(1, revision + 1))]
    if (type(p['source_files']) is not list or p['source_files'] != names
            or p['projection_file'] != 'projection.json'
            or p['report_file'] != 'report.json'):
        raise ValueError('AUTO_PUBLICATION_COMPLETE_FILE_ROSTER_REQUIRED')
    if (p['status'] != 'ACKNOWLEDGED' or type(p['ack_id']) is not str
            or not p['ack_id'] or len(p['ack_id']) > 256):
        raise ValueError('AUTO_PUBLICATION_ACK_REQUIRED')
    # Metadata validity is not evidence of an independently authenticated ack.
    return p
