"""Fail-closed publication evidence adapter for existing-only native readback.

Requires separately injected custody acknowledgment and financial replay ports.
No default grants, filesystem publication, or test-to-operational conversion.
"""
from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_autonomous_publication_binding import bind_financial_publication_to_native_cut
from app.services.quality_dips_autonomous_publication_contract import validate_financial_publication


class BoundAutonomousFinancialPublication:
    def __init__(self, *, publication=None, custody_ack=None, financial_replay=None):
        if publication is None or custody_ack is None or financial_replay is None:
            raise ValueError('AUTO_PUBLICATION_INDEPENDENT_PORTS_REQUIRED')
        self.publication = publication
        self.custody_ack = custody_ack
        self.financial_replay = financial_replay

    def verify_cut(self, enrollment, current, documents, now, *, scope):
        if scope != 'LOCAL_ENROLLED' or type(now) is not int or now <= 0:
            raise ValueError('AUTO_PUBLICATION_OPERATIONAL_SCOPE_REQUIRED')
        if type(current) is not dict or current.get('scope') != scope:
            raise ValueError('AUTO_PUBLICATION_CURRENT_SCOPE_MISMATCH')
        # The accepted publisher and custody authority are injected, never
        # inferred from the existence of a publication JSON document.
        with self.publication.lease(enrollment, current, now, scope=scope) as publication_lease:
            p = validate_financial_publication(enrollment, publication_lease.snapshot)
            if publication_lease.check(strict(body(p)), now) is not True:
                raise ValueError('AUTO_PUBLICATION_LEASE_NOT_AUTHENTICATED')
            with self.custody_ack.lease(enrollment, p, now, scope=scope) as ack_lease:
                if (ack_lease.check(p['ack_id'], digest(p), now) is not True):
                    raise ValueError('AUTO_PUBLICATION_ACK_NOT_AUTHENTICATED')
                with self.financial_replay.lease(enrollment, p, now, scope=scope) as replay_lease:
                    cut = strict(body(replay_lease.snapshot))
                    if (type(cut) is not dict or cut.get('scope') != scope):
                        raise ValueError('AUTO_PUBLICATION_FINANCIAL_CUT_SCOPE_MISMATCH')
                    if (type(current.get('financial_digest')) is not str
                            or current['financial_digest'] != digest(cut)):
                        raise ValueError('AUTO_PUBLICATION_CURRENT_FINANCIAL_CUT_MISMATCH')
                    if replay_lease.check(strict(body(cut)), now) is not True:
                        raise ValueError('AUTO_PUBLICATION_FINANCIAL_CUT_NOT_AUTHENTICATED')
                    if bind_financial_publication_to_native_cut(enrollment, p, cut, documents) is not True:
                        raise ValueError('AUTO_PUBLICATION_FINANCIAL_BINDING_REFUSED')
                    if self.financial_replay.verify(enrollment, p, cut, documents, now,
                                                    scope=scope) is not True:
                        raise ValueError('AUTO_PUBLICATION_INDEPENDENT_REPLAY_REFUSED')
                    # Continuity must survive the external financial auditor.
                    if (replay_lease.check(strict(body(cut)), now) is not True
                            or ack_lease.check(p['ack_id'], digest(p), now) is not True
                            or publication_lease.check(strict(body(p)), now) is not True):
                        raise ValueError('AUTO_PUBLICATION_CONTINUITY_LOST')
                    return True
