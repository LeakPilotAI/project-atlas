"""Both actual planners/observers/native writers fed by original source publishers."""
import os
from pathlib import Path

import pytest
from app.adapters.hyperliquid import _paper_funding_observation
from source_publication_native_fixture import Publications
from test_unified_actual_native_lanes import cycle
from unified_actual_lanes_fixture import build


@pytest.fixture
def system(tmp_path):
    conf=Path(os.environ['ATLAS_PERP_ORDER_TEST_ROOT']);qd=Path(os.environ['ATLAS_UNIFIED_QD_TEST_ROOT'])
    assert tmp_path.is_relative_to(conf)
    publications=Publications(tmp_path)
    s=build(tmp_path,conf,qd,publication_factory=publications.factory)
    s.r.start({'session_id':'synthetic-unified-session'})
    try:yield s,publications
    finally:s.close()


@pytest.mark.asyncio
async def test_original_source_publications_drive_both_native_lanes_and_shutdown(system):
    s,pub=system
    await cycle(s)
    assert s.q.writer._cut()['state']['revision']==1
    order=next(iter(s.p.orders.snapshot()['state']['orders'].values()))['order']
    s.tick(s.clock()+1)
    s.p.packet['maker_fills'][order['order_id']]=s.p.fill_proof(order,quantity='0.6')
    pub.publish();await cycle(s)
    assert s.p.writer._cut()['state']['revision']==1
    due=next(iter(s.p.writer._cut()['state']['positions'].values()))['next_funding']
    s.tick(due+1)
    s.p.packet['funding']['BTC']=_paper_funding_observation('BTC',[{'coin':'BTC','fundingRate':'-0.001',
        'premium':'0','time':due*1000}],due*1000,(due+3600)*1000,(due+1)*1000,(due+1)*1000)
    pub.publish()
    await s.r.poll()
    with pytest.raises(ValueError,match='HISTORICAL_ORACLE'):
        await s.r.lanes['HYPERLIQUID'].next_proposal(s.r.observations['HYPERLIQUID'])
    assert s.p.writer._cut()['state']['revision']==1
    s.p.packet['oracles'][f'BTC:{due}']={'symbol':'BTC','settlement_at':due,'price':'100',
        'source_id':'SYNTHETIC_HISTORICAL_ORACLE','revision':1}
    pub.publish();await cycle(s)
    assert s.p.writer._cut()['state']['funding']=='0.0600'
    s.tick(due+2,stock_bid='110',stock_ask='110.1',monitor={'evidence_quality':'HIGH','fundamentals_score':60},mark='100.2')
    pub.publish();await cycle(s)
    assert next(iter(s.q.writer._cut()['state']['positions'].values()))['remaining']=='0.6'
    s.tick(due+3,stock_bid='120',stock_ask='120.1',monitor={'classification':'THESIS_BROKEN'},bid='110',ask='110.1',mark='110')
    pub.publish();await cycle(s)
    assert s.r.stop()['state']=='STOPPED'
    assert s.journal.snapshot()['state']['finalized']


@pytest.mark.asyncio
async def test_source_custody_revocation_blocks_proposals_without_financial_effect(system):
    s,pub=system
    pub.ppub.authority.valid=False
    await s.r.poll()
    assert s.r.observations['HYPERLIQUID']['connection']=='UNAVAILABLE'
    assert s.p.writer._cut()['state']['revision']==0
    assert s.q.writer._cut()['state']['revision']==0
