"""Full synthetic transport/original filing/exhibit -> original research board."""
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from app.investment.free_research_transport import FreeResearchClient, ResearchRefused
from app.investment.genuine_historical_source import (
    GenuineHistoricalSource,
    no_split_basis,
)
from app.investment.historical_earnings_valuation import METHOD
from app.services.quality_dips_research_only import project_explicit_research
from test_free_research_pipeline import CONTACT, NOW
from test_historical_earnings_valuation import evidence
from test_quality_dips_valuation_admission import current_row
from test_sec_earnings_exhibit import exhibit, release_main
from test_sec_filing_evidence import document


def producer(tmp_path, damage=None):
    packet=evidence();quarters=packet['companyfacts']['facts']['us-gaap']['EarningsPerShareDiluted']['units']['USD/shares']
    docs={};columns={k:[] for k in ('accessionNumber','filingDate','reportDate','form','primaryDocument','items')}
    for i,row in enumerate(quarters):
        row['accn']=f'0000000000-{row["filed"][2:4]}-{i+1:06d}'
        fields=(row['accn'],row['filed'],row['end'],'10-Q',f'quarter{i}.htm','')
        for key,value in zip(columns,fields,strict=True):columns[key].append(value)
        docs[f'quarter{i}.htm']=document().replace('2026-07-01',row['start']).replace('2026-09-30',row['end']).replace('2.<span>2</span>2','1')
    # One missing Company Facts Q4, supplied exclusively by the original 8-K.
    q4=next(r for r in quarters if r['end']=='2026-06-30');quarters.remove(q4)
    for values in columns.values():values.pop(14)  # 2026 Q2 is fixture index14.
    accession='0000000000-26-000099';filed='2026-07-20'
    for key,value in zip(columns,(accession,filed,filed,'8-K','release.htm','2.02,9.01'),strict=True):columns[key].append(value)
    docs['release.htm']=release_main().replace('2026-07-29',filed)
    docs['msft-ex99_1.htm']=exhibit().replace('$4.81','$1.00').replace('$35,766','$7,443').replace('$3.65','$1.00').replace('$27,233','$7,461')
    submissions={'cik':'789019','name':'MICROSOFT CORP','tickers':['MSFT'],'entityType':'operating','sic':'7372',
        'filings':{'recent':columns,'files':[]}}
    calls=[];ticks=[0.0];clock=[NOW]
    def fetch(url,*args):
        calls.append(url);path=urlsplit(url).path
        if 'company_tickers' in path:value={'0':{'ticker':'MSFT','cik_str':789019}}
        elif '/assets/' in path:value={'symbol':'MSFT','id':'SYNTHETIC-ASSET','class':'us_equity','status':'active','tradable':True,'fractionable':True}
        elif '/submissions/' in path:value=submissions
        elif '/companyfacts/' in path:value=packet['companyfacts']
        elif path.endswith('/bars'):
            query=parse_qs(urlsplit(url).query);offset=1000 if 'page_token' in query else 0;bars=packet['prices']['bars']
            value={'symbol':'MSFT','bars':bars[offset:offset+1000],'next_page_token':'next' if offset==0 and len(bars)>1000 else None}
        elif '/calendar' in path:value=packet['calendar']
        elif '/corporate-actions' in path:value={'corporate_actions':{},'next_page_token':None}
        else:
            name=path.rsplit('/',1)[1]
            text=docs[name]
            if damage=='missing_shares':text=text.replace('us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding','us-gaap:Other')
            return text.encode()
        return json.dumps(value).encode()
    if damage=='wrong_issuer':submissions['cik']='1'
    elif damage=='missing_earnings_item':columns['items'][-1]='9.01'
    elif damage=='wrong_exhibit_eps':docs['msft-ex99_1.htm']=docs['msft-ex99_1.htm'].replace('$1.00','$100.00')
    elif damage=='ambiguous_release':
        for values in columns.values():values.append(values[-1])
        columns['accessionNumber'][-1]='0000000000-26-000100'
    client=FreeResearchClient(cache_root=tmp_path/'cache',now=lambda:clock[0],sec_user_agent=CONTACT,
        credentials=SimpleNamespace(key='SYNTHETIC',secret='SYNTHETIC'),fetch=fetch,
        max_attempts=64,seconds=60,monotonic=lambda:ticks[0],sleep=lambda n:ticks.__setitem__(0,ticks[0]+n))
    source=GenuineHistoricalSource(client=client,now=lambda:clock[0],symbols=('MSFT',))
    return source,packet,calls,clock


