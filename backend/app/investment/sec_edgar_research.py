"""Conservative SEC XBRL normalization, not valuation forecasts or trading authority."""
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from app.investment.enums import DataQuality
from app.investment.free_research_transport import ResearchRefused, utc
from app.investment.freshness import classify_freshness
from app.investment.models import MeasuredValue

TAGS = {
    'revenue': ('RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet'),
    'earnings': ('NetIncomeLossAvailableToCommonStockholdersBasic','NetIncomeLoss'),
    'operating_cash_flow': ('NetCashProvidedByUsedInOperatingActivities',),
    'capex': ('PaymentsToAcquirePropertyPlantAndEquipment',),
    'gross_profit': ('GrossProfit',), 'operating_income': ('OperatingIncomeLoss',),
}
FORMS = {'10-K','10-K/A','10-Q','10-Q/A'}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int,float,str,Decimal)):
        raise ResearchRefused('SEC_NONNUMERIC_FACT')
    try: result = Decimal(str(value))
    except InvalidOperation: raise ResearchRefused('SEC_NONNUMERIC_FACT') from None
    if not result.is_finite() or abs(result) > Decimal('1e24'):
        raise ResearchRefused('SEC_INVALID_FACT')
    return result


def observations(payload, tags, unit, *, now, instant=False):
    selected = {}
    for tag in tags:
        rows=payload.get('facts',{}).get('us-gaap',{}).get(tag,{}).get('units',{}).get(unit,[])
        if type(rows) is not list or len(rows)>8192: raise ResearchRefused('SEC_FACT_CAPACITY')
        for row in rows:
            if type(row) is not dict: raise ResearchRefused('SEC_FACT_SHAPE')
            if row.get('form') not in FORMS or not row.get('accn'): continue
            try:
                end, filed = date.fromisoformat(row['end']), date.fromisoformat(row['filed'])
                start = None if instant else date.fromisoformat(row['start'])
                if filed > now.date() or end > filed or end < now.date()-timedelta(days=3*366): continue
                if start is not None and (start > end or not 1 <= (end-start).days+1 <= 380): continue
                value = number(row['val'])
            except (KeyError,ValueError,TypeError): continue
            key = (start,end)
            proof = {'tag':tag,'accession':row['accn'],'filed':filed.isoformat(),'start':str(start) if start else None,
                     'end':end.isoformat(),'units':unit,'value':str(value)}
            current = selected.get(key)
            if current is None or filed > current['filed']:
                selected[key] = {'start':start,'end':end,'filed':filed,'value':value,'proof':[proof]}
            elif filed == current['filed'] and value != current['value']:
                raise ResearchRefused('SEC_CONFLICTING_SAME_PERIOD_FACTS')
    if len(selected)>256: raise ResearchRefused('SEC_PERIOD_CAPACITY')
    return list(selected.values())


def trailing(rows):
    """Four consecutive quarters; YTD differences only for additive USD facts.

    Never sum overlapping YTD reports, turn annual data into TTM, or difference
    weighted-average shares/EPS. Missing a bridge quarter remains missing.
    """
    quarters = {}
    def accept(row):
        prior = quarters.get(row['end'])
        if prior and (prior['start'] != row['start'] or prior['value'] != row['value']):
            raise ResearchRefused('SEC_DIRECT_DERIVED_QUARTER_CONFLICT')
        if prior is None or row['filed'] > prior['filed']: quarters[row['end']] = row
    for row in rows:
        if 70 <= (row['end']-row['start']).days+1 <= 110: accept(row)
        for earlier in rows:
            if earlier['start'] == row['start'] and 70 <= (row['end']-earlier['end']).days <= 110:
                accept({'start':earlier['end']+timedelta(days=1),'end':row['end'],
                        'filed':max(row['filed'],earlier['filed']),'value':row['value']-earlier['value'],
                        'proof':row['proof']+earlier['proof']})
    for end in sorted(quarters, reverse=True):
        parts = []; cursor = end
        for _ in range(4):
            if cursor not in quarters: break
            row = quarters[cursor]; parts.append(row); cursor = row['start']-timedelta(days=1)
        if len(parts) == 4 and 330 <= (end-parts[-1]['start']).days+1 <= 380:
            return {'value':sum((p['value'] for p in parts),Decimal(0)), 'start':parts[-1]['start'],
                    'end':end,'filed':max(p['filed'] for p in parts),'proof':[q for p in parts for q in p['proof']]}
    return None


