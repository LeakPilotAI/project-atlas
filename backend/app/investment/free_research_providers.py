"""Alpaca Basic/IEX + SEC research inputs for the existing read-only scanner.

No Yahoo fallback, FMP access, scanner start, target generation or financial IO.
Data acquisition is explicit; API accessibility never grants trading authority.
"""
import asyncio
import copy
import json
import re
import threading
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import urlencode

from app.investment.bars import OhlcvBar
from app.investment.enums import DataQuality
from app.investment.free_research_transport import ResearchRefused, utc
from app.investment.freshness import classify_freshness
from app.investment.market_hours import ET, session_bounds
from app.investment.models import MeasuredValue
from app.investment.sec_edgar_research import normalize_companyfacts, number, valuation


def calendar_sessions(packet):
    if type(packet) is not list or len(packet)>1600: raise ResearchRefused('ALPACA_CALENDAR_CAPACITY')
    result={}
    for row in packet:
        day=date.fromisoformat(row['date'])
        opened=datetime.combine(day,time.fromisoformat(row['open']),ET).astimezone(UTC)
        closed=datetime.combine(day,time.fromisoformat(row['close']),ET).astimezone(UTC)
        if day in result or day.weekday()>4 or not opened<closed: raise ResearchRefused('ALPACA_CALENDAR_CONFLICT')
        known=session_bounds(opened)
        if day.year in (2026,2027,2028) and known!=(opened,closed): raise ResearchRefused('ALPACA_CALENDAR_CONFLICT')
        result[day]=(opened,closed)
    return result


def daily_bars(raw, adjusted, *, now, retrieved_at, calendar):
    now, retrieved_at = utc(now), utc(retrieved_at)
    if retrieved_at > now: raise ResearchRefused('ALPACA_RECEIPT_FUTURE')
    def index(packet):
        if type(packet) is not dict or type(packet.get('bars')) is not list or packet.get('next_page_token'):
            raise ResearchRefused('ALPACA_INCOMPLETE_HISTORY')
        result = {}
        for row in packet['bars']:
            stamp = utc(datetime.fromisoformat(row['t']))
            day = stamp.astimezone(ET).date()
            if stamp != datetime.combine(day,datetime.min.time(),ET).astimezone(UTC):
                raise ResearchRefused('ALPACA_DAILY_TIMESTAMP')
            if day in result: raise ResearchRefused('ALPACA_DUPLICATE_SESSION')
            op,hi,lo,cl = (number(row[k]) for k in ('o','h','l','c'))
            volume = number(row['v'])
            if min(op,hi,lo,cl)<=0 or volume<0 or not lo<=min(op,cl)<=max(op,cl)<=hi:
                raise ResearchRefused('ALPACA_INVALID_BAR')
            bounds = calendar.get(day)
            if bounds is None: raise ResearchRefused('ALPACA_UNSUPPORTED_SESSION_CALENDAR')
            if bounds[1] > now: continue  # A still-open daily bar is not a completed close.
            result[day] = (row,bounds[1])
        return result
    a,b = index(raw),index(adjusted)
    if a.keys()!=b.keys(): raise ResearchRefused('ALPACA_ADJUSTMENT_COVERAGE_MISMATCH')
    return [OhlcvBar(session_date=str(day),open=float(number(row['o'])),high=float(number(row['h'])),
        low=float(number(row['l'])),close=float(number(row['c'])),volume=float(number(row['v'])),
        adjusted_close=float(number(b[day][0]['c'])),source='ALPACA_IEX_DAILY_RAW_AND_ALL_ADJUSTED',
        retrieved_at=retrieved_at,effective_timestamp=end,
        quality=classify_freshness(end,kind='daily_bar',now=now).value)
        for day,(row,end) in sorted(a.items())]


