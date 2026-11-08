import asyncio
import copy
import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from app.investment.offline_research import ResearchInputRefused
from test_market_replay_integration import fixture
from test_r7e47s_observation_bootstrap import make_fixture

from scripts.observation_runtime.contracts import digest
from scripts.observation_runtime.market_replay import ReplayStore, create_replay_app
from scripts.observation_runtime.session_quality import session_quality


def inputs(stamp='2026-10-20T12:00:00+00:00'):
    ts=datetime.fromisoformat(stamp);now=ts+timedelta(seconds=190)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db)
        for offset in (0,2):store.ingest(fixture(ts+timedelta(minutes=offset)),observed_at=now,asset_class='US_ETF')
        return store.history('SPY',now=now),now


@pytest.mark.parametrize('stamp,session',[
    ('2026-10-20T12:00:00+00:00','PRE_MARKET'),('2026-10-20T14:00:00+00:00','REGULAR'),
    ('2026-10-20T21:00:00+00:00','AFTER_HOURS'),('2026-11-27T18:00:00+00:00','AFTER_HOURS'),
    ('2026-11-02T14:30:00+00:00','REGULAR'),('2026-11-02T23:59:00+00:00','AFTER_HOURS')])
def test_actual_history_gaps_delay_and_calendar(stamp,session):
    history,now=inputs(stamp);before=copy.deepcopy(history)
    result=session_quality(history,now=now)
    window=result['windows'][0]
    assert window['session']==session
    assert window['observed_bar_n']==2 and window['missing_minutes_between_observed_bars']==1
    assert (window['receipt_delay_min_seconds'],window['receipt_delay_max_seconds'])==(10,130)
    assert window['status']=='FRESH_AT_REPORT_CLOCK'
    assert result['lifecycle']['status']=='NOT_SUPPLIED'
    assert result['session_completeness_verified'] is False
    assert history==before


def test_identical_receipt_dedup_uses_first_observed_time():
    history,now=inputs();row=copy.deepcopy(history['rows'][0])
    row['observed_at']=(now-timedelta(seconds=1)).isoformat();history['rows'].append(row)
    result=session_quality(history,now=now)
    assert result['observed_bar_n']==2 and result['repeated_receipt_n']==1
    assert result['windows'][0]['receipt_delay_max_seconds']==129


@pytest.mark.parametrize('fault',['conflict','future','authority','headless_lifecycle'])
def test_contradictory_inputs_refuse(fault):
    history,now=inputs()
    if fault=='conflict':
        row=copy.deepcopy(history['rows'][0]);row['close']=101.1;history['rows'].append(row)
    elif fault=='future':history['rows'][0]['observed_at']=(now+timedelta(seconds=1)).isoformat()
    elif fault=='authority':history['rows'][0]['startup_authorized']=True
    else:
        with pytest.raises(ValueError):session_quality(history,now=now,lifecycle=[],lifecycle_expected_head=None)
        return
    with pytest.raises(ResearchInputRefused):session_quality(history,now=now)


def test_stale_truncated_window_never_complete():
    history,now=inputs();history['more_retained_rows']=True
    result=session_quality(history,now=now+timedelta(minutes=5))
    assert result['windows'][0]['status']=='STALE_AT_REPORT_CLOCK'
    assert result['history_window_truncated'] is True
    assert result['missed_market_events_established'] is False


@pytest.mark.parametrize('interrupted',[False,True])
def test_actual_existing_session_history_retains_nonclearing_state(tmp_path,interrupted):
    _manifest,_pin,_contract,journal,world,bootstrap=make_fixture(tmp_path/'session-fixture')
    runtime=bootstrap.start()
    if interrupted:
        journal.append('INTERRUPTED',{'reason':'UNKNOWN_EXIT'},str(uuid.uuid4()),observed_at=world.now)
    else:runtime.stop()
    rows=journal.verify();before=journal.path.read_bytes();history,now=inputs()
    result=session_quality(history,now=now,lifecycle=rows,lifecycle_expected_head=rows[-1]['digest'])
    assert result['lifecycle']['status']==('RECOVERY_REQUIRED' if interrupted else 'RECORDED_COMPLETE')
    assert result['recovery_authorized'] is False and result['startup_authorized'] is False
    assert result['lifecycle']['live_process_state_verified'] is False
    assert journal.path.read_bytes()==before
    with pytest.raises(ValueError):session_quality(history,now=now,lifecycle=rows,lifecycle_expected_head='a'*64)


