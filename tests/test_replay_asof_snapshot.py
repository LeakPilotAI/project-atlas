import asyncio
import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from test_market_replay_integration import fixture, quote_fixture

from scripts.observation_runtime.market_replay import (
    ReplayStore,
    create_replay_app,
    normalize_quote,
)


def add(store,kind,event,receipt):
    if kind=='bar':store.ingest(fixture(event),observed_at=receipt,asset_class='US_ETF')
    else:store.ingest_quote(quote_fixture(event),observed_at=receipt,asset_class='US_ETF')


def snapshot(store,kind,now,**kwargs):
    if kind=='bar':return store.snapshot(['SPY'],now=now,**kwargs)['rows'][0]
    return store.quote_snapshot(['SPY'],now=now,**kwargs)[0]


@pytest.mark.parametrize('kind',['bar','quote'])
@pytest.mark.parametrize('hour',[12,14,21])
def test_future_receipt_never_hides_latest_known_eligible_value(kind,hour):
    now=datetime(2026,10,20,hour,1,10,tzinfo=UTC)
    old=now-timedelta(seconds=70 if kind=='bar' else 2)
    future=now.replace(second=0) if kind=='bar' else now+timedelta(seconds=5)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);add(store,kind,old,now);before=snapshot(store,kind,now)
        add(store,kind,future,now+timedelta(minutes=2));after=snapshot(store,kind,now)
        assert after==before
        assert after['status']=='FRESH' and after['timestamp']==old.isoformat()


@pytest.mark.parametrize('kind',['bar','quote'])
def test_future_receipts_do_not_promote_stale_fallback_or_previous_session(kind):
    now=datetime(2026,10,20,13,30,10,tzinfo=UTC)
    old=now.replace(minute=29,second=0) if kind=='bar' else now.replace(minute=29,second=58)
    future=now.replace(second=0) if kind=='bar' else now+timedelta(seconds=1)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);add(store,kind,old,now if kind=='bar' else old+timedelta(seconds=1))
        add(store,kind,future,now+timedelta(minutes=2))
        row=snapshot(store,kind,now)
        assert row['status']=='STALE' and row['price'] is None
        assert row['session']=='PRE_MARKET'
        assert row['reference_close' if kind=='bar' else 'reference_price']>0


@pytest.mark.parametrize('kind',['bar','quote'])
def test_missing_and_only_future_receipts_remain_unavailable(kind):
    now=datetime(2026,10,20,14,1,10,tzinfo=UTC)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);assert snapshot(store,kind,now)['status']=='UNAVAILABLE'
        stamp=now.replace(second=0)-timedelta(minutes=1) if kind=='bar' else now-timedelta(seconds=1)
        add(store,kind,stamp,now+timedelta(minutes=2))
        row=snapshot(store,kind,now)
        assert row['status']=='NOT_YET_OBSERVED' and row['price'] is None
        assert not any(row.get(key) is not None for key in ('reference_close','reference_price'))


def test_delayed_earlier_quote_stays_delayed_and_prices_are_not_executable():
    now=datetime(2026,10,20,14,1,10,tzinfo=UTC);payload=quote_fixture(now-timedelta(seconds=2))
    payload['quoteResponse']['result'][0]['exchangeDataDelayedBy']=15
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);store.ingest_quote(payload,observed_at=now,asset_class='US_ETF')
        add(store,'quote',now+timedelta(seconds=5),now+timedelta(seconds=10))
        row=snapshot(store,'quote',now)
        assert row['status']=='DELAYED' and row['price'] is None
        assert row['reference_price']==103 and row['provider_delay_unit']=='UNVERIFIED_FIXTURE_METADATA'


@pytest.mark.parametrize('kind',['bar','quote'])
def test_future_record_integrity_failure_is_not_silently_skipped(kind):
    now=datetime(2026,10,20,14,1,10,tzinfo=UTC)
    stamp=now.replace(second=0) if kind=='bar' else now+timedelta(seconds=5)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);add(store,kind,stamp,now+timedelta(minutes=2))
        table='replay_bars' if kind=='bar' else 'replay_quotes'
        db.execute(f"UPDATE {table} SET digest='corrupt'");db.commit()
        with pytest.raises(ValueError,match='integrity'):snapshot(store,kind,now)


