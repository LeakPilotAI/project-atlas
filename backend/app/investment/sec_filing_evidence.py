"""Bounded SEC submission/index and original inline-XBRL verification.

No network on import, guessed filings, unverified share-basis assertions or EPS
inference. Legacy shares-outstanding and diluted-average shares stay distinct.
"""
import hashlib
import re
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser
from time import strptime

from app.investment.free_research_transport import ResearchRefused
from app.investment.sec_edgar_research import number

CONCEPTS = {'EarningsPerShareDiluted','WeightedAverageNumberOfDilutedSharesOutstanding',
            'CommonStockSharesOutstanding','NetIncomeLoss','NetIncomeLossAvailableToCommonStockholdersBasic',
            'StockholdersEquity','StockSplitConversionRatio1','StockSplitConversionRatio'}
VOID = {'br','hr','meta','link','img','input','wbr','source','area','base','col','embed','param','track'}


def _refuse(code):
    raise ResearchRefused('SEC_ORIGINAL_'+code)


def filing_rows(packet, *, cik, symbol=None, forms=('10-Q','10-K','10-Q/A','10-K/A')):
    """Return provider-owned accession metadata without inventing document names."""
    if not re.fullmatch(r'\d{10}',cik) or type(packet) is not dict:
        _refuse('SUBMISSIONS_IDENTITY')
    if 'filings' in packet:
        if str(packet.get('cik')).zfill(10) != cik or symbol is not None and symbol not in packet.get('tickers',[]):
            _refuse('SUBMISSIONS_IDENTITY')
        columns = packet['filings']['recent']
    else:
        columns = packet  # Historical file is bound by its current parent manifest.
    names = ('accessionNumber','filingDate','reportDate','form','primaryDocument')
    if (type(columns) is not dict or any(type(columns.get(k)) is not list for k in names)
            or len({len(columns[k]) for k in names}) != 1 or len(columns['form']) > 10000):
        _refuse('SUBMISSIONS_COLUMNS')
    out={}
    for values in zip(*(columns[k] for k in names),strict=True):
        accession,filed,report,form,document=values
        if form not in forms:
            continue
        if (type(accession) is not str or not re.fullmatch(r'\d{10}-\d{2}-\d{6}',accession)
                or type(document) is not str or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]{0,159}\.(?:htm|html|xml)',document)):
            _refuse('DOCUMENT_REFERENCE')
        filing_date,report_date=date.fromisoformat(filed),date.fromisoformat(report)
        if report_date>filing_date or accession in out:
            _refuse('ACCESSION_OR_PERIOD_CONFLICT')
        out[accession]={'cik':cik,'accession':accession,'filed':filed,'report_date':report,'form':form,
            'url':f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-","")}/{document}'}
    return out


class _Node:
    def __init__(self,tag,attrs):
        self.tag,self.attrs,self.children,self.parts=tag,dict(attrs),[],[]

    def text(self):
        return ''.join(part if isinstance(part,str) else part.text() for part in self.parts)

    def find(self,local):
        return [n for child in self.children for n in ([child] if child.tag.split(':')[-1]==local else [])+child.find(local)]


class _Inline(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.roots=[];self.stack=[];self.nodes=0;self.namespaces={}

    def handle_decl(self,decl):
        if not decl.lower().startswith('doctype html'):
            _refuse('DOCUMENT_DECLARATION')
        if '[' in decl or 'entity' in decl.lower():
            _refuse('EXTERNAL_ENTITY')

    def handle_starttag(self,tag,attrs):
        self.nodes+=1
        if self.nodes>250000 or len(self.stack)>64:
            _refuse('DOCUMENT_CAPACITY')
        if len(attrs)!=len({key for key,_ in attrs}):
            _refuse('DUPLICATE_ATTRIBUTE')
        for key,value in attrs:
            if key.startswith('xmlns:'):
                prefix=key.split(':',1)[1]
                if prefix in self.namespaces and self.namespaces[prefix]!=value:
                    _refuse('NAMESPACE_CONFLICT')
                self.namespaces[prefix]=value
        if tag in VOID:
            return
        local=tag.split(':')[-1]
        if self.stack or local in ('context','unit','nonfraction','nonnumeric'):
            node=_Node(tag,attrs)
            if self.stack:
                self.stack[-1].children.append(node);self.stack[-1].parts.append(node)
            else:self.roots.append(node)
            self.stack.append(node)

    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID:self.handle_endtag(tag)

    def handle_endtag(self,tag):
        if self.stack:
            if self.stack[-1].tag != tag:
                _refuse('UNBALANCED_INLINE_EVIDENCE')
            self.stack.pop()

    def handle_data(self,data):
        if self.stack:self.stack[-1].parts.append(data)


def parse_original_filing(document, reference, *, now, require_facts=True):
    if type(document) is not str or len(document.encode())>16*1024*1024:
        _refuse('DOCUMENT_CAPACITY')
    if (date.fromisoformat(reference['filed'])>now.date()
            or not re.fullmatch(r'\d{10}',reference['cik'])
            or not re.fullmatch(r'\d{10}-\d{2}-\d{6}',reference['accession'])):
        _refuse('REFERENCE_IDENTITY_OR_TIME')
    parser=_Inline();parser.feed(document);parser.close()
    if parser.stack:
        _refuse('INCOMPLETE_DOCUMENT')
    contexts={};units={};facts=[];dei={}
    def measure(node):
        prefix,sep,local=node.text().strip().partition(':')
        expected={'USD':'http://www.xbrl.org/2003/iso4217','shares':'http://www.xbrl.org/2003/instance',
                  'pure':'http://www.xbrl.org/2003/instance'}
        if not sep or prefix.lower() not in parser.namespaces:_refuse('UNIT_NAMESPACE')
        if local not in expected:return 'UNSUPPORTED:'+prefix+':'+local
        if parser.namespaces[prefix.lower()]!=expected[local]:_refuse('UNIT_NAMESPACE')
        return local
    for node in parser.roots:
        local=node.tag.split(':')[-1]
        if local=='context':
            if parser.namespaces.get(node.tag.split(':')[0])!='http://www.xbrl.org/2003/instance':_refuse('CONTEXT_NAMESPACE')
            identity=node.attrs.get('id')
            if not identity or identity in contexts:_refuse('CONTEXT_IDENTITY')
            identifiers=node.find('identifier');starts=node.find('startdate');ends=node.find('enddate');instants=node.find('instant')
            if (len(identifiers)!=1 or not identifiers[0].text().strip().isdigit()
                    or identifiers[0].attrs.get('scheme') not in ('http://www.sec.gov/CIK','https://www.sec.gov/CIK')):_refuse('CONTEXT_ENTITY')
            if str(int(identifiers[0].text().strip())).zfill(10)!=reference['cik']:_refuse('CONTEXT_FOREIGN_ENTITY')
            dimensioned=bool(node.find('segment') or node.find('scenario'))
            if len(starts)==len(ends)==1 and not instants:
                start,end=(date.fromisoformat(n[0].text().strip()) for n in (starts,ends))
            elif len(instants)==1 and not starts and not ends:
                start=None;end=date.fromisoformat(instants[0].text().strip())
            else:_refuse('CONTEXT_PERIOD')
            if end>date.fromisoformat(reference['filed']) or start is not None and start>end:_refuse('CONTEXT_PERIOD')
            contexts[identity]=(start,end,dimensioned)
        elif local=='unit':
            if parser.namespaces.get(node.tag.split(':')[0])!='http://www.xbrl.org/2003/instance':_refuse('UNIT_NAMESPACE')
            identity=node.attrs.get('id')
            if not identity or identity in units:_refuse('UNIT_IDENTITY')
            numerator=node.find('unitnumerator');denominator=node.find('unitdenominator')
            if numerator or denominator:
                if len(numerator)!=1 or len(denominator)!=1:_refuse('UNIT_RATIO')
                a=numerator[0].find('measure');b=denominator[0].find('measure')
                if len(a)!=1 or len(b)!=1:_refuse('UNIT_RATIO')
                unit=measure(a[0])+'/'+measure(b[0])
            else:
                measures=node.find('measure')
                if len(measures)!=1:_refuse('UNIT_MEASURE')
                unit=measure(measures[0])
            units[identity]=unit
    for node in parser.roots:
        if node.tag.split(':')[-1] not in ('nonfraction','nonnumeric'):continue
        if parser.namespaces.get(node.tag.split(':')[0]) not in (
                'http://www.xbrl.org/2013/inlineXBRL','http://www.xbrl.org/2008/inlineXBRL'):
            _refuse('INLINE_NAMESPACE')
        name=node.attrs.get('name','');prefix,sep,concept=name.partition(':')
        namespace=parser.namespaces.get(prefix.lower(),'')
        if re.fullmatch(r'https?://xbrl.sec.gov/dei/(?:\d{4}(?:-\d{2}-\d{2})?|202[12]q4)',namespace) and concept in (
                'DocumentType','DocumentPeriodEndDate','EntityCentralIndexKey'):
            if (node.attrs.get('continuedat') or node.attrs.get('xsi:nil') in ('true','1')
                    or node.attrs.get('contextref') not in contexts):_refuse('INCOMPLETE_DOCUMENT_IDENTITY')
            dei.setdefault(concept,set()).add(node.text().strip())
            continue
        if not sep or concept not in CONCEPTS or not re.fullmatch(r'https?://fasb.org/us-gaap/\d{4}(?:-\d{2}-\d{2})?',namespace):continue
        if node.attrs.get('continuedat') or node.attrs.get('xsi:nil') in ('true','1'):_refuse('INCOMPLETE_FACT')
        context=contexts.get(node.attrs.get('contextref'));unit=units.get(node.attrs.get('unitref'))
        if context is None or unit is None:_refuse('FACT_CONTEXT_OR_UNIT')
        if context[2]:continue  # Dimensional classes/segments are not consolidated facts.
        raw=node.text().strip().replace('\u00a0','').replace(' ','')
        if not re.fullmatch(r'-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?',raw):_refuse('FACT_NUMERIC_FORMAT')
        if node.attrs.get('format','').split(':')[-1].lower() not in ('','num-dot-decimal','numdotdecimal'):_refuse('FACT_TRANSFORM')
        scale=int(node.attrs.get('scale','0'))
        if not -12<=scale<=12 or node.attrs.get('sign','') not in ('','-'):_refuse('FACT_SCALE')
        value=number(raw.replace(',',''))*Decimal(10)**scale
        if node.attrs.get('sign')=='-':value=-value
        record={'concept':concept,'start':str(context[0]) if context[0] else None,'end':str(context[1]),
                'units':unit,'value':str(value),'filed':reference['filed'],'accession':reference['accession']}
        key=tuple(record[k] for k in ('concept','start','end','units'))
        prior=next((f for f in facts if tuple(f[k] for k in ('concept','start','end','units'))==key),None)
        if prior is not None and number(prior['value'])!=value:_refuse('CONTRADICTORY_FACT')
        if prior is None:facts.append(record)
    if require_facts and not facts:_refuse('NO_VERIFIED_STANDARD_FACTS')
    if dei.get('DocumentType')!={reference['form']}:_refuse('DOCUMENT_TYPE')
    if len(dei.get('EntityCentralIndexKey',()))!=1 or str(int(next(iter(dei['EntityCentralIndexKey'])))).zfill(10)!=reference['cik']:
        _refuse('DOCUMENT_ISSUER')
    dates=set()
    for raw in dei.get('DocumentPeriodEndDate',()):
        for fmt in ('%Y-%m-%d','%B %d, %Y','%b %d, %Y','%m/%d/%Y'):
            try:dates.add(date(*strptime(raw,fmt)[:3]).isoformat());break
            except ValueError:continue
        else:_refuse('DOCUMENT_REPORT_DATE')
    if dates!={reference['report_date']}:_refuse('DOCUMENT_REPORT_DATE')
    return {'schema':'SEC_ORIGINAL_INLINE_FACTS_V1','reference':dict(reference),
            'sha256':hashlib.sha256(document.encode()).hexdigest(),'facts':facts}


class _Links(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.current=None;self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.current=[dict(attrs).get('href',''),'']
    def handle_data(self,data):
        if self.current is not None:self.current[1]+=data
    def handle_endtag(self,tag):
        if tag=='a' and self.current is not None:self.links.append(self.current);self.current=None


def earnings_exhibit_reference(main, reference, *, now):
    if reference['form']!='8-K':_refuse('EARNINGS_FORM')
    parsed=parse_original_filing(main,reference,now=now,require_facts=False)
    parser=_Links();parser.feed(main);parser.close()
    matches=[href for href,label in parser.links if re.fullmatch(
        r'[A-Za-z0-9_-]*ex99[_\.-]?1\.htm',href,re.IGNORECASE)
        and ('press release' in label.lower() or 'earnings release' in label.lower())]
    if len(set(matches))!=1:_refuse('EARNINGS_EXHIBIT_REFERENCE')
    return {'url':reference['url'].rsplit('/',1)[0]+'/'+matches[0],
            'main_sha256':parsed['sha256'],'reference':dict(reference)}


def quarter_witness(parsed, requested, *, share_basis=None):
    """Match original reported EPS; do not infer quarters, shares or split basis."""
    reference=parsed['reference']
    if (requested['accn']!=reference['accession'] or requested['filed']!=reference['filed']
            or requested['form']!=reference['form']):_refuse('FACT_REFERENCE_MISMATCH')
    matches=[r for r in parsed['facts'] if r['concept']=='EarningsPerShareDiluted'
        and r['start']==requested['start'] and r['end']==requested['end'] and r['units']=='USD/shares']
    if len(matches)!=1 or number(matches[0]['value'])!=number(requested['val']):_refuse('QUARTER_EPS_MISMATCH')
    duration=(date.fromisoformat(requested['end'])-date.fromisoformat(requested['start'])).days+1
    if not 70<=duration<=110:_refuse('STANDALONE_QUARTER_REQUIRED')
    diluted=[r for r in parsed['facts'] if r['concept']=='WeightedAverageNumberOfDilutedSharesOutstanding'
        and r['start']==requested['start'] and r['end']==requested['end'] and r['units']=='shares']
    if len(diluted)!=1 or number(diluted[0]['value'])<=0:_refuse('DILUTED_WEIGHTED_SHARES_REQUIRED')
    if type(share_basis) is not str or not share_basis:_refuse('ACCEPTED_SPLIT_BASIS_REQUIRED')
    return {'accession':requested['accn'],'start':requested['start'],'end':requested['end'],'filed':requested['filed'],
            'eps':str(number(requested['val'])),'share_basis':share_basis,'filing_sha256':parsed['sha256']}
