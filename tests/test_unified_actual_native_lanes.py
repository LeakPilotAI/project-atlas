"""Both real planners/writers and native global custody; all inputs/authorities synthetic."""
import asyncio
import json
import os
import time
from pathlib import Path

import pytest
from app.adapters.hyperliquid import _paper_funding_observation
from app.services.paper_financial_replay import number
from app.services.unified_paper_runtime import UnifiedPaperRuntime
from test_perp_order_crash_race_native import start
from unified_actual_lanes_fixture import build


@pytest.fixture
def system(tmp_path):
    conf = Path(os.environ['ATLAS_PERP_ORDER_TEST_ROOT'])
    qdconf = Path(os.environ['ATLAS_UNIFIED_QD_TEST_ROOT'])
    assert tmp_path.is_relative_to(conf)
    s = build(tmp_path, conf, qdconf)
    try:
        s.r.start({'session_id': 'synthetic-unified-session'})
        yield s
    finally:
        s.close()


async def cycle(s):
    await s.r.poll()
    for lane in ('QUALITY_DIPS', 'HYPERLIQUID'):
        proposal = await s.r.lanes[lane].next_proposal(s.r.observations[lane])
        if proposal is None: continue
        if proposal['kind'] == 'RESTING_ORDER': s.r.admit_resting(proposal)
        else: s.r.dispatch(lane, proposal)


@pytest.mark.asyncio
async def test_actual_two_strategy_orders_fills_funding_partial_exits_and_shutdown(system):
    s = system
    await cycle(s)
    assert s.q.writer._cut()['state']['revision'] == 1
    assert s.p.store.verified_cut()['state']['revision'] == 0
    orders = s.p.orders.snapshot()['state']['orders']
    assert len(orders) == 1
    order = next(iter(orders.values()))['order']
    s.tick(s.clock() + 1)
    s.p.packet['maker_fills'][order['order_id']] = s.p.fill_proof(order, quantity='0.6')
    await cycle(s)
    assert s.p.store.verified_cut()['state']['revision'] == 1
    at = next(iter(s.p.store.verified_cut()['state']['positions'].values()))['next_funding']
    s.tick(at + 1)
    s.p.packet['funding']['BTC'] = _paper_funding_observation('BTC', [{'coin': 'BTC', 'fundingRate': '-0.001',
        'premium': '0', 'time': at * 1000}], at * 1000, (at + 3600) * 1000, (at + 1) * 1000, (at + 1) * 1000)
    s.p.packet['oracles'][f'BTC:{at}'] = {'symbol': 'BTC', 'settlement_at': at, 'price': '100',
        'source_id': 'SYNTHETIC_HISTORICAL_ORACLE', 'revision': 1}
    await cycle(s)
    assert number(s.p.store.verified_cut()['state']['funding']) == number('.06')
    s.tick(at + 2, mark='100.2', stock_bid='110', stock_ask='110.1',
           monitor={'evidence_quality': 'HIGH', 'fundamentals_score': 60})
    await cycle(s)
    assert s.q.writer._cut()['state']['revision'] == 2
    assert s.p.store.verified_cut()['state']['revision'] == 3
    s.tick(at + 3, bid='110', ask='110.1', mark='110', stock_bid='120', stock_ask='120.1',
           monitor={'classification': 'THESIS_BROKEN'})
    await cycle(s)
    qcut, pcut = s.q.writer._cut(), s.p.store.verified_cut()
    assert qcut['state']['revision'] == 3 and pcut['state']['revision'] == 4
    assert number(qcut['state']['cash']) == number('1015.9136')
    assert number(pcut['state']['cash']) == number('1000') + number(pcut['state']['net'])
    assert s.r.snapshot()['total_cash'] is None and s.r.snapshot()['total_equity'] is None
    outcome = s.r.stop()
    assert outcome['state'] == 'STOPPED', outcome
    assert s.journal.snapshot()['state']['finalized']['outcomes'] == outcome['lanes']
    assert all(row['state'] == 'ACKNOWLEDGED' for row in s.journal.snapshot()['state']['operations'].values())
    assert s.r.stop() == outcome