def test_complete_source_to_original_board_without_financial_authority(tmp_path):
    source,packet,calls,_=producer(tmp_path);original=deepcopy(packet['companyfacts'])
    result=source.valuation('MSFT')
    assert Decimal(result['current_eps_proxy'])==Decimal(4) and len(result['anchors'])==13
    assert result['domain']=='SYNTHETIC' and not result['paper_eligible']
    assert packet['companyfacts']==original
    count=len(calls);row=current_row();row.pop('valuation_sources');row['symbol']='MSFT';row['price']=40
    linked=source.attach_research(row,method=METHOD)
    board=project_explicit_research([linked],now=NOW)
    assert board[0]['quality_dips_v2']['valuation_source_count']==3
    assert len(calls)==count and 'valuation_sources' not in row
    assert all(not any(p in url for p in ('/orders','/account','/positions')) for url in calls)
    with pytest.raises(ResearchRefused,match='RESERVED'):source.capture('MSFT')


def test_concurrent_source_capture_reserves_exactly_one_attempt(tmp_path):
    source,_,calls,_=producer(tmp_path)
    def run():
        try:return source.capture('MSFT')['schema']
        except ResearchRefused as e:return str(e)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:run(),range(2)))
    assert results.count('QD_HISTORICAL_EARNINGS_INPUT_V2')==1
    assert sum('CAPTURE_ALREADY_RESERVED' in result for result in results)==1
    assert len(calls)==len(source.receipts)


@pytest.mark.parametrize('damage',['wrong_issuer','missing_earnings_item','wrong_exhibit_eps','ambiguous_release','missing_shares'])
def test_failed_source_never_blesses_or_retries_incomplete_evidence(tmp_path,damage):
    source,_,calls,_=producer(tmp_path,damage)
    with pytest.raises((ResearchRefused,ValueError)):source.valuation('MSFT')
    count=len(calls)
    with pytest.raises(ResearchRefused):source.attach_research({},method=METHOD)
    with pytest.raises(ResearchRefused,match='RESERVED'):source.capture('MSFT')
    assert len(calls)==count


@pytest.mark.parametrize('damage',['changed_packet','receipt','expiry','rollback','changed_domain','unselected_method'])
def test_current_cut_and_explicit_method_refuse_changed_or_stale_data(tmp_path,damage):
    source,_,calls,clock=producer(tmp_path);packet=source.capture('MSFT');count=len(calls)
    if damage=='changed_packet':packet['instrument']['symbol']='OTHER'
    elif damage=='receipt':source.receipts.clear()
    elif damage=='expiry':clock[0]+=timedelta(seconds=61)
    elif damage=='rollback':clock[0]-=timedelta(seconds=1)
    elif damage=='changed_domain':source.client.domain='TLS_PUBLIC_PROVIDER'
    if damage=='unselected_method':
        row=current_row();row.pop('valuation_sources')
        with pytest.raises(ResearchRefused):source.attach_research(row,method='NOT_APPROVED')
    else:
        with pytest.raises(ResearchRefused):source.verify(packet,now=clock[0])
    assert len(calls)==count


@pytest.mark.parametrize('damage',['split','unknown_action','wrong_cash_merger_role','missing_session','pagination'])
def test_share_basis_refuses_incomplete_or_changed_security_evidence(damage):
    p=evidence();raw=p['prices'];split=deepcopy(raw);actions={'corporate_actions':{},'next_page_token':None}
    if damage=='split':split['bars'][0]['c']='81'
    elif damage=='unknown_action':actions['corporate_actions']['stock_splits']=[{'symbol':'MSFT'}]
    elif damage=='wrong_cash_merger_role':actions['corporate_actions']['cash_mergers']=[{'acquirer_symbol':'OTHER','acquiree_symbol':'MSFT','rate':'20','id':'SYNTHETIC','effective_date':'2026-01-01'}]
    elif damage=='missing_session':raw['bars'].pop(0);split['bars'].pop(0)
    elif damage=='pagination':actions['next_page_token']='missing-page'
    with pytest.raises(ResearchRefused):no_split_basis(raw,split,p['calendar'],actions,symbol='MSFT',now=NOW,
        received_at=NOW,start=__import__('datetime').date(2020,1,1))


