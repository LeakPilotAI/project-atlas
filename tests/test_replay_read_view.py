import asyncio
import hashlib
import json
import sqlite3
from builtins import BaseExceptionGroup
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from test_market_refusals import seeded
from test_market_replay_integration import fixture, quote_fixture
from test_retained_research import reference

from scripts.observation_runtime.market_replay import (
    ReplayStore,
    create_replay_app,
    normalize_chart,
    normalize_quote,
)


def append_pair(path,now):
    """Independent fixture writer commits both normalized observations together."""
    bar=fixture(now.replace(second=0)-timedelta(minutes=1))
    bar['chart']['result'][0]['indicators']['quote'][0]['close']=[102]
    quote=quote_fixture(now-timedelta(seconds=1))
    for key in ('preMarketPrice','regularMarketPrice','postMarketPrice'):
        quote['quoteResponse']['result'][0][key]=104
    values=[('replay_bars',normalize_chart(bar,observed_at=now,asset_class='US_ETF')[0]),
            ('replay_quotes',normalize_quote(quote,observed_at=now,asset_class='US_ETF'))]
    with sqlite3.connect(path,timeout=0.1) as writer:
        for table,row in values:
            body=json.dumps(row,sort_keys=True)
            writer.execute(f'INSERT INTO {table} VALUES (?,?,?,?)',
                (row['symbol'],row['timestamp'],hashlib.sha256(body.encode()).hexdigest(),body))


@pytest.mark.parametrize('url',['/api/market-data','/'])
def test_one_report_never_mixes_commits_from_an_independent_writer(tmp_path,monkeypatch,url):
    async def scenario():
        path=tmp_path/'synthetic.sqlite';now=datetime(2026,10,20,14,3,10,tzinfo=UTC)
        with sqlite3.connect(path,timeout=0.1) as db,ThreadPoolExecutor(max_workers=1) as pool:
            assert db.execute('PRAGMA journal_mode=WAL').fetchone()[0]=='wal'
            store=ReplayStore(db)
            store.ingest(fixture(now.replace(second=0)-timedelta(minutes=2)),observed_at=now,asset_class='US_ETF')
            store.ingest_quote(quote_fixture(now-timedelta(seconds=2)),observed_at=now,asset_class='US_ETF')
            original=store.snapshot;fired=False
            def interleave(*args,**kwargs):
                nonlocal fired
                result=original(*args,**kwargs)
                if not fired:
                    pool.submit(append_pair,path,now).result(timeout=3);fired=True
                return result
            monkeypatch.setattr(store,'snapshot',interleave)
            app=create_replay_app(store,symbols=['SPY'],clock=lambda:now)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
                first=await client.get(url);assert first.status_code==200
                if url.startswith('/api/'):
                    assert [first.json()['rows'][0]['price'],first.json()['quote_rows'][0]['price']]==[101,103]
                else:assert '<td>101.0</td>' in first.text and '<td>103.0</td>' in first.text and '<td>104.0</td>' not in first.text
                second=await client.get(url);assert second.status_code==200
                if url.startswith('/api/'):
                    assert [second.json()['rows'][0]['price'],second.json()['quote_rows'][0]['price']]==[102,104]
                else:assert '<td>102.0</td>' in second.text and '<td>104.0</td>' in second.text
            assert not db.in_transaction
    asyncio.run(scenario())


URLS=['/api/market-data','/','/api/market-data/history?symbol=SPY','/api/market-data/quality?symbol=SPY',
      '/quality?symbol=SPY','/api/market-data/quote-quality','/quote-quality',
      '/api/market-data/research?symbol=SPY','/research?symbol=SPY']


@pytest.mark.parametrize('url',URLS)
def test_every_successful_surface_closes_one_read_view_without_commit(url):
    async def scenario():
        db,store,now=seeded();statements=[]
        try:
            app=create_replay_app(store,symbols=['SPY'],clock=lambda:now,previous_closes={'SPY':reference(now)})
            before=db.total_changes;db.set_trace_callback(statements.append)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
                response=await client.get(url)
                assert response.status_code==200 and response.headers['cache-control']=='no-store'
            assert statements.count('BEGIN')==statements.count('ROLLBACK')==1
            assert 'COMMIT' not in statements and db.total_changes==before and not db.in_transaction
        finally:db.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('url',URLS)
def test_pending_caller_writes_are_never_committed_or_rolled_back_by_api(url):
    async def scenario():
        db,store,now=seeded()
        try:
            app=create_replay_app(store,symbols=['SPY'],clock=lambda:now,previous_closes={'SPY':reference(now)})
            db.execute('CREATE TABLE caller_owned (value INTEGER)');db.execute('INSERT INTO caller_owned VALUES (7)')
            before=db.total_changes
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
                response=await client.get(url)
                assert response.status_code==503
            assert db.in_transaction and db.execute('SELECT value FROM caller_owned').fetchall()==[(7,)]
            assert db.total_changes==before
            db.rollback();assert db.execute('SELECT value FROM caller_owned').fetchall()==[]
        finally:db.close()
    asyncio.run(scenario())


