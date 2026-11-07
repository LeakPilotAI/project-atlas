"""Actual retained research preserves fractional clock and reference semantics."""
import asyncio
import json
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from test_retained_research import chart, reference

from scripts.observation_runtime.market_replay import ReplayStore, create_replay_app


def request(store,now,ref):
    app=create_replay_app(store,symbols=['SPY'],clock=lambda:now,previous_closes={'SPY':ref})
    async def response():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://in-process.invalid') as client:
            result=await client.get('/api/market-data/research?symbol=SPY')
            assert result.headers['cache-control']=='no-store'
            payload=result.json()
            if payload.get('status')=='REFUSED':
                assert result.status_code==503
                assert payload['schema']=='ATLAS_MARKET_DATA_REFUSAL_V1'
                assert payload['reason']=='DATA_UNAVAILABLE'
                assert payload['rows']==[] and payload['quote_rows']==[]
            else:
                assert result.status_code==200
                assert payload['schema']=='ATLAS_RETAINED_RESEARCH_V1'
            return payload
    return asyncio.run(response())


def browser(report,tmp_path):
    path=tmp_path/'research.json'
    path.write_text(json.dumps(report),encoding='utf-8')
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/market-replay/view.cjs'
    code="const fs=require('node:fs');const api=require(process.argv[1]);const v=api.parseRetainedResearch(fs.readFileSync(process.argv[2],'utf8'));if(v.source_authenticated!==false||v.trading_authorized!==false)throw Error('authority');"
    result=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',code,str(viewer),str(path)],capture_output=True,text=True,timeout=20,check=False)
    if report.get('schema')=='ATLAS_MARKET_DATA_REFUSAL_V1':
        assert result.returncode!=0
        assert 'Research identity mismatch' in result.stderr
    else:
        assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('micros',[1,123456,999999])
@pytest.mark.parametrize('stamp,session',[
    ('2026-10-20T12:03:10+00:00','PRE_MARKET'),
    ('2026-10-20T13:33:10+00:00','REGULAR'),
    ('2026-10-20T21:03:10+00:00','AFTER_HOURS'),
    ('2026-11-03T00:02:10+00:00','AFTER_HOURS'),
    ('2026-11-27T18:03:10+00:00','AFTER_HOURS'),
    ('2026-11-02T14:33:10+00:00','REGULAR'),
])
def test_actual_fractional_research_preserves_exchange_local_reference_day(tmp_path,micros,stamp,session):
    now=datetime.fromisoformat(stamp)+timedelta(microseconds=micros)
    first=now.replace(second=0,microsecond=0)-timedelta(minutes=3)
    path=tmp_path/'fixture.sqlite'
    with sqlite3.connect(path) as connection:
        store=ReplayStore(connection)
        store.ingest(chart([first+timedelta(minutes=i) for i in range(3)],current=True),observed_at=now,asset_class='US_ETF')
    with sqlite3.connect(path) as connection:
        store=ReplayStore(connection)
        ref=reference(now)
        ref['available_at']=now.isoformat()
        before=connection.execute('SELECT * FROM replay_bars').fetchall()
        result=request(store,now,ref)
        assert result['status']=='DESCRIPTIVE_RESEARCH_ONLY'
        assert result['analysis']['session']==session
        assert result['analysis']['reference_available_at']==now.isoformat()
        assert result['analysis']['previous_session_date']==ref['previous_session_date']
        assert result['asof']==now.isoformat()
        assert connection.execute('SELECT * FROM replay_bars').fetchall()==before
    browser(result,tmp_path)


@pytest.mark.parametrize('micros,status',[(0,'DESCRIPTIVE_RESEARCH_ONLY'),(1,'REFUSED')])
def test_actual_bar_start_ttl_preserves_exact_refusal(tmp_path,micros,status):
    first=datetime(2026,10,20,13,30,tzinfo=UTC)
    receipt=first+timedelta(minutes=3,seconds=10)
    now=first+timedelta(minutes=5,microseconds=micros)
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store=ReplayStore(connection)
        store.ingest(chart([first+timedelta(minutes=i) for i in range(3)],current=True),observed_at=receipt,asset_class='US_ETF')
        result=request(store,now,reference(now))
        assert result['status']==status
        if status=='REFUSED':
            assert result['rows']==[] and result['quote_rows']==[]
    browser(result,tmp_path)


def test_reference_available_one_microsecond_later_is_not_descriptive(tmp_path):
    now=datetime(2026,10,20,13,33,10,123456,tzinfo=UTC)
    first=now.replace(minute=30,second=0,microsecond=0)
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store=ReplayStore(connection)
        store.ingest(chart([first+timedelta(minutes=i) for i in range(3)],current=True),observed_at=now,asset_class='US_ETF')
        ref=reference(now)
        ref['available_at']=(now+timedelta(microseconds=1)).isoformat()
        result=request(store,now,ref)
        assert result['status']=='REFUSED'
        assert result['rows']==[] and result['quote_rows']==[]
    browser(result,tmp_path)


def test_not_yet_completed_latest_bar_does_not_enter_research(tmp_path):
    first=datetime(2026,10,20,13,30,tzinfo=UTC)
    receipt=first+timedelta(minutes=3,seconds=10)
    now=first+timedelta(minutes=3,microseconds=-1)
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store=ReplayStore(connection)
        # Earlier completed observations are already known; newest one has a future receipt.
        store.ingest(chart([first,first+timedelta(minutes=1)]),observed_at=first+timedelta(minutes=2,seconds=10),asset_class='US_ETF')
        store.ingest(chart([first+timedelta(minutes=2)],price=999),observed_at=receipt,asset_class='US_ETF')
        result=request(store,now,reference(now))
        assert result['status']=='DESCRIPTIVE_RESEARCH_ONLY'
        assert result['analysis']['bar_timestamp']==(first+timedelta(minutes=1)).isoformat()
        assert result['analysis']['bar_close']==100
    browser(result,tmp_path)
