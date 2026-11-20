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


def test_sec_exhibit_long_issuer_filename_is_safe_but_still_requires_gaap_quarter():
    """A real AVGO 8-K uses an issuer-prefixed ex99 filename, not ex99_1."""
    main=release_main().replace('msft-ex99_1.htm',
        'avgo-11022025x8kxex99.htm')
    parsed_original=parsed(main=main)
    assert parsed_original['url'].endswith('/avgo-11022025x8kxex99.htm')
    assert [r['val'] for r in exhibit_rows([parsed_original],cik='0000789019')]==['4.81','3.65']
    # An identified SEC link alone never approves an unrelated or non-GAAP table.
    with pytest.raises(ResearchRefused):
        parsed(main=main,text=exhibit().replace('INCOME STATEMENTS','NON-GAAP INCOME STATEMENTS'))


@pytest.mark.parametrize('bad_link',[
    '../avgo-11022025x8kxex99.htm',
    'avgo-11022025x8kxex99.htm?x=1',
    'avgo-11022025x8kxex99.htm#f',
    'avgo-11022025x8kxex99_2.htm',
    '/avgo-11022025x8kxex99.htm',
])
def test_sec_long_original_exhibit_filename_refuses_unsafe_links(bad_link):
    main=release_main().replace('msft-ex99_1.htm',bad_link)
    with pytest.raises(ResearchRefused,match='EXHIBIT_REFERENCE'):
        parsed(main=main)

def avgo_release_reference():
    ref = release_reference()
    ref.update(cik='0001730168', accession='0001730168-25-000116',
               form='8-K', filed='2025-12-11', report_date='2025-12-11',
               url=('https://www.sec.gov/Archives/edgar/data/1730168/'
                    '000173016825000116/avgo-20251211.htm'))
    return ref


def avgo_release_main():
    return (release_main()
            .replace('0000789019', '0001730168')
            .replace('2026-07-29', '2025-12-11')
            .replace('2026-07-01', '2025-09-01')
            .replace('msft-ex99_1.htm', 'avgo-11022025x8kxex99.htm'))


def avgo_gaap_table():
    """Minimal synthetic version of original SEC AVGO GAAP operations layout."""
    def row(label='', blocks=None):
        head = '<td colspan="3">' + label + '</td><td colspan="3"></td>'
        cells = ''
        for column in range(5):
            value = (blocks or {}).get(column)
            width = 3 if column == 4 else 6
            if isinstance(value, tuple):  # Dollar marker plus a numeric value
                cells += ('<td>$</td><td>' + str(value[0])
                          + '</td><td colspan="' + str(width - 2) + '"></td>')
            elif value is not None:
                cells += ('<td colspan="2">' + str(value)
                          + '</td><td colspan="' + str(width - 2) + '"></td>')
            else:
                cells += '<td colspan="' + str(width) + '"></td>'
        return '<tr>' + head + cells + '</tr>'

    dates = ['November 2,2025', 'August 3,2025', 'November 3,2024',
             'November 2,2025', 'November 3,2024']
    header = ('<tr><td colspan="6"></td><td colspan="15">Fiscal Quarter Ended</td>'
              '<td colspan="3"></td><td colspan="9">Fiscal Year Ended</td></tr>')
    date_row = '<tr><td colspan="6"></td>'
    for i, day in enumerate(dates):
        date_row += '<td colspan="3">' + day + '</td>'
        if i < 4:
            date_row += '<td colspan="3"></td>'
    date_row += '</tr>'
    rows = ['<tr></tr>', header, date_row]
    rows += ['<tr></tr>'] * 6
    rows.append(row('net income', {0: ('8,518',), 1: ('4,140',),
                                   2: ('4,324',), 3: ('23,126',),
                                   4: ('5,895',)}))
    rows += ['<tr></tr>'] * 25
    rows.append(row('basic income per share:'))
    rows.append(row('net income per share', {0: ('1.80',)}))
    rows += ['<tr></tr>'] * 2
    rows.append(row('diluted income per share:'))
    rows.append(row('income per share from continuing operations', {0: ('1.74',)}))
    rows.append(row('net income per share', {0: ('1.74',), 1: ('0.85',),
                                            2: ('0.90',), 3: ('4.77',),
                                            4: ('1.23',)}))
    rows += ['<tr></tr>'] * 2
    rows.append(row('weighted-average shares used in per share calculations:'))
    rows.append(row('basic', {0: '4,732'}))
    rows.append(row('diluted', {0: '4,889', 1: '4,860', 2: '4,828',
                                3: '4,853', 4: '4,778'}))
    while len(rows) < 60:
        rows.append('<tr></tr>')
    return ('<html><h2>BROADCOM INC. CONDENSED CONSOLIDATED STATEMENTS '
            'OF OPERATIONS — UNAUDITED (IN MILLIONS, EXCEPT PER SHARE DATA)'
            '</h2><table>' + ''.join(rows) + '</table></html>')


