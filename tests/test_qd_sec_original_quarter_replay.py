"""Synthetic caches for direct SEC original-document quarter corroboration.

No network, original-filing authority, corporate-action assertion or account IO.
"""
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json

import pytest

from app.investment.free_research_transport import ResearchRefused
from scripts.observation_runtime import qd_sec_original_quarter_replay as replay
from test_sec_filing_evidence import document, submission, reference

NOW = datetime(2026, 11, 10, 17, 45, tzinfo=UTC)
CIK = "0000789019"
SUB = "https://data.sec.gov/submissions/CIK" + CIK + ".json"
FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK" + CIK + ".json"
ORIGINAL = reference()["url"]


def companyfacts():
    def fact(value):
        return {"start": "2026-07-01", "end": "2026-09-30",
                "filed": "2026-10-20", "form": "10-Q",
                "accn": "0000000000-26-000001", "val": value}
    return {
        "cik": 789019,
        "facts": {"us-gaap": {
            "EarningsPerShareDiluted": {"units": {"USD/shares": [fact(2.22)]}},
            "WeightedAverageNumberOfDilutedSharesOutstanding": {
                "units": {"shares": [fact(1000000000)]}},
        }},
    }


def store(root, url, value, *, provider="SEC_EDGAR"):
    raw = value if type(value) is str else json.dumps(value, sort_keys=True)
    packet = {"schema": "FREE_RESEARCH_CACHE_V1", "provider": provider,
              "url": url, "domain": "TLS_PUBLIC_PROVIDER",
              "retrieved_at": NOW.isoformat(),
              "sha256": hashlib.sha256(raw.encode()).hexdigest(),
              "raw": raw}
    path = root / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    path.write_text(json.dumps(packet, sort_keys=True), encoding="utf-8")
    return path


def prepared(tmp_path):
    store(tmp_path, SUB, submission())
    store(tmp_path, FACTS, companyfacts())
    store(tmp_path, ORIGINAL, document(), provider="SEC_EDGAR_DOCUMENT")
    return tmp_path


def run(root, *, now=NOW, symbol="MSFT", cik=CIK, accession=None):
    return replay.inspect_original_quarter(
        symbol=symbol, cik=cik, cache_root=root, now=now,
        accession=accession)


def test_realistic_original_inline_and_separate_sec_companyfacts_agree(tmp_path):
    result = run(prepared(tmp_path))
    assert result["status"] == "DIRECT_SEC_ORIGINAL_AND_COMPANYFACTS_CORROBORATED"
    assert result["symbol"] == "MSFT" and result["cik"] == CIK
    assert result["diluted_eps_usd"] == "2.22"
    assert result["diluted_weighted_average_shares"] == "1000000000"
    assert result["period_start"] == "2026-07-01"
    assert result["period_end"] == "2026-09-30"
    assert result["accession"] == reference()["accession"]
    assert result["original_filing_sha256"] == hashlib.sha256(document().encode()).hexdigest()
    for key in ("share_adjustment_basis_accepted", "twelve_quarter_history_accepted",
                "operational_source_accepted", "financial_paper_authorized",
                "live_order_authorized"):
        assert result[key] is False
    assert result["external_provider_requests"] == 0


