"""Native history + externally injected publisher/custodian checks, non-authorizing.

This is a fail-closed integration seam, not an authenticated publisher, signer,
independent custodian or accepted V4 financial publication protocol.
"""
from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_v4_native_publication_reader_proposal import inspect_proposed_v4_native_publication


def inspect_proposed_v4_native_witness(reader, pins, enrollment, publication,
                                       acknowledgment, publisher, custodian, now):
    if (type(now) is not int or now <= 0 or publisher is None or custodian is None
            or publisher is custodian
            or not callable(getattr(publisher, 'verify_publication', None))
            or not callable(getattr(custodian, 'verify_acknowledgment', None))):
        raise ValueError('V4_NATIVE_WITNESS_SEPARATE_PORTS_REQUIRED')
    before_pub, before_ack = digest(publication), digest(acknowledgment)
    first = inspect_proposed_v4_native_publication(reader, pins, enrollment,
                                                   publication, acknowledgment)
    for _ in range(2):
        if publisher.verify_publication(before_pub, publication['publication_id'], now) is not True:
            raise ValueError('V4_NATIVE_WITNESS_PUBLISHER_REFUSED')
        if custodian.verify_acknowledgment(before_ack, before_pub,
                                          acknowledgment['ack_id'], now) is not True:
            raise ValueError('V4_NATIVE_WITNESS_CUSTODIAN_REFUSED')
        if digest(publication) != before_pub or digest(acknowledgment) != before_ack:
            raise ValueError('V4_NATIVE_WITNESS_CLAIMS_CHANGED')
        again = inspect_proposed_v4_native_publication(reader, pins, enrollment,
                                                       publication, acknowledgment)
        if again != first:
            raise ValueError('V4_NATIVE_WITNESS_NATIVE_EVIDENCE_CHANGED')
    return {**first, 'external_witness_checks_passed': True,
            'independent_custody_verified': False,
            'independent_publication_verified': False,
            'operational_authority_accepted': False,
            'paper_execution_authorized': False, 'live_order_authorized': False}