"""Native Windows history-to-publisher/custodian injected witness integration."""
import pytest
from app.services.quality_dips_autonomous_v4_native_witness_reader_proposal import inspect_proposed_v4_native_witness
from test_quality_dips_autonomous_v4_native_history_reader_proposal import ConfinedReader, native_proposal
from test_quality_dips_autonomous_v4_publication_proposal import publication_case


class Publisher:
    def __init__(self): self.calls = 0
    def verify_publication(self, *args):
        self.calls += 1
        return True


class Custodian:
    def __init__(self): self.calls = 0
    def verify_acknowledgment(self, *args):
        self.calls += 1
        return True


def check(fixture, publisher=None, custodian=None, reader=None):
    _, _, _, publication, acknowledgment = publication_case()
    p = publisher if publisher is not None else Publisher()
    c = custodian if custodian is not None else Custodian()
    result = inspect_proposed_v4_native_witness(reader or ConfinedReader(fixture), fixture[3],
        fixture[4], publication, acknowledgment, p, c, 1000)
    return result, p, c


def test_native_witness_checks_revalidate_full_history_twice(native_proposal):
    result, p, c = check(native_proposal)
    assert p.calls == c.calls == 2
    assert result['external_witness_checks_passed'] is True
    assert result['independent_custody_verified'] is False
    assert result['independent_publication_verified'] is False
    assert result['paper_execution_authorized'] is False


@pytest.mark.parametrize('attack', ['same_port', 'missing_port', 'publisher_denied',
    'custodian_denied', 'publisher_revoked', 'custodian_revoked',
    'native_event_changed', 'native_assertion_changed', 'native_removed',
    'native_added', 'native_changed_after_witness', 'native_changed_after_second_witness'])
def test_native_witness_refuses_denial_revocation_or_native_mutation(native_proposal, attack):
    p, c = Publisher(), Custodian()
    reader = ConfinedReader(native_proposal)
    source = reader.root / 'source'
    if attack == 'same_port': c = p
    if attack == 'missing_port': p.verify_publication = None
    if attack == 'publisher_denied': p.verify_publication = lambda *args: False
    if attack == 'custodian_denied': c.verify_acknowledgment = lambda *args: False
    if attack == 'publisher_revoked':
        def revoke_p(*args):
            p.calls += 1
            return p.calls == 1
        p.verify_publication = revoke_p
    if attack == 'custodian_revoked':
        def revoke_c(*args):
            c.calls += 1
            return c.calls == 1
        c.verify_acknowledgment = revoke_c
    if attack == 'native_event_changed': (source / '0002-event.json').write_bytes(b'{}')
    if attack == 'native_assertion_changed': (source / 'assertion.json').write_bytes(b'{}')
    if attack == 'native_removed': (source / '0002-event.json').unlink()
    if attack == 'native_added': (source / 'unexpected.json').write_bytes(b'{}')
    if attack.startswith('native_changed_after_'):
        original = c.verify_acknowledgment
        def mutate(*args):
            result = original(*args)
            if c.calls == (1 if attack == 'native_changed_after_witness' else 2):
                (source / '0002-event.json').write_bytes(b'{}')
            return result
        c.verify_acknowledgment = mutate
    with pytest.raises((ValueError, OSError, AttributeError)):
        check(native_proposal, p, c, reader)