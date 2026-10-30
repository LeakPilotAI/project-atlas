"""Concrete data-only SEC/Alpaca source producer for the approved method.

No native financial store, account, runtime start, quote refresh on GET or default
issuer. Source verification is based on captured permitted provider evidence;
its research receipt is not operational financial/enrollment authority.
"""
from datetime import date, datetime, timedelta
from threading import Lock
from urllib.parse import urlencode

from app.investment.alpaca_iex import SYMBOL
from app.investment.free_research_providers import calendar_sessions, daily_bars
from app.investment.free_research_transport import FreeResearchClient, ResearchRefused, utc
from app.investment.historical_earnings_valuation import (
    EXHIBIT_SCHEMA,
    METHOD,
    SCHEMA,
    _years_ago,
    attach_historical_valuation,
    build_historical_valuation,
)
from app.investment.market_hours import ET
from app.investment.sec_earnings_exhibit import exhibit_rows, parse_earnings_exhibit
from app.investment.sec_edgar_research import number
from app.investment.sec_filing_evidence import filing_rows, parse_original_filing, quarter_witness
from app.services.paper_financial_replay import body, digest, strict


def refuse(code):
    raise ResearchRefused('GENUINE_HISTORICAL_'+code)


def standalone_coverage(companyfacts, *, now, supplements=()):
    """Date-only discovery; no implied Q4, diluted shares or valuation output."""
    rows=companyfacts.get('facts',{}).get('us-gaap',{}).get('EarningsPerShareDiluted',{}).get('units',{}).get('USD/shares',[])
    if type(rows) is not list or len(rows)>8192:refuse('EPS_CAPACITY')
    direct=[]
    for row in rows+list(supplements):
        if row.get('form') not in ('10-Q','10-K','10-Q/A','10-K/A','8-K') or not row.get('start'):continue
        if row.get('form')=='8-K' and row not in supplements:continue
        start,end,filed=(date.fromisoformat(row[k]) for k in ('start','end','filed'))
        if filed>now.date() or end>filed:refuse('EPS_SOURCE_TIME')
        if 70<=(end-start).days+1<=110 and end>=_years_ago(now.date(),6):direct.append(row)
    if not direct:return {'complete':False,'missing':'DIRECT_QUARTER_EPS','rows':[]}
    cursor=max(date.fromisoformat(r['end']) for r in direct);latest=cursor;parts=[]
    for _ in range(4):
        candidates=[r for r in direct if r['end']==str(cursor)]
        if not candidates:return {'complete':False,'latest_period':str(latest),'missing_end':str(cursor),'rows':direct}
        chosen=max(candidates,key=lambda r:r['filed']);parts.append(chosen)
        cursor=date.fromisoformat(chosen['start'])-timedelta(days=1)
    return {'complete':True,'latest_period':str(latest),'current_rows':parts,'rows':direct}


