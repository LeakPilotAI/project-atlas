"""External witness boundary remains non-authorizing even with passing test doubles."""
import copy
import pytest
from app.services.quality_dips_autonomous_v4_witness_boundary_proposal import ProposedV4WitnessBoundary
from test_quality_dips_autonomous_v4_publication_proposal import publication_case


class Publisher:
    def __init__(self): self.calls = 0
    def verify_publication(self, digest, publication_id, now):
        self.calls += 1
        return True


class Custodian:
    def __init__(self): self.calls = 0
    def verify_acknowledgment(self, ack_digest, pub_digest, ack_id, now):
        self.calls += 1
        return True


def test_external_witness_boundary_requires_distinct_ports():
    with pytest.raises(ValueError): ProposedV4WitnessBoundary()
    with pytest.raises(ValueError): ProposedV4WitnessBoundary(publisher=Publisher())
    with pytest.raises(ValueError): ProposedV4WitnessBoundary(publisher=Publisher(), custodian=object())
    p = Publisher()
    with pytest.raises(ValueError): ProposedV4WitnessBoundary(publisher=p, custodian=p)


def test_external_witness_checks_do_not_grant_operational_authority():
    p, c = Publisher(), Custodian()
    boundary = ProposedV4WitnessBoundary(publisher=p, custodian=c)
    result = boundary.inspect(*publication_case(), 1000)
    assert p.calls == c.calls == 2
    assert result['external_witness_checks_passed'] is True
    assert result['independent_custody_verified'] is False
    assert result['independent_publication_verified'] is False
    assert result['operational_authority_accepted'] is False
    assert result['paper_execution_authorized'] is False
    assert result['live_order_authorized'] is False


@pytest.mark.parametrize('damage', ['bad_clock', 'publisher_denied', 'custodian_denied',
    'publisher_revoked', 'custodian_revoked', 'publisher_mutated', 'custodian_mutated'])
def test_external_witness_boundary_fails_closed(damage):
    e, events, assertion, pub, ack = publication_case()
    p, c = Publisher(), Custodian()
    if damage == 'publisher_denied': p.verify_publication = lambda *a: False
    if damage == 'custodian_denied': c.verify_acknowledgment = lambda *a: False
    if damage == 'publisher_revoked':
        p.verify_publication = lambda *a: setattr(p, 'calls', p.calls + 1) or p.calls == 1
    if damage == 'custodian_revoked':
        c.verify_acknowledgment = lambda *a: setattr(c, 'calls', c.calls + 1) or c.calls == 1
    if damage == 'publisher_mutated':
        def mutate_p(*a):
            pub['head'] = 'f' * 64
            return True
        p.verify_publication = mutate_p
    if damage == 'custodian_mutated':
        def mutate_c(*a):
            ack['ack_id'] = 'REPLACED'
            return True
        c.verify_acknowledgment = mutate_c
    boundary = ProposedV4WitnessBoundary(publisher=p, custodian=c)
    with pytest.raises(ValueError):
        boundary.inspect(e, events, assertion, pub, ack, False if damage == 'bad_clock' else 1000)


def test_external_witness_inspection_preserves_inputs():
    inputs = publication_case()
    before = copy.deepcopy(inputs)
    ProposedV4WitnessBoundary(publisher=Publisher(), custodian=Custodian()).inspect(*inputs, 1000)
    assert inputs == before