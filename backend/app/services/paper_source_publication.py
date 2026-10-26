"""Actual cache/research -> current source publications; no provider or trade startup.

Publication/custody/authenticator ports must already be accepted. No local hash,
cache revision, parsed TLS response or injected fixture becomes an issuer here.
"""
from datetime import datetime

from app.services.paper_financial_replay import body, digest, number, strict, text


def parse_public_trades(frame, *, received_ms):
    if (type(received_ms) is not int or type(frame) is not dict or set(frame) != {'channel', 'data'}
            or frame['channel'] != 'trades' or type(frame['data']) is not list or not 0 < len(frame['data']) <= 256):
        raise ValueError('EXACT_BOUNDED_PUBLIC_TRADES_REQUIRED')
    rows = []
    for row in frame['data']:
        if (type(row) is not dict or set(row) not in ({'coin','side','px','sz','hash','time','tid'},
                {'coin','side','px','sz','hash','time','tid','users'})
                or row['coin'] not in ('BTC','ETH','SOL') or row['side'] not in ('A','B')
                or type(row['time']) is not int or not 0 <= received_ms-row['time'] <= 5000
                or type(row['tid']) is not int or row['tid'] < 0 or type(row['hash']) is not str or not row['hash']
                or number(row['px']) <= 0 or number(row['sz']) <= 0):
            raise ValueError('PUBLIC_TRADE_IDENTITY_PRICE_OR_TIME_REFUSED')
        rows.append({k: row[k] for k in ('coin','side','px','sz','hash','time','tid')})
    ids = [(r['coin'], r['time'], r['tid']) for r in rows]
    if len(set(ids)) != len(rows) or len({r['coin'] for r in rows}) != 1:
        raise ValueError('DUPLICATE_OR_MIXED_TRADE_SOURCE')
    return {'schema':'HL_PUBLIC_TRADES_V1','symbol':rows[0]['coin'],'received_ms':received_ms,
            'rows':rows,'complete_window':False,'financial_execution_authorized':False}