def _realistic_fiscal_week_rows():
    """Four AVGO-style Q1/Q2/Q3 dates surrounding an unreported fiscal Q4."""
    return [
        {'start':'2026-05-04','end':'2026-08-02','filed':'2026-09-10','form':'10-Q'},
        {'start':'2026-02-02','end':'2026-05-03','filed':'2026-06-12','form':'10-Q'},
        {'start':'2025-11-03','end':'2026-02-01','filed':'2026-03-12','form':'10-Q'},
        {'start':'2025-05-05','end':'2025-08-03','filed':'2025-09-10','form':'10-Q'},
        {'start':'2025-02-03','end':'2025-05-04','filed':'2025-06-12','form':'10-Q'},
        {'start':'2024-11-04','end':'2025-02-02','filed':'2025-03-12','form':'10-Q'},
        {'start':'2024-05-06','end':'2024-08-04','filed':'2024-09-12','form':'10-Q'},
    ]


def test_fiscal_week_original_quarter_discovery_never_guesses_calendar_month_ends():
    from app.investment.genuine_historical_source import missing_original_quarter_ends
    from datetime import date
    dates=missing_original_quarter_ends(_realistic_fiscal_week_rows(),now=NOW)
    assert dates==[date(2025,11,2),date(2024,11,3)]
    assert date(2025,10,31) not in dates
    assert date(2024,10,31) not in dates


def test_calendar_quarter_discovery_remains_backward_compatible():
    from app.investment.genuine_historical_source import missing_original_quarter_ends
    from datetime import date
    quarters=[
        {'start':'2026-07-01','end':'2026-09-30','filed':'2026-10-28','form':'10-Q'},
        {'start':'2026-01-01','end':'2026-03-31','filed':'2026-04-29','form':'10-Q'},
        {'start':'2025-10-01','end':'2025-12-31','filed':'2026-01-28','form':'10-Q'},
        {'start':'2025-07-01','end':'2025-09-30','filed':'2025-10-28','form':'10-Q'},
    ]
    assert missing_original_quarter_ends(quarters,now=NOW)==[date(2026,6,30)]


@pytest.mark.parametrize('damage',[
    'conflicting_restatement','gap_of_two_quarters','out_of_range_quarter',
    'future_filed','filed_before_period_end','invalid_start','unknown_form',
])
def test_gap_discovery_refuses_uncorroborated_fiscal_quarter_shapes(damage):
    from app.investment.genuine_historical_source import missing_original_quarter_ends
    rows=deepcopy(_realistic_fiscal_week_rows())
    if damage=='conflicting_restatement':
        different=deepcopy(rows[0]);different['start']='2026-05-05';rows.append(different)
    elif damage=='gap_of_two_quarters':
        # Leave the still older known original quarter to expose a >110-day
        # unsupported gap, not a truncated history with no observed gap.
        rows.pop(3)
    elif damage=='out_of_range_quarter':
        rows[0]['start']='2026-04-01'
    elif damage=='future_filed':
        rows[0]['filed']='2027-09-10'
    elif damage=='filed_before_period_end':
        rows[0]['filed']='2026-07-01'
    elif damage=='invalid_start':
        rows[0]['start']='2026-INVALID'
    elif damage=='unknown_form':
        rows[0]['form']='8-K-UNKNOWN'
    with pytest.raises(ResearchRefused):
        missing_original_quarter_ends(rows,now=NOW)


def test_gap_discovery_requires_direct_issuer_rows_and_never_forges_source():
    from app.investment.genuine_historical_source import missing_original_quarter_ends
    with pytest.raises(ResearchRefused,match='DIRECT_QUARTER_GAP_EVIDENCE_REQUIRED'):
        missing_original_quarter_ends([],now=NOW)
    # The routine reports ONLY missing exact period-end dates, with no EPS,
    # original document, source authorization, or price adjustment fabricated.
    assert all(type(day).__name__=='date' for day in
        missing_original_quarter_ends(_realistic_fiscal_week_rows(),now=NOW))
