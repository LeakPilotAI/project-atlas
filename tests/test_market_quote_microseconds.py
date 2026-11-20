"""Quote-quality microseconds and unavailable/future states through real fixture API."""
import asyncio
import json
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from app.investment.offline_research import equity_session

from scripts.observation_runtime.market_replay import ReplayStore, create_replay_app


def add(store,symbol,event,receipt,delay=0):
    prefix={'PRE_MARKET':'preMarket','REGULAR':'regularMarket','AFTER_HOURS':'postMarket'}[equity_session(receipt)]
    store.ingest_quote({'quoteResponse':{'error':None,'result':[{'symbol':symbol,'currency':'USD',
        prefix+'Time':int(event.timestamp()),prefix+'Price':100,'exchangeDataDelayedBy':delay}]}},observed_at=receipt,asset_class='US_ETF')


def read(store,now,symbols):
    app=create_replay_app(store,symbols=symbols,clock=lambda:now)
    async def response():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://in-process.invalid') as client:
            value=await client.get('/api/market-data/quote-quality')
            assert value.status_code==200
            assert value.headers['cache-control']=='no-store'
            return value.json()
    return asyncio.run(response())


def browser(report,tmp_path):
    path=tmp_path/'quality.json'
    path.write_text(json.dumps(report),encoding='utf-8')
    view=Path(__file__).resolve().parents[1]/'frontend/offline/market-replay/view.cjs'
    code="const fs=require('node:fs');const api=require(process.argv[1]);const v=api.parseQuoteQuality(fs.readFileSync(process.argv[2],'utf8'));if(v.network_authorized!==false||v.provider_freshness_verified!==false)throw Error('authority');"
    result=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',code,str(view),str(path)],capture_output=True,text=True,timeout=20,check=False)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('micros',[0,1,99,100,999,123456,999999])
@pytest.mark.parametrize('hour,session',[(12,'PRE_MARKET'),(14,'REGULAR'),(21,'AFTER_HOURS')])
def test_actual_quote_quality_all_states_with_microsecond_receipts(tmp_path,micros,hour,session):
    base=datetime(2026,10,20,hour,0,10,tzinfo=UTC)
    now=base+timedelta(microseconds=micros)
    path=tmp_path/'fixture.sqlite'
    with sqlite3.connect(path) as connection:
        store=ReplayStore(connection)
        for symbol,seconds,delay in [('SPY',10,0),('QQQ',60,0),('IWM',5,15),('DIA',300,15)]:
            add(store,symbol,base-timedelta(seconds=seconds),now,delay)
        add(store,'FUTURE',base-timedelta(seconds=1),now+timedelta(microseconds=1))
    with sqlite3.connect(path) as connection:
        store=ReplayStore(connection)
        before=connection.execute('SELECT * FROM replay_quotes ORDER BY symbol').fetchall()
        report=read(store,now,['SPY','QQQ','IWM','DIA','FUTURE','MISSING'])
        rows={r['symbol']:r for r in report['rows']}
        assert report['current_market_session']==session
        assert report['status_counts']=={'FRESH':1,'STALE':1,'DELAYED':2,'UNAVAILABLE':1,'NOT_YET_OBSERVED':1}
        assert rows['SPY']['event_age_seconds']==(10000000+micros)/1000000
        assert rows['SPY']['receipt_delay_seconds']==(10000000+micros)/1000000
        assert rows['SPY']['receipt_time']==now.isoformat()
        assert rows['FUTURE']['receipt_time'] is None
        assert rows['FUTURE']['event_time'] is None
        assert rows['DIA']['event_stale_at_report_clock'] is True
        assert rows['IWM']['event_stale_at_report_clock'] is False
        assert report['provider_service_health']=='NOT_OBSERVED'
        assert connection.execute('SELECT * FROM replay_quotes ORDER BY symbol').fetchall()==before
    browser(report,tmp_path)


@pytest.mark.parametrize('micros,status',[(0,'FRESH'),(1,'STALE')])
def test_actual_quality_ttl_boundary_is_exact(tmp_path,micros,status):
    event=datetime(2026,10,20,14,tzinfo=UTC)
    now=event+timedelta(seconds=30,microseconds=micros)
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store=ReplayStore(connection)
        add(store,'SPY',event,now)
        report=read(store,now,['SPY'])
        assert report['rows'][0]['status']==status
        assert report['rows'][0]['event_age_seconds']==(30000000+micros)/1000000
    browser(report,tmp_path)