def parsed_avgo(*, text=None, main=None, ref=None, issuer_name='BROADCOM INC.'):
    return parse_earnings_exhibit(
        avgo_release_main() if main is None else main,
        avgo_gaap_table() if text is None else text,
        avgo_release_reference() if ref is None else ref,
        issuer_name=issuer_name, now=NOW)


def test_avgo_original_gaap_column_layout_only_admits_direct_latest_quarter():
    value = parsed_avgo()
    assert [(f['concept'], f['value']) for f in value['facts']] == [
        ('EarningsPerShareDiluted', '1.74'),
        ('WeightedAverageNumberOfDilutedSharesOutstanding', '4889000000'),
        ('NetIncomeLoss', '8518000000'),
    ]
    assert [(r['start'], r['end'], r['val']) for r in
            exhibit_rows([value], cik='0001730168')] == [
        ('2025-08-04', '2025-11-02', '1.74'),
    ]
    assert value['reference']['form'] == '8-K'
    assert value['accounting_basis'] == 'REPORTED_GAAP_STANDALONE_QUARTER'
    assert all(f['end'] != '2024-11-03' for f in value['facts'])
    assert all(f['value'] != '1.95' for f in value['facts'])


@pytest.mark.parametrize('damage', [
    'non_gaap_statement', 'duplicate_gaap_table', 'wrong_income',
    'adjusted_eps', 'wrong_shares', 'no_diluted_section',
    'no_weighted_diluted_shares', 'quarter_header_says_year',
    'changed_previous_quarter', 'future_period', 'wrong_yearly_end',
    'duplicate_eps_row', 'annual_amount_as_eps',
])
def test_avgo_gaap_original_rejects_ambiguous_or_adjusted_quarters(damage):
    text = avgo_gaap_table()
    if damage == 'non_gaap_statement':
        text = text.replace('UNAUDITED (IN MILLIONS', 'NON-GAAP UNAUDITED (IN MILLIONS')
    elif damage == 'duplicate_gaap_table':
        title = text[text.index('<h2>'):text.index('</h2>') + 5]
        second = text[text.index('<table>'):text.index('</table>') + 8]
        text = text.replace('</html>', title + second + '</html>')
    elif damage == 'wrong_income':
        text = text.replace('8,518', '9,518', 1)
    elif damage == 'adjusted_eps':
        text = text.replace('1.74', '1.95')
    elif damage == 'wrong_shares':
        text = text.replace('4,889', '4,990', 1)
    elif damage == 'no_diluted_section':
        text = text.replace('diluted income per share:', 'adjusted earnings per share:')
    elif damage == 'no_weighted_diluted_shares':
        text = text.replace('<td colspan="3">diluted</td>', '<td colspan="3">adjusted</td>')
    elif damage == 'quarter_header_says_year':
        text = text.replace('Fiscal Quarter Ended', 'Fiscal Year Ended')
    elif damage == 'changed_previous_quarter':
        text = text.replace('August 3,2025', 'May 3,2025')
    elif damage == 'future_period':
        text = text.replace('November 2,2025', 'December 31,2026')
    elif damage == 'wrong_yearly_end':
        text = text.replace('November 2,2025', 'November 7,2025', 1)
    elif damage == 'duplicate_eps_row':
        text = text.replace('weighted-average shares used in per share calculations:',
            'net income per share</td></tr><tr><td colspan="3">'
            'weighted-average shares used in per share calculations:', 1)
    elif damage == 'annual_amount_as_eps':
        text = text.replace('1.74', '4.77')
    with pytest.raises((ResearchRefused, ValueError)):
        parsed_avgo(text=text)


