"""Synthetic SEC/Alpaca source acceptance; never operational financial authority."""
import asyncio
import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.investment.enums import AssetType, DataQuality
from app.investment.free_research_providers import (
    FreeResearchBundle,
    calendar_sessions,
    daily_bars,
    read_only_ingest,
)
from app.investment.free_research_transport import FreeResearchClient, ResearchRefused
from app.investment.models import MeasuredValue
from app.investment.quality_dips_v2_valuation import build_normalization_window
from app.investment.sec_edgar_research import normalize_companyfacts, valuation
from app.investment.universe import InvestmentUniverse, UniverseEntry

NOW=datetime(2026,10,29,14,0,tzinfo=UTC)
CONTACT='ProjectAtlas/1.0 synthetic-test@example.invalid'
SEC='https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json'


def facts():
    def duration(vals):
        periods=[('2025-01-01','2025-09-30'),('2025-01-01','2025-12-31'),
                 ('2026-01-01','2026-03-31'),('2026-01-01','2026-06-30'),('2026-01-01','2026-09-30')]
        return {'units':{'USD':[{'start':start,'end':end,'filed':'2026-10-20',
            'val':value,'form':'10-K' if end.endswith('12-31') else '10-Q','accn':'SYNTHETIC-'+str(i)}
            for i,((start,end),value) in enumerate(zip(periods,vals,strict=True))]}}
    f={name:duration(values) for name,values in {
        'Revenues':[300,400,110,230,360],'NetIncomeLoss':[30,40,11,23,36],
        'NetCashProvidedByUsedInOperatingActivities':[30,40,12,25,39],
        'PaymentsToAcquirePropertyPlantAndEquipment':[6,8,2,5,9],
        'GrossProfit':[150,200,55,115,180],'OperatingIncomeLoss':[60,80,22,46,72]}.items()}
    for name,value,unit in [('CommonStockSharesOutstanding',10,'shares'),
            ('CashCashEquivalentsAndShortTermInvestments',100,'USD'),('ShortTermBorrowings',0,'USD'),
            ('LongTermDebtCurrent',5,'USD'),('LongTermDebtNoncurrent',20,'USD')]:
        f[name]={'units':{unit:[{'end':'2026-09-30','filed':'2026-10-20','val':value,'form':'10-Q','accn':'SYNTHETIC-BALANCE'}]}}
    return {'cik':789019,'facts':{'us-gaap':f}}


def normalized(payload=None, now=NOW):
    return normalize_companyfacts(payload or facts(),cik='0000789019',now=now,retrieved_at=now)


def test_ttm_ytd_differences_and_cost_cashflow_are_exact_and_not_double_counted():
    f=normalized()
    assert f['revenue'].value==460 and f['earnings'].value==46
    assert f['operating_cash_flow'].value==49 and f['free_cash_flow'].value==38
    assert f['total_debt'].value==25 and f['cash'].value==100
    assert f['gross_margin'].value==.5 and f['net_margin'].value==.1
    assert not f['eps'].availability
    proof=json.loads(f['revenue'].notes)
    assert proof['period_start']=='2025-10-01' and proof['period_end']=='2026-09-30'
    assert proof['exact_decimal']=='460' and proof['basis']=='TTM_RECONCILED'


@pytest.mark.parametrize('damage',['quarter','capex','shares','debt_component','currency'])
def test_missing_facts_never_become_zero_or_unsupported_estimates(damage):
    p=facts();f=p['facts']['us-gaap']
    if damage=='quarter':f['Revenues']['units']['USD'].pop(3)
    if damage=='capex':del f['PaymentsToAcquirePropertyPlantAndEquipment']
    if damage=='shares':del f['CommonStockSharesOutstanding']
    if damage=='debt_component':del f['ShortTermBorrowings']
    if damage=='currency':f['Revenues']['units']['EUR']=f['Revenues']['units'].pop('USD')
    result=normalized(p)
    key={'quarter':'revenue','capex':'free_cash_flow','shares':'shares_outstanding','debt_component':'total_debt','currency':'revenue'}[damage]
    assert not result[key].availability and result[key].value is None


def test_conflicting_same_period_and_direct_derived_quarter_refuse():
    p=facts();rows=p['facts']['us-gaap']['Revenues']['units']['USD']
    rows.append({**rows[-1],'val':999})
    with pytest.raises(ResearchRefused,match='CONFLICT'):normalized(p)
    p=facts();rows=p['facts']['us-gaap']['Revenues']['units']['USD']
    rows.append({**rows[-1],'start':'2026-07-01','val':999})
    with pytest.raises(ResearchRefused,match='CONFLICT'):normalized(p)