@pytest.mark.parametrize("damage", [
    "alter_original_bytes", "alter_original_hash", "wrong_provider", "wrong_cache_domain",
    "stale_acquisition", "future_acquisition", "wrong_cik", "wrong_eps",
    "missing_diluted_shares", "wrong_shares", "different_report",
    "wrong_original_document_identity", "missing_original", "invalid_decimal",
    "duplicate_quarter_period", "different_cik_parameter",
])
def test_original_quarter_refuses_tampered_or_unmatched_sources(tmp_path, damage):
    prepared(tmp_path)
    paths = {
        "sub": tmp_path / (hashlib.sha256(SUB.encode()).hexdigest() + ".json"),
        "facts": tmp_path / (hashlib.sha256(FACTS.encode()).hexdigest() + ".json"),
        "original": tmp_path / (hashlib.sha256(ORIGINAL.encode()).hexdigest() + ".json"),
    }
    if damage == "missing_original":
        paths["original"].unlink()
    elif damage == "different_cik_parameter":
        with pytest.raises(ValueError):
            run(tmp_path, cik="0001730168")
        return
    else:
        filename = "original" if damage.startswith("alter_original") or damage == "wrong_original_document_identity" else "facts"
        if damage in ("different_report",):
            filename = "sub"
        path = paths[filename]
        cached = json.loads(path.read_text())
        if damage == "alter_original_bytes":
            cached["raw"] += "<!-- tampered -->"
        elif damage == "alter_original_hash":
            cached["sha256"] = "0" * 64
        elif damage == "wrong_provider":
            cached["provider"] = "UNTRUSTED"
        elif damage == "wrong_cache_domain":
            cached["domain"] = "SYNTHETIC"
        elif damage == "stale_acquisition":
            cached["retrieved_at"] = "2026-01-01T00:00:00+00:00"
        elif damage == "future_acquisition":
            cached["retrieved_at"] = "2026-12-01T00:00:00+00:00"
        elif damage == "wrong_original_document_identity":
            cached["raw"] = cached["raw"].replace("0000789019", "0001730168")
            cached["sha256"] = hashlib.sha256(cached["raw"].encode()).hexdigest()
        else:
            data = json.loads(cached["raw"])
            if damage == "wrong_cik":
                data["cik"] = 1730168
            elif damage == "wrong_eps":
                data["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"][0]["val"] = 5.55
            elif damage == "missing_diluted_shares":
                data["facts"]["us-gaap"].pop("WeightedAverageNumberOfDilutedSharesOutstanding")
            elif damage == "wrong_shares":
                data["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"]["units"]["shares"][0]["val"] = 8
            elif damage == "invalid_decimal":
                data["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"][0]["val"] = "INVALID"
            elif damage == "duplicate_quarter_period":
                data["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"].append(
                    deepcopy(data["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"][0]))
            elif damage == "different_report":
                data["filings"]["recent"]["reportDate"][0] = "2026-06-30"
            cached["raw"] = json.dumps(data, sort_keys=True)
            cached["sha256"] = hashlib.sha256(cached["raw"].encode()).hexdigest()
        path.write_text(json.dumps(cached, sort_keys=True), encoding="utf-8")
    with pytest.raises((ValueError, TypeError)):
        run(tmp_path)


def test_cache_recheck_refuses_symlinked_original_file(tmp_path):
    prepared(tmp_path)
    original = tmp_path / (hashlib.sha256(ORIGINAL.encode()).hexdigest() + ".json")
    replacement = tmp_path / "archived-copy"
    original.rename(replacement)
    try:
        original.symlink_to(replacement)
    except (OSError, NotImplementedError):
        pytest.skip("Windows local symlink privilege not available")
    with pytest.raises(ValueError, match="CACHED_EXACT_ORIGINAL_REQUIRED"):
        run(tmp_path)


@pytest.mark.parametrize("bad", ["msft", "MSFT/../", "A" * 9])
def test_security_symbol_must_be_exact_and_never_trigger_io(tmp_path, bad):
    with pytest.raises(ValueError, match="EXPLICIT_SECURITY"):
        run(tmp_path, symbol=bad)


def test_explicit_accession_replays_only_matching_original_10q(tmp_path):
    prepared(tmp_path)
    result = run(tmp_path, accession=reference()["accession"])
    assert result["accession"] == reference()["accession"]
    assert result["diluted_eps_usd"] == "2.22"
    assert result["original_filing_and_companyfacts_matched"] is True
    assert result["twelve_quarter_history_accepted"] is False
    assert result["financial_paper_authorized"] is False


@pytest.mark.parametrize("bad_accession", [
    "0000000000-26-000002", "0000000000-26-999999",
])
def test_exact_requested_quarter_never_falls_back_to_latest(tmp_path, bad_accession):
    prepared(tmp_path)
    with pytest.raises(ValueError, match="SUBMISSIONS_10Q_ACCESSION_REQUIRED"):
        run(tmp_path, accession=bad_accession)


@pytest.mark.parametrize("bad_accession", [
    "", "000000000026000001", "0000000000-26-000001/../",
    "0000000000-26-000001?fake", 123, True,
])
def test_invalid_accession_refuses_without_accessing_cached_resources(tmp_path, bad_accession):
    with pytest.raises(ValueError, match="EXACT_HISTORICAL_ACCESSION_REQUIRED"):
        run(tmp_path, accession=bad_accession)


