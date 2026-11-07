"""Valid-hash retained bytes are not automatically valid normalized observations."""
import asyncio
import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.investment.offline_research import ResearchInputRefused

from scripts.observation_runtime.market_replay import ReplayStore, create_replay_app

STAMP = datetime(2026,10,20,14,tzinfo=UTC)
NOW = STAMP + timedelta(seconds=70)


def store_fixture(connection, kind):
    store = ReplayStore(connection)
    if kind == 'bar':
        payload = {'chart':{'error':None,'result':[{'meta':{'symbol':'SPY','currency':'USD','dataGranularity':'1m'},'timestamp':[int(STAMP.timestamp())],
            'indicators':{'quote':[{'open':[100],'high':[102],'low':[99],'close':[101],'volume':[120]}]}}]}}
        store.ingest(payload,observed_at=NOW,asset_class='US_ETF')
    else:
        payload = {'quoteResponse':{'error':None,'result':[{'symbol':'SPY','currency':'USD','regularMarketTime':int((NOW-timedelta(seconds=5)).timestamp()),'regularMarketPrice':101,'exchangeDataDelayedBy':0}]}}
        store.ingest_quote(payload,observed_at=NOW,asset_class='US_ETF')
    return store


def reseal(connection, kind, mutation):
    table = 'replay_bars' if kind == 'bar' else 'replay_quotes'
    body = connection.execute(f'SELECT body FROM {table}').fetchone()[0]
    row = json.loads(body)
    mutation(row)
    changed = json.dumps(row,sort_keys=True,separators=(',',':'))
    connection.execute(f'UPDATE {table} SET body=?,digest=?',(changed,hashlib.sha256(changed.encode()).hexdigest()))
    connection.commit()
    return connection.execute(f'SELECT body,digest FROM {table}').fetchall()


def mutation(field,value):
    def apply(row):
        if value == 'DELETE':
            del row[field]
        else:
            row[field] = value
    return apply


@pytest.mark.parametrize('field,value',[('open','100'),('volume',2**53),('volume',120.0),('high',98),('data_mode','LIVE'),('source','LIVE_FEED'),('asset_class','CRYPTO'),('interval_seconds',True),('bar_end','2026-10-20T14:02:00+00:00'),('session','AFTER_HOURS'),('close','DELETE')])
@pytest.mark.parametrize('read',['snapshot','history'])
def test_invalid_hashed_bar_refuses_without_rewriting(tmp_path,field,value,read):
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store=store_fixture(connection,'bar')
        before=reseal(connection,'bar',mutation(field,value))
        with pytest.raises(ResearchInputRefused):
            store.snapshot(['SPY'],now=NOW) if read=='snapshot' else store.history('SPY',now=NOW)
        assert connection.execute('SELECT body,digest FROM replay_bars').fetchall()==before


@pytest.mark.parametrize('field,value',[('price','101'),('price',True),('provider_reported_delay',True),('provider_delay_unit','SECONDS_VERIFIED'),('price_kind','EXECUTABLE'),('asset_class','CRYPTO'),('session','PRE_MARKET')])
def test_invalid_hashed_quote_refuses_without_rewriting(tmp_path,field,value):
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store=store_fixture(connection,'quote')
        before=reseal(connection,'quote',mutation(field,value))
        with pytest.raises(ResearchInputRefused):
            store.quote_snapshot(['SPY'],now=NOW)
        assert connection.execute('SELECT body,digest FROM replay_quotes').fetchall()==before


@pytest.mark.parametrize('kind',['bar','quote'])
def test_api_refuses_invalid_retained_semantics_with_sanitized_503(tmp_path,kind):
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store=store_fixture(connection,kind)
        reseal(connection,kind,mutation('open' if kind=='bar' else 'price','private-fixture-value'))
        app=create_replay_app(store,symbols=['SPY'],clock=lambda:NOW)
        async def exercise():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://in-process.invalid') as client:
                for url in ['/api/market-data','/']:
                    response=await client.get(url)
                    assert response.status_code==503
                    assert 'private-fixture-value' not in response.text
                    assert 'FRESH' not in response.text
                    if url.startswith('/api'):
                        assert response.json()['reason']=='DATA_UNAVAILABLE'
        asyncio.run(exercise())


def test_well_formed_historical_integer_ohlc_remains_readable(tmp_path):
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store=store_fixture(connection,'bar')
        before=reseal(connection,'bar',lambda row:row.update(open=100,high=102,low=99))
        assert store.snapshot(['SPY'],now=NOW)['rows'][0]['price']==101
        assert store.history('SPY',now=NOW)['rows'][0]['open']==100
        assert connection.execute('SELECT body,digest FROM replay_bars').fetchall()==before

@pytest.mark.parametrize('kind',['bar','quote'])
def test_duplicate_retained_json_fields_refuse_even_with_valid_hash(tmp_path,kind):
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store=store_fixture(connection,kind)
        table='replay_bars' if kind=='bar' else 'replay_quotes'
        body=connection.execute(f'SELECT body FROM {table}').fetchone()[0]
        duplicated='{"data_mode":"LIVE",'+body[1:]
        connection.execute(f'UPDATE {table} SET body=?,digest=?',(duplicated,hashlib.sha256(duplicated.encode()).hexdigest()))
        connection.commit()
        before=connection.execute(f'SELECT body,digest FROM {table}').fetchall()
        with pytest.raises(ResearchInputRefused):
            store.snapshot(['SPY'],now=NOW) if kind=='bar' else store.quote_snapshot(['SPY'],now=NOW)
        assert connection.execute(f'SELECT body,digest FROM {table}').fetchall()==before