@pytest.mark.parametrize('damage', ['wrong_issuer', 'wrong_cik', 'wrong_form', 'wrong_main'])
def test_avgo_original_gaap_requires_exact_sec_issuer_and_release(damage):
    ref = avgo_release_reference()
    name = 'BROADCOM INC.'
    main = avgo_release_main()
    if damage == 'wrong_issuer':
        name = 'FAKE BROADCOM INC.'
    elif damage == 'wrong_cik':
        ref['cik'] = '0000789019'
    elif damage == 'wrong_form':
        ref['form'] = '10-Q'
    else:
        main = main.replace('0001730168', '0000789019')
    with pytest.raises((ResearchRefused, ValueError)):
        parsed_avgo(ref=ref, main=main, issuer_name=name)


def avgo_fy2024_fixture():
    ref=avgo_release_reference()
    ref.update(accession='0001730168-24-000125',
               filed='2024-12-12',report_date='2024-12-12',
               url=('https://www.sec.gov/Archives/edgar/data/1730168/'
                    '000173016824000125/avgo-20241212.htm'))
    main=(avgo_release_main()
          .replace('2025-12-11','2024-12-12')
          .replace('2025-09-01','2024-09-01')
          .replace('avgo-11022025x8kxex99.htm',
                   'avgo-11032024x8kxex99.htm'))
    text=(avgo_gaap_table()
          .replace('November 3,2024','October 29,2023')
          .replace('November 2,2025','November 3,2024')
          .replace('August 3,2025','August 4,2024')
          .replace('basic income per share:',
                   'basic income (loss) per share (1):')
          .replace('diluted income per share:',
                   'diluted income (loss) per share (1):')
          .replace('weighted-average shares used in per share calculations:',
                   'weighted-average shares used in per share calculations (1):')
          .replace('<td colspan="3">net income</td>',
                   '<td colspan="3">net income (loss)</td>')
          .replace('net income per share','net income (loss) per share')
          .replace('8,518','4,324')
          .replace('1.74','0.90')
          .replace('4,889','4,828'))
    return main,text,ref


def test_avgo_fy2024_original_gaap_footnoted_loss_sections_direct_quarter():
    main,text,ref=avgo_fy2024_fixture()
    parsed=parse_earnings_exhibit(
        main,text,ref,issuer_name='BROADCOM INC.',now=NOW)
    assert [(row['start'],row['end'],row['val'])
            for row in exhibit_rows([parsed],cik='0001730168')]==[
        ('2024-08-05','2024-11-03','0.90')]
    assert {r['concept']:r['value'] for r in parsed['facts']}=={
        'EarningsPerShareDiluted':'0.90',
        'WeightedAverageNumberOfDilutedSharesOutstanding':'4828000000',
        'NetIncomeLoss':'4324000000',
    }
    assert all(r['end'] != '2023-10-29' for r in parsed['facts'])


@pytest.mark.parametrize('damage',[
    'adjusted_eps','net_income_wrong','wrong_diluted_shares',
    'basic_eps_substituted','missing_original_gaap_section',
    'duplicate_gaap_footnote','future_report_date','foreign_entity',
])
def test_avgo_fy2024_footnoted_layout_never_promotes_non_gaap(damage):
    main,text,ref=avgo_fy2024_fixture()
    if damage=='adjusted_eps':
        text=text.replace('0.90','1.42')
    elif damage=='net_income_wrong':
        text=text.replace('4,324','5,324')
    elif damage=='wrong_diluted_shares':
        text=text.replace('4,828','4,900')
    elif damage=='basic_eps_substituted':
        text=text.replace('diluted income (loss) per share (1):',
                          'basic income (loss) per share (1):')
    elif damage=='missing_original_gaap_section':
        text=text.replace('CONDENSED CONSOLIDATED STATEMENTS OF OPERATIONS',
                          'CONDENSED NON-GAAP STATEMENTS OF OPERATIONS')
    elif damage=='duplicate_gaap_footnote':
        duplicate=('<tr><td colspan="3">net income (loss) per share</td>'
                   '<td colspan="30"></td></tr>')
        text=text.replace('<tr><td colspan="3">weighted-average shares used in per share calculations (1):',
                          duplicate+'<tr><td colspan="3">weighted-average shares used in per share calculations (1):',1)
    elif damage=='future_report_date':
        text=text.replace('November 3,2024','December 31,2025')
    elif damage=='foreign_entity':
        ref['cik']='0000789019'
    with pytest.raises((ResearchRefused,ValueError)):
        parse_earnings_exhibit(main,text,ref,issuer_name='BROADCOM INC.',now=NOW)