def test_quality_api_and_unavailable_symbol_without_fake_gaps():
    now=datetime(2026,10,20,12,tzinfo=UTC)
    with sqlite3.connect(':memory:') as db:
        app=create_replay_app(ReplayStore(db),symbols=['SPY'],clock=lambda:now)
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
                response=await client.get('/api/market-data/quality',params={'symbol':'SPY'})
                assert response.status_code==200 and response.headers['cache-control']=='no-store'
                assert response.json()['status']=='NO_OBSERVATIONS'
                assert response.json()['windows']==[]
                page=await client.get('/quality',params={'symbol':'SPY'})
                assert page.status_code==200 and 'NO_OBSERVATIONS' in page.text
                assert 'not missed market events' in page.text
                assert page.headers['cache-control']=='no-store'
                assert (await client.get('/api/market-data/quality',params={'symbol':'QQQ'})).status_code==404
        asyncio.run(check())


@pytest.mark.parametrize('fault',['digest','future','health_before_start','stale_head','replayed_event','shutdown_after_interruption'])
def test_lifecycle_contradiction_never_becomes_permission(tmp_path,fault):
    _m,_p,_c,journal,world,bootstrap=make_fixture(tmp_path/'lifecycle-fixture')
    runtime=bootstrap.start()
    if fault=='shutdown_after_interruption':
        journal.append('INTERRUPTED',{'reason':'UNKNOWN_EXIT'},str(uuid.uuid4()),observed_at=world.now)
    else:runtime.stop()
    rows=copy.deepcopy(journal.verify());history,now=inputs()
    if fault=='digest':rows[-1]['payload']['unexpected']='tampered'
    elif fault=='future':rows[-1]['observed_at']=now.timestamp()+1
    elif fault=='health_before_start':rows[0].update(event='HEALTH',payload={'state':'READY'})
    elif fault=='replayed_event':rows.append(copy.deepcopy(rows[0]))
    elif fault=='shutdown_after_interruption':
        rows.append({**rows[-1],'event':'GRACEFUL_SHUTDOWN','event_id':str(uuid.uuid4()),'payload':{'outcome':'COMPLETE'}})
    if fault!='digest':
        previous='0'*64
        for row in rows:
            row['previous']=previous
            row['digest']=digest({k:v for k,v in row.items() if k!='digest'})
            previous=row['digest']
    expected='f'*64 if fault=='stale_head' else rows[-1]['digest']
    with pytest.raises(ValueError):session_quality(history,now=now,lifecycle=rows,lifecycle_expected_head=expected)


def test_windows_are_chronological_across_named_sessions():
    now=datetime(2026,10,20,22,tzinfo=UTC)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db)
        for hour in (21,12,14):
            store.ingest(fixture(now.replace(hour=hour)),observed_at=now,asset_class='US_ETF')
        result=session_quality(store.history('SPY',now=now),now=now)
        assert [row['session'] for row in result['windows']]==['PRE_MARKET','REGULAR','AFTER_HOURS']


def test_actual_quality_api_matches_frontend_fixture():
    now=datetime(2026,11,3,0,2,10,tzinfo=UTC)
    first=datetime(2026,11,2,23,58,tzinfo=UTC)
    expected=json.loads((Path(__file__).parent/'fixtures/market-replay-v1/quality.json').read_bytes())
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db)
        for offset in (0,2,3):store.ingest(fixture(first+timedelta(minutes=offset)),observed_at=now,asset_class='US_ETF')
        app=create_replay_app(store,symbols=['SPY'],clock=lambda:now)
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
                assert (await client.get('/api/market-data/quality',params={'symbol':'SPY'})).json()==expected
        asyncio.run(check())