def test_initialization_nested_views_and_ingestion_refuse_caller_transaction_adoption():
    db,store,now=seeded()
    try:
        before=db.total_changes
        with store.read_view():
            with pytest.raises(ValueError):ReplayStore(db)
            with pytest.raises(ValueError),store.read_view():raise AssertionError('nested body must not run')
            with pytest.raises(ValueError):store.ingest(fixture(now.replace(second=0)),observed_at=now+timedelta(minutes=2),asset_class='US_ETF')
            assert db.in_transaction and store.snapshot(['SPY'],now=now)['rows'][0]['status']=='FRESH'
        assert not db.in_transaction and db.total_changes==before
    finally:db.close()


@pytest.mark.parametrize('cancel',[False,True])
def test_operation_failure_identity_and_cancellation_survive_successful_cleanup(cancel):
    db,store,_=seeded();error=asyncio.CancelledError() if cancel else OSError('synthetic primary failure')
    try:
        with pytest.raises(type(error)) as captured,store.read_view():raise error
        assert captured.value is error and not db.in_transaction and store._read_view_fault is None
    finally:db.close()


class FaultConnection(sqlite3.Connection):
    rollback_mode=None
    begin_mode=None
    cleanup_error=None
    begin_error=None
    rollback_calls=0

    def execute(self,sql,*args,**kwargs):
        if sql=='BEGIN' and self.begin_mode:
            if self.begin_mode=='after':super().execute(sql,*args,**kwargs)
            if self.begin_mode=='noop':return None
            raise self.begin_error
        return super().execute(sql,*args,**kwargs)

    def rollback(self):
        self.rollback_calls+=1
        if self.rollback_mode=='before':raise self.cleanup_error
        if self.rollback_mode=='noop':return
        super().rollback()
        if self.rollback_mode=='after':raise self.cleanup_error


@pytest.mark.parametrize('mode',['before','after','noop'])
def test_successful_computation_cannot_acknowledge_uncertain_cleanup(mode):
    db=sqlite3.connect(':memory:',factory=FaultConnection);store=ReplayStore(db)
    db.rollback_mode=mode;db.cleanup_error=OSError('synthetic cleanup failure')
    try:
        with pytest.raises((OSError,ValueError)) as captured,store.read_view():pass
        assert store._read_view_fault is captured.value
        # Even an after-rollback error leaves this store instance refusing: an
        # idle connection alone is not cleanup acknowledgement.
        with pytest.raises(ValueError) as again,store.read_view():raise AssertionError('latched body must not run')
        assert again.value.__cause__ is captured.value
    finally:db.close()


@pytest.mark.parametrize('cancel',[False,True])
@pytest.mark.parametrize('mode',['before','after'])
def test_multiple_failures_preserve_both_original_objects_and_latched_context(cancel,mode):
    db=sqlite3.connect(':memory:',factory=FaultConnection);store=ReplayStore(db)
    primary=asyncio.CancelledError() if cancel else ValueError('synthetic source failure')
    cleanup=OSError('synthetic rollback failure');db.cleanup_error=cleanup;db.rollback_mode=mode
    try:
        with pytest.raises(BaseExceptionGroup) as captured,store.read_view():raise primary
        assert captured.value.exceptions==(primary,cleanup)
        assert store._read_view_fault is captured.value
        with pytest.raises(ValueError) as refused:store.history('SPY',now=datetime(2026,10,20,14,tzinfo=UTC))
        assert refused.value.__cause__ is captured.value
    finally:db.close()


@pytest.mark.parametrize('mode',['before','after','noop'])
def test_uncertain_begin_never_rolls_back_or_adopts_unknown_ownership(mode):
    db=sqlite3.connect(':memory:',factory=FaultConnection);store=ReplayStore(db)
    error=OSError('synthetic BEGIN uncertainty');db.begin_error=error;db.begin_mode=mode
    try:
        with pytest.raises((OSError,ValueError)),store.read_view():raise AssertionError('source body must not run')
        assert db.rollback_calls==0 and store._read_view_fault is not None
        assert db.in_transaction==(mode=='after')
    finally:db.close()


def test_raw_caller_ending_view_is_detected_without_committing_any_data():
    db,store,_=seeded()
    try:
        with pytest.raises(ValueError,match='ended before'),store.read_view():db.rollback()
        assert store._read_view_fault is not None
    finally:db.close()


