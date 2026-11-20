"""Approved recipe acceptance with synthetic statements, sources and calendars."""
from bisect import bisect_right
from copy import deepcopy
from datetime import UTC, date, datetime, time, timedelta
from decimal import getcontext

import pytest
from app.investment.enums import AssetType
from app.investment.free_research_providers import FreeResearchBundle, read_only_ingest
from app.investment.free_research_transport import ResearchRefused
from app.investment.historical_earnings_valuation import (
    METHOD,
    attach_historical_valuation,
    build_historical_valuation,
)
from app.investment.market_hours import ET, session_bounds
from app.investment.quality_dips_v2_valuation import build_normalization_window
from app.investment.universe import InvestmentUniverse, UniverseEntry
from app.services.paper_financial_replay import digest
from app.services.quality_dips_research_only import project_explicit_research
from test_free_research_pipeline import NOW, client, facts
from test_quality_dips_valuation_admission import current_row


def evidence():
    payload = facts(); quarters=[]; witnesses=[]; ends=[]
    for index in range(16):
        month = 2022*12+9+index*3
        year,m = divmod(month,12); start=date(year,m+1,1)
        following = date(year+1,1,1) if m == 9 else date(year,m+4,1)
        end=following-timedelta(days=1); filed=end+timedelta(days=20)
        row={'start':str(start),'end':str(end),'filed':str(filed),'val':'1',
             'form':'10-Q','accn':'SYNTHETIC-FILING-'+str(index)}
        quarters.append(row);ends.append(end)
        witnesses.append({'accession':row['accn'],'start':str(start),'end':str(end),
            'filed':str(filed),'eps':'1','share_basis':'SYNTHETIC-BASIS-A','filing_sha256':digest(row)})
    payload['facts']['us-gaap']['EarningsPerShareDiluted']={'units':{'USD/shares':quarters}}
    calendar=[]; prices=[]; basis={}; day=date(2022,10,1)
    while day <= NOW.date():
        bounds=session_bounds(datetime.combine(day,time(12),ET)) if day.year == 2026 else (
            (datetime.combine(day,time(9,30),ET),datetime.combine(day,time(16),ET)) if day.weekday()<5 else None)
        if bounds:
            calendar.append({'date':str(day),'open':'09:30','close':bounds[1].astimezone(ET).strftime('%H:%M')})
            if bounds[1] <= NOW:
                prices.append({'t':datetime.combine(day,time(),ET).astimezone(UTC).isoformat(),
                    'o':'80','h':'100','l':'40','c':'80','v':1000})
                basis[str(day)]='SYNTHETIC-BASIS-A'
        day+=timedelta(days=1)
    sessions=[date.fromisoformat(r['date']) for r in calendar]
    for index,end in enumerate(ends[3:]):
        anchor=sessions[bisect_right(sessions,end+timedelta(days=20))]
        record=next(r for r in prices if datetime.fromisoformat(r['t']).astimezone(ET).date()==anchor)
        record.update(o=str(4*(10+index)),h=str(4*(10+index)+1),
                      l=str(4*(10+index)-1),c=str(4*(10+index)))
    return {'schema':'QD_HISTORICAL_EARNINGS_INPUT_V1','method':METHOD,'domain':'SYNTHETIC',
        'instrument':{'symbol':'MSFT','asset_id':'SYNTHETIC-MSFT','cik':'0000789019','asset_class':'STOCK',
            'business_type':'NON_FINANCIAL_OPERATING_COMPANY_COMMON','currency':'USD','units':'SHARES'},
        'companyfacts':payload,'facts_received_at':NOW.isoformat(),
        'prices':{'symbol':'MSFT','bars':prices,'next_page_token':None},'calendar':calendar,
        'price_adjustment':'raw','filing_witnesses':witnesses,'price_basis':basis}


def verifier(packet, *, now):
    assert packet['domain']=='SYNTHETIC' and now==NOW
    return {'schema':'QD_HISTORICAL_EARNINGS_SOURCE_VERIFIED_V1','binding':digest(packet),
            'domain':'SYNTHETIC','scope':'RESEARCH_ONLY','verified':True,'receipt_id':'SYNTHETIC-NOT-OPERATIONAL'}


