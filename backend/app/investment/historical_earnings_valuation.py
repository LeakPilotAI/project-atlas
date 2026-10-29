"""Explicitly selected historical relative valuation, never analyst targets.

Source-only PERSONAL PAPER method. Accepted source verification is injected;
there is no network, store, issuer, financial dispatch or operational default.
"""
from bisect import bisect_right
from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from app.investment.free_research_providers import calendar_sessions, daily_bars
from app.investment.free_research_transport import ResearchRefused, utc
from app.investment.freshness import FUNDAMENTAL_TTL_SECONDS, VALUATION_TTL_SECONDS
from app.investment.market_hours import ET
from app.investment.sec_edgar_research import normalize_companyfacts, number, ratio_fact_evidence
from app.services.paper_financial_replay import body, digest, strict

METHOD = 'QD_HISTORICAL_EARNINGS_MULTIPLE_V1'
SCHEMA = 'QD_HISTORICAL_EARNINGS_INPUT_V1'
FIELDS = {'schema','method','domain','instrument','companyfacts','facts_received_at',
          'prices','calendar','price_adjustment','filing_witnesses','price_basis'}


def refused(reason):
    raise ResearchRefused('HISTORICAL_EARNINGS_'+reason)


def _years_ago(day, years):
    year = day.year-years
    return date(year,day.month,min(day.day,monthrange(year,day.month)[1]))


def _four(rows, end, cut):
    """Four standalone quarters as known at cut, no EPS/YTD differences."""
    selected = {}
    for row in rows:
        if row['filed'] > cut:
            continue
        key = row['end']
        old = selected.get(key)
        if old is None or row['filed'] > old['filed']:
            selected[key] = row
        elif row['filed'] == old['filed'] and any(row[k] != old[k] for k in ('start','eps','basis')):
            refused('CONFLICTING_QUARTER')
    parts = []; cursor = end
    for _ in range(4):
        row = selected.get(cursor)
        if row is None:
            return None
        parts.append(row); cursor = row['start']-timedelta(days=1)
    if not 330 <= (end-parts[-1]['start']).days+1 <= 380:
        refused('TTM_PERIOD')
    if sum((row['eps'] for row in parts),Decimal(0)) <= 0:
        refused('NONPOSITIVE_TTM_EPS')
    if len({row['basis'] for row in parts}) != 1:
        refused('EPS_SHARE_BASIS')
    return parts


def _verified(verify_source, packet, now):
    if not callable(verify_source):
        refused('ACCEPTED_SOURCE_VERIFIER_REQUIRED')
    binding = digest(packet)
    copied = strict(body(packet))
    proof = verify_source(copied, now=now)
    if (type(proof) is not dict or set(proof) != {'schema','binding','domain','scope','verified','receipt_id'}
            or proof['schema'] != 'QD_HISTORICAL_EARNINGS_SOURCE_VERIFIED_V1'
            or proof['binding'] != binding or digest(copied) != binding or proof['domain'] != packet['domain']
            or proof['scope'] != 'RESEARCH_ONLY' or proof['verified'] is not True
            or type(proof['receipt_id']) is not str or not proof['receipt_id']):
        refused('SOURCE_BINDING')
    return strict(body(proof))


def build_historical_valuation(evidence, *, method, now, verify_source=None):
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        return _build(evidence,method=method,now=now,verify_source=verify_source)


