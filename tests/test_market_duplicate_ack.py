"""Duplicate acknowledgements require valid immutable retained observations."""
import copy
import hashlib
import sqlite3
from datetime import timedelta

import pytest
from app.investment.offline_research import ResearchInputRefused
from test_market_retained_schema import NOW, STAMP, reseal, store_fixture

from scripts.observation_runtime.market_replay import normalize_chart, normalize_quote


def incoming(kind):
    if kind=='bar':
        payload={'chart':{'error':None,'result':[{'meta':{'symbol':'SPY','currency':'USD','dataGranularity':'1m'},'timestamp':[int(STAMP.timestamp())],
            'indicators':{'quote':[{'open':[100],'high':[102],'low':[99],'close':[101],'volume':[120]}]}}]}}
        return normalize_chart(payload,observed_at=NOW,asset_class='US_ETF')
    return [normalize_quote({'quoteResponse':{'error':None,'result':[{'symbol':'SPY','currency':'USD','regularMarketTime':int((NOW-timedelta(seconds=5)).timestamp()),'regularMarketPrice':101,'exchangeDataDelayedBy':0}]}},observed_at=NOW,asset_class='US_ETF')]


@pytest.mark.parametrize('kind,fault',[('bar','duplicate-key'),('quote','duplicate-key'),('bar','volume-float'),('bar','interval-float'),('quote','delay-bool'),('quote','delay-float'),('bar','receipt'),('quote','receipt')])
def test_invalid_retained_duplicate_cannot_acknowledge_success(tmp_path,kind,fault):
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store=store_fixture(connection,kind)
        table='replay_bars' if kind=='bar' else 'replay_quotes'
        if fault=='duplicate-key':
            body=connection.execute(f'SELECT body FROM {table}').fetchone()[0]
            changed='{"data_mode":"LIVE",'+body[1:]
            connection.execute(f'UPDATE {table} SET body=?,digest=?',(changed,hashlib.sha256(changed.encode()).hexdigest()))
            connection.commit()
        else:
            field,value={'volume-float':('volume',120.0),'interval-float':('interval_seconds',60.0),
                         'delay-bool':('provider_reported_delay',False),'delay-float':('provider_reported_delay',0.0),
                         'receipt':('observed_at',(STAMP-timedelta(minutes=1)).isoformat())}[fault]
            reseal(connection,kind,lambda row:row.update({field:value}))
        before=connection.execute(f'SELECT body,digest FROM {table}').fetchall()
        with pytest.raises(ResearchInputRefused):
            store._insert(incoming(kind),table)
        assert connection.execute(f'SELECT body,digest FROM {table}').fetchall()==before
        assert not connection.in_transaction


@pytest.mark.parametrize('kind',['bar','quote'])
def test_well_formed_duplicate_returns_zero_and_preserves_first_receipt(tmp_path,kind):
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store=store_fixture(connection,kind)
        table='replay_bars' if kind=='bar' else 'replay_quotes'
        before=connection.execute(f'SELECT body,digest FROM {table}').fetchall()
        rows=incoming(kind)
        rows[0]['observed_at']=(NOW+timedelta(seconds=2)).isoformat()
        assert store._insert(rows,table)==0
        assert connection.execute(f'SELECT body,digest FROM {table}').fetchall()==before


def test_invalid_duplicate_rolls_back_earlier_new_rows(tmp_path):
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store=store_fixture(connection,'bar')
        reseal(connection,'bar',lambda row:row.update(volume=120.0))
        existing=incoming('bar')[0]
        earlier=copy.deepcopy(existing)
        earlier['timestamp']=(STAMP-timedelta(minutes=1)).isoformat()
        earlier['bar_end']=STAMP.isoformat()
        before=connection.execute('SELECT event_time,body,digest FROM replay_bars').fetchall()
        with pytest.raises(ResearchInputRefused):
            store._insert([earlier,existing],'replay_bars')
        assert connection.execute('SELECT event_time,body,digest FROM replay_bars').fetchall()==before
        assert not connection.in_transaction
