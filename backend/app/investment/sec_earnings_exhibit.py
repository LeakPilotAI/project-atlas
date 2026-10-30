"""QD-HIST-EPS-EXHIBIT-V1: directly disclosed GAAP quarters, never EPS differences.

One deliberately narrow table dialect. Unsupported layouts refuse. The original
8-K issuer/header and its actual exhibit link are verified before extraction.
This projection is separate from, and never edits, SEC Company Facts.
"""
import hashlib
import re
from calendar import monthrange
from datetime import date
from decimal import Context, Decimal, localcontext
from html.parser import HTMLParser

from app.investment.sec_edgar_research import number
from app.investment.sec_filing_evidence import _refuse, earnings_exhibit_reference

SCHEMA = 'SEC_EARNINGS_EXHIBIT_FACTS_V1'


def _words(text):
    return ' '.join(text.split()).casefold()


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables=[]; self.table=None; self.row=None; self.cell=None
        self.recent=''; self.nodes=0; self.pending={}; self.column=0

    def handle_decl(self, decl):
        if '[' in decl or 'entity' in decl.casefold():_refuse('EXHIBIT_ENTITY')

    def handle_starttag(self, tag, attrs):
        self.nodes+=1
        if self.nodes>250000:_refuse('EXHIBIT_CAPACITY')
        if tag not in ('table','tr','td','th'):return
        if len(attrs)!=len(dict(attrs)):_refuse('EXHIBIT_DUPLICATE_ATTRIBUTE')
        if tag=='table':
            if self.table is not None:_refuse('EXHIBIT_NESTED_TABLE_UNSUPPORTED')
            self.table={'context':self.recent[-1000:],'rows':[],'unsupported_layout':False};self.pending={}
        elif self.table is not None:
            if tag=='tr':
                if self.row is not None:_refuse('EXHIBIT_INCOMPLETE_ROW')
                self.row={column:text for column,(text,_) in self.pending.items()}
                self.pending={column:(text,left-1) for column,(text,left) in self.pending.items() if left>1}
                self.column=0
            else:
                attributes=dict(attrs)
                try:span=int(attributes.get('colspan','1'));height=int(attributes.get('rowspan','1'))
                except ValueError:_refuse('EXHIBIT_SPAN')
                if self.cell is not None or self.row is None or not 1<=span<=64 or not 1<=height<=16:
                    _refuse('EXHIBIT_SPAN')
                hidden='hidden' in attributes or bool(re.search(r'(?:^|;)\s*display\s*:\s*none\s*(?:;|$)',attributes.get('style',''),re.IGNORECASE))
                self.cell=['',span,height,hidden]

    def handle_data(self, text):
        self.recent=(self.recent+text+' ')[-2000:]
        if self.cell is not None:self.cell[0]+=text

    def handle_endtag(self, tag):
        if tag in ('td','th') and self.cell is not None:
            text,span,height,hidden=self.cell;self.cell=None
            if hidden:return  # CSS-hidden spacer cells occupy no table columns.
            while self.column in self.row:self.column+=1
            if self.column+span>64:
                self.table['unsupported_layout']=True
                return  # Bounded skip of unrelated unsupported table columns.
            for column in range(self.column,self.column+span):
                if column in self.row:_refuse('EXHIBIT_OVERLAPPING_SPAN')
                self.row[column]=_words(text)
                if height>1:self.pending[column]=(_words(text),height-1)
            self.column+=span
        elif tag=='tr' and self.table is not None:
            if self.row is None or self.cell is not None:_refuse('EXHIBIT_INCOMPLETE_ROW')
            self.table['rows'].append([self.row.get(i,'') for i in range(max(self.row,default=-1)+1)]);self.row=None
            if len(self.table['rows'])>4096:_refuse('EXHIBIT_CAPACITY')
        elif tag=='table':
            if self.table is None or self.row is not None or self.pending:_refuse('EXHIBIT_INCOMPLETE_TABLE')
            self.tables.append(self.table);self.table=None
            if len(self.tables)>128:_refuse('EXHIBIT_CAPACITY')


def _amount(text):
    if not re.fullmatch(r'\$?-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?|\(\$?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?\)',text):
        _refuse('EXHIBIT_NUMBER')
    value=number(text.replace('$','').replace(',','').strip('()'))
    return -value if text.startswith('(') else value


def parse_earnings_exhibit(main, document, reference, *, issuer_name, now):
    with localcontext(Context(prec=28)):
        return _parse_earnings_exhibit(main,document,reference,issuer_name=issuer_name,now=now)


