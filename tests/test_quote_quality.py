import asyncio
import copy
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from app.investment.offline_research import ResearchInputRefused
from test_market_replay_integration import quote_fixture

from scripts.observation_runtime.market_replay import ReplayStore, create_replay_app
from scripts.observation_runtime.quote_quality import quote_quality


def populate(store,now):
    for symbol,age,delay,receipt_offset in [('SPY',10,0,0),('QQQ',60,0,0),('IWM',5,15,0),
                                         ('DIA',300,15,0),('FUTURE',1,0,10)]:
        payload=quote_fixture(now-timedelta(seconds=age))
        payload['quoteResponse']['result'][0].update(symbol=symbol,exchangeDataDelayedBy=delay)
        store.ingest_quote(payload,observed_at=now+timedelta(seconds=receipt_offset),asset_class='US_ETF')
    return ['SPY','QQQ','IWM','DIA','FUTURE','MISSING']


def test_actual_quote_snapshot_states_and_staleness_remain_independent():
    now=datetime(2026,10,20,14,0,10,tzinfo=UTC)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);symbols=populate(store,now)
        rows=store.quote_snapshot(symbols,now=now);before=copy.deepcopy(rows)
        report=quote_quality(rows,now=now)
        by_symbol={row['symbol']:row for row in report['rows']}
        assert by_symbol['SPY']['status']=='FRESH'
        assert by_symbol['QQQ']['status']=='STALE'
        assert by_symbol['DIA']['status']=='DELAYED' and by_symbol['DIA']['event_stale_at_report_clock'] is True
        assert by_symbol['IWM']['status']=='DELAYED' and by_symbol['IWM']['event_stale_at_report_clock'] is False
        assert by_symbol['FUTURE']['event_time'] is None
        assert by_symbol['MISSING']['event_stale_at_report_clock'] is None
        assert report['status_counts']=={'FRESH':1,'STALE':1,'DELAYED':2,'UNAVAILABLE':1,'NOT_YET_OBSERVED':1}
        assert all('price' not in row for row in report['rows'])
        assert rows==before


@pytest.mark.parametrize('fault',['receipt','age','delay','price','authority','duplicate','unavailable_leak'])
def test_quote_quality_refuses_contradictions(fault):
    now=datetime(2026,10,20,14,0,10,tzinfo=UTC)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);symbols=populate(store,now);rows=store.quote_snapshot(symbols,now=now)
        fresh=next(row for row in rows if row['symbol']=='SPY')
        if fault=='receipt':fresh['observed_at']=(now+timedelta(seconds=1)).isoformat()
        elif fault=='age':fresh['age_seconds']=-1
        elif fault=='delay':fresh['provider_delay_unit']='SECONDS'
        elif fault=='price':fresh['price']=True
        elif fault=='authority':fresh['startup_authorized']=True
        elif fault=='duplicate':rows.append(copy.deepcopy(fresh))
        else:next(row for row in rows if row['symbol']=='MISSING')['timestamp']=now.isoformat()
        with pytest.raises(ResearchInputRefused):quote_quality(rows,now=now)


def test_winter_after_hours_and_closed_session_are_distinct():
    now=datetime(2026,11,3,0,0,10,tzinfo=UTC)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);symbols=populate(store,now)
        report=quote_quality(store.quote_snapshot(symbols,now=now),now=now)
        assert report['current_market_session']=='AFTER_HOURS'
        later=now.replace(hour=2)
        report=quote_quality(store.quote_snapshot(symbols,now=later),now=later)
        assert report['current_market_session']=='CLOSED'
        assert report['status_counts']['FRESH']==0


def test_actual_quote_quality_api_and_html():
    now=datetime(2026,10,20,14,0,10,tzinfo=UTC)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);symbols=populate(store,now)
        expected=quote_quality(store.quote_snapshot(symbols,now=now),now=now)
        app=create_replay_app(store,symbols=symbols,clock=lambda:now)
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
                response=await client.get('/api/market-data/quote-quality')
                assert response.json()==expected and response.headers['cache-control']=='no-store'
                assert response.json()==json.loads((Path(__file__).parent/'fixtures/market-replay-v1/quote-quality.json').read_bytes())
                page=await client.get('/quote-quality')
                assert page.status_code==200 and 'unverified units' in page.text
                assert (await client.post('/api/market-data/quote-quality')).status_code==405
        asyncio.run(check())


@pytest.mark.parametrize('stamp,session',[
    ('2026-10-20T12:01:10+00:00','PRE_MARKET'),('2026-10-20T14:01:10+00:00','REGULAR'),
    ('2026-10-20T21:01:10+00:00','AFTER_HOURS'),('2026-11-27T18:01:10+00:00','AFTER_HOURS')])
def test_quote_quality_across_sessions_and_early_close(stamp,session):
    now=datetime.fromisoformat(stamp)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db)
        store.ingest_quote(quote_fixture(now-timedelta(seconds=10)),observed_at=now,asset_class='US_ETF')
        result=quote_quality(store.quote_snapshot(['SPY'],now=now),now=now)
        assert result['current_market_session']==session
        assert result['status_counts']['FRESH']==1
        assert result['provider_service_health']=='NOT_OBSERVED'


def test_closed_weekend_missing_evidence_is_not_provider_down():
    now=datetime(2026,10,24,14,tzinfo=UTC)
    result=quote_quality([{'symbol':'SPY','status':'UNAVAILABLE','price':None}],now=now)
    assert result['current_market_session']=='CLOSED'
    assert result['provider_service_health']=='NOT_OBSERVED'


def test_unverified_calendar_horizon_refuses_quote_quality():
    with pytest.raises(ResearchInputRefused):
        quote_quality([{'symbol':'SPY','status':'UNAVAILABLE','price':None}],now=datetime(2030,10,20,tzinfo=UTC))
