import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from test_bar_vintages import seeded as vintage_seeded
from test_market_replay_integration import fixture, quote_fixture
from test_retained_research import reference

from scripts.observation_runtime import market_replay
from scripts.observation_runtime.bar_vintages import create_vintage_app
from scripts.observation_runtime.market_refusals import refusal_payload
from scripts.observation_runtime.market_replay import ReplayStore, create_replay_app


def seeded():
    db=sqlite3.connect(':memory:');store=ReplayStore(db)
    now=datetime(2026,10,20,14,1,10,tzinfo=UTC)
    store.ingest(fixture(now-timedelta(seconds=70)),observed_at=now,asset_class='US_ETF')
    store.ingest_quote(quote_fixture(now-timedelta(seconds=2)),observed_at=now,asset_class='US_ETF')
    return db,store,now


@pytest.mark.parametrize('url',['/api/market-data','/','/api/market-data/research?symbol=SPY','/research?symbol=SPY'])
def test_corrupt_source_is_non_success_no_store_and_no_partial_prices(url):
    async def scenario():
        db,store,now=seeded()
        try:
            app=create_replay_app(store,symbols=['SPY'],clock=lambda:now,previous_closes={'SPY':reference(now)})
            db.execute("UPDATE replay_bars SET digest='corrupt'");db.commit()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app,raise_app_exceptions=False),base_url='http://fixture') as client:
                response=await client.get(url)
                assert response.status_code==503
                assert response.headers['cache-control']=='no-store'
                assert response.headers['x-content-type-options']=='nosniff'
                assert '101.0' not in response.text and '103.0' not in response.text
                if url.startswith('/api/'):
                    assert response.json()['rows']==[] and response.json()['quote_rows']==[]
                    fixture_path=Path(__file__).parent/'fixtures/market-replay-v1/market-refusal.json'
                    assert response.content==fixture_path.read_bytes()
                else:assert 'Data unavailable' in response.text
        finally:db.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('url',['/api/market-data','/','/api/market-data/history?symbol=SPY',
    '/api/market-data/quality?symbol=SPY','/quality?symbol=SPY','/api/market-data/quote-quality','/quote-quality',
    '/api/market-data/research?symbol=SPY','/research?symbol=SPY'])
def test_closed_sqlite_is_sanitized_non_success_for_every_read_surface(url):
    async def scenario():
        db,store,now=seeded();errors=[]
        app=create_replay_app(store,symbols=['SPY'],clock=lambda:now,previous_closes={'SPY':reference(now)},failure_observer=errors.append)
        db.close()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
            response=await client.get(url)
            assert response.status_code==503 and response.headers['cache-control']=='no-store'
            assert 'Cannot operate' not in response.text and 'sqlite' not in response.text
            assert len(errors)==1 and isinstance(errors[0],sqlite3.Error)
            assert app.state.market_failure_counts=={'responses':1,'observer_failures':0}
    asyncio.run(scenario())


@pytest.mark.parametrize('fault',['os','budget','unknown','render','observer'])
def test_original_exception_is_observable_without_leaking_or_masking(fault,monkeypatch):
    async def scenario():
        db,store,now=seeded();errors=[]
        secret='SYNTHETIC_PRIVATE_VALUE'
        error=RuntimeError(secret) if fault=='unknown' else ValueError(secret) if fault in ('budget','render') else OSError(secret)
        def observe(exception):
            errors.append(exception)
            if fault=='observer':raise RuntimeError('SYNTHETIC_REPORTING_FAILURE')
        def fail(*args,**kwargs):raise error
        app=create_replay_app(store,symbols=['SPY'],clock=lambda:now,failure_observer=observe)
        if fault=='render':monkeypatch.setattr(market_replay,'render_dashboard',fail)
        else:monkeypatch.setattr(store,'snapshot',fail)
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app,raise_app_exceptions=False),base_url='http://fixture') as client:
                response=await client.get('/' if fault=='render' else '/api/market-data')
                assert response.status_code==(500 if fault=='unknown' else 503)
                assert secret not in response.text and 'SYNTHETIC_REPORTING_FAILURE' not in response.text
                assert errors==[error]
                assert app.state.market_failure_counts['observer_failures']==(1 if fault=='observer' else 0)
                if fault=='observer':assert error.__notes__==['Optional failure observer did not complete; primary failure retained.']
        finally:db.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('url',['/api/market-data','/'])
def test_quote_failure_never_publishes_already_computed_good_bars(url):
    async def scenario():
        db,store,now=seeded();app=create_replay_app(store,symbols=['SPY'],clock=lambda:now)
        try:
            db.execute("UPDATE replay_quotes SET digest='corrupt'");db.commit()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
                response=await client.get(url)
                assert response.status_code==503
                assert '101.0' not in response.text and 'FRESH' not in response.text
                if url.startswith('/api/'):assert response.json()['rows']==[]
                else:assert response.headers['content-security-policy']=="default-src 'none'; frame-ancestors 'none'"
        finally:db.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('url,status',[('/api/market-data/history?symbol=SPY&limit=SYNTHETIC_PRIVATE_VALUE',422),
    ('/api/market-data/history?symbol=SYNTHETIC_PRIVATE_VALUE',422),
    ('/api/market-data/history?symbol=QQQ',404),('/SYNTHETIC_PRIVATE_VALUE',404)])
