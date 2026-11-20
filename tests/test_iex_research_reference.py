"""Synthetic IEX -> existing free research, no socket or financial publication."""
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from app.investment.alpaca_iex import IEXFeed, IEXRefused
from app.investment.enums import DataQuality
from app.investment.free_research_providers import FreeResearchBundle
from app.services.quality_dips_iex_input import IEXPaperQuotes
from test_alpaca_iex import authority, message
from test_free_research_pipeline import NOW, client, facts
from test_historical_earnings_valuation import evidence


def setup(symbol='MSFT',kind='STOCK'):
    now=[NOW.timestamp()+.5]
    feed=IEXFeed([symbol],clock=lambda:now[0])
    feed.receive('[{"T":"success","msg":"authenticated"}]')
    feed.receive(json.dumps([{'T':'subscription','quotes':[symbol]}]))
    feed.receive(json.dumps([message(S=symbol,t=NOW.isoformat().replace('+00:00','Z'))]))
    instrument={'symbol':symbol,'instrument_id':'SYNTHETIC-'+symbol,'asset_class':kind,'currency':'USD',
                'units':'SHARES','fractional':True,'long_supported':True,'rules_revision':'SYNTHETIC'}
    port=IEXPaperQuotes(feed=feed,execution_authority=authority(instrument,{'is_open':True}))
    return port,feed,now,instrument


@pytest.mark.parametrize('symbol,kind',[('MSFT','STOCK'),('SPY','ETF')])
def test_accepted_ask_reference_keeps_source_and_never_issues_financial_frame(symbol,kind):
    port,feed,now,instrument=setup(symbol,kind)
    before=feed.snapshot();value=port.research_reference_price(symbol,instrument=instrument)
    assert value.value==100.1 and value.quality==DataQuality.FRESH
    assert value.effective_timestamp==NOW and value.retrieved_at==datetime.fromtimestamp(now[0],UTC)
    proof=json.loads(value.notes)
    assert proof['exact_ask']=='100.1' and proof['basis']=='ASK_REFERENCE_NOT_FILL'
    assert proof['financial_execution_authorized'] is False and proof['scope']=='SINGLE_EXCHANGE_NOT_NBBO'
    assert proof['instrument_id']==instrument['instrument_id'] and proof['source_ns']==int(NOW.timestamp())*10**9
    assert feed.snapshot()==before and port._sequence==0 and port._issued_frame is None and port._issued_shutdown is None


@pytest.mark.parametrize('damage',['authority','permission','closed','stale','disconnect','missing_quote','foreign_symbol','foreign_currency','no_identity','bad_units'])
def test_invalid_reference_never_falls_back_to_a_historical_close(damage):
    port,feed,now,instrument=setup()
    if damage=='authority':port.authority=None
    elif damage=='permission':port.authority=authority(instrument,{'is_open':True},valid=False)
    elif damage=='closed':port.authority=authority(instrument,{'is_open':False})
    elif damage=='stale':now[0]+=6
    elif damage=='disconnect':feed.disconnect()
    elif damage=='missing_quote':feed.quotes.clear()
    elif damage=='foreign_symbol':instrument['symbol']='OTHER'
    elif damage=='foreign_currency':instrument['currency']='USDC'
    elif damage=='no_identity':instrument.pop('instrument_id')
    elif damage=='bad_units':instrument['units']='CONTRACTS'
    with pytest.raises(IEXRefused):port.research_reference_price('MSFT',instrument=instrument)
    assert port._issued_frame is None and port._sequence==0


def test_changed_quote_cut_refuses_instead_of_blending_evidence():
    port,feed,_,instrument=setup();original=port.quote;calls=[]
    def change(value):
        result=original(value);calls.append(1)
        if len(calls)==1:feed.receive(json.dumps([message(bp=100.1,ap=100.2,t=(NOW+timedelta(milliseconds=200)).isoformat().replace('+00:00','Z'))]))
        return result
    port.quote=change
    with pytest.raises(IEXRefused,match='CHANGED'):port.research_reference_price('MSFT',instrument=instrument)
    assert port._issued_frame is None


def test_revocation_at_final_lease_refuses():
    port,_,_,instrument=setup();calls=[]
    @contextmanager
    def lease(request,now):
        calls.append(1)
        data={'verified':len(calls)==1,'instrument':instrument,'feed_id':'ALPACA_IEX_L1_V1','round_lot_shares':100,
            'market_status':'TRADING','entitlement_id':'SYNTHETIC','calendar':{'is_open':True},'clock_uncertainty_seconds':'0'}
        from app.investment.alpaca_iex import FEED
        data['feed_id']=FEED
        yield SimpleNamespace(snapshot=data,check=lambda p,t:len(calls)==1)
    port.authority=SimpleNamespace(lease=lease)
    with pytest.raises(IEXRefused):port.research_reference_price('MSFT',instrument=instrument)
    assert len(calls)==2 and port._issued_frame is None


def test_changed_authority_refuses_even_when_the_quote_is_identical():
    port,_,_,instrument=setup();original=port.quote
    def change(value):
        packet=original(value)
        port.authority=authority(instrument,{'is_open':True})
        return packet
    port.quote=change
    with pytest.raises(IEXRefused):port.research_reference_price('MSFT',instrument=instrument)


def test_excessive_physical_clock_uncertainty_does_not_become_fresh_research():
    port,_,_,instrument=setup();original=port.authority.lease
    @contextmanager
    def uncertain(request,now):
        with original(request,now) as lease:
            lease.snapshot['clock_uncertainty_seconds']='1.001'
            yield lease
    port.authority=SimpleNamespace(lease=uncertain)
    with pytest.raises(IEXRefused,match='CLOCK_UNCERTAINTY'):port.research_reference_price('MSFT',instrument=instrument)


def test_existing_free_bundle_uses_current_reference_for_ratios_and_rejects_disconnect(tmp_path):
    port,feed,now,instrument=setup();packet=evidence()
    def response(url):
        if '/assets/' in url:return {'symbol':'MSFT','id':instrument['instrument_id'],'class':'us_equity','status':'active','tradable':True,'fractionable':True,'exchange':'NASDAQ'}
        if '/bars?' in url:
            page='page_token' in parse_qs(urlsplit(url).query);bars=packet['prices']['bars']
            return {'symbol':'MSFT','bars':bars[1000:] if page else bars[:1000],'next_page_token':None if page or len(bars)<=1000 else 'next'}
        if '/calendar?' in url:return packet['calendar']
        if 'company_tickers' in url:return {'0':{'cik_str':789019,'ticker':'MSFT'}}
        return facts()
    c,clock,calls,_=client(tmp_path,response=response)
    clock[0]=datetime.fromtimestamp(now[0],UTC)
    bundle=FreeResearchBundle(client=c,now=lambda:clock[0],
        reference_price=lambda symbol:port.research_reference_price(symbol,instrument=instrument))
    value=bundle.load('MSFT')
    assert value['price'].value==100.1 and value['valuation']['pe'].value==pytest.approx(1001/46)
    assert value['paper_eligible'] is False and not value['valuation']['target_mean_price'].availability
    count=len(calls);feed.disconnect()
    with pytest.raises(IEXRefused):bundle.load('MSFT')
    assert len(calls)==count and all('/orders' not in url for url,_ in calls)
