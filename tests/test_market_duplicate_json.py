"""Retained invalid JSON/cell types refuse consistently without successful acks."""
import copy
import hashlib
import json
import sqlite3
from datetime import timedelta

import pytest
from app.investment.offline_research import ResearchInputRefused
from test_market_duplicate_ack import incoming
from test_market_retained_schema import NOW, STAMP, store_fixture


@pytest.mark.parametrize('kind',['bar','quote'])
@pytest.mark.parametrize('body',['null','[]','42','"plain string"','true','{"broken":'])
def test_malformed_or_nonmapping_duplicate_refuses_with_cause(tmp_path,kind,body):
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store=store_fixture(connection,kind)
        table='replay_bars' if kind=='bar' else 'replay_quotes'
        connection.execute(f'UPDATE {table} SET body=?,digest=?',(body,hashlib.sha256(body.encode()).hexdigest()))
        connection.commit()
        before=connection.execute(f'SELECT body,digest FROM {table}').fetchall()
        with pytest.raises(ResearchInputRefused) as caught:
            store._insert(incoming(kind),table)
        assert isinstance(caught.value.__cause__, ValueError)
        if body=='{"broken":':
            assert isinstance(caught.value.__cause__,json.JSONDecodeError)
        assert connection.execute(f'SELECT body,digest FROM {table}').fetchall()==before
        assert not connection.in_transaction


@pytest.mark.parametrize('kind',['bar','quote'])
@pytest.mark.parametrize('operation',['duplicate','read'])
def test_nontext_retained_body_is_typed_integrity_refusal(tmp_path,kind,operation):
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store=store_fixture(connection,kind)
        table='replay_bars' if kind=='bar' else 'replay_quotes'
        body=b'[]'
        connection.execute(f'UPDATE {table} SET body=?,digest=?',(body,hashlib.sha256(body).hexdigest()))
        connection.commit()
        before=connection.execute(f'SELECT body,digest FROM {table}').fetchall()
        with pytest.raises(ResearchInputRefused,match='integrity'):
            if operation=='duplicate':
                store._insert(incoming(kind),table)
            elif kind=='bar':
                store.snapshot(['SPY'],now=NOW)
            else:
                store.quote_snapshot(['SPY'],now=NOW)
        assert connection.execute(f'SELECT body,digest FROM {table}').fetchall()==before


def test_malformed_duplicate_rolls_back_earlier_batch_insert(tmp_path):
    with sqlite3.connect(tmp_path/'fixture.sqlite') as connection:
        store=store_fixture(connection,'bar')
        body='[]'
        connection.execute('UPDATE replay_bars SET body=?,digest=?',(body,hashlib.sha256(body.encode()).hexdigest()))
        connection.commit()
        rows=incoming('bar')
        earlier=copy.deepcopy(rows[0])
        earlier['timestamp']=(STAMP-timedelta(minutes=1)).isoformat()
        earlier['bar_end']=STAMP.isoformat()
        before=connection.execute('SELECT * FROM replay_bars').fetchall()
        with pytest.raises(ResearchInputRefused):
            store._insert([earlier,*rows],'replay_bars')
        assert connection.execute('SELECT * FROM replay_bars').fetchall()==before
        assert not connection.in_transaction