class SourcePublication:
    """Narrow publication port; original source receipts stay outside trading commands."""
    def __init__(self, *, lane, source_id, authority, archive, clock):
        if lane not in ('QUALITY_DIPS','HYPERLIQUID') or not source_id or any(x is None for x in (authority,archive,clock)):
            raise ValueError('ACCEPTED_SOURCE_PUBLICATION_DEPENDENCIES_REQUIRED')
        text(source_id)
        self.lane,self.source_id,self.authority,self.archive,self.clock=lane,source_id,authority,archive,clock
        self.components={'lane':lane,'source_id':source_id,'archive':archive,'clock':clock,'authority':authority}
        self.last=None
        if type(self) is SourcePublication:
            raise ValueError('CONCRETE_SOURCE_PRODUCER_REQUIRED')

    def _verify(self):
        if (any(getattr(self,k) is not v if k not in ('lane','source_id') else getattr(self,k)!=v
                for k,v in self.components.items()) or self.authority.verify_components(self.components) is not True):
            raise ValueError('SOURCE_COMPONENTS_CHANGED')

    def publish(self, packet, sources):
        self._verify()
        self._shape(packet)
        now=self.clock()
        old=self.archive.current()
        if (packet.get('revision')!=old['revision']+1
                or self.authority.verify_publication(self.components,old,packet,sources,now) is not True):
            raise ValueError('AUTHENTICATED_SOURCE_PUBLICATION_REQUIRED')
        # Archive owns native immutable publication + durable CAS. No in-memory
        # revision or locally supplied digest can substitute for that contract.
        self.archive.publish(expected=old, packet=strict(body(packet)), sources=strict(body(sources)))
        current=self.read_current()
        if current!=packet: raise ValueError('SOURCE_PUBLICATION_ACK_UNCERTAIN')
        return current

    def read_current(self):
        self._verify()
        now=self.clock(); before=self.archive.current()
        packet=strict(body(self.archive.read(before)))
        self._shape(packet)
        identity=(packet['source_id'],packet['revision'],digest(packet))
        schema,fields=('QD_SCANNER_PUBLICATION_V1',{'bundles','monitors'}) if self.lane=='QUALITY_DIPS' else (
            'PERP_STRATEGY_SOURCE_V1',{'markets','candles','books','funding','oracles','maker_fills','setups'})
        if (set(packet)!= {'schema','source_id','revision','observed_at'}|fields or packet['schema']!=schema
                or type(before.get('revision')) is not int
                or before.get('revision')!=packet['revision'] or before.get('digest')!=digest(packet)
                or packet['source_id'] != self.source_id or type(packet['revision']) is not int or packet['revision'] < 1
                or type(packet['observed_at']) is not int or not 0 <= now-packet['observed_at'] <= (30 if self.lane=='QUALITY_DIPS' else 5)
                or len(body(packet).encode()) > 131072 or self.archive.current()!=before
                or self.authority.verify_current(self.components,before,packet,now) is not True
                or self.last is not None and (identity[0]!=self.last[0] or identity[1]<self.last[1]
                    or identity[1]==self.last[1] and identity[2]!=self.last[2])):
            raise ValueError('SOURCE_CURRENT_CUSTODY_ROLLBACK_OR_FRESHNESS_REFUSED')
        end=self.clock()
        if type(end) is not int or not 0<=end-now<=1:raise ValueError('SOURCE_CLOCK_CONTINUITY_REFUSED')
        self.last=identity
        return packet

    def _shape(self,packet):
        schema,fields=('QD_SCANNER_PUBLICATION_V1',{'bundles','monitors'}) if self.lane=='QUALITY_DIPS' else (
            'PERP_STRATEGY_SOURCE_V1',{'markets','candles','books','funding','oracles','maker_fills','setups'})
        if (type(packet) is not dict or set(packet)!= {'schema','source_id','revision','observed_at'}|fields
                or packet['schema']!=schema or packet['source_id']!=self.source_id
                or type(packet['revision']) is not int or packet['revision']<1
                or type(packet['observed_at']) is not int
                or not 0<=self.clock()-packet['observed_at']<=(30 if self.lane=='QUALITY_DIPS' else 5)
                or len(body(packet).encode())>131072):
            raise ValueError('EXACT_CURRENT_SOURCE_PACKET_REQUIRED')

    def _packet(self,schema):
        self._verify()
        old=self.archive.current()
        if (type(old.get('revision')) is not int or old['revision']<0
                or self.authority.verify_head(self.components,old,self.clock()) is not True):
            raise ValueError('SOURCE_AUTHENTICATED_HIGH_WATER_REQUIRED')
        return {'schema':schema,'source_id':self.source_id,'revision':old['revision']+1,'observed_at':self.clock()}


class QualityDipsSourcePublication(SourcePublication):
    def __init__(self, *, research, candidates, **kwargs):
        from app.investment.quality_dips_candidate_evidence import CandidateEvidenceAdapter
        super().__init__(lane='QUALITY_DIPS',**kwargs)
        self.research,self.candidates=research,candidates
        if research is None or type(candidates) is not CandidateEvidenceAdapter: raise ValueError('QD_RESEARCH_AND_EXISTING_CANDIDATE_ADAPTER_REQUIRED')
        self.components.update(research=research,candidates=candidates)
        self._verify()

    def publish_scanner(self, rows, observed_at):
        self._verify()
        raw=strict(body(self.research.read_current()))
        now=self.clock()
        if (set(raw)!= {'board','observations','instruments','quotes','publication','monitors'}
                or type(raw['instruments']) is not list or len(raw['instruments'])>16
                or type(raw['board']) is not list or len(raw['board'])>100
                or type(raw['monitors']) is not dict or len(raw['monitors'])>16
                or self.authority.verify_research(rows,observed_at,raw,now) is not True):
            raise ValueError('QD_ORIGINAL_RESEARCH_PUBLICATION_BINDING_REQUIRED')
        bundles=[]
        for instrument in raw['instruments']:
            symbol=instrument['symbol']
            bundle={'board':raw['board'],'observation':raw['observations'][symbol],
                'instrument':instrument,'quote':raw['quotes'][symbol],'publication':raw['publication']}
            self.candidates.candidate(bundle,level='L1',now=now)
            bundles.append(bundle)
        if len(bundles)>16: raise ValueError('QD_SOURCE_CANDIDATE_CAPACITY')
        packet={**self._packet('QD_SCANNER_PUBLICATION_V1'),'bundles':bundles,'monitors':raw['monitors']}
        return self.publish(packet,{'research':raw,'scanner_rows':rows,'scanner_observed_at':observed_at})

    def read_publication(self,timeout):
        if type(timeout) not in (int,float) or not 0<timeout<=.2: raise ValueError('QD_BOUNDED_SOURCE_READ_REQUIRED')
        return self.read_current()


