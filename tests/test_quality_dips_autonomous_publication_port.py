"""Injected authority-port contract tests, not operational acceptance."""
import copy
from contextlib import contextmanager
from types import SimpleNamespace
import pytest
from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_publication_port import BoundAutonomousFinancialPublication
from test_quality_dips_autonomous_publication_binding import sample


class Lease:
    def __init__(self, snapshot, check):
        self.snapshot, self._check = snapshot, check

    def check(self, *args):
        return self._check(*args)


class Port:
    def __init__(self, snapshot, check):
        self.snapshot, self.check = snapshot, check

    @contextmanager
    def lease(self, *args, **kwargs):
        yield Lease(copy.deepcopy(self.snapshot), self.check)


class Replay(Port):
    def verify(self, *args, **kwargs):
        return True


def setup():
    e, p, cut, docs = sample()
    cut['scope'] = 'LOCAL_ENROLLED'
    publication = Port(p, lambda snapshot, now: snapshot == p)
    ack = Port(None, lambda ack_id, publication_digest, now:
               ack_id == p['ack_id'] and publication_digest == digest(p))
    replay = Replay(cut, lambda snapshot, now: snapshot == cut)
    return e, p, cut, docs, publication, ack, replay


def test_rejects_missing_independent_ports():
    with pytest.raises(ValueError):
        BoundAutonomousFinancialPublication()


def test_synthetic_injected_lease_path_requires_all_checks():
    e, p, cut, docs, publication, ack, replay = setup()
    port = BoundAutonomousFinancialPublication(publication=publication, custody_ack=ack,
                                                financial_replay=replay)
    assert port.verify_cut(e, {'scope': 'LOCAL_ENROLLED', 'financial_digest': digest(cut)}, docs, 1000,
                           scope='LOCAL_ENROLLED') is True


@pytest.mark.parametrize('damage', ['disposable_scope', 'bad_clock', 'publisher_refusal',
    'ack_refusal', 'cut_refusal', 'replay_refusal', 'financial_mismatch', 'current_scope', 'missing_financial_digest', 'wrong_financial_digest'])
def test_publication_port_refuses_without_all_evidence(damage):
    e, p, cut, docs, publication, ack, replay = setup()
    scope, now, current = 'LOCAL_ENROLLED', 1000, {'scope': 'LOCAL_ENROLLED', 'financial_digest': digest(cut)}
    if damage == 'disposable_scope': scope = 'DISPOSABLE_TEST'
    if damage == 'bad_clock': now = True
    if damage == 'publisher_refusal': publication.check = lambda *a: False
    if damage == 'ack_refusal': ack.check = lambda *a: False
    if damage == 'cut_refusal': replay.check = lambda *a: False
    if damage == 'replay_refusal': replay.verify = lambda *a, **k: False
    if damage == 'financial_mismatch': docs['projection']['projection.json']['state']['cash'] = '999'
    if damage == 'current_scope': current['scope'] = 'DISPOSABLE_TEST'
    if damage == 'missing_financial_digest': current.pop('financial_digest')
    if damage == 'wrong_financial_digest': current['financial_digest'] = 'f' * 64
    port = BoundAutonomousFinancialPublication(publication=publication, custody_ack=ack,
                                                financial_replay=replay)
    with pytest.raises(ValueError):
        port.verify_cut(e, current, docs, now, scope=scope)

@pytest.mark.parametrize('damage', ['publication_revoked', 'ack_revoked', 'cut_revoked',
    'publication_replaced', 'cut_replaced'])
def test_publication_authority_continuity_refuses_mid_audit_revocation(damage):
    """Lease state changes during financial replay must never yield acceptance."""
    e, p, cut, docs, publication, ack, replay = setup()
    valid = {'publication': True, 'ack': True, 'cut': True}
    publication.check = lambda snapshot, now: valid['publication'] and snapshot == p
    ack.check = lambda ack_id, publication_digest, now: (
        valid['ack'] and ack_id == p['ack_id'] and publication_digest == digest(p))
    replay.check = lambda snapshot, now: valid['cut'] and snapshot == cut

    def audit(*args, **kwargs):
        if damage == 'publication_revoked': valid['publication'] = False
        if damage == 'ack_revoked': valid['ack'] = False
        if damage == 'cut_revoked': valid['cut'] = False
        if damage == 'publication_replaced': p['ack_id'] = 'REPLACED'
        if damage == 'cut_replaced': cut['scope'] = 'REPLACED'
        return True

    replay.verify = audit
    port = BoundAutonomousFinancialPublication(publication=publication, custody_ack=ack,
                                                financial_replay=replay)
    with pytest.raises(ValueError):
        port.verify_cut(e, {'scope': 'LOCAL_ENROLLED', 'financial_digest': digest(cut)}, docs, 1000,
                        scope='LOCAL_ENROLLED')


@pytest.mark.parametrize('foreign_scope', ['DISPOSABLE_TEST', 'OTHER', None])
def test_operational_publication_refuses_disposable_or_foreign_cut(foreign_scope):
    e, p, cut, docs, publication, ack, replay = setup()
    cut['scope'] = foreign_scope
    replay.snapshot = copy.deepcopy(cut)
    current = {'scope': 'LOCAL_ENROLLED', 'financial_digest': digest(cut)}
    port = BoundAutonomousFinancialPublication(publication=publication, custody_ack=ack,
                                                financial_replay=replay)
    with pytest.raises(ValueError, match='AUTO_PUBLICATION_FINANCIAL_CUT_SCOPE_MISMATCH'):
        port.verify_cut(e, current, docs, 1000, scope='LOCAL_ENROLLED')


@pytest.mark.parametrize('damage', ['financial_digest_replaced', 'financial_digest_removed',
    'scope_replaced', 'scope_removed'])
def test_publication_refuses_current_evidence_replacement_during_audit(damage):
    e, p, cut, docs, publication, ack, replay = setup()
    current = {'scope': 'LOCAL_ENROLLED', 'financial_digest': digest(cut)}

    def audit(*args, **kwargs):
        if damage == 'financial_digest_replaced': current['financial_digest'] = 'f' * 64
        if damage == 'financial_digest_removed': current.pop('financial_digest')
        if damage == 'scope_replaced': current['scope'] = 'DISPOSABLE_TEST'
        if damage == 'scope_removed': current.pop('scope')
        return True

    replay.verify = audit
    port = BoundAutonomousFinancialPublication(publication=publication, custody_ack=ack,
                                                financial_replay=replay)
    with pytest.raises(ValueError, match='AUTO_PUBLICATION_CURRENT_CONTINUITY_LOST'):
        port.verify_cut(e, current, docs, 1000, scope='LOCAL_ENROLLED')