def no_split_basis(raw, split, calendar, actions, *, symbol, now, received_at, start):
    """Conservative first binding: no unsupported action/split is adjusted away.

    Empty provider action history is scoped to that queried dataset, not a claim
    that providers guarantee instant/complete discovery of every corporate action.
    """
    if (raw.get('symbol')!=symbol or split.get('symbol')!=symbol
            or raw.get('next_page_token') or split.get('next_page_token')):refuse('SPLIT_PRICE_IDENTITY')
    sessions=calendar_sessions(calendar)
    validated=daily_bars(raw,split,now=now,retrieved_at=received_at,calendar=sessions)
    if not validated:refuse('EMPTY_SPLIT_HISTORY')
    if type(actions) is not dict or set(actions)!={'corporate_actions','next_page_token'} or actions['next_page_token']:
        refuse('CORPORATE_ACTION_PAGINATION')
    if type(actions['corporate_actions']) is not dict:refuse('CORPORATE_ACTION_SCHEMA')
    mapped_cash_acquisitions=[]
    for kind,rows in actions['corporate_actions'].items():
        if type(rows) is not list or len(rows)>1000:refuse('CORPORATE_ACTION_CAPACITY')
        if rows and kind not in ('cash_dividends','cash_mergers'):refuse('NONCASH_ACTION_REQUIRES_EXPLICIT_MAPPING')
        for row in rows:
            if type(row) is not dict:refuse('CORPORATE_ACTION_SECURITY')
            if kind=='cash_mergers':
                if (row.get('acquirer_symbol')!=symbol or not row.get('acquiree_symbol')
                        or row['acquiree_symbol']==symbol or number(row.get('rate'))<=0
                        or not row.get('id') or date.fromisoformat(row['effective_date'])>now.date()):
                    refuse('CASH_MERGER_POSITION_CONVERSION_UNVERIFIED')
                mapped_cash_acquisitions.append({'id':row['id'],'effective_date':row['effective_date'],
                    'classification':'CASH_ACQUISITION_ACQUIRER_NO_SHARE_CONVERSION',
                    'acquiree_symbol':row['acquiree_symbol']})
            elif row.get('symbol')!=symbol:refuse('CORPORATE_ACTION_SECURITY')
    completed={bar.session_date for bar in validated}
    a={r['t']:r for r in raw['bars'] if str(datetime.fromisoformat(r['t']).astimezone(ET).date()) in completed}
    b={r['t']:r for r in split['bars'] if str(datetime.fromisoformat(r['t']).astimezone(ET).date()) in completed}
    if a.keys()!=b.keys():refuse('SPLIT_SERIES_COVERAGE')
    for stamp,row in a.items():
        if any(number(row[k])!=number(b[stamp][k]) for k in ('o','h','l','c','v')):
            refuse('SPLIT_FACTOR_REQUIRES_EXPLICIT_ACTION_MAPPING')
    # Six-year request must cover all expected sessions, not only returned rows.
    expected={str(day) for day,bounds in sessions.items() if day>=start and bounds[1]<=now}
    observed={bar.session_date for bar in validated}
    if observed!=expected:refuse('MISSING_HISTORY_SESSION')
    binding=digest({'symbol':symbol,'start':str(start),'raw':raw,'split':split,'actions':actions})
    basis='ALPACA_PROVIDER_NO_SPLIT_ADJUSTMENT:'+binding
    return {'basis':basis,'price_basis':{str(datetime.fromisoformat(r['t']).astimezone(ET).date()):basis for r in raw['bars']},
        'completed_raw':{'symbol':symbol,'bars':list(a.values()),'next_page_token':None},
        'sessions':len(observed),'scope':'RETRIEVED_PROVIDER_HISTORY_NOT_UNIVERSAL_ACTION_OR_HALT_AUTHORITY',
        'mapped_cash_acquisitions':mapped_cash_acquisitions,
        'cash_dividends_preserved_raw_prices':True,'basis_digest':binding}


