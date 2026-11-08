"""Synthetic original SEC filing and confined data-only transport tests."""
from copy import deepcopy

import pytest
from app.investment.free_research_transport import FreeResearchClient, ResearchRefused
from app.investment.sec_filing_evidence import (
    filing_rows,
    parse_original_filing,
    quarter_witness,
)
from test_free_research_pipeline import CONTACT, NOW, client

SUBMISSIONS='https://data.sec.gov/submissions/CIK0000789019.json'
DOCUMENT='https://www.sec.gov/Archives/edgar/data/789019/000000000026000001/msft.htm'


def submission():
    return {'cik':'789019','tickers':['MSFT'],'entityType':'operating','sic':'7372','filings':{'recent':{
        'accessionNumber':['0000000000-26-000001'],'filingDate':['2026-10-20'],'reportDate':['2026-09-30'],
        'form':['10-Q'],'primaryDocument':['msft.htm']}}}


def document():
    return '''<!DOCTYPE html><html xmlns:us-gaap="http://fasb.org/us-gaap/2026"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:dei="http://xbrl.sec.gov/dei/2026"
      xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
      <xbrli:context id="quarter"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000789019</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:startDate>2026-07-01</xbrli:startDate><xbrli:endDate>2026-09-30</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:context id="point"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000789019</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:instant>2026-09-30</xbrli:instant></xbrli:period></xbrli:context>
      <xbrli:unit id="eps"><xbrli:divide><xbrli:unitNumerator><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unitNumerator>
      <xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator></xbrli:divide></xbrli:unit>
      <xbrli:unit id="shares"><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unit>
      <ix:nonNumeric name="dei:DocumentType" contextRef="quarter">10-Q</ix:nonNumeric>
      <ix:nonNumeric name="dei:DocumentPeriodEndDate" contextRef="quarter">2026-09-30</ix:nonNumeric>
      <ix:nonNumeric name="dei:EntityCentralIndexKey" contextRef="quarter">0000789019</ix:nonNumeric>
      <ix:nonFraction name="us-gaap:EarningsPerShareDiluted" contextRef="quarter" unitRef="eps" decimals="2">2.<span>2</span>2</ix:nonFraction>
      <ix:nonFraction name="us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding" contextRef="quarter" unitRef="shares" scale="6">1,000</ix:nonFraction>
      <ix:nonFraction name="us-gaap:CommonStockSharesOutstanding" contextRef="point" unitRef="shares" scale="6">900</ix:nonFraction>
      </html>'''


def reference():
    return next(iter(filing_rows(submission(),cik='0000789019',symbol='MSFT').values()))


def requested():
    return {'accn':'0000000000-26-000001','start':'2026-07-01','end':'2026-09-30',
            'filed':'2026-10-20','form':'10-Q','val':'2.22'}


def test_original_eps_and_share_definitions_remain_distinct():
    result=parse_original_filing(document(),reference(),now=NOW)
    facts={r['concept']:r for r in result['facts']}
    assert facts['EarningsPerShareDiluted']['value']=='2.22'
    assert facts['WeightedAverageNumberOfDilutedSharesOutstanding']['value']=='1000000000'
    assert facts['CommonStockSharesOutstanding']['value']=='900000000'
    assert facts['CommonStockSharesOutstanding']['start'] is None
    with pytest.raises(ResearchRefused,match='SPLIT_BASIS'):quarter_witness(result,requested())
    witness=quarter_witness(result,requested(),share_basis='SYNTHETIC-VERIFIED-BASIS')
    assert witness['eps']=='2.22' and witness['filing_sha256']==result['sha256']


@pytest.mark.parametrize('damage',['issuer','symbol','document_escape','duplicate_accession','columns','future_report'])
def test_submission_metadata_refuses_identity_or_path_ambiguity(damage):
    data=submission();rows=data['filings']['recent']
    if damage=='issuer':data['cik']='1'
    elif damage=='symbol':data['tickers']=['OTHER']
    elif damage=='document_escape':rows['primaryDocument']=['../secret.htm']
    elif damage=='duplicate_accession':
        for key in rows:rows[key]*=2
    elif damage=='columns':rows['form']=[]
    elif damage=='future_report':rows['reportDate']=['2026-10-21']
    with pytest.raises((ResearchRefused,ValueError)):filing_rows(data,cik='0000789019',symbol='MSFT')