def test_invalid_requests_do_not_echo_sensitive_inputs_or_cache_errors(url,status):
    async def scenario():
        db,store,now=seeded();app=create_replay_app(store,symbols=['SPY'],clock=lambda:now)
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
                response=await client.get(url)
                assert response.status_code==status and 'SYNTHETIC_PRIVATE_VALUE' not in response.text
                body=response.json();assert body['http_status']==status and body['rows']==body['quote_rows']==[]
                assert body['network_authorized'] is False and response.headers['cache-control']=='no-store'
                denied=await client.post('/api/market-data',json={'password':'SYNTHETIC_PRIVATE_VALUE'})
                assert denied.status_code==405 and denied.headers['allow']=='GET'
                assert 'SYNTHETIC_PRIVATE_VALUE' not in denied.text
        finally:db.close()
    asyncio.run(scenario())


def test_empty_success_and_domain_research_refusal_are_not_source_failures():
    async def scenario():
        db=sqlite3.connect(':memory:');store=ReplayStore(db);now=datetime(2026,10,20,14,tzinfo=UTC)
        app=create_replay_app(store,symbols=['SPY'],clock=lambda:now)
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
                response=await client.get('/api/market-data')
                assert response.status_code==200 and response.json()['rows'][0]['status']=='UNAVAILABLE'
                response=await client.get('/api/market-data/research?symbol=SPY')
                assert response.status_code==200 and response.json()['status']=='INSUFFICIENT_REFERENCE'
                assert app.state.market_failure_counts['responses']==0
        finally:db.close()
    asyncio.run(scenario())


def test_factory_copies_symbol_universe_and_rejects_unbounded_configuration():
    async def scenario():
        db,store,now=seeded();symbols=['SPY'];app=create_replay_app(store,symbols=symbols,clock=lambda:now)
        symbols.append('QQQ');symbols.clear()
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
                response=await client.get('/api/market-data')
                assert response.status_code==200 and [row['symbol'] for row in response.json()['rows']]==['SPY']
            with pytest.raises(ValueError):create_replay_app(store,symbols=[],clock=lambda:now)
            with pytest.raises(ValueError):create_replay_app(store,symbols=['SPY']*101,clock=lambda:now)
            with pytest.raises(ValueError):create_replay_app(store,symbols=['SPY'],clock=lambda:now,failure_observer=True)
        finally:db.close()
    asyncio.run(scenario())


def test_cancellation_is_not_converted_into_a_response_or_success(monkeypatch):
    async def scenario():
        db,store,now=seeded();errors=[]
        def cancel(*args,**kwargs):raise asyncio.CancelledError()
        monkeypatch.setattr(store,'snapshot',cancel)
        app=create_replay_app(store,symbols=['SPY'],clock=lambda:now,failure_observer=errors.append)
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
                with pytest.raises(asyncio.CancelledError):await client.get('/api/market-data')
                assert errors==[] and app.state.market_failure_counts['responses']==0
        finally:db.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('status',[200,True,None,600])
def test_invalid_error_status_can_never_become_success(status):
    assert refusal_payload(status)['http_status']==500


@pytest.mark.parametrize('url',['/api/market-data/receipt-history?symbol=SPY','/api/market-data/vintage-research?symbol=SPY','/vintage-research?symbol=SPY'])
def test_vintage_source_refusal_preserves_original_cause_and_never_returns_partial_data(url,monkeypatch):
    async def scenario():
        with sqlite3.connect(':memory:') as db:
            store,now,ref=vintage_seeded(db);errors=[];error=OSError('SYNTHETIC_PRIVATE_VALUE')
            def fail(*args,**kwargs):raise error
            app=create_vintage_app(store,symbols=['SPY'],clock=lambda:now,previous_closes={'SPY':[ref]},failure_observer=errors.append)
            monkeypatch.setattr(store,'archive',fail)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
                response=await client.get(url)
                assert response.status_code==503 and 'SYNTHETIC_PRIVATE_VALUE' not in response.text
                assert response.headers['cache-control']=='no-store'
                assert len(errors)==1 and errors[0].__cause__ is error
    asyncio.run(scenario())


def test_actual_locked_fixture_database_refuses_then_recovers_without_cached_success(tmp_path):
    async def scenario():
        path=tmp_path/'synthetic.db';db=sqlite3.connect(path,timeout=0.01);locker=None
        now=datetime(2026,10,20,14,1,10,tzinfo=UTC);store=ReplayStore(db);errors=[]
        store.ingest(fixture(now-timedelta(seconds=70)),observed_at=now,asset_class='US_ETF')
        app=create_replay_app(store,symbols=['SPY'],clock=lambda:now,failure_observer=errors.append)
        try:
            locker=sqlite3.connect(path,timeout=0.01);locker.execute('BEGIN EXCLUSIVE')
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
                response=await client.get('/api/market-data')
                assert response.status_code==503 and response.json()['reason']=='DATA_UNAVAILABLE'
                assert 'synthetic.db' not in response.text and 'locked' not in response.text
                assert len(errors)==1 and isinstance(errors[0],sqlite3.OperationalError)
                locker.rollback()
                recovered=await client.get('/api/market-data')
                assert recovered.status_code==200 and recovered.json()['rows'][0]['price']==101
                assert app.state.market_failure_counts['responses']==1
        finally:
            if locker is not None:locker.rollback();locker.close()
            db.close()
    asyncio.run(scenario())