@pytest.mark.parametrize('damage',['issuer','receipt_future','future_filing','stale'])
def test_identity_future_and_stale_evidence_are_not_relabelled(damage):
    p=facts()
    if damage=='issuer':
        p['cik']=1
        with pytest.raises(ResearchRefused):normalized(p)
    elif damage=='receipt_future':
        with pytest.raises(ResearchRefused):normalize_companyfacts(p,cik='0000789019',now=NOW,retrieved_at=NOW+timedelta(seconds=1))
    elif damage=='future_filing':
        for row in p['facts']['us-gaap']['Revenues']['units']['USD']:row['filed']='2027-01-01'
        assert not normalized(p)['revenue'].availability
    else:
        assert normalized(p,now=NOW+timedelta(days=60))['revenue'].quality==DataQuality.STALE


def test_observed_negative_cashflow_is_preserved_not_zeroed():
    p=facts()
    for r in p['facts']['us-gaap']['NetCashProvidedByUsedInOperatingActivities']['units']['USD']:r['val']=-r['val']
    f=normalized(p)
    assert f['operating_cash_flow'].value==-49 and f['free_cash_flow'].value==-60


def test_ratio_derivation_does_not_invent_normalization_targets():
    f=normalized();price=MeasuredValue.of(20,source='ALPACA_IEX',timestamp=NOW,retrieved_at=NOW)
    values=valuation(f,price,now=NOW)
    assert values['pe'].value==pytest.approx(200/46)
    assert values['ps'].value==pytest.approx(200/460)
    assert values['fcf_yield'].value==.19
    assert all(not values[name].availability for name in ('forward_pe','pb','ev_ebitda','target_low_price','target_mean_price','target_high_price'))
    assert build_normalization_window([])['complete'] is False
    f['earnings'].quality=DataQuality.STALE
    assert not valuation(f,price,now=NOW)['pe'].availability


def client(tmp_path, *, response=None, max_attempts=12, contact=CONTACT):
    now=[NOW];calls=[];ticks=[0.]
    def fetch(url,headers,timeout,maximum):
        calls.append((url,dict(headers)))
        value=response(url) if callable(response) else response or {'ok':True}
        return json.dumps(value).encode()
    c=FreeResearchClient(cache_root=tmp_path/'cache',now=lambda:now[0],sec_user_agent=contact,
        credentials=SimpleNamespace(key='SYNTHETIC_KEY',secret='SYNTHETIC_SECRET'),
        fetch=fetch,max_attempts=max_attempts,monotonic=lambda:ticks[0],sleep=lambda n:ticks.__setitem__(0,ticks[0]+n))
    return c,now,calls,ticks


def test_cache_reuse_rate_budget_provenance_and_no_secrets(tmp_path):
    c,now,calls,ticks=client(tmp_path)
    first,receipt=c.get(SEC,ttl=60)
    assert c.get(SEC,ttl=60)==(first,receipt) and len(calls)==1
    now[0]+=timedelta(seconds=61)
    c.get(SEC,ttl=60)
    assert len(calls)==2 and ticks[0]==.5
    text=next((tmp_path/'cache').glob('*.json')).read_text()
    assert receipt['domain']=='SYNTHETIC' and 'SYNTHETIC_SECRET' not in text and CONTACT not in text


@pytest.mark.parametrize('url',[SEC.replace('https:','http:'),'https://data.sec.gov/other',
    'https://paper-api.alpaca.markets/v2/orders','https://api.alpaca.markets/v2/assets/MSFT',
    'https://data.alpaca.markets/v2/stocks/MSFT/bars?feed=sip&timeframe=1Day&adjustment=raw&limit=1',
    'https://financialmodelingprep.com/stable/income-statement?apikey=x'])
def test_no_unapproved_hosts_paid_feeds_or_financial_routes(tmp_path,url):
    c,_,calls,_=client(tmp_path)
    with pytest.raises(ResearchRefused):c.get(url,ttl=10)
    assert not calls and not (tmp_path/'cache').exists()