@pytest.mark.parametrize('damage',['foreign_entity','period','unit','scale','continued','nil','dtd','conflicting','unclosed','namespace'])
def test_original_inline_evidence_refuses_bad_context_or_values(damage):
    text=document()
    if damage=='foreign_entity':text=text.replace('0000789019','0000000001')
    elif damage=='period':text=text.replace('2026-09-30','2027-09-30')
    elif damage=='unit':text=text.replace('unitRef="eps"','unitRef="unknown"')
    elif damage=='scale':text=text.replace('scale="6"','scale="99"')
    elif damage=='continued':text=text.replace('decimals="2"','decimals="2" continuedAt="missing"')
    elif damage=='nil':text=text.replace('decimals="2"','decimals="2" xsi:nil="true"')
    elif damage=='dtd':text=text.replace('<!DOCTYPE html>','<!DOCTYPE html [<!ENTITY x SYSTEM "file:///private">]>')
    elif damage=='conflicting':text=text.replace('</html>','<ix:nonFraction name="us-gaap:EarningsPerShareDiluted" contextRef="quarter" unitRef="eps">999</ix:nonFraction></html>')
    elif damage=='unclosed':text=text.replace('</xbrli:context>','',1)
    elif damage=='namespace':text=text.replace('http://fasb.org/us-gaap/2026','http://untrusted.invalid/us-gaap/2026')
    with pytest.raises((ResearchRefused,ValueError)):parse_original_filing(text,reference(),now=NOW)


def test_quarter_match_never_substitutes_annual_or_outstanding_shares():
    result=parse_original_filing(document(),reference(),now=NOW)
    bad=deepcopy(requested());bad['start']='2026-01-01'
    with pytest.raises(ResearchRefused):quarter_witness(result,bad,share_basis='SYNTHETIC')
    text=document().replace('us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding','us-gaap:Unrelated')
    result=parse_original_filing(text,reference(),now=NOW)
    with pytest.raises(ResearchRefused,match='WEIGHTED'):quarter_witness(result,requested(),share_basis='SYNTHETIC')


@pytest.mark.parametrize('namespace',['http://xbrl.sec.gov/dei/2021q4','http://xbrl.sec.gov/dei/2020-01-31'])
def test_official_historical_dei_versions_keep_issuer_type_and_dates(namespace):
    text=document().replace('http://xbrl.sec.gov/dei/2026',namespace)
    assert parse_original_filing(text,reference(),now=NOW)['facts']


def test_unrelated_currency_unit_is_not_treated_as_usd():
    text=document().replace('</html>','<xbrli:unit id="euro"><xbrli:measure>iso4217:EUR</xbrli:measure></xbrli:unit></html>')
    assert parse_original_filing(text,reference(),now=NOW)['facts']


@pytest.mark.parametrize('attribute',['contextRef="missing"','contextRef="quarter" continuedAt="missing"',
    'contextRef="quarter" xsi:nil="true"'])
def test_document_identity_cannot_use_missing_context_or_nil_continued_fact(attribute):
    text=document().replace('name="dei:DocumentType" contextRef="quarter"','name="dei:DocumentType" '+attribute)
    with pytest.raises(ResearchRefused,match='DOCUMENT_IDENTITY'):parse_original_filing(text,reference(),now=NOW)


def test_official_documents_are_cached_without_reencoding_or_json_assumption(tmp_path):
    raw=('\ufeff'+document()).encode()
    c=FreeResearchClient(cache_root=tmp_path,now=lambda:NOW,sec_user_agent=CONTACT,fetch=lambda *args:raw)
    text,receipt=c.get(DOCUMENT,ttl=60)
    assert text.encode()==raw and receipt['provider']=='SEC_EDGAR_DOCUMENT'
    assert c.get(DOCUMENT,ttl=60)[0]==text and c.attempted==1


@pytest.mark.parametrize('url',[SUBMISSIONS,'https://data.sec.gov/submissions/CIK0000789019-submissions-001.json',
    DOCUMENT])
def test_narrow_source_scope_is_allowed_only_with_identification(tmp_path,url):
    c,_,_,_=client(tmp_path)
    assert c._scope(url)[0].startswith('SEC_EDGAR')


@pytest.mark.parametrize('url',['https://www.sec.gov/Archives/edgar/data/789019/000000000026000001/../x.htm',
    DOCUMENT+'?redirect=x',DOCUMENT.replace('www.sec.gov','evil.invalid'),
    'https://data.sec.gov/submissions/../../x.json','https://paper-api.alpaca.markets/v2/orders'])
def test_filing_endpoint_expansion_does_not_allow_escape_or_orders(tmp_path,url):
    c,_,_,_=client(tmp_path)
    with pytest.raises(ResearchRefused):c._scope(url)
