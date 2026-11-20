import asyncio
import copy
import json
import sqlite3
import subprocess
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

import httpx
import pytest
from app.investment.market_hours import session_bounds
from app.investment.offline_research import ET, previous_session

from scripts.observation_runtime.market_replay import ReplayStore, create_replay_app
from scripts.observation_runtime.retained_research import retained_research


def chart(stamps, *, current=False, price=None):
    closes=[101,102,103] if current else [100]*len(stamps)
    if price is not None:closes=[price]*len(stamps)
    return {'chart':{'error':None,'result':[{'meta':{'symbol':'SPY','currency':'USD','dataGranularity':'1m'},
      'timestamp':[int(stamp.timestamp()) for stamp in stamps],
      'indicators':{'quote':[{'open':[100]*len(stamps),'high':[max(105,max(closes))]*len(stamps),
                            'low':[99]*len(stamps),'close':closes,'volume':[200 if current else 100]*len(stamps)}]}}]}}


def reference(now):
    day=previous_session(now.astimezone(ET).date())
    closing=session_bounds(datetime.combine(day,time(12),ET))[1]
    return {'symbol':'SPY','previous_close':100,'previous_session_date':day.isoformat(),'source':'SYNTHETIC_REFERENCE',
            'available_at':(closing+timedelta(minutes=1)).isoformat(),'currency':'USD','asset_class':'US_ETF','data_mode':'SYNTHETIC_REPLAY'}


def populate(store, *, baseline=True, future_baseline=False):
    now=datetime(2026,10,20,13,33,10,tzinfo=UTC)
    if baseline:
        for day in (13,14,15,16,19):
            first=datetime(2026,10,day,13,30,tzinfo=UTC)
            receipt=now+timedelta(seconds=10) if future_baseline and day==19 else first+timedelta(minutes=3,seconds=10)
            store.ingest(chart([first+timedelta(minutes=i) for i in range(3)]),observed_at=receipt,asset_class='US_ETF')
    first=now.replace(minute=30,second=0)
    store.ingest(chart([first+timedelta(minutes=i) for i in range(3)],current=True),observed_at=now,asset_class='US_ETF')
    return now,reference(now)


def test_actual_retained_history_to_existing_analysis_no_fake_volume_or_authority():
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);now,ref=populate(store)
        history=store.history('SPY',now=now);before=copy.deepcopy(history)
        result=retained_research(history,ref,now=now)
        analysis=result['analysis']
        assert analysis['observed_change_percent']==3
        assert analysis['session_momentum_percent']==1.98
        assert analysis['relative_volume']==2 and analysis['baseline_sessions']==5
        assert analysis['volume_window_completed_minutes']==2
        assert result['sessions'][0]['observed_volume'] is None
        assert result['sessions'][1]['observed_volume']==600
        assert result['sessions'][2]['observed_volume'] is None
        assert result['trading_authorized'] is False and result['corporate_actions_reconciled'] is False
        assert history==before


def test_insufficient_baseline_remains_unknown():
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);now,ref=populate(store,baseline=False)
        result=retained_research(store.history('SPY',now=now),ref,now=now)
        assert result['analysis']['relative_volume'] is None
        assert result['analysis']['relative_volume_status']=='BASELINE_REQUIRED'


def test_historical_baseline_not_received_at_decision_is_excluded():
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);now,ref=populate(store,future_baseline=True)
        result=retained_research(store.history('SPY',now=now),ref,now=now)
        assert result['analysis']['relative_volume'] is None
        assert result['analysis']['baseline_sessions']==4
        assert result['analysis']['relative_volume_status']=='BASELINE_INSUFFICIENT'


@pytest.mark.parametrize('fault',['future_ref','before_close','wrong_session','scalar','source','authority','duplicate','stale'])
def test_reference_and_vintage_refusals(fault):
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);now,ref=populate(store);history=store.history('SPY',now=now)
        if fault=='future_ref':ref['available_at']=(now+timedelta(seconds=1)).isoformat()
        elif fault=='before_close':ref['available_at']='2026-10-19T19:59:00+00:00'
        elif fault=='wrong_session':ref['previous_session_date']='2026-10-16'
        elif fault=='scalar':ref=100
        elif fault=='source':ref['source']='UNKNOWN'
        elif fault=='authority':ref['trading_authorized']=True
        elif fault=='duplicate':history['rows'].append(copy.deepcopy(history['rows'][-1]))
        else:now+=timedelta(minutes=5)
        with pytest.raises(ValueError):retained_research(history,ref,now=now)


def test_future_receipt_cannot_change_decision_evidence():
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);now,ref=populate(store)
        before=retained_research(store.history('SPY',now=now),ref,now=now)
        stamp=now.replace(second=0)
        store.ingest(chart([stamp],price=999),observed_at=now+timedelta(minutes=2),asset_class='US_ETF')
        after=retained_research(store.history('SPY',now=now),ref,now=now)
        assert before==after