def test_caller_sql_inside_owned_view_is_not_committed():
    db,store,_=seeded()
    try:
        db.execute('CREATE TABLE extra_fixture (value INTEGER)')
        with store.read_view():db.execute('INSERT INTO extra_fixture VALUES (1)')
        assert db.execute('SELECT * FROM extra_fixture').fetchall()==[]
    finally:db.close()


def test_api_cleanup_failure_refuses_already_built_fresh_response():
    async def scenario():
        db=sqlite3.connect(':memory:',factory=FaultConnection);store=ReplayStore(db)
        now=datetime(2026,10,20,14,1,10,tzinfo=UTC)
        store.ingest(fixture(now-timedelta(seconds=70)),observed_at=now,asset_class='US_ETF')
        errors=[];app=create_replay_app(store,symbols=['SPY'],clock=lambda:now,failure_observer=errors.append)
        db.cleanup_error=OSError('SYNTHETIC_PRIVATE_ROLLBACK');db.rollback_mode='after'
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
                first=await client.get('/api/market-data')
                assert first.status_code==503 and first.json()['rows']==[]
                assert 'SYNTHETIC_PRIVATE_ROLLBACK' not in first.text
                assert errors[0] is db.cleanup_error and not db.in_transaction
                db.rollback_mode=None
                second=await client.get('/api/market-data')
                assert second.status_code==503 and errors[1].__cause__ is errors[0]
        finally:db.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('kind',['bar','quote'])
def test_exact_ingestion_retry_cannot_commit_unrelated_pending_writes(kind):
    db,store,now=seeded()
    try:
        db.execute('CREATE TABLE pending_fixture (value INTEGER)');db.execute('INSERT INTO pending_fixture VALUES (9)')
        with pytest.raises(ValueError):
            if kind=='bar':store.ingest(fixture(now-timedelta(seconds=70)),observed_at=now,asset_class='US_ETF')
            else:store.ingest_quote(quote_fixture(now-timedelta(seconds=2)),observed_at=now,asset_class='US_ETF')
        assert db.in_transaction and db.execute('SELECT * FROM pending_fixture').fetchall()==[(9,)]
        db.rollback();assert db.execute('SELECT * FROM pending_fixture').fetchall()==[]
    finally:db.close()


def test_api_aggregate_refusal_preserves_primary_and_cleanup_without_partial_prices(monkeypatch):
    async def scenario():
        db=sqlite3.connect(':memory:',factory=FaultConnection);store=ReplayStore(db);errors=[]
        now=datetime(2026,10,20,14,1,10,tzinfo=UTC)
        primary=ValueError('SYNTHETIC_PRIVATE_SOURCE');cleanup=OSError('SYNTHETIC_PRIVATE_CLEANUP')
        def fail(*args,**kwargs):raise primary
        app=create_replay_app(store,symbols=['SPY'],clock=lambda:now,failure_observer=errors.append)
        monkeypatch.setattr(store,'snapshot',fail);db.rollback_mode='before';db.cleanup_error=cleanup
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app,raise_app_exceptions=False),base_url='http://fixture') as client:
                response=await client.get('/api/market-data')
                assert response.status_code==500 and response.json()['rows']==[]
                assert 'SYNTHETIC_PRIVATE' not in response.text
                assert errors[0].exceptions==(primary,cleanup) and store._read_view_fault is errors[0]
                again=await client.get('/api/market-data')
                assert again.status_code==503 and errors[1].__cause__ is errors[0]
        finally:db.close()
    asyncio.run(scenario())


def test_delete_journal_writer_timeout_preserves_old_pair_until_read_view_ends(tmp_path):
    path=tmp_path/'synthetic-delete.sqlite';now=datetime(2026,10,20,14,3,10,tzinfo=UTC)
    with sqlite3.connect(path,timeout=0.1) as db,ThreadPoolExecutor(max_workers=1) as pool:
        assert db.execute('PRAGMA journal_mode=DELETE').fetchone()[0]=='delete'
        store=ReplayStore(db)
        store.ingest(fixture(now.replace(second=0)-timedelta(minutes=2)),observed_at=now,asset_class='US_ETF')
        store.ingest_quote(quote_fixture(now-timedelta(seconds=2)),observed_at=now,asset_class='US_ETF')
        with store.read_view():
            assert store.snapshot(['SPY'],now=now)['rows'][0]['price']==101
            with pytest.raises(sqlite3.OperationalError):pool.submit(append_pair,path,now).result(timeout=3)
            assert store.quote_snapshot(['SPY'],now=now)[0]['price']==103
        pool.submit(append_pair,path,now).result(timeout=3)
        with store.read_view():
            assert store.snapshot(['SPY'],now=now)['rows'][0]['price']==102
            assert store.quote_snapshot(['SPY'],now=now)[0]['price']==104
