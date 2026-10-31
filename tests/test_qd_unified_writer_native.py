"""Actual V5 coordinator behind unified durable reservation; synthetic authorities."""
import copy

import pytest
import test_qd_v5_pre_effect_native as native_fixtures
from app.services.paper_financial_replay import digest
from app.services.quality_dips_unified_writer import EnrolledQualityDipsWriter
from test_qd_v5_pre_effect_native import capture, frame

system = native_fixtures.system


class FixtureCustodyAuthority:
    def __init__(self, runtime):
        self.runtime, self.reserved = runtime, None
    def verify_components(self, binding): return binding['runtime'] is self.runtime
    def verify_cut(self, binding, cut): return cut['root'] == self.runtime.financial.store.trust.current()['root']
    def verify_frame(self, binding, value, observation, cut):
        return observation == {'connection': 'CONNECTED', 'session': 'OPEN',
                               'at': self.runtime.runtime.engine.clock(), 'frame': digest(value)}
    def verify_reservation(self, binding, proposal, reservation, cut): return self.reserved is not None and reservation == self.reserved


def writer(s):
    s.runtime.start(s.grant)
    authority = FixtureCustodyAuthority(s.runtime)
    return EnrolledQualityDipsWriter(runtime=s.runtime, authority=authority), authority


def proposed(s, w):
    f = frame(s)
    o = {'connection': 'CONNECTED', 'session': 'OPEN', 'at': s.x.x.clock(), 'frame': digest(f)}
    return w.propose(f, o), o


def test_actual_qd_writer_reserved_dispatch_uses_v5_exactly_once(system, monkeypatch):
    s = system
    w, a = writer(s)
    before = capture(s)
    p, o = proposed(s, w)
    assert capture(s) == before
    preview = w.preview(p, o)
    a.reserved = {'state': 'RESERVED', 'binding': digest(p)}
    original, calls = s.x.x.store.execute, []
    def execute(*args, **kwargs):
        calls.append(args[0]['operation_id'])
        return original(*args, **kwargs)
    monkeypatch.setattr(s.x.x.store, 'execute', execute)
    receipt = w.dispatch(p, a.reserved)
    assert receipt == preview['receipt'] and calls == [p['operation_id']]
    assert w.verify_proposal(p, o) is True
    assert s.x.n.ledger.snapshot()['revision'] == 1 and w._cut()['state']['revision'] == 1
    # Replay belongs to authenticated global custody, never a second callback.
    with pytest.raises(ValueError): w.dispatch(p, a.reserved)
    assert calls == [p['operation_id']]


@pytest.mark.parametrize('damage', ['reservation', 'frame', 'enrollment', 'command', 'source'])
def test_qd_writer_refuses_substitution_before_financial_effect(system, damage):
    s = system
    w, a = writer(s)
    p, o = proposed(s, w)
    a.reserved = {'state': 'RESERVED', 'binding': digest(p)}
    p = copy.deepcopy(p)
    before = capture(s)
    if damage == 'reservation':
        with pytest.raises(ValueError): w.dispatch(p, {'state': 'RESERVED', 'binding': 'foreign'})
    else:
        if damage == 'frame': p['frame']['sequence'] = 2
        elif damage == 'enrollment': p['enrollment_digest'] = 'f' * 64
        elif damage == 'command': p['command']['quantity'] = '0.1'
        else: p['source_head'] = 'f' * 64
        with pytest.raises(ValueError): w.verify_proposal(p, o)
    assert capture(s) == before


def test_qd_writer_cannot_ack_unknown_coordination_or_reapply_native_commit(system, monkeypatch):
    s = system
    w, a = writer(s)
    p, _ = proposed(s, w)
    a.reserved = {'state': 'RESERVED', 'binding': digest(p)}
    original, calls = s.x.x.store.execute, []
    def lose_ack(*args, **kwargs):
        original(*args, **kwargs)
        calls.append(1)
        raise OSError('SYNTHETIC_COMMIT_BEFORE_ACK')
    monkeypatch.setattr(s.x.x.store, 'execute', lose_ack)
    with pytest.raises(ValueError): w.dispatch(p, a.reserved)
    before = capture(s)
    with pytest.raises(ValueError): w.dispatch(p, a.reserved)
    assert capture(s) == before and calls == [1]


def test_qd_writer_no_default_or_foreign_runtime_authority(system):
    with pytest.raises(ValueError): EnrolledQualityDipsWriter(runtime=object(), authority=object())
    system.runtime.start(system.grant)
    with pytest.raises(ValueError): EnrolledQualityDipsWriter(runtime=system.runtime, authority=None)