@pytest.mark.parametrize('contact',[None,'ProjectAtlas [INSERT MY REAL EMAIL ADDRESS]','invalid'])
def test_sec_placeholder_or_missing_identity_refuses_before_network(tmp_path,contact):
    c,_,calls,_=client(tmp_path,contact=contact)
    with pytest.raises(ResearchRefused,match='CONTACT'):c.get(SEC,ttl=10)
    assert not calls


def test_all_failed_attempts_are_charged_no_retries(tmp_path):
    def fail(*args):raise ResearchRefused('RESEARCH_HTTP_429')
    c,_,calls,_=client(tmp_path,max_attempts=1,response=fail)
    with pytest.raises(ResearchRefused,match='429'):c.get(SEC,ttl=10)
    with pytest.raises(ResearchRefused,match='BUDGET'):c.get(SEC,ttl=10)
    assert c.attempted==1 and len(calls)==1


@pytest.mark.parametrize('damage',['hash','future','domain','pending'])
def test_corrupt_cache_future_receipt_or_partial_publication_never_falls_back(tmp_path,damage):
    c,_,calls,_=client(tmp_path);c.get(SEC,ttl=10)
    p=next((tmp_path/'cache').glob('*.json'));data=json.loads(p.read_text())
    if damage=='hash':data['sha256']='0'*64
    if damage=='future':data['retrieved_at']=(NOW+timedelta(days=1)).isoformat()
    if damage=='domain':data['domain']='TLS_PUBLIC_PROVIDER'
    if damage=='pending':(tmp_path/'cache'/'a.pending').write_text('interrupted')
    else:p.write_text(json.dumps(data))
    with pytest.raises(ResearchRefused):c.get(SEC,ttl=10)
    assert len(calls)==1


def bars():
    return {'symbol':'MSFT','bars':[{'t':'2026-10-28T04:00:00Z','o':10,'h':12,'l':9,'c':11,'v':100}], 'next_page_token':None}


@pytest.mark.parametrize('damage',['adjustment','duplicate','bad_ohlc','future_open','calendar'])
def test_historical_price_coverage_and_sessions(damage):
    raw=bars();adj=copy.deepcopy(raw)
    calendar=calendar_sessions([{'date':'2026-10-28','open':'09:30','close':'16:00'}])
    if damage=='adjustment':adj['bars']=[]
    if damage=='duplicate':raw['bars']*=2
    if damage=='bad_ohlc':raw['bars'][0]['h']=8
    if damage=='calendar':calendar={}
    if damage=='future_open':
        assert daily_bars(raw,adj,now=NOW-timedelta(days=1),retrieved_at=NOW-timedelta(days=1),calendar=calendar)==[]
    else:
        with pytest.raises(ResearchRefused):daily_bars(raw,adj,now=NOW,retrieved_at=NOW,calendar=calendar)


def test_complete_provider_bundle_feeds_existing_readonly_ingest_without_yahoo(tmp_path,monkeypatch):
    def response(url):
        if '/assets/' in url:return {'symbol':'MSFT','id':'SYNTHETIC-ASSET','class':'us_equity','status':'active','tradable':True,'fractionable':True,'exchange':'NASDAQ'}
        if '/bars?' in url:return bars()
        if '/calendar?' in url:return [{'date':'2026-10-28','open':'09:30','close':'16:00'}]
        if 'company_tickers' in url:return {'0':{'cik_str':789019,'ticker':'MSFT','title':'Synthetic'}}
        return facts()
    c,_,calls,_=client(tmp_path,response=response)
    b=FreeResearchBundle(client=c,now=lambda:NOW)
    value=b.load('MSFT')
    assert value['fundamentals']['revenue'].value==460 and value['paper_eligible'] is False
    assert value['price'].quality==DataQuality.STALE and 'NOT_EXECUTABLE' in value['price'].source
    assert len(value['bars'])==1 and all(not value['valuation'][k].availability for k in ('target_low_price','target_mean_price','target_high_price'))
    from app.investment import ingest
    monkeypatch.setattr(ingest,'YFinanceClient',lambda:pytest.fail('Yahoo fallback'))
    universe=InvestmentUniverse([UniverseEntry('MSFT',asset_type=AssetType.STOCK)])
    reader=read_only_ingest(bundle=b,universe=universe,history_root=tmp_path/'history')
    snapshot=asyncio.run(reader.ingest_symbol(universe.get('MSFT')))
    assert snapshot.fundamentals['revenue'].value==460 and reader.read_only and not reader.persist
    assert not (tmp_path/'history').exists() and len(calls)==6


