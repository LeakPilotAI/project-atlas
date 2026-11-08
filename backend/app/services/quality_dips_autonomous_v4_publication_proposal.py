"""Non-authorizing proposed V4 publisher/custody receipt binding contract.

A claimed acknowledgment is never proof of independent custody or publication.
This function validates internal financial consistency only, without I/O.
"""
from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_autonomous_v4_native_envelope_proposal import verify_proposed_v4_native_envelopes


def inspect_proposed_v4_publication(enrollment, envelopes, assertion, publication, acknowledgment):
    if (type(publication) is not dict or set(publication) != {
            'schema', 'account_id', 'epoch', 'enrollment_digest', 'revision',
            'head', 'receipts_digest', 'assertion_digest', 'publication_id'}
            or publication['schema'] != 'QD_AUTO_V4_PUBLICATION_PROPOSAL_V1'
            or any(publication[k] != enrollment.get(k) for k in ('account_id', 'epoch', 'enrollment_digest'))
            or type(publication['publication_id']) is not str
            or not 1 <= len(publication['publication_id']) <= 128):
        raise ValueError('V4_PUBLICATION_PROPOSAL_SCHEMA')
    audit = verify_proposed_v4_native_envelopes(enrollment, envelopes, assertion)
    if (type(publication['revision']) is not int
            or publication['revision'] != audit['revision']
            or publication['head'] != audit['head']
            or publication['receipts_digest'] != audit['receipts_digest']
            or publication['assertion_digest'] != digest(assertion)):
        raise ValueError('V4_PUBLICATION_PROPOSAL_FINANCIAL_MISMATCH')
    if (type(acknowledgment) is not dict or set(acknowledgment) != {
            'schema', 'publication_id', 'publication_digest', 'ack_id', 'status'}
            or acknowledgment['schema'] != 'QD_AUTO_V4_CUSTODY_ACK_PROPOSAL_V1'
            or acknowledgment['publication_id'] != publication['publication_id']
            or acknowledgment['publication_digest'] != digest(publication)
            or type(acknowledgment['ack_id']) is not str
            or not 1 <= len(acknowledgment['ack_id']) <= 128
            or acknowledgment['status'] != 'ACKNOWLEDGED'):
        raise ValueError('V4_PUBLICATION_PROPOSAL_ACK_MISMATCH')
    return {'schema': 'QD_AUTO_V4_PUBLICATION_INSPECTION_PROPOSAL_V1',
            'revision': audit['revision'], 'publication_digest': digest(publication),
            'acknowledgment_digest': digest(acknowledgment),
            'internal_consistency_verified': True,
            'independent_custody_verified': False,
            'independent_publication_verified': False,
            'operational_authority_accepted': False,
            'paper_execution_authorized': False, 'live_order_authorized': False}