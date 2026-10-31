"""Synthetic original-exhibit tests: no providers or financial stores."""
from copy import deepcopy
from datetime import timedelta

import pytest
from app.investment.free_research_transport import ResearchRefused
from app.investment.historical_earnings_valuation import EXHIBIT_SCHEMA
from app.investment.sec_earnings_exhibit import exhibit_rows, parse_earnings_exhibit
from app.investment.sec_filing_evidence import quarter_witness
from test_free_research_pipeline import NOW
from test_historical_earnings_valuation import calculate, evidence
from test_sec_filing_evidence import document, reference


def release_reference():
    ref=reference();ref.update(form='8-K',filed='2026-07-29',report_date='2026-07-29')
    return ref


def release_main():
    return document().replace('>10-Q<','>8-K<').replace('2026-09-30','2026-07-29').replace('</html>',
        '<a href="msft-ex99_1.htm">Press release, July 29, 2026</a></html>')


def exhibit():
    return '''<html><h2>MICROSOFT CORPORATION</h2><h2>INCOME STATEMENTS</h2>
    <p>(In millions, except per share amounts) (Unaudited)</p><table>
    <tr><td></td><td colspan="3">Three Months Ended June 30,</td><td>Twelve Months Ended June 30,</td></tr>
    <tr><td></td><td>2026</td><td></td><td>2025</td><td>2026</td></tr>
    <tr><td>Net income</td><td>$35,766</td><td></td><td>$27,233</td><td>$133,749</td></tr>
    <tr><td>Earnings per share:</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>Basic</td><td>$4.82</td><td></td><td>$3.66</td><td>$18.00</td></tr>
    <tr><td>Diluted</td><td>$4.81</td><td></td><td>$3.65</td><td>$17.95</td></tr>
    <tr><td>Weighted average shares outstanding:</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>Basic</td><td>7,427</td><td></td><td>7,432</td><td>7,429</td></tr>
    <tr><td>Diluted</td><td>7,443</td><td></td><td>7,461</td><td>7,453</td></tr>
    </table></html>'''


def parsed(**kwargs):
    return parse_earnings_exhibit(kwargs.pop('main',release_main()),kwargs.pop('text',exhibit()),
        kwargs.pop('ref',release_reference()),issuer_name='MICROSOFT CORPORATION',now=NOW,**kwargs)


def test_direct_gaap_quarter_original_reference_and_weighted_share_basis():
    value=parsed();rows=exhibit_rows([value],cik='0000789019')
    assert [(r['start'],r['end'],r['val']) for r in rows]==[
        ('2026-04-01','2026-06-30','4.81'),('2025-04-01','2025-06-30','3.65')]
    assert all(r['filed']=='2026-07-29' for r in rows)  # Never backdate comparison.
    assert all(r['val']!='17.95' for r in rows)  # Annual not a quarter.
    assert value['share_definition']=='WEIGHTED_AVERAGE_DILUTED'
    shares=[f['value'] for f in value['facts'] if f['concept']=='WeightedAverageNumberOfDilutedSharesOutstanding']
    assert shares==['7443000000','7461000000']
    witness=quarter_witness(value,rows[0],share_basis='SYNTHETIC-SPLIT-BASIS')
    assert witness['filing_sha256']==value['sha256'] and witness['eps']=='4.81'


def test_row_spanning_headers_and_hidden_spacers_keep_exact_columns():
    text=exhibit().replace('<td></td><td colspan="3">Three', '<td rowspan="2"></td><td colspan="3" rowspan="2">Three',1)
    text=text.replace('<td>Twelve Months Ended June 30,</td></tr>',
        '<td rowspan="2">Twelve Months Ended June 30,</td></tr><tr><td style="display:none"></td></tr>')
    assert [r['val'] for r in exhibit_rows([parsed(text=text)],cik='0000789019')]==['4.81','3.65']


def test_table_capacity_is_explicit_and_bounded():
    # Real old filings contain many layout tables. They are not financial
    # evidence, but still count toward the bounded document parser ceiling.
    text='<table><tr><td>layout</td></tr></table>'*81+exhibit()
    assert len(parsed(text=text)['facts'])==6
    with pytest.raises(ResearchRefused,match='CAPACITY'):
        parsed(text='<table></table>'*128+exhibit())


@pytest.mark.parametrize('damage',['annual','ytd','non_gaap','wrong_name','outstanding','basic_only','wrong_shares',
    'bad_eps','wrong_units','future_period','bad_year','columns','rowspan','nested','duplicate','duplicate_eps',
    'negative_shares','incomplete','missing_link','foreign_main','duplicate_link','traversal','bad_number','dtd'])