def calculate(packet=None, **kwargs):
    return build_historical_valuation(packet or evidence(),method=METHOD,now=NOW,verify_source=verifier,**kwargs)


def test_exact_nearest_rank_calculation_and_original_projection():
    packet=evidence();original=deepcopy(packet)
    result=calculate(packet)
    assert len(result['anchors'])==13 and result['current_eps_proxy']=='4'
    assert [r['value'] for r in result['valuation_sources']]==[52,64,76]
    assert result['eps_basis']=='SUM_OF_REPORTED_QUARTERLY_DILUTED_EPS'
    assert result['domain']=='SYNTHETIC' and not result['paper_eligible'] and not result['analyst_targets_generated']
    row=current_row();row.pop('valuation_sources');row['symbol']='MSFT';row['price']=40
    linked=attach_historical_valuation(row,packet,method=METHOD,now=NOW,verify_source=verifier)
    projection=project_explicit_research([linked],now=NOW)[0]['quality_dips_v2']
    assert projection['valuation_source_count']==3
    assert projection['quality_dips_v3']['fair_value_anchor']==64
    assert projection['quality_dips_v3']['entry_ladder']['levels'][0]['limit_price']==54.4
    assert packet==original and 'valuation_method_evidence' not in row


@pytest.mark.parametrize('damage',['no_verifier','bool_proof','foreign_binding','fixture_relabel','wrong_method','revocation'])
def test_missing_or_changed_source_acceptance_refuses(damage):
    packet=evidence();calls=[]
    def proof(p, *, now):
        calls.append(1);out=verifier(p,now=now)
        if damage=='bool_proof':return True
        if damage=='foreign_binding':out['binding']='0'*64
        if damage=='fixture_relabel':out['domain']='TLS_PUBLIC_PROVIDER'
        if damage=='revocation' and len(calls)>1:out['verified']=False
        return out
    with pytest.raises(ResearchRefused):
        build_historical_valuation(packet,method='WRONG' if damage=='wrong_method' else METHOD,now=NOW,
            verify_source=None if damage=='no_verifier' else proof)


@pytest.mark.parametrize('damage',['no_eps','negative_eps','missing_quarter','missing_cashflow','negative_cashflow',
    'old_filing','foreign_issuer','foreign_price','future_receipt','foreign_currency','etf','financial_firm',
    'no_witness','wrong_witness_value','duplicate_quarter','duplicate_witness','share_basis','price_basis','adjusted_price',
    'missing_price','extreme_multiple','dispersion','insufficient_anchors','ytd_only','partial_prices'])
def test_incomplete_conflicting_or_ineligible_evidence_never_emits_estimates(damage):
    packet=evidence();gaap=packet['companyfacts']['facts']['us-gaap']
    rows=gaap['EarningsPerShareDiluted']['units']['USD/shares']
    if damage=='no_eps':gaap.pop('EarningsPerShareDiluted')
    elif damage=='negative_eps':rows[-1]['val']='-4';packet['filing_witnesses'][-1]['eps']='-4'
    elif damage=='missing_quarter':rows.pop(-2)
    elif damage=='missing_cashflow':gaap.pop('NetCashProvidedByUsedInOperatingActivities')
    elif damage=='negative_cashflow':
        for r in gaap['NetCashProvidedByUsedInOperatingActivities']['units']['USD']:r['val']=-r['val']
    elif damage=='old_filing':
        # Source acquisition is recent, but the original statement remains old.
        for block in gaap.values():
            for records in block['units'].values():
                for row in records:row['filed']=str(date.fromisoformat(row['end'])+timedelta(days=1))
        # Make the latest reporting cut itself stale, without using a later receipt.
        for block in gaap.values():
            for records in block['units'].values():records[:]=[r for r in records if r['end']<'2026-09-01']
    elif damage=='foreign_issuer':packet['companyfacts']['cik']=1
    elif damage=='foreign_price':packet['prices']['symbol']='OTHER'
    elif damage=='future_receipt':packet['facts_received_at']=(NOW+timedelta(seconds=1)).isoformat()
    elif damage=='foreign_currency':packet['instrument']['currency']='EUR'
    elif damage=='etf':packet['instrument']['asset_class']='ETF'
    elif damage=='financial_firm':packet['instrument']['business_type']='FINANCIAL_FIRM'
    elif damage=='no_witness':packet['filing_witnesses'].pop(-1)
    elif damage=='wrong_witness_value':packet['filing_witnesses'][-1]['eps']='999'
    elif damage=='duplicate_quarter':rows.append(deepcopy(rows[-1]))
    elif damage=='duplicate_witness':packet['filing_witnesses'].append(deepcopy(packet['filing_witnesses'][-1]))
    elif damage=='share_basis':packet['filing_witnesses'][-1]['share_basis']='WRONG'
    elif damage=='price_basis':packet['price_basis']={}
    elif damage=='adjusted_price':packet['price_adjustment']='all'
    elif damage=='missing_price':packet['prices']['bars']=[]
    elif damage in ('extreme_multiple','dispersion'):
        for r in packet['prices']['bars']:
            day=datetime.fromisoformat(r['t']).astimezone(ET).date()
            if damage=='extreme_multiple':px='400'
            else:px='20' if day.year<2025 else '240'
            r.update(o=px,h=px,l=px,c=px)
    elif damage=='insufficient_anchors':rows[:]=rows[4:]
    elif damage=='ytd_only':
        for r in rows:r['start']=r['end'][:4]+'-01-01'
    elif damage=='partial_prices':packet['prices']['next_page_token']='not-complete'
    with pytest.raises((ResearchRefused,ValueError)):
        calculate(packet)