@pytest.mark.asyncio
async def test_continuous_two_real_planners_no_duplicate_entry_and_pause(system):
    s = system
    await s.r.run(seconds=.3, interval=.05)
    assert s.r.state == 'PAUSED'
    assert s.q.writer._cut()['state']['revision'] == 1
    assert s.p.store.verified_cut()['state']['revision'] == 0
    assert len(s.p.orders.snapshot()['state']['orders']) == 1
    assert s.r.stop()['state'] == 'STOPPED'  # Cancels the actual unfilled order through global custody.


@pytest.mark.asyncio
async def test_global_native_ack_loss_refuses_replay_and_restart(system):
    s = system
    await s.r.poll()
    p = await s.r.lanes['QUALITY_DIPS'].next_proposal(s.r.observations['QUALITY_DIPS'])
    s.a.fail_ack = True
    with pytest.raises(OSError): s.r.dispatch('QUALITY_DIPS', p)
    assert s.r.uncertain and s.r.state == 'STOP_INCOMPLETE'
    assert s.q.writer._cut()['state']['revision'] == 1
    with pytest.raises(ValueError): s.r.dispatch('QUALITY_DIPS', p)
    assert s.custody.verify_restart({'session_id': 'synthetic-unified-session'}) is False


@pytest.mark.asyncio
async def test_real_child_crash_after_native_fill_before_order_and_global_ack(system):
    s = system
    await cycle(s)
    order = next(iter(s.p.orders.snapshot()['state']['orders'].values()))['order']
    s.tick(s.clock() + 1)
    s.p.packet['maker_fills'][order['order_id']] = s.p.fill_proof(order, quantity='0.6')
    await s.r.poll()
    proposal = await s.plane.next_proposal(s.r.observations['HYPERLIQUID'])
    request = {'lane': 'HYPERLIQUID', 'grant': s.r.grant, 'proposal': proposal}
    config = {'confinement': str(s.confinement), 'portfolio': True, 'root': str(s.root / 'global'),
        'pin': str(s.pins.path), 'now': s.clock(), 'manifest': s.binding,
        'event': {'kind': 'RESERVE', 'order_id': proposal['operation_id'], 'at': s.clock(), 'payload': request},
        'reservation': {'fixture': 'EXPLICIT_SELF_EXIT_BOUNDARY'},
        'financial': {'root': str(s.p.root / 'source'), 'projection': str(s.p.root / 'projection'),
            'projection_id': s.p.projection_id, 'pin': str(s.p.financial_pins.path), 'command': proposal['command']},
        'orders': {'root': str(s.p.root / 'orders'), 'pin': str(s.p.order_pins.path), 'manifest': s.p.m}}
    path = s.root / 'two-lane-crash-config.json'; path.write_text(json.dumps(config))
    child = start(path, 'financial-after-ack')
    stdout, stderr = child.communicate(timeout=12)
    assert child.returncode == 71, (stdout, stderr)
    assert s.p.store.verified_cut()['state']['revision'] == 1
    assert any(row['state'] == 'FILL_PENDING' for row in s.p.orders.snapshot()['state']['orders'].values())
    assert any(row['state'] == 'RESERVED' for row in s.journal.snapshot()['state']['operations'].values())
    before = s.p.store.verified_cut()
    with pytest.raises(ValueError): s.r.dispatch('HYPERLIQUID', proposal)
    restart = UnifiedPaperRuntime(lanes=s.r.lanes, installation=s.r.installation, portfolio=s.custody, clock=s.clock)
    with pytest.raises(ValueError): restart.start({'session_id': 'synthetic-unified-session'})
    assert s.p.store.verified_cut() == before and s.q.writer._cut()['state']['revision'] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('damage', ['rollback', 'same-revision-conflict', 'missing-monitor'])