def test_concurrent_same_client_cache_miss_has_only_one_publication(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    c,_,calls,_=client(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:c.get(SEC,ttl=60),range(8)))
    assert all(r==results[0] for r in results) and len(calls)==1
    assert len(list((tmp_path/'cache').iterdir()))==1


def test_price_research_does_not_depend_on_missing_sec_identity(tmp_path):
    def response(url):
        if '/assets/' in url:return {'symbol':'MSFT','id':'SYNTHETIC-ASSET','class':'us_equity','status':'active','tradable':True,'fractionable':True,'exchange':'NASDAQ'}
        if '/calendar?' in url:return [{'date':'2026-10-28','open':'09:30','close':'16:00'}]
        return bars()
    c,_,calls,_=client(tmp_path,response=response,contact=None)
    b=FreeResearchBundle(client=c,now=lambda:NOW)
    assert len(b.load('MSFT',prices_only=True)['bars'])==1
    with pytest.raises(ResearchRefused,match='CONTACT'):b.load('MSFT')
    assert len(calls)==4 and all('sec.gov' not in url for url,_ in calls)


def test_partial_write_leaves_a_refusing_cache_and_does_not_replay_network(tmp_path,monkeypatch):
    import app.investment.free_research_transport as module
    c,_,calls,_=client(tmp_path)
    def interrupted(*args):raise OSError('synthetic interruption')
    monkeypatch.setattr(module.os,'replace',interrupted)
    with pytest.raises(OSError):c.get(SEC,ttl=60)
    with pytest.raises(ResearchRefused,match='INCOMPLETE'):c.get(SEC,ttl=60)
    assert len(calls)==1


def test_incomplete_pagination_refuses_instead_of_claiming_complete_history(tmp_path):
    def response(url):
        if '/assets/' in url:return {'symbol':'MSFT','id':'SYNTHETIC-ASSET','class':'us_equity','status':'active','tradable':True,'fractionable':True,'exchange':'NASDAQ'}
        return {**bars(),'next_page_token':'repeated-token'}
    c,_,_,_=client(tmp_path,response=response)
    with pytest.raises(ResearchRefused,match='PAGINATION'):FreeResearchBundle(client=c,now=lambda:NOW).load('MSFT',prices_only=True)


def test_readonly_ingest_failure_keeps_actual_provider_label_not_yahoo(tmp_path,monkeypatch):
    from app.investment import ingest
    from app.investment.providers import NullProvider
    class Price:
        name='ALPACA_BASIC_IEX'
        async def get_price(self,*args):raise ResearchRefused('SYNTHETIC_PRICE_REFUSAL')
        async def get_daily_ohlcv(self,*args,**kwargs):return []
    class Empty(NullProvider):
        async def get_all(self,*args):return {}
    monkeypatch.setattr(ingest,'YFinanceClient',lambda:pytest.fail('Yahoo fallback'))
    universe=InvestmentUniverse([UniverseEntry('MSFT',asset_type=AssetType.STOCK)])
    reader=ingest.InvestmentIngest(universe=universe,price=Price(),fundamentals=Empty(),valuation=Empty(),
        history_root=tmp_path,persist=False,read_only=True)
    assert asyncio.run(reader.ingest_symbol(universe.get('MSFT'))).price.source=='ALPACA_BASIC_IEX'


def test_synthetic_cache_cannot_be_relabelled_as_operational_tls(tmp_path):
    c,_,calls,_=client(tmp_path)
    c.domain='TLS_PUBLIC_PROVIDER'
    with pytest.raises(ResearchRefused,match='COMPONENT_CHANGED'):c.get(SEC,ttl=1)
    assert not calls


def test_reserved_contact_is_only_permitted_for_synthetic_tests(tmp_path):
    cache_root=Path('D:/Work/Project Atlas/logs/research')/('reserved-contact-test-'+uuid4().hex)
    assert not cache_root.exists()
    c=FreeResearchClient(cache_root=cache_root,now=lambda:NOW,sec_user_agent=CONTACT)
    with pytest.raises(ResearchRefused,match='CONTACT'):c.get(SEC,ttl=10)
    assert c.attempted==0 and not c.root.exists()


def test_missing_ttm_bridge_does_not_fall_back_to_an_older_reporting_cut():
    p=facts()
    for value in p['facts']['us-gaap'].values():
        for rows in value.get('units',{}).values():
            rows[:]=[r for r in rows if r.get('end')!='2026-06-30']
    f=normalized(p)
    assert not f['revenue'].availability and not f['free_cash_flow'].availability