class PerpSourcePublication(SourcePublication):
    def __init__(self, *, adapter, orders, settlements, maker, lifecycle, **kwargs):
        from app.adapters.hyperliquid import HyperliquidAdapter
        super().__init__(lane='HYPERLIQUID',**kwargs)
        if type(adapter) is not HyperliquidAdapter or any(x is None for x in (orders,settlements,maker,lifecycle)):
            raise ValueError('PERP_ACCEPTED_CACHE_ORDER_SETTLEMENT_AND_QUEUE_PORTS_REQUIRED')
        self.adapter,self.orders,self.settlements,self.maker,self.lifecycle=adapter,orders,settlements,maker,lifecycle
        self.components.update(adapter=adapter,orders=orders,settlements=settlements,maker=maker,lifecycle=lifecycle)
        self._published_cache=None
        self._verify()

    def capture(self):
        self._verify()
        from app.adapters.hyperliquid import (
            _paper_execution_observation,
            _paper_funding_observation,
        )
        cached=self.adapter.paper_source_snapshot(); now=self.clock()
        if (cached.get('schema')!='HL_SOURCE_CACHE_V1' or cached.get('connected') is not True
                or self.authority.verify_cache(self.components,cached,now) is not True):
            raise ValueError('PERP_AUTHENTICATED_CONNECTED_CACHE_REQUIRED')
        facts=cached['facts'];books={};candles={};funding={};oracles={};proofs={}
        markets=strict(body(facts['markets']))
        if not markets or len(markets)>3 or len({r['symbol'] for r in markets})!=len(markets):
            raise ValueError('PERP_CURRENT_MARKET_SOURCE_REQUIRED')
        for row in markets:
            symbol=row['symbol']; stamp=datetime.fromisoformat(row['timestamp'])
            if stamp.tzinfo is None or not 0<=now-stamp.timestamp()<=5: raise ValueError('PERP_MARKET_SOURCE_STALE')
            original=facts['books'][symbol];parsed=original['parsed']
            actual=_paper_execution_observation(symbol,original['metadata'],original['book'],parsed['request_started_ms'],parsed['observed_at_ms'])
            if (actual!=parsed or not 0<=now*1000-actual['book_timestamp_ms']<=5000
                    or not 0<=now*1000-actual['request_started_ms']<=5000):
                raise ValueError('PERP_EXECUTABLE_BOOK_SOURCE_MISMATCH')
            books[symbol]=actual
            bars=facts['candles'][symbol]
            if bars['interval']!='5m' or not 0<=now*1000-bars['observed_at_ms']<=300000 or not 0<len(bars['rows'])<=96:
                raise ValueError('PERP_CURRENT_CANDLE_SOURCE_REQUIRED')
            times=[r['time'] for r in bars['rows']]
            if (any(type(t) is not int or t<=0 or t>now*1000 for t in times)
                    or times!=sorted(set(times)) or now*1000-times[-1]>305000
                    or any(number(str(r['close']))<=0 for r in bars['rows'])):
                raise ValueError('PERP_CANDLE_EVENT_TIME_OR_PRICE_UNVERIFIED')
            candles[symbol]=bars['rows']
            if symbol in facts['funding']:
                raw=facts['funding'][symbol];p=raw['parsed']
                if p['observed_at_ms']>now*1000:raise ValueError('PERP_FUTURE_FUNDING_SOURCE_REFUSED')
                funding[symbol]=_paper_funding_observation(symbol,raw['rows'],p['start_inclusive_ms'],p['end_exclusive_ms'],raw['started_ms'],p['observed_at_ms'])
                if funding[symbol]!=p: raise ValueError('PERP_FUNDING_SOURCE_MISMATCH')
                for record in p['records']:
                    at=record['settlement_at_ms']//1000
                    oracle=self.settlements.read(symbol,at)
                    if oracle is None: continue  # Planner must refuse a due settlement, never substitute current oracle.
                    if (set(oracle)!= {'symbol','settlement_at','price','source_id','revision'}
                            or type(oracle['revision']) is not int or oracle['revision']<1
                            or type(oracle['source_id']) is not str or not oracle['source_id']
                            or oracle.get('symbol')!=symbol or oracle.get('settlement_at')!=at or number(oracle['price'])<=0
                            or self.authority.verify_settlement(p,oracle,now) is not True):
                        raise ValueError('PERP_AUTHENTICATED_HISTORICAL_ORACLE_REQUIRED')
                    oracles[f'{symbol}:{at}']=oracle
        control=self.orders.snapshot()
        for key,row in control['state']['orders'].items():
            if row['state']!='RESERVED': continue
            value=self.maker.read(key)
            if value is None: continue
            order=row['order'];trades=facts['trades'].get(order['symbol'])
            if trades is None or self.authority.verify_maker(order,value,trades,now) is not True:
                raise ValueError('PERP_AUTHENTICATED_QUEUE_AND_TRADE_WINDOW_REQUIRED')
            proof=value['proof']; ids=value['trade_ids']
            if (type(ids) is not list or not 0<len(ids)<=256
                    or any(type(x) is not list or len(x)!=2 or any(type(n) is not int for n in x) for x in ids)):
                raise ValueError('EXACT_EXECUTED_TRADE_IDENTITIES_REQUIRED')
            queue=value['queue']; original=queue['book']
            _paper_execution_observation(order['symbol'],queue['metadata'],original,original['time'],original['time'])
            levels=original['levels'][0 if order['side']=='LONG' else 1]
            at_limit=[r for r in levels if number(r['px'])==number(order['limit_price'])]
            if (queue.get('source_digest')!=order['source_digest'] or queue.get('source_revision')!=order['source_revision']
                    or original.get('coin')!=order['symbol'] or len(at_limit)!=1
                    or original.get('time')!=order['created_at']*1000
                    or number(proof['queue_ahead'])<number(at_limit[0]['sz'])
                    or proof['source_ref']!=digest({'queue':queue,'trades':trades})):
                raise ValueError('PERP_ORIGINAL_VISIBLE_QUEUE_AND_RECEIPT_REQUIRED')
            selected=[r for r in trades['rows'] if [r['time'],r['tid']] in ids]
            if (not ids or len(selected)!=len(ids) or len({tuple(x) for x in ids})!=len(ids)
                    or any(r['side']!=('A' if order['side']=='LONG' else 'B')
                           or number(r['px'])!=number(proof['trade_price'])
                           or not order['created_at']*1000<r['time']<=now*1000 for r in selected)
                    or number(proof['traded_quantity'])!=sum(number(r['sz']) for r in selected)
                    or proof['order_id']!=key or proof['rested_at']!=order['created_at']):
                raise ValueError('PERP_EXECUTED_TRADE_TO_QUEUE_PROOF_MISMATCH')
            if proof['trade_at']!=max(r['time'] for r in selected)//1000:
                raise ValueError('PERP_TRADE_CLOCK_PROOF_MISMATCH')
            proofs[key]=proof
        packet={**self._packet('PERP_STRATEGY_SOURCE_V1'),'markets':markets,'candles':candles,'books':books,
            'funding':funding,'oracles':oracles,'maker_fills':proofs,'setups':self.lifecycle.read_current()}
        if self.adapter.paper_source_snapshot()!=cached or self.orders.snapshot()!=control:
            raise ValueError('PERP_SOURCE_CHANGED_DURING_PUBLICATION')
        result=self.publish(packet,{'cache':cached,'orders':control})
        self._published_cache=digest(cached)
        return result

    def read_cut(self):
        value=self.read_current()
        cache=self.adapter.paper_source_snapshot()
        if (cache['connected'] is not True or self._published_cache!=digest(cache)
                or self.authority.verify_cache(self.components,cache,self.clock()) is not True):
            raise ValueError('PERP_SOURCE_CACHE_CHANGED_REPUBLICATION_REQUIRED')
        return value
