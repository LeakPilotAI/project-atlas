"""Actual discovery, native order custody and financial replay; synthetic providers/authority."""
import copy
import os
from pathlib import Path

import pytest
from app.adapters.hyperliquid import _paper_funding_observation
from app.services.paper_financial_replay import digest, number
from app.services.perp_resting_writer import RestingPerpWriter
from perp_order_native_fixture import build, native


@pytest.fixture
def system(tmp_path):
    root = Path(os.environ['ATLAS_PERP_ORDER_TEST_ROOT'])
    assert tmp_path.is_relative_to(root)
    s = build(tmp_path, root)
    try:
        yield s
    finally:
        s.close()


async def admitted(s):
    p = await s.planner.next_proposal(None, s.writer._cut())
    assert p['kind'] == 'RESTING_ORDER'
    s.arm(p)
    return p['order']


@pytest.mark.asyncio
async def test_real_discovery_arm_is_not_a_fill_and_queue_fill_is_once(system):
    s = system
    order = await admitted(s)
    assert s.store.verified_cut()['state']['revision'] == 0
    s.advance(3603, bid='99.6', ask='99.8', mark='99.7')
    assert await s.planner.next_proposal(None, s.writer._cut()) is None  # Touch alone never fills.
    s.advance(3604)
    s.packet['maker_fills'][order['order_id']] = s.fill_proof(order, quantity='0.6')
    p = await s.planner.next_proposal(None, s.writer._cut())
    receipt = s.dispatch(p)
    state = s.store.verified_cut()['state']
    assert state['revision'] == 1 and receipt['payload_digest'] == digest(p['command'])
    assert next(iter(state['positions'].values()))['remaining'] == '0.6'
    assert s.orders.snapshot()['state']['orders'][order['order_id']]['state'] == 'ACKNOWLEDGED'
    with pytest.raises(ValueError): s.dispatch(p)
    assert s.store.verified_cut()['state']['revision'] == 1


@pytest.mark.asyncio
async def test_actual_funding_mark_exit_are_source_bound_and_reconcile(system):
    s = system
    order = await admitted(s)
    s.advance(3604)
    s.packet['maker_fills'][order['order_id']] = s.fill_proof(order, quantity='0.6')
    s.dispatch(await s.planner.next_proposal(None, s.writer._cut()))
    s.advance(7201)
    with pytest.raises(ValueError, match='HISTORICAL_ORACLE'): await s.planner.next_proposal(None, s.writer._cut())
    s.packet['funding']['BTC'] = _paper_funding_observation('BTC', [{'coin': 'BTC', 'fundingRate': '-0.001',
        'premium': '0', 'time': 7200000}], 7200000, 10800000, 7201000, 7201000)
    s.packet['revision'] += 1
    with pytest.raises(ValueError, match='HISTORICAL_ORACLE'): await s.planner.next_proposal(None, s.writer._cut())
    s.packet['oracles']['BTC:7200'] = {'symbol': 'BTC', 'settlement_at': 7200, 'price': '100',
                                     'source_id': 'SYNTHETIC_HISTORICAL_ORACLE', 'revision': 1}
    s.packet['revision'] += 1
    p = await s.planner.next_proposal(None, s.writer._cut())
    assert p['kind'] == 'FUNDING'
    s.dispatch(p)
    assert s.store.verified_cut()['state']['funding'] == '0.0600'
    s.advance(7202, mark='100.2')
    p = await s.planner.next_proposal(None, s.writer._cut())
    assert p['kind'] == 'MARK'
    s.dispatch(p)
    s.advance(7203, bid='110', ask='110.1', mark='110')
    p = await s.planner.next_proposal(None, s.writer._cut())
    assert p['kind'] == 'EXIT'
    s.dispatch(p)
    cut = s.store.verified_cut()
    assert cut['state']['revision'] == 4 and all(number(p['remaining']) == 0 for p in cut['state']['positions'].values())
    assert number(cut['state']['cash']) == number('1000') + number(cut['state']['net'])
    assert cut['audit']['source_revision'] == 4