def test_actual_scanner_and_original_board_keep_missing_normalization_ineligible(tmp_path,monkeypatch):
    from app.investment import scan
    from app.investment.scan_settings import ScanSettings
    from app.services.quality_dips_research_only import project_explicit_research
    def response(url):
        if '/assets/' in url:return {'symbol':'MSFT','id':'SYNTHETIC-ASSET','class':'us_equity','status':'active','tradable':True,'fractionable':True,'exchange':'NASDAQ'}
        if '/bars?' in url:return bars()
        if '/calendar?' in url:return [{'date':'2026-10-28','open':'09:30','close':'16:00'}]
        if 'company_tickers' in url:return {'0':{'cik_str':789019,'ticker':'MSFT','title':'Synthetic'}}
        return facts()
    c,_,_,_=client(tmp_path,response=response)
    bundle=FreeResearchBundle(client=c,now=lambda:NOW)
    universe=InvestmentUniverse([UniverseEntry('MSFT',asset_type=AssetType.STOCK)])
    ingest=read_only_ingest(bundle=bundle,universe=universe,history_root=tmp_path/'history')
    scanner=scan.InvestmentScanner(settings=ScanSettings(enabled=False,persist=False,notify_discord=False,
        inter_symbol_delay_seconds=0,max_retries=0),universe=universe,ingest=ingest,history_root=tmp_path/'history',
        persist=False,research_only=True)
    monkeypatch.setattr(scanner,'_paper_book',lambda:pytest.fail('Financial writer invoked'))
    monkeypatch.setattr(scanner,'_port',lambda:pytest.fail('Legacy financial records accessed'))
    result=asyncio.run(scanner.run_once(now=NOW))
    assert result.evaluated==1 and result.failed==0
    board=project_explicit_research([result.observations[0].research.as_dict()])
    projected=board[0]['quality_dips_v2']
    assert projected['valuation_source_count']==0
    assert projected['entry_ladder']['ready'] is False
    assert projected['evidence_gate']['gate_passed'] is False
    assert not (tmp_path/'history').exists()


def test_zero_shares_are_not_an_eligible_market_cap_basis():
    p=facts();p['facts']['us-gaap']['CommonStockSharesOutstanding']['units']['shares'][0]['val']=0
    assert normalized(p)['shares_outstanding'].availability is False


def test_boolean_duration_is_not_a_declared_request_budget(tmp_path):
    with pytest.raises(ResearchRefused,match='BUDGET'):
        FreeResearchClient(cache_root=tmp_path,now=lambda:NOW,seconds=True)


def test_late_response_or_expired_cache_lease_cannot_publish_success(tmp_path):
    ticks=[0.]
    def slow(*args):ticks[0]=61;return b'{"late":true}'
    c=FreeResearchClient(cache_root=tmp_path/'cache',now=lambda:NOW,sec_user_agent=CONTACT,
        fetch=slow,monotonic=lambda:ticks[0],sleep=lambda _:None,seconds=60)
    with pytest.raises(ResearchRefused,match='TIME_BUDGET'):c.get(SEC,ttl=60)
    assert c.attempted==1 and not c.root.exists()
    c,_,calls,clock=client(tmp_path)
    c.get(SEC,ttl=60);clock[0]=61
    with pytest.raises(ResearchRefused,match='TIME_BUDGET'):c.get(SEC,ttl=60)
    assert len(calls)==1


@pytest.mark.parametrize('maximum',[5,1024])
def test_native_transport_stream_is_bounded_and_closed(monkeypatch,maximum):
    import app.investment.free_research_transport as module
    raw=b'{"ok":true}';closed=[]
    class Response:
        status=200
        def __init__(self):self.left=raw
        def __enter__(self):return self
        def __exit__(self,*args):closed.append(True)
        def read1(self,limit):
            block,self.left=self.left[:limit],self.left[limit:]
            return block
    class Opener:
        def open(self,request,timeout):
            assert request.method=='GET' and timeout>0
            return Response()
    monkeypatch.setattr(module,'build_opener',lambda handler:Opener())
    if maximum==5:
        with pytest.raises(ResearchRefused,match='CAPACITY'):FreeResearchClient._get(SEC,{},2,maximum)
    else:
        assert FreeResearchClient._get(SEC,{},2,maximum)==raw
    assert closed==[True]