def test_explicit_accession_cannot_admit_annual_report_as_standalone_10q(tmp_path):
    prepared(tmp_path)
    path = tmp_path / (hashlib.sha256(SUB.encode()).hexdigest() + ".json")
    cache = json.loads(path.read_text(encoding="utf-8"))
    data = json.loads(cache["raw"])
    data["filings"]["recent"]["form"][0] = "10-K"
    cache["raw"] = json.dumps(data, sort_keys=True)
    cache["sha256"] = hashlib.sha256(cache["raw"].encode()).hexdigest()
    path.write_text(json.dumps(cache, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="SUBMISSIONS_10Q_ACCESSION_REQUIRED"):
        run(tmp_path, accession=reference()["accession"])


def prepared_avgo_split(tmp_path):
    """Fully synthetic originals; never claim an installed issuer or market feed."""
    from test_sec_filing_evidence import document, submission
    sub=submission()
    sub['cik']='1730168'
    sub['tickers']=['AVGO']
    recent=sub['filings']['recent']
    acc='0001730168-24-000099'
    recent['accessionNumber']=[acc]
    recent['filingDate']=['2024-09-11']
    recent['reportDate']=['2024-08-04']
    recent['primaryDocument']=['avgo-20240804.htm']
    original=(document()
       .replace('0000789019','0001730168')
       .replace('2026-07-01','2024-05-06')
       .replace('2026-09-30','2024-08-04')
       .replace('http://fasb.org/us-gaap/2026','http://fasb.org/us-gaap/2023')
       .replace('http://xbrl.sec.gov/dei/2026','http://xbrl.sec.gov/dei/2024'))
    insert = (
       '<xbrli:context id="split"><xbrli:entity><xbrli:identifier '
       'scheme="http://www.sec.gov/CIK">0001730168</xbrli:identifier>'
       '</xbrli:entity><xbrli:period><xbrli:startDate>2024-07-12'
       '</xbrli:startDate><xbrli:endDate>2024-07-12</xbrli:endDate>'
       '</xbrli:period></xbrli:context>'
       '<xbrli:unit id="number"><xbrli:measure>xbrli:pure'
       '</xbrli:measure></xbrli:unit>'
       '<ix:nonFraction name="us-gaap:StockholdersEquityNoteStockSplitConversionRatio1"'
       ' contextRef="split" unitRef="number" decimals="0" scale="0"'
       ' format="ixt-sec:numwordsen">ten</ix:nonFraction>')
    original=original.replace('</html>',insert+'</html>')
    facts=companyfacts()
    facts['cik']=1730168
    for concept,unit in (('EarningsPerShareDiluted','USD/shares'),
                         ('WeightedAverageNumberOfDilutedSharesOutstanding','shares')):
        row=facts['facts']['us-gaap'][concept]['units'][unit][0]
        row.update(start='2024-05-06',end='2024-08-04',
                   filed='2024-09-11',accn=acc)
    facts['facts']['us-gaap']['StockholdersEquityNoteStockSplitConversionRatio1']={
        'units': {'pure':[{'accn':acc,'form':'10-Q','filed':'2024-09-11',
                          'end':'2024-07-12','val':10}]}}
    url=('https://www.sec.gov/Archives/edgar/data/1730168/'
         '000173016824000099/avgo-20240804.htm')
    store(tmp_path,'https://data.sec.gov/submissions/CIK0001730168.json',sub)
    store(tmp_path,'https://data.sec.gov/api/xbrl/companyfacts/CIK0001730168.json',facts)
    store(tmp_path,url,original,provider='SEC_EDGAR_DOCUMENT')
    return url


def test_exact_avgo_split_ratio_corresponds_to_original_sec_inline_and_companyfacts(tmp_path):
    prepared_avgo_split(tmp_path)
    result=replay.inspect_original_avgo_split(cache_root=tmp_path,now=NOW)
    assert result['forward_split_new_shares_per_old_share']==10
    assert result['stock_split_effective_date']=='2024-07-12'
    assert result['accession']=='0001730168-24-000099'
    assert result['original_sec_quarter_facts_also_corroborated'] is True
    for k in ('pre_split_history_price_adjustment_verified',
              'historical_share_basis_operationally_accepted',
              'historical_valuation_12_anchors_accepted',
              'paper_financial_order_authorized','real_money_order_authorized'):
        assert result[k] is False
    assert result['external_provider_requests']==0


@pytest.mark.parametrize('damage',[
    'original_number_eleven','split_fact_missing','duplicate_split_fact',
    'split_date_changed','split_unit_wrong','split_namespace_wrong',
    'issuer_context_changed','original_split_factor_non_numeric',
    'companyfacts_split_factor_mismatch','companyfacts_split_date_wrong',
    'companyfacts_split_duplicate','wrong_companyfacts_accession',
    'signed_source_hash_tampered','cached_provider_forged',
])
def test_avgo_original_sec_split_provenance_fails_closed(tmp_path,damage):
    url=prepared_avgo_split(tmp_path)
    original_path=tmp_path/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    cf_url='https://data.sec.gov/api/xbrl/companyfacts/CIK0001730168.json'
    cf_path=tmp_path/(hashlib.sha256(cf_url.encode()).hexdigest()+'.json')
    if damage.startswith('companyfacts') or damage=='wrong_companyfacts_accession':
        path=cf_path
    else:
        path=original_path
    packet=json.loads(path.read_text())
    if damage=='signed_source_hash_tampered':
        packet['sha256']='f'*64
    elif damage=='cached_provider_forged':
        packet['provider']='SYNTHETIC'
    elif path==original_path:
        body=packet['raw']
        if damage=='original_number_eleven':
            body=body.replace('>ten</ix:nonFraction>','>eleven</ix:nonFraction>')
        elif damage=='split_fact_missing':
            body=body.replace('StockholdersEquityNoteStockSplitConversionRatio1',
                              'UnrelatedStockRatio')
        elif damage=='duplicate_split_fact':
            tag=('<ix:nonFraction name="us-gaap:StockholdersEquityNoteStockSplitConversionRatio1"'
                 ' contextRef="split" unitRef="number" decimals="0" scale="0"'
                 ' format="ixt-sec:numwordsen">ten</ix:nonFraction>')
            body=body.replace('</html>',tag+'</html>')
        elif damage=='split_date_changed':
            body=body.replace('2024-07-12','2024-07-11')
        elif damage=='split_unit_wrong':
            body=body.replace('<xbrli:measure>xbrli:pure','<xbrli:measure>xbrli:shares')
        elif damage=='split_namespace_wrong':
            body=body.replace('http://fasb.org/us-gaap/2023','https://wrong.invalid/us-gaap/2023')
        elif damage=='issuer_context_changed':
            body=body.replace('0001730168</xbrli:identifier>','0000000001</xbrli:identifier>',1)
        elif damage=='original_split_factor_non_numeric':
            body=body.replace('format="ixt-sec:numwordsen"','format="ixt-sec:unverified"')
        packet['raw']=body
        packet['sha256']=hashlib.sha256(body.encode()).hexdigest()
    else:
        document=json.loads(packet['raw'])
        row=document['facts']['us-gaap']['StockholdersEquityNoteStockSplitConversionRatio1']['units']['pure'][0]
        if damage=='companyfacts_split_factor_mismatch':
            row['val']=9
        elif damage=='companyfacts_split_date_wrong':
            row['end']='2024-07-11'
        elif damage=='companyfacts_split_duplicate':
            document['facts']['us-gaap']['StockholdersEquityNoteStockSplitConversionRatio1']['units']['pure'].append(deepcopy(row))
        elif damage=='wrong_companyfacts_accession':
            row['accn']='0001730168-24-000001'
        packet['raw']=json.dumps(document,sort_keys=True)
        packet['sha256']=hashlib.sha256(packet['raw'].encode()).hexdigest()
    path.write_text(json.dumps(packet,sort_keys=True),encoding='utf-8')
    with pytest.raises((ValueError,ResearchRefused)):
        replay.inspect_original_avgo_split(cache_root=tmp_path,now=NOW)


def _synthetic_avgo_raw_split_history(tmp_path):
    from urllib.parse import urlencode

    prepared_avgo_split(tmp_path)
    days=['2024-07-11','2024-07-12','2024-07-15','2024-07-16']
    def bars(adjustment):
        data=[]
        for day, raw_price, volume in zip(days,(1700,1650,165,170),
                                           (50,80,120,140),strict=True):
            is_pre=day <= '2024-07-12'
            factor=10 if is_pre and adjustment=='split' else 1
            price=raw_price/factor
            v=volume*factor
            data.append({'t':day+'T04:00:00Z','o':price,'h':price+1/factor,
                         'l':price-1/factor,'c':price,'v':v,
                         'n':1,'vw':price})
        return data

    sources={}
    for adjustment in ('raw','split'):
        rows=bars(adjustment)
        query={'feed':'iex','timeframe':'1Day','adjustment':adjustment,
               'sort':'asc','start':'2021-11-03','end':'2026-11-07','limit':1000}
        original_url=('https://data.alpaca.markets/v2/stocks/AVGO/bars?'
                      +urlencode(query))
        store(tmp_path,original_url,{
            'symbol':'AVGO','bars':rows[:2],
            'next_page_token':'TEST_CONTINUATION'},provider='ALPACA_BASIC_IEX')
        query['page_token']='TEST_CONTINUATION'
        page2_url=('https://data.alpaca.markets/v2/stocks/AVGO/bars?'
                   +urlencode(query))
        store(tmp_path,page2_url,{
            'symbol':'AVGO','bars':rows[2:],
            'next_page_token':None},provider='ALPACA_BASIC_IEX')
        sources[adjustment]=(original_url,page2_url)
    action_query={'symbols':'AVGO','start':'2021-11-03',
                  'end':'2026-11-07','region':'us',
                  'limit':1000,'data_quality':'all'}
    action_url=('https://data.alpaca.markets/v1/corporate-actions?'
                +urlencode(action_query))
    store(tmp_path,action_url,{
        'corporate_actions': {
            'forward_splits': [{
                'symbol':'AVGO','id':'ab22e5df-2b84-427e-84c7-c0e6e24c4696',
                'record_date':'2024-07-11','payable_date':'2024-07-12',
                'ex_date':'2024-07-15','process_date':'2024-07-15',
                'due_bill_redemption_date':'2024-07-15',
                'old_rate':1,'new_rate':10
            }],
            'cash_dividends':[], 'stock_mergers':[],
        },
        'next_page_token':None,
    },provider='ALPACA_BASIC_IEX')
    calendar_query={'start':'2021-11-03','end':'2026-11-07'}
    calendar_url=('https://paper-api.alpaca.markets/v2/calendar?'
                  +urlencode(calendar_query))
    store(tmp_path,calendar_url,[
        {'date':day,'open':'09:30','close':'16:00'}
        for day in days
    ],provider='ALPACA_BASIC_IEX')
    return sources


def test_original_avgo_split_certifies_historical_price_pair_only(tmp_path):
    _synthetic_avgo_raw_split_history(tmp_path)
    result=replay.inspect_avgo_split_only_history(cache_root=tmp_path,now=NOW)
    assert result['matching_returned_daily_bar_count']==4
    assert result['pre_split_returned_bars']==2
    assert result['post_split_returned_bars']==2
    assert result['maximum_split_adjustment_rounding_difference_usd']=='0'
    assert result['sec_original_new_shares_per_old_share']==10
    assert len(result['source_content_sha256_by_adjustment']['raw'])==2
    for key in ('complete_exchange_calendar_sessions_verified',
                'all_corporate_actions_covered','provider_price_data_rights_accepted',
                'split_adjusted_share_basis_for_historical_valuation_accepted',
                'twelve_historical_valuation_anchors_accepted',
                'native_source_publisher_enrolled','financial_paper_order_authorized',
                'real_money_order_authorized'):
        assert result[key] is False
    assert result['network_requests']==0


@pytest.mark.parametrize('damage',[
    'pre_split_price','pre_split_volume','post_split_price','post_split_volume',
    'missing_day','duplicate_day','non_midnight_timestamp','future_date',
    'negative_price','ohlc_high_below_open','nan_price','fractional_volume',
    'duplicate_page_token','foreign_symbol','stale_or_forged_source',
    'wrong_provider','missing_page','swapped_page_order',
])
def test_original_avgo_split_price_history_fails_closed(tmp_path,damage):
    urls=_synthetic_avgo_raw_split_history(tmp_path)
    if damage in ('missing_page',):
        chosen=urls['split'][1]
        (tmp_path/(hashlib.sha256(chosen.encode()).hexdigest()+'.json')).unlink()
        with pytest.raises((ValueError,ResearchRefused,OSError)):
            replay.inspect_avgo_split_only_history(cache_root=tmp_path,now=NOW)
        return
    selected='split'
    page=0
    if damage in ('negative_price','fractional_volume'):
        selected='raw'
    if damage in ('duplicate_day','swapped_page_order','post_split_price','post_split_volume',
                  'non_midnight_timestamp','future_date','duplicate_page_token'):
        page=1
    url=urls[selected][page]
    filename=tmp_path/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    receipt=json.loads(filename.read_text())
    packet=json.loads(receipt['raw'])
    bar=packet['bars'][0]
    if damage=='pre_split_price':bar['c']+=3
    elif damage=='pre_split_volume':bar['v']+=1
    elif damage=='post_split_price':bar['c']+=3
    elif damage=='post_split_volume':bar['v']+=1
    elif damage=='missing_day':packet['bars'].pop(0)
    elif damage=='duplicate_day':packet['bars'][1]['t']=bar['t']
    elif damage=='non_midnight_timestamp':bar['t']='2024-07-15T05:00:00Z'
    elif damage=='future_date':bar['t']='2027-11-15T05:00:00Z'
    elif damage=='negative_price':bar['o']=-1
    elif damage=='ohlc_high_below_open':bar['h']=bar['o']-2
    elif damage=='nan_price':bar['c']='NaN'
    elif damage=='fractional_volume':bar['v']=1.4
    elif damage=='duplicate_page_token':packet['next_page_token']='TEST_CONTINUATION'
    elif damage=='foreign_symbol':packet['symbol']='MSFT'
    elif damage=='wrong_provider':receipt['provider']='SEC_EDGAR'
    elif damage=='swapped_page_order':
        packet['bars']=packet['bars'][::-1]
    elif damage=='stale_or_forged_source':
        receipt['sha256']='0'*64
    if damage not in ('wrong_provider','stale_or_forged_source'):
        receipt['raw']=json.dumps(packet,sort_keys=True)
        receipt['sha256']=hashlib.sha256(receipt['raw'].encode()).hexdigest()
    filename.write_text(json.dumps(receipt,sort_keys=True),encoding='utf-8')
    with pytest.raises((ValueError,ResearchRefused,OSError)):
        replay.inspect_avgo_split_only_history(cache_root=tmp_path,now=NOW)


@pytest.mark.parametrize('damage',[
    'forward_ratio_changed','old_ratio_changed','wrong_ex_date',
    'wrong_payable_date','wrong_record_date','duplicate_split',
    'missing_split','action_next_page_token','foreign_split_symbol',
    'hidden_unrecognized_action_class','provider_action_hash_changed',
    'action_history_missing',
])
def test_original_sec_alpaca_split_corporate_action_refuses_tampering(tmp_path,damage):
    from urllib.parse import urlencode

    _synthetic_avgo_raw_split_history(tmp_path)
    q={'symbols':'AVGO','start':'2021-11-03','end':'2026-11-07',
       'region':'us','limit':1000,'data_quality':'all'}
    url='https://data.alpaca.markets/v1/corporate-actions?'+urlencode(q)
    path=tmp_path/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    if damage=='action_history_missing':
        path.unlink()
    else:
        receipt=json.loads(path.read_text())
        actions=json.loads(receipt['raw'])
        row=actions['corporate_actions']['forward_splits'][0]
        if damage=='forward_ratio_changed':
            row['new_rate']=9
        elif damage=='old_ratio_changed':
            row['old_rate']=2
        elif damage=='wrong_ex_date':
            row['ex_date']='2024-07-16'
        elif damage=='wrong_payable_date':
            row['payable_date']='2024-07-11'
        elif damage=='wrong_record_date':
            row['record_date']='2024-07-12'
        elif damage=='duplicate_split':
            actions['corporate_actions']['forward_splits'].append(deepcopy(row))
        elif damage=='missing_split':
            actions['corporate_actions']['forward_splits'].clear()
        elif damage=='action_next_page_token':
            actions['next_page_token']='UNFINISHED'
        elif damage=='foreign_split_symbol':
            row['symbol']='MSFT'
        elif damage=='hidden_unrecognized_action_class':
            actions['corporate_actions']['reverse_splits']=[{'symbol':'AVGO'}]
        elif damage=='provider_action_hash_changed':
            receipt['sha256']='0'*64
        if damage!='provider_action_hash_changed':
            receipt['raw']=json.dumps(actions,sort_keys=True)
            receipt['sha256']=hashlib.sha256(receipt['raw'].encode()).hexdigest()
        path.write_text(json.dumps(receipt,sort_keys=True),encoding='utf-8')
    with pytest.raises((ValueError,ResearchRefused,OSError)):
        replay.inspect_avgo_split_only_history(cache_root=tmp_path,now=NOW)


@pytest.mark.parametrize('damage',[
    'calendar_missing_cache','calendar_wrong_provider','calendar_hash_tamper',
    'calendar_missing_session','calendar_extra_session','calendar_duplicate_session',
    'calendar_weekend_session','calendar_outside_requested_window',
    'calendar_reversed_hours','calendar_invalid_date',
])
def test_avgo_split_provider_calendar_must_cover_exact_daily_bar_sessions(tmp_path,damage):
    from urllib.parse import urlencode

    _synthetic_avgo_raw_split_history(tmp_path)
    url=('https://paper-api.alpaca.markets/v2/calendar?'
         +urlencode({'start':'2021-11-03','end':'2026-11-07'}))
    path=tmp_path/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    if damage=='calendar_missing_cache':
        path.unlink()
    else:
        record=json.loads(path.read_text(encoding='utf-8'))
        rows=json.loads(record['raw'])
        if damage=='calendar_wrong_provider':
            record['provider']='SEC_EDGAR'
        elif damage=='calendar_hash_tamper':
            record['sha256']='f'*64
        elif damage=='calendar_missing_session':
            rows.pop(1)
        elif damage=='calendar_extra_session':
            rows.append({'date':'2024-07-17','open':'09:30','close':'16:00'})
        elif damage=='calendar_duplicate_session':
            rows.append(deepcopy(rows[-1]))
        elif damage=='calendar_weekend_session':
            rows.append({'date':'2024-07-13','open':'09:30','close':'16:00'})
        elif damage=='calendar_outside_requested_window':
            rows.append({'date':'2021-11-02','open':'09:30','close':'16:00'})
        elif damage=='calendar_reversed_hours':
            rows[0]['open']='17:00'
        elif damage=='calendar_invalid_date':
            rows[0]['date']='2024-BAD'
        if damage not in ('calendar_wrong_provider','calendar_hash_tamper'):
            record['raw']=json.dumps(rows,sort_keys=True)
            record['sha256']=hashlib.sha256(record['raw'].encode()).hexdigest()
        path.write_text(json.dumps(record,sort_keys=True),encoding='utf-8')
    with pytest.raises((ValueError,ResearchRefused,OSError)):
        replay.inspect_avgo_split_only_history(cache_root=tmp_path,now=NOW)


def _synthetic_avgo_original_split_equivalence_inputs():
    """Algebra-only fixture; no claim these artificial hashes attest SEC data."""
    keys=[
        ('0001730168-24-000023','2023-10-30','2024-02-04','2024-03-14','2.84','467000000'),
        ('0001730168-24-000080','2024-02-05','2024-05-05','2024-06-13','4.42','480000000'),
        ('0001730168-24-000099','2024-05-06','2024-08-04','2024-09-11','-0.40','4663000000'),
    ]
    quarters=[]
    for i,(acc,start,end,filed,eps,shares) in enumerate(keys):
        quarters.append({
            'schema':replay.SCHEMA,'symbol':'AVGO','cik':'0001730168',
            'accession':acc,'period_start':start,'period_end':end,'filed':filed,
            'original_filing_sha256':str(i+1)*64,
            'companyfacts_sha256':'a'*64,
            'diluted_eps_usd':eps,
            'diluted_weighted_average_shares':shares,
            'original_filing_and_companyfacts_matched':True,
            'share_adjustment_basis_accepted':False,
            'twelve_quarter_history_accepted':False,
            'operational_source_accepted':False,
            'financial_paper_authorized':False,
            'live_order_authorized':False,
        })
    proof={
        'schema':'ATLAS_AVGO_SEC_SPLIT_ONLY_PRICE_PAIR_REPLAY_V1',
        'sec_original_split_date':'2024-07-12',
        'sec_original_new_shares_per_old_share':10,
        'sec_original_split_sha256':'c'*64,
        'provider_corporate_action_sha256':'d'*64,
        'provider_calendar_sha256':'e'*64,
        'provider_original_split_event_corroborated':True,
        'provider_calendar_session_coverage_verified':True,
        'provider_split_ex_date':'2024-07-15',
        'matching_returned_daily_bar_count':1258,
        'provider_calendar_expected_completed_sessions':1258,
        'pre_split_returned_bars':675,
        'post_split_returned_bars':583,
        'complete_exchange_calendar_sessions_verified':False,
        'provider_price_data_rights_accepted':False,
        'split_adjusted_share_basis_for_historical_valuation_accepted':False,
        'twelve_historical_valuation_anchors_accepted':False,
        'financial_paper_order_authorized':False,
        'real_money_order_authorized':False,
    }
    return quarters,proof


def test_original_reported_eps_is_not_replaced_by_split_equivalence_research():
    from decimal import Decimal

    quarters,proof=_synthetic_avgo_original_split_equivalence_inputs()
    original=deepcopy(quarters)
    report=replay.reconcile_avgo_original_eps_split_basis(quarters,proof)
    assert quarters==original
    assert report['quarter_count']==3
    rows=report['quarters']
    assert [x['as_reported_diluted_eps_usd'] for x in rows]==['2.84','4.42','-0.40']
    assert [x['split_equivalent_eps_usd_research_only'] for x in rows]==[
        '0.284','0.442','-0.40']
    assert [x['as_reported_weighted_diluted_shares'] for x in rows]==[
        '467000000','480000000','4663000000']
    assert [x['split_equivalent_weighted_shares_research_only'] for x in rows]==[
        '4670000000','4800000000','4663000000']
    assert [x['derived_new_shares_per_reported_share'] for x in rows]==[10,10,1]
    assert [x['transformed_not_sec_reported'] for x in rows]==[True,True,False]
    for source,adjusted in zip(quarters,rows,strict=True):
        assert (Decimal(source['diluted_eps_usd']) *
                Decimal(source['diluted_weighted_average_shares']) ==
                Decimal(adjusted['split_equivalent_eps_usd_research_only']) *
                Decimal(adjusted['split_equivalent_weighted_shares_research_only']))
    assert report['original_sec_gaap_values_preserved'] is True
    assert report['derived_values_are_not_restatements_of_original_sec_filings'] is True
    for flag in ('full_15_quarter_earnings_witness_chain_complete',
                 'entire_historical_eps_price_basis_accepted',
                 'operational_qd_financial_source_enrolled',
                 'financial_paper_authorized','live_order_authorized'):
        assert report[flag] is False
    assert report['network_requests']==0


@pytest.mark.parametrize('damage',[
    'wrong_symbol','wrong_cik','wrong_schema','different_accession',
    'stale_original_quarter','future_quarter_filing',
    'pre_split_report_labeled_as_post_split','post_split_report_labeled_as_pre_split',
    'pre_split_reported_shares_already_scaled','post_split_shares_not_scaled',
    'missing_original_hash','bogus_original_hash','foreign_companyfacts_hash',
    'missing_original_match','original_claims_financial_authority',
    'no_split_price_proof','wrong_split_ratio','wrong_split_date',
    'wrong_provider_exdate','incomplete_calendar','missing_bars',
    'wrong_pre_post_bar_count','provider_rights_falsely_accepted',
    'nan_eps','invalid_shares','missing_quarter','duplicate_quarter',
    'no_negative_original_loss',
])
def test_avgo_original_split_eps_basis_never_silently_accepts_bad_facts(damage):
    quarters,proof=_synthetic_avgo_original_split_equivalence_inputs()
    if damage=='wrong_symbol':quarters[0]['symbol']='MSFT'
    elif damage=='wrong_cik':quarters[0]['cik']='0000789019'
    elif damage=='wrong_schema':quarters[0]['schema']='UNVERIFIED'
    elif damage=='different_accession':quarters[1]['accession']='0001730168-24-999999'
    elif damage=='stale_original_quarter':quarters[0]['period_start']='2023-10-29'
    elif damage=='future_quarter_filing':quarters[1]['filed']='2024-07-20'
    elif damage=='pre_split_report_labeled_as_post_split':
        quarters[1]['period_end']='2024-08-04'
    elif damage=='post_split_report_labeled_as_pre_split':
        quarters[2]['filed']='2024-06-13'
    elif damage=='pre_split_reported_shares_already_scaled':
        quarters[1]['diluted_weighted_average_shares']='4800000000'
    elif damage=='post_split_shares_not_scaled':
        quarters[2]['diluted_weighted_average_shares']='466300000'
    elif damage=='missing_original_hash':quarters[0]['original_filing_sha256']=None
    elif damage=='bogus_original_hash':quarters[0]['original_filing_sha256']='g'*64
    elif damage=='foreign_companyfacts_hash':quarters[1]['companyfacts_sha256']='z'*64
    elif damage=='missing_original_match':
        quarters[0]['original_filing_and_companyfacts_matched']=False
    elif damage=='original_claims_financial_authority':
        quarters[1]['financial_paper_authorized']=True
    elif damage=='no_split_price_proof':proof['schema']='WRONG_SCHEMA'
    elif damage=='wrong_split_ratio':proof['sec_original_new_shares_per_old_share']=9
    elif damage=='wrong_split_date':proof['sec_original_split_date']='2024-07-11'
    elif damage=='wrong_provider_exdate':proof['provider_split_ex_date']='2024-07-12'
    elif damage=='incomplete_calendar':
        proof['provider_calendar_session_coverage_verified']=False
    elif damage=='missing_bars':proof['matching_returned_daily_bar_count']=1257
    elif damage=='wrong_pre_post_bar_count':proof['pre_split_returned_bars']=674
    elif damage=='provider_rights_falsely_accepted':
        proof['provider_price_data_rights_accepted']=True
    elif damage=='nan_eps':quarters[0]['diluted_eps_usd']='NaN'
    elif damage=='invalid_shares':quarters[1]['diluted_weighted_average_shares']='infinite'
    elif damage=='missing_quarter':quarters.pop(0)
    elif damage=='duplicate_quarter':quarters[1]=deepcopy(quarters[0])
    elif damage=='no_negative_original_loss':quarters[2]['diluted_eps_usd']='0.40'
    with pytest.raises(ValueError):
        replay.reconcile_avgo_original_eps_split_basis(quarters,proof)