async def test_actual_qd_scanner_publication_refuses_incomplete_source(system, damage):
    s = system
    await cycle(s)
    before = s.q.writer._cut()
    if damage == 'rollback': s.q_packet['revision'] = 0
    elif damage == 'same-revision-conflict': s.q_packet['source_id'] = 'substituted-source'
    else:
        s.q_packet['revision'] += 1
        s.q_packet['bundles'] = []
        s.q_packet['monitors'] = {}
    with pytest.raises(ValueError):
        s.reader.read_request(timeout=.2)
    assert s.q.writer._cut() == before


@pytest.mark.asyncio
async def test_actual_native_global_reservation_race_is_one_pending_effect(system):
    s = system
    await s.r.poll()
    proposal = await s.qlane.next_proposal(s.r.observations['QUALITY_DIPS'])
    request = {'lane': 'QUALITY_DIPS', 'grant': s.r.grant, 'proposal': proposal}
    barrier, children = s.root / 'global-go', []
    for index in range(2):
        path, ready = s.root / f'global-race-{index}.json', s.root / f'global-ready-{index}'
        path.write_text(json.dumps({'confinement': str(s.confinement), 'portfolio': True,
            'root': str(s.root / 'global'), 'pin': str(s.pins.path), 'now': s.clock(), 'manifest': s.binding,
            'event': {'kind': 'RESERVE', 'order_id': proposal['operation_id'], 'at': s.clock(), 'payload': request},
            'reservation': {'fixture': 'SYNTHETIC_RACE'}, 'barrier': str(barrier), 'ready': str(ready)}))
        children.append((start(path, 'none'), ready))
    deadline = time.monotonic() + 8
    while not all(ready.exists() for _, ready in children):
        if time.monotonic() >= deadline: raise AssertionError('Global custody children did not become ready')
        await asyncio.sleep(.01)
    barrier.write_text('GO')
    replies = []
    for child, _ in children:
        stdout, stderr = child.communicate(timeout=12)
        assert child.returncode == 0, stderr
        replies.append(json.loads(stdout))
    assert replies[0] == replies[1]
    assert len(s.journal.snapshot()['state']['operations']) == 1
    assert s.q.writer._cut()['state']['revision'] == 0
    assert s.custody.verify_restart({'session_id': 'synthetic-unified-session'}) is False


@pytest.mark.asyncio
@pytest.mark.parametrize('lane', ['QUALITY_DIPS', 'HYPERLIQUID'])
async def test_new_session_grant_cannot_adopt_open_or_resting_exposure(system, lane):
    s = system
    await s.r.poll()
    proposal = await s.r.lanes[lane].next_proposal(s.r.observations[lane])
    if lane == 'QUALITY_DIPS': s.r.dispatch(lane, proposal)
    else: s.r.admit_resting(proposal)
    assert s.custody.close_entry_admission(s.r.grant)
    s.a.verify_session = lambda *args: True  # Explicit new fixture grant, NOT recovery acceptance.
    before = s.journal.snapshot()
    assert s.custody.verify_restart({'session_id': 'different-synthetic-session'}) is False
    assert s.journal.snapshot() == before


@pytest.mark.asyncio
async def test_missing_global_final_publication_refuses_clean_shutdown_and_new_session(system):
    s = system
    await cycle(s)
    original = s.a.event_authorization
    def failure(kind, *args):
        if kind == 'FINAL': raise OSError('SYNTHETIC_GLOBAL_FINAL_PUBLICATION_FAILURE')
        return original(kind, *args)
    s.a.event_authorization = failure
    outcome = s.r.stop()
    assert outcome['state'] == 'STOP_INCOMPLETE'
    assert s.journal.snapshot()['state']['finalized'] is None
    assert all(number(p['remaining']) == 0 for p in s.q.writer._cut()['state']['positions'].values())
    s.a.verify_session = lambda *args: True
    assert s.custody.verify_restart({'session_id': 'another-synthetic-session'}) is False
    assert s.r.stop() == outcome