def _parse_earnings_exhibit(main, document, reference, *, issuer_name, now):
    """Read only labelled, standalone GAAP income-statement quarter columns.

    The main 8-K supplies CIK/accession/date/link, not the quarter end. The
    exhibit's explicit three-month header supplies the period. Annual columns,
    basic EPS, non-GAAP reconciliation and point-in-time common shares are not
    interchangeable. Weighted diluted shares and net income cross-check EPS.
    """
    linked=earnings_exhibit_reference(main,reference,now=now)
    if (type(document) is not str or len(document.encode())>16*1024*1024
            or type(issuer_name) is not str or not issuer_name.strip()):_refuse('EXHIBIT_IDENTITY')
    parser=_Tables();parser.feed(document);parser.close()
    if parser.table is not None or parser.cell is not None:_refuse('EXHIBIT_INCOMPLETE_TABLE')
    candidates=[]
    for table in parser.tables:
        context=_words(table['context'])
        if (not context.endswith('(in millions, except per share amounts) (unaudited)')
                or _words(issuer_name)+' income statements' not in context[-350:]):continue
        if 'non-gaap' in context[-180:]:continue
        candidates.append(table)
    if len(candidates)!=1:_refuse('EXHIBIT_GAAP_STATEMENT_UNRESOLVED')
    if candidates[0]['unsupported_layout']:_refuse('EXHIBIT_CAPACITY')
    rows=candidates[0]['rows'];facts=[]
    period_rows=[i for i,r in enumerate(rows) if any(re.fullmatch(r'three months ended\s*[a-z]+ \d{1,2},?',c) for c in r)]
    if not period_rows or len({tuple(rows[i]) for i in period_rows})!=1:_refuse('EXHIBIT_QUARTER_HEADER')
    header_index=period_rows[0];header=rows[header_index]
    year_index=header_index+1
    while year_index<len(rows) and rows[year_index]==header and year_index<=header_index+3:year_index+=1
    if year_index>=len(rows) or year_index>header_index+3:_refuse('EXHIBIT_YEAR_HEADER')
    years=rows[year_index]
    width=len(header)
    if len(years)!=width or any(len(r)!=width for r in rows if any(r)):_refuse('EXHIBIT_COLUMN_ALIGNMENT')
    sections={};section=None
    for row in rows[year_index+1:]:
        label=row[0].rstrip(':') if row else ''
        if label in ('earnings per share','weighted average shares outstanding'):section=label
        elif label=='diluted' and section:
            if section in sections:_refuse('EXHIBIT_DUPLICATE_DILUTED_ROW')
            sections[section]=row
        elif label=='net income':
            if 'net income' in sections:_refuse('EXHIBIT_DUPLICATE_NET_INCOME')
            sections['net income']=row
    if set(sections)!={'earnings per share','weighted average shares outstanding','net income'}:
        _refuse('EXHIBIT_DILUTED_EVIDENCE_REQUIRED')
    expected_periods=set();completed_periods=set()
    for column,label in enumerate(header):
        match=re.fullmatch(r'three months ended\s*([a-z]+) (\d{1,2}),?',label)
        if not match:continue
        if not re.fullmatch(r'20\d{2}',years[column]):
            if years[column] or sections['earnings per share'][column]:_refuse('EXHIBIT_YEAR_HEADER')
            continue
        from time import strptime
        try:end=date(int(years[column]),strptime(match[1],'%B').tm_mon,int(match[2]))
        except ValueError:_refuse('EXHIBIT_QUARTER_DATE')
        if end.month not in (3,6,9,12) or end.day!=monthrange(end.year,end.month)[1] or end>date.fromisoformat(reference['filed']):
            _refuse('EXHIBIT_NONSTANDARD_OR_FUTURE_PERIOD')
        start=date(end.year,end.month-2,1)
        expected_periods.add(end)
        if not any(sections[key][column] for key in sections):continue
        if end in completed_periods:_refuse('EXHIBIT_DUPLICATE_PERIOD_COLUMN')
        completed_periods.add(end)
        eps=_amount(sections['earnings per share'][column])
        shares=_amount(sections['weighted average shares outstanding'][column])*Decimal(1000000)
        income=_amount(sections['net income'][column])*Decimal(1000000)
        if shares<=500000 or shares!=shares.to_integral_value():_refuse('EXHIBIT_DILUTED_SHARES')
        # Both table amounts are rounded to millions. Half a million of rounding
        # uncertainty on each term must contain the explicitly reported EPS.
        low=min(income/(shares-500000),income/(shares+500000))
        high=max(income/(shares-500000),income/(shares+500000))
        tolerance=Decimal(500000)/(shares-500000)+Decimal('.005')
        if not low-tolerance<=eps<=high+tolerance:_refuse('EXHIBIT_EPS_SHARE_CONTRADICTION')
        for concept,units,value in (('EarningsPerShareDiluted','USD/shares',eps),
                ('WeightedAverageNumberOfDilutedSharesOutstanding','shares',shares),('NetIncomeLoss','USD',income)):
            facts.append({'concept':concept,'start':str(start),'end':str(end),'units':units,'value':str(value),
                'filed':reference['filed'],'accession':reference['accession']})
    if not facts or completed_periods!=expected_periods:_refuse('EXHIBIT_NO_DIRECT_QUARTER')
    return {'schema':SCHEMA,'reference':dict(reference),'main_sha256':linked['main_sha256'],
        'url':linked['url'],'sha256':hashlib.sha256(document.encode()).hexdigest(),
        'accounting_basis':'REPORTED_GAAP_STANDALONE_QUARTER','share_definition':'WEIGHTED_AVERAGE_DILUTED',
        'units_note':'MILLIONS_EXCEPT_USD_PER_SHARE','facts':facts}