def test_no_method_mixing_or_other_security_row():
    with pytest.raises(ResearchRefused,match='UNMIXED'):
        attach_historical_valuation(current_row(),evidence(),method=METHOD,now=NOW,verify_source=verifier)
    row=current_row();row.pop('valuation_sources');row['symbol']='OTHER'
    with pytest.raises(ResearchRefused,match='SECURITY'):
        attach_historical_valuation(row,evidence(),method=METHOD,now=NOW,verify_source=verifier)


def test_deterministic_replay_despite_caller_decimal_context():
    packet=evidence();expected=calculate(packet);old=getcontext().prec
    try:
        getcontext().prec=6
        assert calculate(packet)==expected
    finally:getcontext().prec=old


def test_expiry_cannot_extend_underlying_fact_freshness():
    result=calculate()
    assert datetime.fromisoformat(result['expires_at'])<=NOW+timedelta(days=7)
    row=current_row();row.pop('valuation_sources');row['symbol']='MSFT'
    linked=attach_historical_valuation(row,evidence(),method=METHOD,now=NOW,verify_source=verifier)
    for source in linked['valuation_sources']:source['expires_at']=(NOW-timedelta(seconds=1)).isoformat()
    out=project_explicit_research([linked],now=NOW)[0]['quality_dips_v2']
    assert out['valuation_source_count']==0 and not out['entry_ladder']['ready']


def test_source_verifier_cannot_mutate_the_calculated_cut():
    packet=evidence();original=deepcopy(packet)
    def mutate(p, *, now):
        p['instrument']['asset_id']='SUBSTITUTED'
        return verifier(p,now=now)
    with pytest.raises(ResearchRefused,match='SOURCE_BINDING'):
        build_historical_valuation(packet,method=METHOD,now=NOW,verify_source=mutate)
    assert packet==original


def test_reported_loss_quarter_is_preserved_when_ttm_is_positive():
    packet=evidence()
    packet['companyfacts']['facts']['us-gaap']['EarningsPerShareDiluted']['units']['USD/shares'][-1]['val']='-1'
    packet['filing_witnesses'][-1]['eps']='-1'
    out=calculate(packet)
    assert out['current_eps_proxy']=='2'
    assert packet['filing_witnesses'][-1]['eps']=='-1'


def test_exact_minimum_twelve_anchor_boundary():
    packet=evidence()
    rows=packet['companyfacts']['facts']['us-gaap']['EarningsPerShareDiluted']['units']['USD/shares']
    rows.pop(0)
    out=calculate(packet)
    assert len(out['anchors'])==12
    rows.pop(0)
    with pytest.raises(ResearchRefused,match='TWELVE'):
        calculate(packet)