def test_actual_unified_reservation_routes_to_qd_v5_and_unknown_blocks_retry(system):
    import sqlite3
    from concurrent.futures import ThreadPoolExecutor
    from decimal import Decimal

    from app.services.paper_writer_fixture import (
        _validated_operations,
        provision_fixture_writers,
    )
    from app.services.unified_paper_runtime import UnifiedPaperRuntime
    from test_unified_native_writer import FixtureCustody
    from test_unified_paper_runtime import Installation, Lane, accounts

    s = system
    w, a = writer(s)
    p, o = proposed(s, w)

    class QDCustody(FixtureCustody):
        def verify(self, request):
            if any(row[3] == 0 for row in _validated_operations(self.db)): return False
            prior = self.db.execute('SELECT acked,payload FROM writer_operations WHERE id=?',
                                    (request['proposal']['operation_id'],)).fetchone()
            if prior:
                if prior != (1, digest(request)): raise ValueError('Conflicting acknowledged request')
                return True
            self.preview = w.preview(request['proposal'], r.observations['QUALITY_DIPS'])
            self.before = self.cut(self.preview['before'], self.preview['source_head'])
            self.projected = self.cut(self.preview['after'], digest(self.preview['after']))
            return True
        def cut(self, state, head):
            rows = accounts()
            for row in rows: row['at'] = self.clock()
            target = rows[0]
            target.update(epoch=w.manifest['epoch'], head=head, revision=state['revision'])
            for ident, position in state['positions'].items():
                qty = Decimal(position['remaining'])
                if not qty: continue
                cost = qty * Decimal(position['entry'])
                target['positions'].append({'id': ident, 'instrument_id': position['symbol'], 'side': 'LONG',
                    'quantity': str(qty), 'gross_usd': str(cost), 'loss_usd': str(cost),
                    'reserved_usd': str(cost), 'derivatives': None})
            target['committed_usd'] = str(sum(Decimal(x['reserved_usd']) for x in target['positions']))
            return rows
        def reserve(self, request):
            key, payload = request['proposal']['operation_id'], digest(request)
            self.db.execute('INSERT INTO writer_operations VALUES(?,?,?,0,?)', (key, 'qd', 'fixture-incarnation', payload))
            self.db.commit()
            self.db.execute('BEGIN IMMEDIATE')
            a.reserved = {'state': 'RESERVED', 'binding': payload}
            return a.reserved

    class ActualQDLane:
        verify_proposal = w.verify_proposal
        dispatch = w.dispatch

    path = str(s.x.x.root / 'unified-fixture-writers.sqlite')
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE control(stopped INTEGER)')
        db.execute('INSERT INTO control VALUES(0)')
    provision_fixture_writers(path, {'qd': 'fixture-incarnation', 'perp': 'fixture-incarnation'})
    custody = QDCustody(path, w, a, s.x.x.clock)
    custody.policy['max_loss_usd'] = '200'  # Explicit fixture risk: entire stock notional can be lost.
    r = UnifiedPaperRuntime(lanes={'QUALITY_DIPS': ActualQDLane(), 'HYPERLIQUID': Lane('HYPERLIQUID')},
                            installation=Installation(), portfolio=custody, clock=s.x.x.clock)
    r.start({'session_id': 'synthetic-unified'})
    r.observations['QUALITY_DIPS'] = {'connection': 'CONNECTED', 'session': 'OPEN', 'at': s.x.x.clock(), **o}
    with ThreadPoolExecutor(max_workers=3) as pool:
        receipts = list(pool.map(lambda _: r.dispatch('QUALITY_DIPS', p), range(3)))
    receipt = receipts[0]
    assert receipts == [receipt] * 3
    assert r.dispatch('QUALITY_DIPS', p) == receipt and w._cut()['state']['revision'] == 1
    assert s.x.n.ledger.snapshot()['revision'] == 1
    # A second actual partial exit loses the global ACK after V5/native ACK.
    s.x.n.now[0] += 1
    f = s.x.frame(2, 'partial')
    o = {'connection': 'CONNECTED', 'session': 'OPEN', 'at': s.x.x.clock(), 'frame': digest(f)}
    p = w.propose(f, o)
    r.observations['QUALITY_DIPS'] = {'connection': 'CONNECTED', 'session': 'OPEN', 'at': s.x.x.clock(), **o}
    custody.fail_ack = True
    with pytest.raises(ValueError, match='ACKNOWLEDGEMENT_UNCERTAIN'): r.dispatch('QUALITY_DIPS', p)
    assert r.uncertain and r.state == 'STOP_INCOMPLETE' and w._cut()['state']['revision'] == 2
    before = capture(s)
    with pytest.raises(ValueError): r.dispatch('QUALITY_DIPS', p)
    assert capture(s) == before and w._cut()['state']['revision'] == 2
    restart = UnifiedPaperRuntime(lanes=r.lanes, installation=Installation(), portfolio=custody, clock=s.x.x.clock)
    with pytest.raises(ValueError, match='RESTART_UNRESOLVED'): restart.start({'session_id': 'new-synthetic'})
    assert capture(s) == before