def exhibit_rows(exhibits, *, cik):
    """Validate the separately authenticated projection, not Company Facts rows.

    Source authentication remains the source verifier's responsibility. Shape,
    issuer, original references and direct EPS/share pairing are mandatory too.
    """
    if type(exhibits) is not list or not 0<len(exhibits)<=8:_refuse('EXHIBIT_SET_CAPACITY')
    rows=[];seen=set()
    for parsed in exhibits:
        if (type(parsed) is not dict or set(parsed)!={'schema','reference','main_sha256','url','sha256',
                'accounting_basis','share_definition','units_note','facts'} or parsed['schema']!=SCHEMA
                or parsed['accounting_basis']!='REPORTED_GAAP_STANDALONE_QUARTER'
                or parsed['share_definition']!='WEIGHTED_AVERAGE_DILUTED'
                or parsed['units_note']!='MILLIONS_EXCEPT_USD_PER_SHARE'
                or any(type(parsed[k]) is not str or not re.fullmatch('[0-9a-f]{64}',parsed[k]) for k in ('main_sha256','sha256'))):
            _refuse('EXHIBIT_PROJECTION_SCHEMA')
        ref=parsed['reference']
        if (type(ref) is not dict or set(ref)!={'cik','accession','filed','report_date','form','url'}
                or ref.get('cik')!=cik or ref.get('form')!='8-K' or ref.get('accession') in seen
                or not re.fullmatch(r'\d{10}-\d{2}-\d{6}',ref.get('accession',''))):_refuse('EXHIBIT_PROJECTION_ISSUER')
        if date.fromisoformat(ref['report_date'])>date.fromisoformat(ref['filed']):_refuse('EXHIBIT_PROJECTION_DATE')
        prefix=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{ref["accession"].replace("-","")}/'
        if (not parsed['url'].startswith(prefix) or not re.fullmatch(r'[A-Za-z0-9_-]*ex99[_\.-]?1\.htm',
                parsed['url'][len(prefix):],re.IGNORECASE) or not ref.get('url','').startswith(prefix)
                or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]{0,159}\.(?:htm|html|xml)',ref['url'][len(prefix):])):
            _refuse('EXHIBIT_PROJECTION_REFERENCE')
        seen.add(ref['accession'])
        facts=parsed['facts']
        if type(facts) is not list or not 0<len(facts)<=12:_refuse('EXHIBIT_FACT_CAPACITY')
        identities=set()
        for fact in facts:
            if (type(fact) is not dict or set(fact)!={'concept','start','end','units','value','filed','accession'}
                    or fact['accession']!=ref['accession'] or fact['filed']!=ref['filed']):_refuse('EXHIBIT_FACT_REFERENCE')
            key=fact['concept'],fact['start'],fact['end'],fact['units']
            if key in identities:_refuse('EXHIBIT_DUPLICATE_FACT')
            identities.add(key)
            if fact['concept']!='EarningsPerShareDiluted':continue
            if fact['units']!='USD/shares':_refuse('EXHIBIT_EPS_UNITS')
            matching=[s for s in facts if s['concept']=='WeightedAverageNumberOfDilutedSharesOutstanding'
                and (s['start'],s['end'],s['units'])==(fact['start'],fact['end'],'shares')]
            if len(matching)!=1 or number(matching[0]['value'])<=0:_refuse('EXHIBIT_DILUTED_WEIGHTED_SHARES')
            start,end,filed=(date.fromisoformat(fact[k]) for k in ('start','end','filed'))
            if not 70<=(end-start).days+1<=110 or end>filed:_refuse('EXHIBIT_DIRECT_QUARTER')
            rows.append({'start':fact['start'],'end':fact['end'],'filed':ref['filed'],'form':'8-K',
                'val':str(number(fact['value'])),'accn':ref['accession']})
    if not rows:_refuse('EXHIBIT_NO_DIRECT_QUARTER')
    return rows