@pytest.mark.parametrize('stamp',['2026-10-20T12:03:10+00:00','2026-10-20T21:03:10+00:00',
                                '2026-11-03T00:02:10+00:00','2026-11-27T18:03:10+00:00'])
def test_research_premarket_afterhours_and_utc_midnight(stamp):
    now=datetime.fromisoformat(stamp);first=now.replace(second=0)-timedelta(minutes=3)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db)
        store.ingest(chart([first+timedelta(minutes=i) for i in range(3)],current=True),observed_at=now,asset_class='US_ETF')
        result=retained_research(store.history('SPY',now=now),reference(now),now=now)
        assert result['status']=='DESCRIPTIVE_RESEARCH_ONLY'
        assert result['analysis']['bar_close']==103
        if result['analysis']['session']=='PRE_MARKET':
            assert result['analysis']['premarket_gap_percent']==3
            consumer=Path(__file__).resolve().parents[1]/'frontend/offline/market-replay/view.cjs'
            script="const c=require(process.argv[1]);const r=c.parseRetainedResearch(process.argv[2]);if(r.analysis.premarket_gap_percent!==3)process.exit(2);console.log('PREMARKET_RESEARCH_CONSUMER_PASS');"
            checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(consumer),json.dumps(result)],capture_output=True,text=True,timeout=10,check=True)
            assert 'PREMARKET_RESEARCH_CONSUMER_PASS' in checked.stdout


def test_api_is_reference_opt_in_and_reference_map_is_copied():
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);now,ref=populate(store)
        refs={'SPY':ref}
        app=create_replay_app(store,symbols=['SPY'],clock=lambda:now,previous_closes=refs)
        ref['previous_close']=999
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
                response=await client.get('/api/market-data/research',params={'symbol':'SPY'})
                assert response.json()['analysis']['observed_change_percent']==3
                assert response.json()==json.loads((Path(__file__).parent/'fixtures/market-replay-v1/research.json').read_bytes())
                assert response.headers['cache-control']=='no-store'
                page=await client.get('/research',params={'symbol':'SPY'})
                assert 'Not a forecast' in page.text and 'Unknown' in page.text
                assert (await client.post('/api/market-data/research',params={'symbol':'SPY'})).status_code==405
            empty=create_replay_app(store,symbols=['SPY'],clock=lambda:now)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=empty),base_url='http://fixture') as client:
                data=(await client.get('/api/market-data/research',params={'symbol':'SPY'})).json()
                assert data['status']=='INSUFFICIENT_REFERENCE' and data['analysis'] is None
        asyncio.run(check())


def test_nonfinite_derived_change_is_refused():
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);now,ref=populate(store)
        ref['previous_close']=1e-308
        with pytest.raises(ValueError,match='not finite'):
            retained_research(store.history('SPY',now=now),ref,now=now)


def test_observed_volume_cannot_overflow_portable_integer_evidence():
    now=datetime(2026,10,20,13,33,10,tzinfo=UTC)
    first=now.replace(minute=30,second=0)
    payload=chart([first+timedelta(minutes=i) for i in range(3)],current=True)
    payload['chart']['result'][0]['indicators']['quote'][0]['volume']=[2**53-1]*3
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);store.ingest(payload,observed_at=now,asset_class='US_ETF')
        with pytest.raises(ValueError,match='portable integer'):
            retained_research(store.history('SPY',now=now),reference(now),now=now)


@pytest.mark.parametrize('future',[False,True])
def test_empty_history_does_not_bypass_reference_validation(future):
    now=datetime(2026,10,20,13,33,10,tzinfo=UTC);ref=reference(now)
    with sqlite3.connect(':memory:') as db:
        history=ReplayStore(db).history('SPY',now=now)
        if future:
            ref['available_at']=(now+timedelta(seconds=1)).isoformat()
            with pytest.raises(ValueError):retained_research(history,ref,now=now)
        else:
            result=retained_research(history,ref,now=now)
            assert result['status']=='INSUFFICIENT_HISTORY' and result['analysis'] is None


def test_observed_zero_volume_is_distinct_from_unobserved_session():
    now=datetime(2026,10,20,13,33,10,tzinfo=UTC);first=now.replace(minute=30,second=0)
    payload=chart([first+timedelta(minutes=i) for i in range(3)],current=True)
    payload['chart']['result'][0]['indicators']['quote'][0]['volume']=[0]*3
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);store.ingest(payload,observed_at=now,asset_class='US_ETF')
        result=retained_research(store.history('SPY',now=now),reference(now),now=now)
        assert result['sessions'][0]['observed_volume'] is None
        assert result['sessions'][1]['observed_volume']==0 and result['sessions'][1]['observed_bar_n']==3
