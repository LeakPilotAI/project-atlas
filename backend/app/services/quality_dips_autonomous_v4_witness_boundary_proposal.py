"""Fail-closed external witness boundary for proposed V4 publication custody.

No witness implementation, key, publisher, signer, writer, or authority is installed.
Caller-supplied checks are necessary but never sufficient for operational use.
"""
from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_v4_publication_proposal import inspect_proposed_v4_publication


class ProposedV4WitnessBoundary:
    """Read-only proposed contract; no self-issued or synthetic authority grants."""

    def __init__(self, *, publisher=None, custodian=None):
        if (publisher is None or custodian is None or publisher is custodian
                or not callable(getattr(publisher, 'verify_publication', None))
                or not callable(getattr(custodian, 'verify_acknowledgment', None))):
            raise ValueError('V4_WITNESS_INDEPENDENT_PORTS_REQUIRED')
        self.publisher, self.custodian = publisher, custodian

    def inspect(self, enrollment, envelopes, assertion, publication, acknowledgment, now):
        if type(now) is not int or now <= 0:
            raise ValueError('V4_WITNESS_CLOCK_REQUIRED')
        result = inspect_proposed_v4_publication(
            enrollment, envelopes, assertion, publication, acknowledgment)
        pub_digest = digest(publication)
        ack_digest = digest(acknowledgment)
        # These are externally supplied observations; neither grants operational
        # acceptance without a separately approved issuer/host/rights protocol.
        if self.publisher.verify_publication(pub_digest, publication['publication_id'], now) is not True:
            raise ValueError('V4_WITNESS_PUBLISHER_NOT_VERIFIED')
        if self.custodian.verify_acknowledgment(
                ack_digest, pub_digest, acknowledgment['ack_id'], now) is not True:
            raise ValueError('V4_WITNESS_CUSTODY_NOT_VERIFIED')
        # Revalidate the entire mutable evidence graph after external calls.
        again = inspect_proposed_v4_publication(
            enrollment, envelopes, assertion, publication, acknowledgment)
        if again != result or digest(publication) != pub_digest or digest(acknowledgment) != ack_digest:
            raise ValueError('V4_WITNESS_EVIDENCE_CHANGED_DURING_CHECK')
        if self.publisher.verify_publication(pub_digest, publication['publication_id'], now) is not True:
            raise ValueError('V4_WITNESS_PUBLISHER_REVOKED')
        if self.custodian.verify_acknowledgment(
                ack_digest, pub_digest, acknowledgment['ack_id'], now) is not True:
            raise ValueError('V4_WITNESS_CUSTODY_REVOKED')
        return {**result, 'external_witness_checks_passed': True,
                'independent_custody_verified': False,
                'independent_publication_verified': False,
                'operational_authority_accepted': False,
                'paper_execution_authorized': False, 'live_order_authorized': False}