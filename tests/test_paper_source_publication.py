"""Actual adapter caches/parser and original research; all trust explicitly synthetic."""
import copy
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from app.adapters.hyperliquid import HyperliquidAdapter, _paper_execution_observation
from app.services.paper_financial_replay import digest
from app.services.paper_source_publication import (
    PerpSourcePublication,
    QualityDipsSourcePublication,
    parse_public_trades,
)
from test_hyperliquid_public_book import inputs
from test_quality_dips_autonomous_paper import candidate, setup


class Archive:
    """Synthetic CAS archive, NOT native custody or operational source authority."""
    def __init__(self): self.pin={'revision':0}; self.packet=None; self.fail=False
    def current(self): return copy.deepcopy(self.pin)
    def publish(self, *, expected, packet, sources):
        assert expected==self.pin
        if self.fail: raise OSError('SYNTHETIC_SOURCE_PUBLICATION_FAILURE')
        self.packet=copy.deepcopy(packet);self.pin={'revision':packet['revision'],'digest':digest(packet)}
    def read(self,pin):
        assert pin==self.pin
        return copy.deepcopy(self.packet)


def auth():
    a=SimpleNamespace(valid=True)
    for name in ('verify_components','verify_publication','verify_head','verify_current','verify_cache',
                 'verify_research','verify_settlement','verify_maker'):
        setattr(a,name,lambda *args:a.valid)
    return a


def perp_source():
    now=[100];a=auth();archive=Archive();adapter=HyperliquidAdapter();adapter._connected=True
    metadata,book=inputs()
    parsed=_paper_execution_observation('BTC',metadata,book,99999,100001)
    adapter._cache_paper('books','BTC',{'parsed':parsed,'metadata':metadata,'book':book})
    adapter._cache_paper('markets',None,[{'symbol':'BTC','price':100,'volume_24h':20000000,'open_interest':8000000,
        'funding_rate':-.001,'timestamp':datetime.fromtimestamp(100,UTC).isoformat()}])
    adapter._cache_paper('candles','BTC',{'interval':'5m','observed_at_ms':100000,'rows':[{'close':100,'time':100000}]})
    control={'state':{'orders':{}}};orders=SimpleNamespace(snapshot=lambda:copy.deepcopy(control))
    settlements=SimpleNamespace(read=lambda symbol,at:None);maker=SimpleNamespace(read=lambda key:None)
    lifecycle=SimpleNamespace(read_current=list)
    p=PerpSourcePublication(adapter=adapter,orders=orders,settlements=settlements,maker=maker,lifecycle=lifecycle,
        source_id='EXPLICIT_SYNTHETIC_PROVIDER',authority=a,archive=archive,clock=lambda:now[0])
    return SimpleNamespace(**locals())


def test_actual_adapter_cache_read_publication_does_not_connect_or_refresh(monkeypatch):
    s=perp_source();before=s.adapter.paper_source_snapshot()
    monkeypatch.setattr(s.adapter,'_post',lambda *args:pytest.fail('provider called by cache read'))
    packet=s.p.capture()
    assert packet['books']['BTC']['bid']=='100' and not packet['maker_fills'] and not packet['oracles']
    assert s.p.read_cut()==packet and s.adapter.paper_source_snapshot()==before
    assert s.archive.pin['revision']==1


@pytest.mark.parametrize('symbol',['BTC','ETH','SOL'])
def test_selected_perp_instruments_use_their_original_metadata_mapping(symbol):
    s=perp_source();metadata,book=inputs();metadata[0]['universe'][0]['name']=symbol;book['coin']=symbol
    parsed=_paper_execution_observation(symbol,metadata,book,99999,100001)
    s.adapter._cache_paper('books',symbol,{'parsed':parsed,'metadata':metadata,'book':book})
    row={**s.adapter.paper_source_snapshot()['facts']['markets'][0],'symbol':symbol}
    s.adapter._cache_paper('markets',None,[row])
    s.adapter._cache_paper('candles',symbol,{'interval':'5m','observed_at_ms':100000,'rows':[{'close':100,'time':100000}]})
    s.a.verify_components=lambda c:set(c)== {'lane','source_id','archive','clock','authority','adapter','orders','settlements','maker','lifecycle'}
    assert set(s.p.capture()['books'])=={symbol}


@pytest.mark.parametrize('damage',['authority','disconnect','book','candle','market','component','archive'])
def test_source_refusal_before_publication(damage):
    s=perp_source()
    if damage=='authority':s.a.valid=False
    elif damage=='disconnect':s.adapter._connected=False
    elif damage=='book':s.adapter._paper_cache['books']['BTC']['parsed']['bid']='0.01'
    elif damage=='candle':s.adapter._paper_cache['candles']['BTC']['observed_at_ms']=-999999
    elif damage=='market':s.adapter._paper_cache['markets'][0]['timestamp']='1970-01-01T00:00:01+00:00'
    elif damage=='component':s.p.adapter=HyperliquidAdapter()
    else:s.archive.fail=True
    with pytest.raises((ValueError,OSError)):s.p.capture()
    assert s.archive.pin=={'revision':0}