@pytest.mark.asyncio
@pytest.mark.parametrize('damage', ['source', 'stale', 'queue', 'trade-side', 'fraction', 'origin', 'reservation'])
async def test_no_unverified_fill_or_authority_substitution(system, damage):
    s = system
    order = await admitted(s)
    s.advance(3604)
    s.packet['maker_fills'][order['order_id']] = s.fill_proof(order, quantity='0.6')
    if damage == 'source': s.a.valid = False
    elif damage == 'stale': s.packet['observed_at'] = 3500
    elif damage == 'queue': s.packet['maker_fills'][order['order_id']]['queue_ahead'] = '100'
    elif damage == 'trade-side': s.packet['maker_fills'][order['order_id']]['trade_side'] = 'BUY'
    elif damage == 'fraction': s.packet['maker_fills'][order['order_id']]['filled_quantity'] = '0.00001'
    if damage in ('origin', 'reservation'):
        p = await s.planner.next_proposal(None, s.writer._cut())
        if damage == 'origin': p['command']['origin_ref'] = 'foreign-order'
        with pytest.raises(ValueError): s.writer.dispatch(p, {'state': 'RESERVED', 'binding': 'unaccepted'})
    else:
        with pytest.raises(ValueError): await s.planner.next_proposal(None, s.writer._cut())
    s.a.valid = True
    assert s.store.verified_cut()['state']['revision'] == 0


@pytest.mark.asyncio
async def test_lost_financial_ack_cannot_replay_or_cancel(system, monkeypatch):
    s = system
    order = await admitted(s)
    s.advance(3604)
    s.packet['maker_fills'][order['order_id']] = s.fill_proof(order, quantity='0.6')
    p = await s.planner.next_proposal(None, s.writer._cut())
    original = s.financial.dispatch
    def lose_ack(*args):
        original(*args)
        raise OSError('SYNTHETIC_NATIVE_COMMIT_BEFORE_ORDER_ACK')
    monkeypatch.setattr(s.financial, 'dispatch', lose_ack)
    with pytest.raises(OSError): s.dispatch(p)
    assert s.store.verified_cut()['state']['revision'] == 1
    assert s.orders.snapshot()['state']['orders'][order['order_id']]['state'] == 'FILL_PENDING'
    with pytest.raises(ValueError): s.dispatch(p)
    with pytest.raises(ValueError): RestingPerpWriter(financial=s.financial, orders=s.orders)
    cancel = {'operation_id': 'cancel', 'kind': 'CANCEL_RESTING_ORDER', 'order': order}
    with pytest.raises(ValueError): s.arm(cancel)


@pytest.mark.asyncio
async def test_immutable_order_retry_and_restart_no_adoption(system):
    s = system
    p = await s.planner.next_proposal(None, s.writer._cut())
    receipt = s.arm(p)
    assert s.arm(p) == receipt and s.orders.snapshot()['state']['revision'] == 1
    changed = copy.deepcopy(p)
    changed['order']['source_digest'] = 'conflicting-source'
    with pytest.raises(ValueError): s.arm(changed)
    assert s.store.verified_cut()['state']['revision'] == 0
    s.orders.close()
    reopened = native.RestingOrderStore(s.root / 'orders', trust=s.order_pins, authority=s.a, clock=s.clock,
        manifest=s.m, execution_domain='DISPOSABLE_TEST')
    try:
        assert reopened.snapshot()['state']['orders'][p['order']['order_id']]['state'] == 'RESERVED'
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_expired_order_is_cancelled_not_filled_even_with_trade_proof(system):
    s = system
    order = await admitted(s)
    s.advance(order['expires_at'])
    s.packet['maker_fills'][order['order_id']] = s.fill_proof(order, quantity='0.6')
    proposal = await s.planner.next_proposal(None, s.writer._cut())
    assert proposal['kind'] == 'CANCEL_RESTING_ORDER'
    s.arm(proposal)
    assert s.orders.snapshot()['state']['orders'][order['order_id']]['state'] == 'CANCELLED'
    assert s.store.verified_cut()['state']['revision'] == 0