def avgo_fy2023_common_stock_fixture():
    """Synthetic older GAAP common-stock EPS layout; no real SEC certification."""
    ref=avgo_release_reference()
    ref.update(accession='0001730168-23-000093',
               filed='2023-12-07',report_date='2023-12-07',
               url=('https://www.sec.gov/Archives/edgar/data/1730168/'
                    '000173016823000093/avgo-20231207.htm'))
    main=(avgo_release_main()
          .replace('2025-12-11','2023-12-07')
          .replace('2025-09-01','2023-11-01')
          .replace('avgo-11022025x8kxex99.htm',
                   'avgo-10292023x8kxex99.htm'))
    exhibit=(avgo_gaap_table()
          .replace('November 3,2024','October 30,2022')
          .replace('November 2,2025','October 29,2023')
          .replace('August 3,2025','July 30,2023')
          .replace('<td colspan="3">net income</td>',
                   '<td colspan="3">net income attributable to common stock</td>')
          .replace('basic income per share:',
                   'net income per share attributable to common stock:')
          .replace('diluted income per share:',
                   'GAAP income attributable to common stock:')
          .replace('<td colspan="3">net income per share</td>',
                   '<td colspan="3">basic</td>',1)
          .replace('<td colspan="3">net income per share</td>',
                   '<td colspan="3">diluted (1)</td>',1)
          .replace('<td colspan="3">diluted</td>',
                   '<td colspan="3">diluted (1)</td>')
          .replace('8,518','3,524')
          .replace('1.74','8.25')
          .replace('4,889','427'))
    return main,exhibit,ref


def test_avgo_fy2023_original_common_stock_gaap_eps_not_adjusted():
    main,text,ref=avgo_fy2023_common_stock_fixture()
    parsed=parse_earnings_exhibit(main,text,ref,issuer_name='BROADCOM INC.',now=NOW)
    assert [(r['start'],r['end'],r['val']) for r in
            exhibit_rows([parsed],cik='0001730168')] == [
        ('2023-07-31','2023-10-29','8.25')]
    assert {x['concept']:x['value'] for x in parsed['facts']}=={
        'EarningsPerShareDiluted':'8.25',
        'WeightedAverageNumberOfDilutedSharesOutstanding':'427000000',
        'NetIncomeLoss':'3524000000',
    }
    assert parsed['accounting_basis']=='REPORTED_GAAP_STANDALONE_QUARTER'


@pytest.mark.parametrize('damage',[
    'wrong_accession','wrong_filed_date','wrong_fiscal_quarter',
    'wrong_issuer','wrong_net_income','adjusted_eps_substituted',
    'wrong_diluted_share_count','missing_common_share_attribution',
    'wrong_diluted_label','duplicate_diluted_row','foreign_non_gaap_statement',
])
def test_avgo_2023_original_gaap_common_stock_layout_refuses_tampering(damage):
    main,text,ref=avgo_fy2023_common_stock_fixture()
    if damage=='wrong_accession':
        ref['accession']='0001730168-23-000092'
    elif damage=='wrong_filed_date':
        ref['filed']='2023-12-08'
    elif damage=='wrong_fiscal_quarter':
        text=text.replace('October 29,2023','October 30,2023')
    elif damage=='wrong_issuer':
        ref['cik']='0000789019'
    elif damage=='wrong_net_income':
        text=text.replace('3,524','5,524',1)
    elif damage=='adjusted_eps_substituted':
        text=text.replace('8.25','11.06')
    elif damage=='wrong_diluted_share_count':
        text=text.replace('427','467')
    elif damage=='missing_common_share_attribution':
        text=text.replace('net income attributable to common stock',
                          'adjusted non-GAAP income',1)
    elif damage=='wrong_diluted_label':
        text=text.replace('<td colspan="3">diluted (1)</td>',
                          '<td colspan="3">adjusted diluted</td>',1)
    elif damage=='duplicate_diluted_row':
        duplicated=('<tr><td colspan="3">diluted (1)</td>'
                    '<td colspan="30"></td></tr>')
        text=text.replace('<tr><td colspan="3">weighted-average shares used in per share calculations:',
                          duplicated+'<tr><td colspan="3">weighted-average shares used in per share calculations:',1)
    elif damage=='foreign_non_gaap_statement':
        text=text.replace('UNAUDITED (IN MILLIONS',
                          'NON-GAAP UNAUDITED (IN MILLIONS')
    with pytest.raises((ResearchRefused,ValueError)):
        parse_earnings_exhibit(main,text,ref,issuer_name='BROADCOM INC.',now=NOW)