def normalize_companyfacts(payload, *, cik, now, retrieved_at):
    now, retrieved_at = utc(now), utc(retrieved_at)
    if (type(cik) is not str or not cik.isdigit() or len(cik)!=10 or type(payload) is not dict
            or type(payload.get('cik')) is not int or payload['cik']!=int(cik) or retrieved_at>now
            or (now-retrieved_at).total_seconds()>86400):
        raise ResearchRefused('SEC_ISSUER_OR_RECEIPT_MISMATCH')
    reported = {name:observations(payload,tags,'USD',now=now) for name,tags in TAGS.items()}
    amounts = {name:trailing(rows) for name,rows in reported.items()}
    latest = max((r['end'] for rows in reported.values() for r in rows), default=None)
    coherent = {name:r for name,r in amounts.items() if r and r['end']==latest}
    def point(tags, unit='USD'):
        rows = observations(payload,tags,unit,now=now,instant=True)
        return next((r for r in rows if r['end']==latest),None)
    coherent['shares_outstanding'] = point(('CommonStockSharesOutstanding',),'shares')
    coherent['cash'] = point(('CashCashEquivalentsAndShortTermInvestments',))
    coherent['book_equity'] = point(('StockholdersEquity',))
    for name in ('cash','shares_outstanding','book_equity'):
        if coherent.get(name) and coherent[name]['value']<0:coherent[name]=None
    if coherent.get('shares_outstanding') and coherent['shares_outstanding']['value']==0:coherent['shares_outstanding']=None
    if coherent.get('capex') and coherent['capex']['value']<0:coherent['capex']=None
    # Missing a debt component is not evidence that it equals zero.
    debt = [point((tag,)) for tag in ('ShortTermBorrowings','LongTermDebtCurrent','LongTermDebtNoncurrent')]
    if all(r and r['value']>=0 for r in debt):
        coherent['total_debt'] = {'value':sum((r['value'] for r in debt),Decimal(0)),
            'start':None,'end':latest,'filed':max(r['filed'] for r in debt),'proof':[p for r in debt for p in r['proof']]}
    def derive(name,left,right,divide=False):
        a,b = coherent.get(left),coherent.get(right)
        if not a or not b or (divide and b['value']<=0): return
        coherent[name] = {'value':a['value']/b['value'] if divide else a['value']-b['value'],
            'start':a['start'],'end':a['end'],'filed':max(a['filed'],b['filed']),'proof':a['proof']+b['proof']}
    derive('free_cash_flow','operating_cash_flow','capex')
    derive('gross_margin','gross_profit','revenue',True)
    derive('operating_margin','operating_income','revenue',True)
    derive('net_margin','earnings','revenue',True)
    result = {}
    fields = ('revenue','earnings','eps','free_cash_flow','operating_cash_flow','gross_margin','operating_margin',
              'net_margin','total_debt','cash','shares_outstanding','market_cap','book_equity')
    for name in fields:
        row = coherent.get(name)
        if row is None:
            result[name] = MeasuredValue.unknown('SEC_EDGAR', 'MISSING_RECONCILED_FACT_OR_PERIOD')
            continue
        effective = datetime.combine(row['filed'],datetime.min.time(),UTC)
        result[name] = MeasuredValue(value=float(row['value']),source='SEC_EDGAR',timestamp=effective,
            effective_timestamp=effective,retrieved_at=retrieved_at,availability=True,
            quality=classify_freshness(effective,kind='fundamental',now=now),
            notes=json.dumps({'basis':'TTM_RECONCILED' if row['start'] else 'PERIOD_END_INSTANT',
                'period_start':str(row['start']) if row['start'] else None,'period_end':str(row['end']),
                'exact_decimal':str(row['value']),'filed_date_precision':'DAY','cik':cik,'evidence':row['proof']},sort_keys=True))
    return result


def valuation(funds, price, *, now):
    """Only supported ratios, never forecasts, target prices or synthetic scenarios."""
    now = utc(now)
    result = {k:MeasuredValue.unknown('SEC_EDGAR+ALPACA', 'INPUT_OR_ACCEPTED_VALUATION_ESTIMATE_UNAVAILABLE')
              for k in ('pe','forward_pe','ps','pb','ev_ebitda','fcf_yield','earnings_yield','price_to_fcf',
                        'target_low_price','target_mean_price','target_high_price')}
    shares = funds.get('shares_outstanding')
    if not shares or shares.quality != DataQuality.FRESH or not shares.is_usable() or price.quality != DataQuality.FRESH or not price.is_usable(): return result
    if price.effective_timestamp is None or not 0 <= (now-utc(price.effective_timestamp)).total_seconds() <= 900: return result
    cap = number(shares.value)*number(price.value)
    if cap<=0: return result
    for field,metric,invert in [('pe','earnings',False),('ps','revenue',False),('pb','book_equity',False),('price_to_fcf','free_cash_flow',False),
                                ('fcf_yield','free_cash_flow',True),('earnings_yield','earnings',True)]:
        value = funds.get(metric)
        if not value or value.quality != DataQuality.FRESH or not value.is_usable() or number(value.value)<=0: continue
        amount = number(value.value)
        effective = utc(price.effective_timestamp)
        result[field] = MeasuredValue(value=float(amount/cap if invert else cap/amount),source='SEC_EDGAR+ALPACA_DERIVED',
            timestamp=effective,effective_timestamp=effective,retrieved_at=now,availability=True,
            quality=DataQuality.FRESH,notes=json.dumps({'formula':metric+'/market_cap' if invert else 'market_cap/'+metric,
                'market_cap':str(cap),'price_source':price.source,'price_timestamp':price.effective_timestamp.isoformat(),
                'shares_evidence':shares.notes,'metric_evidence':value.notes},sort_keys=True))
    return result