def _build(evidence, *, method, now, verify_source):
    """Approved recipe only; source receipt verification is a caller trust boundary.

    The verifier must attest original filing versions, complete calendar/raw bar
    scope, security classification and corporate-action/share-basis mapping. A
    content hash or an arbitrary True callback does not satisfy this interface.
    Synthetic verifiers remain synthetic and cannot enroll an operational source.
    """
    now = utc(now)
    if method != METHOD:
        refused('EXPLICIT_METHOD_SELECTION')
    encoded = body(evidence)
    if len(encoded.encode()) > 16*1024*1024:
        refused('INPUT_CAPACITY')
    packet = strict(encoded)
    if (type(packet) is not dict or set(packet) != FIELDS or packet['schema'] != SCHEMA
            or packet['method'] != METHOD or packet['domain'] not in ('SYNTHETIC','TLS_PUBLIC_PROVIDER')
            or packet['price_adjustment'] != 'raw'):
        refused('INPUT_SCHEMA_OR_PRICE_BASIS')
    proof = _verified(verify_source, packet, now)
    instrument = packet['instrument']
    if (type(instrument) is not dict or set(instrument) != {'symbol','asset_id','cik','asset_class','business_type','currency','units'}
            or instrument['asset_class'] != 'STOCK' or instrument['business_type'] != 'NON_FINANCIAL_OPERATING_COMPANY_COMMON'
            or instrument['currency'] != 'USD' or instrument['units'] != 'SHARES'
            or any(type(instrument[k]) is not str or not instrument[k] for k in ('symbol','asset_id','cik'))
            or not instrument['symbol'].isascii() or instrument['symbol'] != instrument['symbol'].strip().upper()
            or len(instrument['cik']) != 10 or not instrument['cik'].isdigit()):
        refused('INSTRUMENT_OR_BUSINESS_TYPE')
    received = utc(datetime.fromisoformat(packet['facts_received_at']))
    funds = normalize_companyfacts(packet['companyfacts'], cik=instrument['cik'], now=now, retrieved_at=received)
    cashflow = ratio_fact_evidence(funds['free_cash_flow'],now=now,units='USD',basis='TTM_RECONCILED')
    if cashflow is None or cashflow[1] <= 0:
        refused('CURRENT_CASHFLOW_OR_FRESHNESS')
    witnesses = packet['filing_witnesses']
    if type(witnesses) is not list or not 0 < len(witnesses) <= 512:
        refused('FILING_WITNESS_CAPACITY')
    indexed = {}
    for witness in witnesses:
        if (type(witness) is not dict or set(witness) != {'accession','start','end','filed','eps','share_basis','filing_sha256'}
                or any(type(witness[k]) is not str or not witness[k] for k in ('accession','share_basis','filing_sha256'))
                or len(witness['filing_sha256']) != 64
                or any(c not in '0123456789abcdef' for c in witness['filing_sha256'])):
            refused('ORIGINAL_FILING_WITNESS')
        key = tuple(witness[k] for k in ('accession','start','end','filed'))
        if key in indexed:
            refused('DUPLICATE_FILING_WITNESS')
        indexed[key] = witness
    raw_rows = packet['companyfacts'].get('facts',{}).get('us-gaap',{}).get('EarningsPerShareDiluted',{}).get('units',{}).get('USD/shares',[])
    if type(raw_rows) is not list or not 0 < len(raw_rows) <= 8192:
        refused('REPORTED_DILUTED_EPS_REQUIRED')
    rows = []; unique = set()
    for row in raw_rows:
        if type(row) is not dict:
            refused('QUARTER_SCHEMA')
        if row.get('form') not in ('10-K','10-Q','10-K/A','10-Q/A'):
            continue
        start,end,filed = (date.fromisoformat(row[k]) for k in ('start','end','filed'))
        if filed > now.date() or end > filed:
            refused('QUARTER_SOURCE_TIMESTAMP')
        if end < _years_ago(now.date(),6) or not 70 <= (end-start).days+1 <= 110:
            continue  # Annual/YTD EPS is never differenced into a quarter.
        key = (row.get('accn'),str(start),str(end),str(filed))
        if key in unique:
            refused('DUPLICATE_QUARTER_IDENTITY')
        unique.add(key)
        witness = indexed.get(key)
        eps = number(row['val'])
        if witness is None or number(witness['eps']) != eps:
            refused('FILING_VALUE_OR_SHARE_BASIS_UNVERIFIED')
        rows.append({'start':start,'end':end,'filed':filed,'eps':eps,'basis':witness['share_basis'],
                     'accession':row['accn'],'filing_sha256':witness['filing_sha256']})
    ends = sorted({row['end'] for row in rows})
    if not ends or len(ends) > 32 or len(rows) > 512:
        refused('QUARTER_COVERAGE_OR_CAPACITY')
    current = _four(rows,ends[-1],now.date())
    if current is None:
        refused('CURRENT_FOUR_QUARTERS')
    current_filed = max(row['filed'] for row in current)
    if (not 0 <= (now-datetime.combine(current_filed,datetime.min.time(),UTC)).total_seconds() <= FUNDAMENTAL_TTL_SECONDS
            or str(ends[-1]) != cashflow[0]['period_end']):
        refused('CURRENT_EPS_FRESHNESS_OR_REPORTING_CUT')
    eps_now = sum((row['eps'] for row in current),Decimal(0))
    calendar = calendar_sessions(packet['calendar'])
    if not calendar or type(packet['price_basis']) is not dict or len(packet['price_basis']) > 1600:
        refused('CALENDAR_OR_PRICE_BASIS')
    prices = packet['prices']
    if type(prices) is not dict or set(prices) != {'symbol','bars','next_page_token'} or prices['symbol'] != instrument['symbol']:
        refused('PRICE_SECURITY')
    if type(prices['bars']) is not list or len(prices['bars']) > 1600:
        refused('PRICE_CAPACITY')
    validated = daily_bars(prices,prices,now=now,retrieved_at=received,calendar=calendar)
    closes = {datetime.fromisoformat(row['t']).astimezone(ET).date():number(row['c'])
              for row in prices['bars']}
    if len(validated) != len(closes):
        refused('INCOMPLETE_OR_UNCLOSED_PRICE_SERIES')
    sessions = sorted(calendar)
    anchors = []
    for end in reversed(ends):
        if end < _years_ago(now.date(),5):
            break
        first = None
        for cut in sorted({row['filed'] for row in rows if row['end'] <= end}):
            if cut < end:
                continue
            parts = _four(rows,end,cut)
            if parts is not None:
                first = cut,parts; break
        if first is None:
            if end < ends[3]:
                break  # Leading edge of the available series, never an interior gap.
            refused('HISTORICAL_FOUR_QUARTERS')
        cut,parts = first
        slot = bisect_right(sessions,cut)
        if slot >= len(sessions):
            refused('CALENDAR_INCOMPLETE')
        day = sessions[slot]
        if calendar[day][1] > now:
            continue  # Still-open session is not a historical valuation anchor.
        if day not in closes:
            refused('ANCHOR_PRICE_MISSING')
        if packet['price_basis'].get(str(day)) != parts[0]['basis']:
            refused('ANCHOR_SPLIT_OR_SHARE_BASIS')
        trailing_eps = sum((row['eps'] for row in parts),Decimal(0))
        multiple = closes[day]/trailing_eps
        if not Decimal(5) <= multiple <= Decimal(60):
            refused('HISTORICAL_MULTIPLE_RANGE')
        anchors.append({'period_end':str(end),'session':str(day),'multiple':str(multiple),
                        'eps_proxy':str(trailing_eps),'share_basis':parts[0]['basis'],
                        'filings':[r['filing_sha256'] for r in parts]})
        if len(anchors) == 20:
            break
    if len(anchors) < 12:
        refused('TWELVE_DISTINCT_QUARTER_ANCHORS')
    latest,oldest = date.fromisoformat(anchors[0]['period_end']),date.fromisoformat(anchors[-1]['period_end'])
    months = (latest.year-oldest.year)*12+latest.month-oldest.month
    if months < 33 or len({row['session'] for row in anchors}) != len(anchors):
        refused('ANCHOR_SPAN_OR_DUPLICATE_SESSION')
    multiples = sorted(number(row['multiple']) for row in anchors)
    chosen = [multiples[(p*len(multiples)+99)//100-1] for p in (25,50,75)]
    amounts = [eps_now*m for m in chosen]
    if amounts[-1]/amounts[0] > 2:
        refused('SCENARIO_DISPERSION')
    binding = digest(packet)
    expiry = min(now+timedelta(seconds=VALUATION_TTL_SECONDS),
        datetime.combine(current_filed,datetime.min.time(),UTC)+timedelta(seconds=FUNDAMENTAL_TTL_SECONDS),
        funds['free_cash_flow'].effective_timestamp+timedelta(seconds=FUNDAMENTAL_TTL_SECONDS))
    sources = [{'value':float(value),'provenance':'HISTORICAL_MULTIPLE','as_of':now.isoformat(),
        'expires_at':expiry.isoformat(),
        'confidence':'INTERNAL_RELATIVE_VALUATION_CORRELATED_SCENARIOS',
        'note':body({'method':METHOD,'percentile':p,'multiple':str(m),'exact_value':str(value),
                     'current_eps_proxy':str(eps_now),'input_digest':binding,'basis':current[0]['basis']})}
        for p,m,value in zip((25,50,75),chosen,amounts,strict=True)]
    if _verified(verify_source,packet,now) != proof:
        refused('SOURCE_ACCEPTANCE_CHANGED')
    return {'schema':'QD_HISTORICAL_EARNINGS_RESULT_V1','method':METHOD,'domain':packet['domain'],
        'symbol':instrument['symbol'],'instrument':instrument,'as_of':now.isoformat(),'input_digest':binding,
        'cohort_id':'QD-HISTORICAL-EARNINGS-'+binding,
        'expires_at':expiry.isoformat(),
        'source_receipt':proof,'eps_basis':'SUM_OF_REPORTED_QUARTERLY_DILUTED_EPS',
        'current_eps_proxy':str(eps_now),'current_report_end':str(ends[-1]),
        'current_filings':[row['filing_sha256'] for row in current], 'anchors':anchors,
        'valuation_sources':sources,'research_only':True,'paper_eligible':False,
        'analyst_targets_generated':False,'financial_publication_authority':False}


def attach_historical_valuation(row, evidence, *, method, now, verify_source=None):
    """Explicit source-only handoff to the original research projection; no mixing."""
    copied = strict(body(row))
    if (type(copied) is not dict or copied.get('asset_type') != 'STOCK'
            or any(copied.get(k) for k in ('valuation_sources','normalization_sources','normalization_value','valuation_window'))):
        refused('EXPLICIT_UNMIXED_RESEARCH_ROW')
    result = build_historical_valuation(evidence,method=method,now=now,verify_source=verify_source)
    if copied.get('symbol') != result['symbol']:
        refused('RESEARCH_SECURITY_MISMATCH')
    copied['valuation_sources'] = result['valuation_sources']
    copied['valuation_method_evidence'] = result
    return copied