class GenuineHistoricalSource:
    def __init__(self, *, client, now, symbols=None):
        if type(client) is not FreeResearchClient or not callable(now):refuse('EXACT_DATA_ONLY_CLIENT_REQUIRED')
        if (type(symbols) is not tuple or not 0<len(symbols)<=16 or len(set(symbols))!=len(symbols)
                or any(type(s) is not str or not SYMBOL.fullmatch(s) for s in symbols)):
            refuse('BOUNDED_SYMBOL_SCOPE_REQUIRED')
        self.client,self.now=client,now
        self.symbols=symbols
        self._ports=client,now,client.domain,symbols
        self.receipts=[];self.documents={};self.diagnostics={};self._packet=None;self._completed=None
        self._admission=Lock();self._attempted=False;self._receipt_cut=None

    def _get(self,url,ttl=86400):
        value,receipt=self.client.get(url,ttl=ttl)
        if receipt['domain']!=self._ports[2]:refuse('SOURCE_DOMAIN_CHANGED')
        self.receipts.append(receipt)
        return value

    def _history(self,symbol,adjustment,start,end):
        q={'feed':'iex','timeframe':'1Day','adjustment':adjustment,'sort':'asc',
           'start':str(start),'end':str(end),'limit':1000}
        records=[];tokens=set()
        for _ in range(3):
            packet=self._get('https://data.alpaca.markets/v2/stocks/'+symbol+'/bars?'+urlencode(q),ttl=3600)
            if packet.get('symbol')!=symbol or type(packet.get('bars')) is not list:refuse('PRICE_SYMBOL')
            records.extend(packet['bars']);token=packet.get('next_page_token')
            if not token:break
            if token in tokens or type(token) is not str or len(token)>2048:refuse('PRICE_PAGINATION')
            tokens.add(token);q['page_token']=token
        else:refuse('PRICE_PAGINATION')
        if len(records)>1600:refuse('PRICE_CAPACITY')
        return {'symbol':symbol,'bars':records,'next_page_token':None}

    def capture(self,symbol):
        with self._admission:
            if self._attempted:refuse('CAPTURE_ALREADY_RESERVED')
            self._attempted=True
        return self._capture(symbol)

    def _capture(self,symbol):
        if symbol not in self.symbols:
            refuse('BOUNDED_OBSERVATION_SYMBOL_SCOPE')
        now=utc(self.now())
        mapping=self._get('https://www.sec.gov/files/company_tickers.json')
        matches=[r for r in mapping.values() if type(r) is dict and r.get('ticker')==symbol]
        if len(matches)!=1 or type(matches[0].get('cik_str')) is not int:refuse('ISSUER_MAPPING')
        cik=str(matches[0]['cik_str']).zfill(10)
        asset=self._get('https://paper-api.alpaca.markets/v2/assets/'+symbol,ttl=3600)
        submissions=self._get('https://data.sec.gov/submissions/CIK'+cik+'.json')
        references=filing_rows(submissions,cik=cik,symbol=symbol)
        earnings={}
        def add_earnings(packet):
            columns=packet['filings']['recent'] if 'filings' in packet else packet
            forms=columns.get('form',[]);items=columns.get('items',[])
            if len(forms)!=len(items):refuse('EARNINGS_SUBMISSION_ITEMS')
            accepted={a for a,i in zip(columns['accessionNumber'],items,strict=True)
                if type(i) is str and '2.02' in i.split(',')}
            earnings.update({k:v for k,v in filing_rows(packet,cik=cik,forms=('8-K',)).items() if k in accepted})
        add_earnings(submissions)
        if (asset.get('symbol')!=symbol or asset.get('class')!='us_equity' or asset.get('status')!='active'
                or asset.get('tradable') is not True or type(asset.get('fractionable')) is not bool
                or type(asset.get('id')) is not str or not asset['id']
                or submissions.get('entityType')!='operating' or not str(submissions.get('sic','')).isdigit()
                or 6000<=int(submissions['sic'])<=6999):refuse('INSTRUMENT_BUSINESS_ELIGIBILITY')
        facts=self._get('https://data.sec.gov/api/xbrl/companyfacts/CIK'+cik+'.json')
        if facts.get('cik')!=int(cik):refuse('COMPANYFACTS_ISSUER')
        coverage=standalone_coverage(facts,now=now)
        self.diagnostics['quarter_coverage']={k:v for k,v in coverage.items() if k not in ('rows','current_rows')}
        latest=max(coverage['rows'],key=lambda r:(r['end'],r['filed'])) if coverage['rows'] else None
        if latest:
            reference=references.get(latest['accn'])
            if reference is None:refuse('CURRENT_FILING_REFERENCE')
            original=self._get(reference['url'])
            self.documents[latest['accn']]=parse_original_filing(original,reference,now=now)
            self.diagnostics['latest_original_filing']=self.documents[latest['accn']]
        start=_years_ago(now.date(),6);end=now.date()
        raw=self._history(symbol,'raw',start,end);split=self._history(symbol,'split',start,end)
        self.diagnostics['historical_prices']={'raw_bars':len(raw['bars']),'split_bars':len(split['bars']),
            'start':str(start),'end':str(end),'raw_and_split_exactly_equal':raw==split,
            'execution_evidence':False}
        calendar=self._get('https://paper-api.alpaca.markets/v2/calendar?'+urlencode({'start':str(start),'end':str(end)}))
        self.diagnostics['calendar_sessions']=len(calendar)
        actions=self._get('https://data.alpaca.markets/v1/corporate-actions?'+urlencode({
            'symbols':symbol,'start':str(start),'end':str(end),'region':'us','limit':1000,'data_quality':'all'}))
        basis=no_split_basis(raw,split,calendar,actions,symbol=symbol,now=now,received_at=now,start=start)
        self.diagnostics['share_basis']={k:v for k,v in basis.items() if k not in ('price_basis','completed_raw')}
        if latest:
            self.diagnostics['latest_quarter_witness']=quarter_witness(self.documents[latest['accn']],latest,share_basis=basis['basis'])
        needed={row['accn'] for row in coverage['rows']}
        if len(needed)>32:refuse('ORIGINAL_DOCUMENT_CAPACITY')
        missing=needed-references.keys()
        historical=submissions.get('filings',{}).get('files',[])
        if type(historical) is not list or len(historical)>32:refuse('HISTORICAL_SUBMISSION_CAPACITY')
        loaded=0
        for entry in historical:
            # Missing original quarters may need an older original 8-K even
            # when all current 10-Q references were in the recent index.
            if not missing and any(date.fromisoformat(r['filed'])<_years_ago(now.date(),5) for r in earnings.values()):break
            import re
            name=entry.get('name','')
            if not re.fullmatch('CIK'+cik+r'-submissions-\d{3}\.json',name):refuse('HISTORICAL_SUBMISSION_REFERENCE')
            if date.fromisoformat(entry['filingTo'])<_years_ago(now.date(),6):continue
            loaded+=1
            if loaded>3:refuse('HISTORICAL_SUBMISSION_CAPACITY')
            historical_packet=self._get('https://data.sec.gov/submissions/'+name)
            additional=filing_rows(historical_packet,cik=cik);add_earnings(historical_packet)
            if any(key in references and references[key]!=value for key,value in additional.items()):refuse('ACCESSION_CONFLICT')
            references.update(additional);missing=needed-references.keys()
        supplements=[];exhibits=[]
        direct_ends={row['end'] for row in coverage['rows']}
        cursor=date.fromisoformat(coverage['latest_period']) if coverage.get('latest_period') else now.date()
        earliest=min((date.fromisoformat(r['end']) for r in coverage['rows']),default=cursor)
        missing_quarters=[]
        while cursor>=earliest:
            if str(cursor) not in direct_ends:missing_quarters.append(cursor)
            month=cursor.month-3;year=cursor.year
            if month<=0:month+=12;year-=1
            from calendar import monthrange
            cursor=date(year,month,monthrange(year,month)[1])
        if len(missing_quarters)>8:refuse('EXHIBIT_QUARTER_CAPACITY')
        # This table dialect has one explicit SEC-issuer/name equivalence. It
        # does not restrict the Quality Dips universe or infer issuer aliases.
        issuer_alias={'0000789019':'MICROSOFT CORPORATION'}.get(cik)
        if missing_quarters and issuer_alias is None:refuse('EXHIBIT_ISSUER_DIALECT_UNSUPPORTED')
        for end in missing_quarters:
            candidates=[r for r in earnings.values() if 0<=(date.fromisoformat(r['filed'])-end).days<=60]
            if len(candidates)!=1:refuse('EARNINGS_ACCESSION_AMBIGUOUS:'+str(end))
            ref=candidates[0];main=self._get(ref['url'])
            from app.investment.sec_filing_evidence import earnings_exhibit_reference
            linked=earnings_exhibit_reference(main,ref,now=now)
            parsed=parse_earnings_exhibit(main,self._get(linked['url']),ref,issuer_name=issuer_alias,now=now)
            rows=exhibit_rows([parsed],cik=cik)
            if not any(row['end']==str(end) for row in rows):refuse('ORIGINAL_EXHIBIT_QUARTER_MISSING:'+str(end))
            # Comparative columns retain THIS publication date. Fetch every
            # original quarter release as well; do not backdate a comparison.
            supplements.extend(rows);exhibits.append(parsed);self.documents[ref['accession']]=parsed
        coverage=standalone_coverage(facts,now=now,supplements=supplements)
        self.diagnostics['quarter_coverage']={k:v for k,v in coverage.items() if k not in ('rows','current_rows')}
        self.diagnostics['original_exhibits']=exhibits
        if not coverage['complete']:refuse('MISSING_STANDALONE_QUARTER:'+coverage.get('missing_end','UNKNOWN'))
        needed={row['accn'] for row in coverage['rows']}
        for accession in sorted(needed):
            if accession in self.documents:continue
            reference=references.get(accession)
            if reference is None:refuse('HISTORICAL_SUBMISSIONS_ORIGINAL_REFERENCE_REQUIRED')
            self.documents[accession]=parse_original_filing(self._get(reference['url']),reference,now=now)
        witnesses=[quarter_witness(self.documents[row['accn']],row,share_basis=basis['basis']) for row in coverage['rows']]
        packet={'schema':EXHIBIT_SCHEMA if exhibits else SCHEMA,'method':METHOD,'domain':self._ports[2],
            'instrument':{'symbol':symbol,'asset_id':asset['id'],'cik':cik,'asset_class':'STOCK',
                'business_type':'NON_FINANCIAL_OPERATING_COMPANY_COMMON','currency':'USD','units':'SHARES'},
            'companyfacts':facts,'facts_received_at':next(r['retrieved_at'] for r in self.receipts if '/companyfacts/' in r['url']),
            'prices':basis['completed_raw'],'calendar':calendar,'price_adjustment':'raw','filing_witnesses':witnesses,'price_basis':basis['price_basis']}
        if exhibits:packet['earnings_exhibits']=exhibits
        self._packet=body(packet);self._completed=utc(self.now());self._receipt_cut=body(self.receipts)
        return strict(self._packet)

    def verify(self,packet,*,now):
        now=utc(now)
        if (self._packet is None or self._completed is None or not 0<=(now-self._completed).total_seconds()<=60
                or self._ports!=(self.client,self.now,self.client.domain,self.symbols) or body(packet)!=self._packet):
            refuse('UNACCEPTED_OR_CHANGED_SOURCE_CUT')
        if body(self.receipts)!=self._receipt_cut:refuse('SOURCE_RECEIPTS_CHANGED')
        # Completed source contents and original filing comparisons are frozen.
        # Native current ranking custody and financial authority remain separate.
        return {'schema':'QD_HISTORICAL_EARNINGS_SOURCE_VERIFIED_V1','binding':digest(packet),
            'domain':self._ports[2],'scope':'RESEARCH_ONLY','verified':True,
            'receipt_id':'RESEARCH-SOURCE:'+digest({'receipts':self.receipts,'packet':digest(packet)})}

    def valuation(self,symbol):
        packet=self.capture(symbol)
        return build_historical_valuation(packet,method=METHOD,now=utc(self.now()),verify_source=self.verify)

    def attach_research(self,row,*,method):
        """No IO: explicit original scanner-row handoff from the accepted cut.

        The existing native publication/candidate authority and executable
        quotes remain separately required. This neither signs nor publishes a
        ranking, starts a scanner, nor refreshes missing/stale source evidence.
        """
        if self._packet is None:refuse('ACCEPTED_SOURCE_CUT_REQUIRED')
        return attach_historical_valuation(row,strict(self._packet),method=method,
            now=utc(self.now()),verify_source=self.verify)
