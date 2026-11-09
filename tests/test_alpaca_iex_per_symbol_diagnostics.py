"""Per-symbol IEX data-only diagnostics. All provider transport is mocked.

This checks whether a requested symbol produced no frames, rejected frames,
or fresh accepted callbacks without exposing quote prices or account data.
"""
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.investment.alpaca_iex import Credentials, IEXFeed, IEXRefused, URL
from scripts.observation_runtime import alpaca_iex_probe as probe
from scripts.observation_runtime import atlas_r12_iex_diagnostic_receipt as receipts


STAMP=datetime(2026,11,9,14,30,30,tzinfo=UTC).timestamp()
TIME='2026-11-09T14:30:30Z'


def quote(symbol, *, condition='R'):
    return {'T':'q', 'S':symbol,'bp':100,'ap':100.01,'bs':3,'as':4,
            'bx':'V','ax':'V','z':'C','c':[condition],'t':TIME}


class FakeWire:
    def __init__(self,frames,symbols):
        self.frames=list(frames)
        self.sent=[]
        self.request=SimpleNamespace(headers={'Host':'stream.data.alpaca.markets'},
                                     path='/v2/iex')

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def recv(self):
        if self.frames:
            return self.frames.pop(0)
        await asyncio.sleep(0.01)
        raise TimeoutError


def transport(symbol_frames):
    wire=FakeWire(['[{"T":"success","msg":"authenticated"}]',
                   '[{"T":"subscription","quotes":["MSFT","SPY"]}]',
                   json.dumps(symbol_frames)],('MSFT','SPY'))
    @asynccontextmanager
    async def connect(url,**kwargs):
        assert url==URL
        assert kwargs['logger'].disabled
        yield wire
    return connect,wire


class LocalDataOnlyFeed(IEXFeed):
    def __init__(self,symbols,connect):
        super().__init__(symbols,clock=lambda:STAMP+0.5)
        self.mock_connect=connect

    async def run(self,credentials,*,seconds,max_reconnects,on_fresh_quote):
        return await super().run(credentials,seconds=seconds,max_reconnects=max_reconnects,
                                 on_fresh_quote=on_fresh_quote,connect=self.mock_connect)


@pytest.mark.asyncio
async def test_new_diagnostics_distinguish_msft_rejected_from_spy_fresh():
    connect,wire=transport([quote('MSFT',condition='H'),quote('SPY')])
    result=await probe.bounded_data_only_probe(
        seconds=1,symbols=['MSFT','SPY'],credentials=Credentials('FAKE-KEY','FAKE-SECRET'),
        feed_factory=lambda symbols:LocalDataOnlyFeed(symbols,connect))
    assert [x['action'] for x in wire.sent]==['auth','subscribe']
    assert result['authenticated'] is True and result['subscribed'] is True
    assert result['observed_symbols']==['SPY']
    assert result['quote_count']==1 and result['callback_quote_count']==1
    assert result['per_symbol_quote_diagnostics']=={
        'MSFT':{'received':1,'accepted':0,'rejected':1,'fresh_callbacks':0},
        'SPY':{'received':1,'accepted':1,'rejected':0,'fresh_callbacks':1}}
    assert 'FAKE-SECRET' not in json.dumps(result)
    assert '100.01' not in json.dumps(result)
    assert result['provider_rights_independently_accepted'] is False
    assert result['paper_fill_authorized'] is False
    assert result['live_order_authorized'] is False


@pytest.mark.asyncio
async def test_new_diagnostics_distinguish_missing_msft_frames():
    connect,_=transport([quote('SPY')])
    result=await probe.bounded_data_only_probe(
        seconds=1,symbols=['MSFT','SPY'],credentials=Credentials('FAKE-KEY','FAKE-SECRET'),
        feed_factory=lambda symbols:LocalDataOnlyFeed(symbols,connect))
    assert result['per_symbol_quote_diagnostics']['MSFT']=={
        'received':0,'accepted':0,'rejected':0,'fresh_callbacks':0}
    assert result['per_symbol_quote_diagnostics']['SPY']['fresh_callbacks']==1


@pytest.mark.asyncio
async def test_new_diagnostics_durable_create_once_readback(tmp_path):
    connect,_=transport([quote('MSFT',condition='H'),quote('SPY')])
    packet=await probe.bounded_data_only_probe(
        seconds=1,symbols=['MSFT','SPY'],credentials=Credentials('FAKE-KEY','FAKE-SECRET'),
        feed_factory=lambda symbols:LocalDataOnlyFeed(symbols,connect))
    got=receipts.write_receipt(packet,['MSFT','SPY'],'b'*32,root=tmp_path)
    assert got['status']=='DIAGNOSTIC_DATA_ONLY_RECEIPT_VERIFIED_NOT_FINANCIAL_AUTHORITY'
    assert got['paper_execution_authorized'] is False
    raw=(tmp_path/('receipt-'+'b'*32+'.json')).read_bytes()
    assert b'per_symbol_quote_diagnostics' in raw
    assert b'FAKE-' not in raw and b'100.01' not in raw
    with pytest.raises(FileExistsError):
        receipts.write_receipt(packet,['MSFT','SPY'],'b'*32,root=tmp_path)


@pytest.mark.parametrize('change',[
    {'MSFT':{'received':1,'accepted':1,'rejected':0,'fresh_callbacks':1}},
    {'MSFT':{'received':1,'accepted':1,'rejected':1,'fresh_callbacks':0}},
    {'SPY':{'received':1,'accepted':0,'rejected':1,'fresh_callbacks':1}},
    {'SPY':{'received':1,'accepted':True,'rejected':0,'fresh_callbacks':1}},
    {'MSFT':{'received':-1,'accepted':0,'rejected':0,'fresh_callbacks':0}},
    {'TSLA':{'received':1,'accepted':0,'rejected':1,'fresh_callbacks':0}},
])
def test_malformed_symbol_diagnostics_cannot_be_admitted(change):
    data={'authenticated':True,'subscribed':True,'quote_count':1,
          'fresh_quote_observed_during_connection':True,
          'result':{'connection':'DISCONNECTED'},
          'per_symbol_quote_diagnostics':{
              'MSFT':{'received':0,'accepted':0,'rejected':0,'fresh_callbacks':0},
              'SPY':{'received':1,'accepted':1,'rejected':0,'fresh_callbacks':1}}}
    data['per_symbol_quote_diagnostics'].update(change)
    with pytest.raises(IEXRefused,match='INVALID_PER_SYMBOL_DIAGNOSTICS'):
        probe.admit_result(data,observed_symbols={'SPY'},observed_count=1,
                           requested_symbols=['MSFT','SPY'])


def test_old_success_receipt_without_diagnostics_remains_readable(tmp_path):
    # V1 receipts already written on November 9 must not be mutated/invalidated.
    packet={'schema':'ATLAS_IEX_BOUNDED_DATA_ONLY_PROBE_V1',
            'status':'BOUNDED_FRESH_IEX_OBSERVED_NOT_FINANCIAL_AUTHORITY',
            'authenticated':True,'subscribed':True,'quote_count':2,
            'fresh_quote_observed_during_connection':True,
            'observed_symbols':['SPY'],'callback_quote_count':1,
            'connection_closed':True,'single_exchange_not_nbbo':True,
            'continuous_executable_prices_verified':False,
            'provider_rights_independently_accepted':False,
            'paper_fill_authorized':False,'live_order_authorized':False}
    got=receipts.write_receipt(packet,['MSFT','SPY'],'c'*32,root=tmp_path)
    assert got['observed_symbols']==['SPY']
    assert got['paper_execution_authorized'] is False