def test_rehashed_impossible_receipt_chronology_refuses():
    now=datetime(2026,10,20,14,1,10,tzinfo=UTC)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);add(store,'quote',now-timedelta(seconds=1),now)
        row=json.loads(db.execute('SELECT body FROM replay_quotes').fetchone()[0]);row['observed_at']=(now-timedelta(seconds=10)).isoformat()
        raw=json.dumps(row,sort_keys=True)
        db.execute('UPDATE replay_quotes SET body=?,digest=?',(raw,hashlib.sha256(raw.encode()).hexdigest()));db.commit()
        with pytest.raises(ValueError,match='chronology'):snapshot(store,'quote',now)


def test_large_future_prefix_refuses_bounded_search_without_hiding_unknown_scope():
    now=datetime(2026,10,20,14,tzinfo=UTC);receipt=now+timedelta(hours=4)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);add(store,'quote',now-timedelta(seconds=1),now)
        rows=[]
        for i in range(1,10001):
            row=normalize_quote(quote_fixture(now+timedelta(seconds=i)),observed_at=receipt,asset_class='US_ETF')
            raw=json.dumps(row,sort_keys=True);rows.append(('SPY',row['timestamp'],hashlib.sha256(raw.encode()).hexdigest(),raw))
        db.executemany('INSERT INTO replay_quotes VALUES (?,?,?,?)',rows);db.commit()
        with pytest.raises(ValueError,match='search bound'):snapshot(store,'quote',now)
        # A normal current-time read returns the very first eligible row instead
        # of refusing merely because the table contains over 10,000 events.
        assert snapshot(store,'quote',receipt)['timestamp']==(now+timedelta(seconds=10000)).isoformat()


def test_lazy_selection_closes_cursor_on_success_and_failure():
    class Cursor:
        closed=False
        def __init__(self,inner):self.inner=inner
        def __iter__(self):return self
        def __next__(self):return next(self.inner)
        def close(self):self.closed=True;self.inner.close()
    class Connection:
        def __init__(self,inner):self.inner=inner;self.selected=[]
        def execute(self,sql,args=()):
            result=self.inner.execute(sql,args)
            if sql.startswith('SELECT body,digest,event_time FROM replay_quotes'):
                result=Cursor(result);self.selected.append(result)
            return result
    now=datetime(2026,10,20,14,1,10,tzinfo=UTC)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);add(store,'quote',now-timedelta(seconds=1),now)
        spy=Connection(db);store.connection=spy
        assert snapshot(store,'quote',now)['status']=='FRESH' and spy.selected[-1].closed
        db.execute("UPDATE replay_quotes SET digest='corrupt'");db.commit()
        with pytest.raises(ValueError):snapshot(store,'quote',now)
        assert spy.selected[-1].closed


def test_actual_api_html_uses_known_values_and_preserves_storage():
    async def scenario():
        now=datetime(2026,10,20,14,1,10,tzinfo=UTC)
        with sqlite3.connect(':memory:') as db:
            store=ReplayStore(db)
            for kind in ('bar','quote'):
                add(store,kind,now-timedelta(seconds=70 if kind=='bar' else 2),now)
                add(store,kind,now.replace(second=0) if kind=='bar' else now+timedelta(seconds=5),now+timedelta(minutes=2))
            before=db.total_changes;app=create_replay_app(store,symbols=['SPY'],clock=lambda:now)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
                response=await client.get('/api/market-data');assert response.status_code==200
                body=response.json();assert body['rows'][0]['status']==body['quote_rows'][0]['status']=='FRESH'
                assert body['network_authorized'] is False
                assert '<td>FRESH</td>' in (await client.get('/')).text
                assert db.total_changes==before
    asyncio.run(scenario())