def trade_frame():
    return {'channel':'trades','data':[{'coin':'BTC','side':'A','px':'100','sz':'2','time':100000,'tid':5,'hash':'synthetic-trade'}]}


@pytest.mark.parametrize('damage',['none','duplicate','side','stale','mixed','nonfinite'])
def test_public_trade_parser_never_claims_complete_queue_or_execution(damage):
    f=trade_frame()
    if damage=='duplicate':f['data'].append(copy.deepcopy(f['data'][0]))
    elif damage=='side':f['data'][0]['side']='SELL'
    elif damage=='stale':f['data'][0]['time']=1
    elif damage=='mixed':f['data'].append({**f['data'][0],'coin':'ETH'})
    elif damage=='nonfinite':f['data'][0]['sz']='NaN'
    if damage!='none':
        with pytest.raises(ValueError):parse_public_trades(f,received_ms=100001)
    else:
        row=parse_public_trades(f,received_ms=100001)
        assert row['rows'][0]['side']=='A' and not row['complete_window'] and not row['financial_execution_authorized']


def test_current_source_restart_rollback_and_stale_refusal():
    s=perp_source();packet=s.p.capture();old=s.archive.current()
    s.p.capture();s.archive.pin=old;s.archive.packet=packet
    with pytest.raises(ValueError,match='ROLLBACK'):s.p.read_cut()
    s.now[0]=106
    with pytest.raises(ValueError):s.p.read_cut()


def test_cache_generation_change_or_disconnect_refuses_old_publication():
    s=perp_source();s.p.capture()
    s.adapter._cache_paper('trades','BTC',{'unacknowledged':'fixture'})
    with pytest.raises(ValueError,match='REPUBLICATION'):s.p.read_cut()
    s.p.capture();s.adapter._connected=False
    with pytest.raises(ValueError,match='REPUBLICATION'):s.p.read_cut()


@pytest.mark.asyncio
async def test_unaccepted_trade_transport_refuses_before_socket(monkeypatch):
    import app.adapters.hyperliquid as module
    a=HyperliquidAdapter(paper_transport=SimpleNamespace(verify_subscription=lambda *args:False))
    a._ws_running=True
    monkeypatch.setattr(module.websockets,'connect',lambda *args,**kwargs:pytest.fail('Socket opened before authority'))
    with pytest.raises(module.hyperliquid_gate_registry.RequestGateRefused):await a._mids_loop()


@pytest.mark.asyncio
async def test_existing_ws_pump_routes_only_accepted_public_trades_and_invalidates_on_exit(monkeypatch):
    import time

    import app.adapters.hyperliquid as module
    observed=[];invalid=[];sent=[]
    transport=SimpleNamespace(verify_subscription=lambda *args:True,open_stream=lambda adapter:'SYNTHETIC_STREAM',
        observe_message=lambda stream,msg,at:{'fixture':'AUTHENTICATED_WINDOW'},invalidate_stream=invalid.append)
    adapter=HyperliquidAdapter(paper_transport=transport);adapter._ws_running=True
    frame=trade_frame();frame['data'][0]['time']=int(time.time()*1000)
    class WS:
        async def send(self,raw):
            import json
            sent.append(json.loads(raw))
        async def __aiter__(self):
            import json
            yield json.dumps(frame)
            observed.append(adapter.paper_source_snapshot()['facts']['trades'])
            adapter._ws_running=False
    class Context:
        async def __aenter__(self):return WS()
        async def __aexit__(self,*args):return False
    monkeypatch.setattr(module.websockets,'connect',lambda *args,**kwargs:Context())
    monkeypatch.setattr(adapter,'_consume_request',lambda kind:None)
    await adapter._mids_loop()
    assert [row['subscription']['type'] for row in sent]==['allMids','trades','trades','trades']
    assert observed[0]['BTC']['rows'][0]['tid']==5 and invalid==['SYNTHETIC_STREAM']
    assert adapter.paper_source_snapshot()['facts']['trades']=={}


def test_original_qd_board_and_candidate_adapter_publication(tmp_path):
    n=setup(tmp_path);b=candidate(n);a=auth();archive=Archive()
    raw={'board':b['board'],'observations':{b['instrument']['symbol']:b['observation']},'instruments':[b['instrument']],
         'quotes':{b['instrument']['symbol']:b['quote']},'publication':b['publication'],'monitors':{}}
    reader=SimpleNamespace(read_current=lambda:copy.deepcopy(raw))
    p=QualityDipsSourcePublication(research=reader,candidates=n.engine.candidates,source_id='SYNTHETIC_QD_ORIGINAL',authority=a,
        archive=archive,clock=lambda:n.now[0])
    before=copy.deepcopy(raw);packet=p.publish_scanner(b['board'],datetime.fromtimestamp(n.now[0],UTC).isoformat())
    assert packet['bundles']==[b] and raw==before and p.read_publication(.2)==packet
    a.valid=False
    with pytest.raises(ValueError):p.read_publication(.2)