def test_incomplete_ambiguous_or_non_equivalent_exhibits_refuse(damage):
    text=exhibit();main=release_main()
    if damage=='annual':text=text.replace('Three Months','Twelve Months')
    elif damage=='ytd':text=text.replace('Three Months','Nine Months')
    elif damage=='non_gaap':text=text.replace('INCOME STATEMENTS','NON-GAAP INCOME STATEMENTS')
    elif damage=='wrong_name':text=text.replace('MICROSOFT CORPORATION','OTHER COMPANY')
    elif damage=='outstanding':text=text.replace('Weighted average shares outstanding:','Common shares outstanding:')
    elif damage=='basic_only':text=text.replace('Diluted','Basic')
    elif damage=='wrong_shares':text=text.replace('7,443','9,000')
    elif damage=='bad_eps':text=text.replace('$4.81','$17.95')
    elif damage=='wrong_units':text=text.replace('In millions','In thousands')
    elif damage=='future_period':text=text.replace('June 30','December 31')
    elif damage=='bad_year':text=text.replace('<td>2026</td>','<td>year 2026</td>')
    elif damage=='columns':text=text.replace('colspan="3"','colspan="4"')
    elif damage=='rowspan':text=text.replace('colspan="3"','colspan="3" rowspan="2"')
    elif damage=='nested':text=text.replace('<td>$4.81</td>','<td><table></table>$4.81</td>')
    elif damage=='duplicate':text+=text
    elif damage=='duplicate_eps':text=text.replace('<tr><td>Basic</td><td>$4.82', '<tr><td>Diluted</td><td>$4.82')
    elif damage=='negative_shares':text=text.replace('7,443','(7,443)')
    elif damage=='incomplete':text=text.replace('</table>','')
    elif damage=='missing_link':main=main.replace('Press release','Other attachment')
    elif damage=='foreign_main':main=main.replace('0000789019','0000000001')
    elif damage=='duplicate_link':main=main.replace('</html>','<a href="other-ex99_1.htm">Press release</a></html>')
    elif damage=='traversal':main=main.replace('msft-ex99_1.htm','../msft-ex99_1.htm')
    elif damage=='bad_number':text=text.replace('$4.81','$4.81 estimated')
    elif damage=='dtd':text='<!DOCTYPE html [<!ENTITY a SYSTEM "file:///secret">]>'+text
    with pytest.raises((ResearchRefused,ValueError)):parsed(main=main,text=text)


def test_v2_exhibits_do_not_modify_companyfacts_or_infer_eps():
    packet=evidence();original=deepcopy(packet['companyfacts'])
    quarters=packet['companyfacts']['facts']['us-gaap']['EarningsPerShareDiluted']['units']['USD/shares']
    target=quarters.pop(7);witness=packet['filing_witnesses'][7]
    ex=parsed()
    ex['reference'].update(accession=target['accn'],filed=target['filed'],report_date=target['filed'])
    # Synthetic method fixtures use mnemonic accessions; use a genuine-format
    # synthetic accession for this separate projection integration.
    accession='0000000000-24-000001'
    ex['reference'].update(accession=accession,cik=packet['instrument']['cik'])
    prefix='https://www.sec.gov/Archives/edgar/data/789019/'+accession.replace('-','')+'/'
    ex['url']=prefix+'msft-ex99_1.htm';ex['reference']['url']=prefix+'msft.htm'
    ex['facts']=[]
    for concept,units,value in [('EarningsPerShareDiluted','USD/shares','1'),
        ('WeightedAverageNumberOfDilutedSharesOutstanding','shares','1000000'),('NetIncomeLoss','USD','1000000')]:
        ex['facts'].append({'concept':concept,'units':units,'value':value,'accession':accession,
            'filed':target['filed'],'start':target['start'],'end':target['end']})
    witness.update(accession=accession,filing_sha256=ex['sha256'])
    unchanged=deepcopy(packet['companyfacts'])
    packet.update(schema=EXHIBIT_SCHEMA,earnings_exhibits=[ex])
    result=calculate(packet)
    assert result['current_eps_proxy']=='4' and len(result['anchors'])==13
    assert packet['companyfacts']==unchanged and packet['companyfacts']!=original
    # Putting the supplement in Company Facts alone never admits the missing
    # quarter. V1 skips 8-K records and the complete-history guard still fails.
    untrusted=deepcopy(packet);untrusted.pop('earnings_exhibits');untrusted['schema']='QD_HISTORICAL_EARNINGS_INPUT_V1'
    untrusted['companyfacts']['facts']['us-gaap']['EarningsPerShareDiluted']['units']['USD/shares']+=exhibit_rows([ex],cik='0000789019')
    with pytest.raises(ResearchRefused):calculate(untrusted)


@pytest.mark.parametrize('damage',['issuer','basis','hash','duplicate','missing_shares','reference','annual_period','future_filing'])
def test_projection_supplement_validation(damage):
    ex=parsed()
    if damage=='issuer':ex['reference']['cik']='0000000001'
    elif damage=='basis':ex['accounting_basis']='ADJUSTED'
    elif damage=='hash':ex['main_sha256']='made-up'
    elif damage=='duplicate':ex['facts'].append(deepcopy(ex['facts'][0]))
    elif damage=='missing_shares':ex['facts']=[r for r in ex['facts'] if r['concept']!='WeightedAverageNumberOfDilutedSharesOutstanding']
    elif damage=='reference':ex['url']=ex['url'].replace('/789019/','/1/')
    elif damage=='annual_period':ex['facts'][0]['start']='2025-07-01'
    elif damage=='future_filing':ex['facts'][0]['filed']=(NOW+timedelta(days=1)).date().isoformat()
    with pytest.raises(ResearchRefused):exhibit_rows([ex],cik='0000789019')