class FreeResearchBundle:
    def __init__(self, *, client, now, reference_price=None):
        self.client,self.now,self.reference_price = client,now,reference_price
        self.lock = threading.RLock()

    def load(self, symbol, *, prices_only=False):
        if type(symbol) is not str or not re.fullmatch('[A-Z][A-Z0-9.-]{0,14}',symbol):
            raise ResearchRefused('RESEARCH_SYMBOL_REQUIRED')
        with self.lock:
            now = utc(self.now()); receipts = []
            asset,receipt = self.client.get('https://paper-api.alpaca.markets/v2/assets/'+symbol,ttl=3600)
            receipts.append(receipt)
            if (asset.get('symbol')!=symbol or asset.get('class')!='us_equity' or asset.get('status')!='active'
                    or asset.get('tradable') is not True or type(asset.get('fractionable')) is not bool
                    or not isinstance(asset.get('id'),str) or not asset['id']
                    or asset.get('exchange') not in ('NYSE','NASDAQ','ARCA','AMEX','BATS','NYSEARCA')):
                raise ResearchRefused('ALPACA_ASSET_IDENTITY_OR_ELIGIBILITY')
            # Asset eligibility is separate from quotes/ranking/accepted PAPER risk.
            history = []
            for adjustment in ('raw','all'):
                query={'feed':'iex','timeframe':'1Day','adjustment':adjustment,'sort':'asc',
                    'start':(now-timedelta(days=5*366)).date().isoformat(),'end':now.date().isoformat(),'limit':1000}
                records=[];seen=set()
                for _ in range(3):
                    packet,receipt=self.client.get('https://data.alpaca.markets/v2/stocks/'+symbol+'/bars?'+urlencode(query),ttl=3600)
                    if packet.get('symbol')!=symbol or type(packet.get('bars')) is not list: raise ResearchRefused('ALPACA_HISTORY_SYMBOL')
                    receipts.append(receipt);records.extend(packet['bars'])
                    token=packet.get('next_page_token')
                    if not token:break
                    if type(token) is not str or token in seen or len(token)>2048: raise ResearchRefused('ALPACA_PAGINATION_REFUSED')
                    seen.add(token);query['page_token']=token
                else:raise ResearchRefused('ALPACA_INCOMPLETE_HISTORY')
                if len(records)>1600:raise ResearchRefused('ALPACA_HISTORY_CAPACITY')
                history.append({'bars':records,'next_page_token':None})
            cal,receipt=self.client.get('https://paper-api.alpaca.markets/v2/calendar?'+urlencode({
                'start':(now-timedelta(days=5*366)).date().isoformat(),'end':now.date().isoformat()}),ttl=86400)
            receipts.append(receipt)
            bars=daily_bars(*history,now=utc(self.now()),retrieved_at=datetime.fromisoformat(receipt['retrieved_at']),calendar=calendar_sessions(cal))
            price=self.reference_price(symbol) if self.reference_price else MeasuredValue.unknown('ALPACA_IEX','NO_CURRENT_AUTHENTICATED_REFERENCE_PRICE')
            if self.reference_price is None and bars:
                latest=bars[-1]
                price=MeasuredValue(value=latest.close,source='ALPACA_IEX_COMPLETED_DAILY_CLOSE_NOT_EXECUTABLE',
                    timestamp=latest.effective_timestamp,effective_timestamp=latest.effective_timestamp,
                    retrieved_at=latest.retrieved_at,availability=True,
                    quality=classify_freshness(latest.effective_timestamp,kind='price',now=utc(self.now())),
                    notes='Historical close only; never a current bid/ask or simulated execution price')
            if price.availability and (price.effective_timestamp is None or number(price.value)<=0
                    or utc(price.effective_timestamp)>utc(self.now())):
                raise ResearchRefused('RESEARCH_REFERENCE_PRICE_REFUSED')
            if prices_only:
                return copy.deepcopy({'price':price,'bars':bars,'asset':asset,'receipts':receipts,'paper_eligible':False})
            mapping,receipt=self.client.get('https://www.sec.gov/files/company_tickers.json',ttl=86400,maximum=4*1024*1024)
            receipts.append(receipt)
            matches=[r for r in mapping.values() if type(r) is dict and r.get('ticker')==symbol]
            if len(matches)!=1 or type(matches[0].get('cik_str')) is not int:
                funds={name:MeasuredValue.unknown('SEC_EDGAR','NO_UNAMBIGUOUS_SEC_ISSUER_MAPPING') for name in (
                    'revenue','earnings','eps','free_cash_flow','operating_cash_flow','gross_margin','operating_margin',
                    'net_margin','total_debt','cash','shares_outstanding','market_cap')}
            else:
                cik=str(matches[0]['cik_str']).zfill(10)
                facts,receipt=self.client.get('https://data.sec.gov/api/xbrl/companyfacts/CIK'+cik+'.json',ttl=86400)
                receipts.append(receipt)
                funds=normalize_companyfacts(facts,cik=cik,now=utc(self.now()),retrieved_at=datetime.fromisoformat(receipt['retrieved_at']))
            values=valuation(funds,price,now=utc(self.now()))
            shares=funds.get('shares_outstanding')
            if (shares and shares.quality==DataQuality.FRESH and price.quality==DataQuality.FRESH
                    and shares.is_usable() and price.is_usable() and number(price.value)>0):
                funds['market_cap']=MeasuredValue(value=float(number(price.value)*number(shares.value)),
                    source='SEC_EDGAR_SHARES_X_ALPACA_REFERENCE',timestamp=price.effective_timestamp,
                    effective_timestamp=price.effective_timestamp,retrieved_at=utc(self.now()),availability=True,
                    quality=DataQuality.FRESH,notes=json.dumps({'shares_evidence':shares.notes,'price_source':price.source,
                        'formula':'shares_outstanding * reference_price','not_execution_evidence':True}))
            return copy.deepcopy({'price':price,'fundamentals':funds,'valuation':values,'bars':bars,
                'asset':asset,'receipts':receipts,'paper_eligible':False,
                'refusals':['NO_THREE_EXPLICIT_ACCEPTED_NORMALIZATION_ESTIMATES',
                            'RESEARCH_ACQUISITION_IS_NOT_FINANCIAL_OR_L1_AUTHORITY']})


class FreePriceProvider:
    name='ALPACA_BASIC_IEX'
    def __init__(self,bundle):self.bundle=bundle
    async def get_price(self,symbol):return (await asyncio.to_thread(self.bundle.load,symbol,prices_only=True))['price']
    async def get_daily_ohlcv(self,symbol,**kwargs):return (await asyncio.to_thread(self.bundle.load,symbol,prices_only=True))['bars']


class FreeFundamentalsProvider:
    name='SEC_EDGAR'
    def __init__(self,bundle):self.bundle=bundle
    async def get_all(self,symbol):return (await asyncio.to_thread(self.bundle.load,symbol))['fundamentals']
    async def get_metric(self,symbol,metric):return (await self.get_all(symbol)).get(metric,MeasuredValue.unknown(self.name))


class FreeValuationProvider:
    name='SEC_EDGAR+ALPACA_DERIVED'
    def __init__(self,bundle):self.bundle=bundle
    async def get_all(self,symbol):return (await asyncio.to_thread(self.bundle.load,symbol))['valuation']
    async def get_valuation(self,symbol):return (await self.get_all(symbol))['pe']


def read_only_ingest(*, bundle, universe, history_root):
    from app.investment.ingest import InvestmentIngest
    return InvestmentIngest(universe=universe,price=FreePriceProvider(bundle),
        fundamentals=FreeFundamentalsProvider(bundle),valuation=FreeValuationProvider(bundle),
        history_root=history_root,persist=False,read_only=True)