def test_future_funding_cannot_be_relabelled_current_or_filled_from_current_oracle():
    from app.adapters.hyperliquid import _paper_funding_observation
    s=perp_source()
    p=_paper_funding_observation('BTC',[{'coin':'BTC','time':3600000,'fundingRate':'0.001','premium':'0'}],
        3600000,7200000,3600000,3600000)
    s.adapter._cache_paper('funding','BTC',{'parsed':p,'rows':[{'coin':'BTC','time':3600000,'fundingRate':'0.001','premium':'0'}],
        'started_ms':3600000})
    with pytest.raises(ValueError,match='FUTURE_FUNDING'):s.p.capture()


@pytest.mark.parametrize('damage',['none','queue','trade-id','quantity','side','authority'])
def test_maker_publication_binds_original_queue_to_actual_public_trade_rows(damage):
    s=perp_source()
    order={'order_id':'synthetic-order','symbol':'BTC','side':'LONG','created_at':98,'limit_price':'100',
           'source_digest':'synthetic-original-source','source_revision':1}
    s.control['state']['orders'][order['order_id']]={'state':'RESERVED','order':order}
    s.adapter.ingest_paper_trades(trade_frame(),received_ms=100001,continuity_receipt='EXPLICIT_SYNTHETIC_COMPLETE_WINDOW')
    trades=s.adapter.paper_source_snapshot()['facts']['trades']['BTC']
    book=copy.deepcopy(inputs()[1]);book['time']=98000
    queue={'book':book,'metadata':inputs()[0],'source_digest':order['source_digest'],'source_revision':1,
           'receipt':'EXPLICIT_SYNTHETIC_ORIGINAL_QUEUE'}
    proof={'schema':'SIMULATED_MAKER_QUEUE_FILL_V1','order_id':order['order_id'],'rested_at':98,
        'queue_ahead':'1.25','traded_quantity':'2','trade_price':'100','trade_at':100,
        'source_ref':digest({'queue':queue,'trades':trades})}
    value={'queue':queue,'proof':proof,'trade_ids':[[100000,5]]}
    if damage=='queue':proof['queue_ahead']='0'
    elif damage=='trade-id':value['trade_ids']=[[100000,6]]
    elif damage=='quantity':proof['traded_quantity']='3'
    elif damage=='side':order['side']='SHORT'
    elif damage=='authority':s.a.verify_maker=lambda *args:False
    s.maker.read=lambda key:copy.deepcopy(value)
    if damage!='none':
        with pytest.raises(ValueError):s.p.capture()
        assert s.archive.pin['revision']==0
    else:
        assert s.p.capture()['maker_fills'][order['order_id']]==proof


@pytest.mark.asyncio
async def test_real_adapter_public_observation_populates_cache_without_extra_requests(monkeypatch):
    from app.adapters import hyperliquid_gate_registry
    a=HyperliquidAdapter();a._client=object()
    payloads=list(inputs());calls=[]
    async def transport(request):calls.append(request);return payloads.pop(0)
    monkeypatch.setattr(a,'_post',transport)
    monkeypatch.setattr(hyperliquid_gate_registry,'require_gate',lambda:object())
    result=await a.paper_execution_observation('BTC',clock_ms=lambda:100001)
    assert a.paper_source_snapshot()['facts']['books']['BTC']['parsed']==result
    assert len(calls)==2 and not a.paper_source_snapshot()['connected']


@pytest.mark.parametrize('damage', ['expiry', 'pin-race', 'invalid-clock'])
def test_read_refuses_source_changed_during_authority_verification(damage):
    s = perp_source()
    s.p.capture()
    last = s.p.last
    if damage == 'expiry':
        s.now[0] = 105  # Exactly fresh at read start, expired at read completion.
        def verify(*args):
            s.now[0] = 106
            return True
        s.a.verify_current = verify
    elif damage == 'pin-race':
        def verify(*args):
            s.archive.pin['revision'] += 1
            return True
        s.a.verify_current = verify
    else:
        s.now[0] = 100.0  # Trusted UTC contract requires an exact integer, not a float.
    with pytest.raises(ValueError):
        s.p.read_current()
    assert s.p.last == last


def test_perp_cache_authority_cannot_return_a_publication_that_expired_during_check():
    s = perp_source()
    s.p.capture()
    s.now[0] = 105
    def verify(*args):
        s.now[0] = 106
        return True
    s.a.verify_cache = verify
    with pytest.raises(ValueError):
        s.p.read_cut()