def test_fundamental_expiry_shortens_seven_day_calculation_lifetime():
    packet=evidence();later=NOW+timedelta(days=35)
    packet['facts_received_at']=later.isoformat()
    def later_proof(p, *, now):
        assert now==later
        return {'schema':'QD_HISTORICAL_EARNINGS_SOURCE_VERIFIED_V1','binding':digest(p),
            'domain':'SYNTHETIC','scope':'RESEARCH_ONLY','verified':True,'receipt_id':'SYNTHETIC-LATER-CUT'}
    out=build_historical_valuation(packet,method=METHOD,now=later,verify_source=later_proof)
    expiry=datetime.fromisoformat(out['expires_at'])
    assert expiry-later<timedelta(days=7)
    assert build_normalization_window(out['valuation_sources'],now=later)['complete']
    assert not build_normalization_window(out['valuation_sources'],now=expiry+timedelta(microseconds=1))['complete']


@pytest.mark.asyncio
async def test_existing_readonly_scanner_to_selected_method_to_original_board(tmp_path,monkeypatch):
    from urllib.parse import parse_qs, urlsplit

    from app.investment import scan
    from app.investment.models import MeasuredValue
    from app.investment.scan_settings import ScanSettings
    packet=evidence()
    def response(url):
        if '/assets/' in url:
            return {'symbol':'MSFT','id':'SYNTHETIC-MSFT','class':'us_equity',
                    'status':'active','tradable':True,'fractionable':True,'exchange':'NASDAQ'}
        if '/bars?' in url:
            second='page_token' in parse_qs(urlsplit(url).query)
            bars=packet['prices']['bars']
            return {'symbol':'MSFT','bars':bars[1000:] if second else bars[:1000],
                    'next_page_token':None if second or len(bars)<=1000 else 'synthetic-next-page'}
        if '/calendar?' in url:return packet['calendar']
        if 'company_tickers' in url:return {'0':{'cik_str':789019,'ticker':'MSFT'}}
        return packet['companyfacts']
    c,_,_,_=client(tmp_path,response=response)
    bundle=FreeResearchBundle(client=c,now=lambda:NOW,
        reference_price=lambda _:MeasuredValue.of(40,source='ALPACA_IEX_SYNTHETIC',timestamp=NOW,retrieved_at=NOW))
    universe=InvestmentUniverse([UniverseEntry('MSFT',asset_type=AssetType.STOCK)])
    ingest=read_only_ingest(bundle=bundle,universe=universe,history_root=tmp_path/'legacy-history')
    scanner=scan.InvestmentScanner(settings=ScanSettings(enabled=False,persist=False,notify_discord=False,
        inter_symbol_delay_seconds=0,max_retries=0),universe=universe,ingest=ingest,
        history_root=tmp_path/'legacy-history',persist=False,research_only=True)
    def forbid(*args,**kwargs):raise AssertionError('legacy financial writer invoked')
    monkeypatch.setattr(scanner,'_paper_book',forbid)
    monkeypatch.setattr(scanner,'_port',forbid)
    report=await scanner.run_once(now=NOW)
    assert report.evaluated==1 and report.failed==0
    original=report.observations[0].research.as_dict()
    linked=attach_historical_valuation(original,packet,method=METHOD,now=NOW,verify_source=verifier)
    projected=project_explicit_research([linked],now=NOW)[0]
    assert projected['quality_dips_v2']['valuation_source_count']==3
    assert projected['quality_dips_v2']['quality_dips_v3']['fair_value_anchor']==64
    assert linked['components']==original['components']
    assert 'valuation_sources' not in original and not (tmp_path/'legacy-history').exists()


@pytest.mark.parametrize('damage',['oversized_prices','oversized_witnesses','unverified_endpoint_domain','malformed_expiry'])
def test_bounded_inputs_and_expiry_refusal(damage):
    packet=evidence()
    if damage=='oversized_prices':packet['prices']['bars']*=3
    elif damage=='oversized_witnesses':packet['filing_witnesses']*=40
    elif damage=='unverified_endpoint_domain':packet['domain']='UNKNOWN'
    else:
        row=current_row()
        for source in row['valuation_sources']:source['expires_at']='not-a-time'
        out=project_explicit_research([row],now=NOW)[0]['quality_dips_v2']
        assert out['valuation_source_count']==0
        return
    with pytest.raises(ResearchRefused):calculate(packet)
