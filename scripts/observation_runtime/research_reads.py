"""Read-only presentation ports. No provider, scanner, store bootstrap or writer imports."""
import copy
import hashlib
import json
import math
import threading


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


class ResearchPublicationRead:
    """Injected accepted publisher/authority; local hashes are integrity, not authority.

    source.read_publication(timeout=...) must be an already accepted nonmutating
    read port. verifier authenticates the entire immutable packet AND current cut.
    No default source, local file adoption, issuer or financial permission.
    """
    def __init__(self, *, source, authority, clock, expected_source):
        if not source or not authority or not clock or not expected_source:
            raise ValueError('ACCEPTED_RESEARCH_READ_DEPENDENCIES_REQUIRED')
        self.source, self.authority, self.clock = source, authority, clock
        self.expected_source = expected_source
        self.last = None
        self.lock = threading.Lock()

    def read(self):
        with self.lock:
            now = self.clock()
            packet = copy.deepcopy(self.source.read_publication(timeout=.2))
            raw = canonical(packet)
            if (type(now) is not int or len(raw.encode()) > 262144 or type(packet) is not dict
                    or set(packet) != {'schema','source_id','revision','observed_at','complete','board'}
                    or packet['schema'] != 'QD_RESEARCH_PUBLICATION_V1'
                    or packet['source_id'] != self.expected_source
                    or type(packet['revision']) is not int or packet['revision'] < 1
                    or type(packet['observed_at']) is not int or not 0 <= now-packet['observed_at'] <= 30
                    or packet['complete'] is not True or type(packet['board']) is not list
                    or len(packet['board']) > 100):
                raise ValueError('CURRENT_COMPLETE_RESEARCH_PUBLICATION_REQUIRED')
            if self.authority.verify_research_publication(packet, now) is not True:
                raise ValueError('RESEARCH_CURRENT_AUTHORITY_UNVERIFIED')
            symbols = []
            for row in packet['board']:
                if type(row) is not dict or type(row.get('symbol')) is not str or not row['symbol']:
                    raise ValueError('RESEARCH_INSTRUMENT_IDENTITY_REQUIRED')
                if (type(row.get('instrument_id')) is not str or not row['instrument_id']
                        or type(row.get('research_observed_at')) is not int
                        or not 0 <= now-row['research_observed_at'] <= 30):
                    raise ValueError('CURRENT_INSTRUMENT_RESEARCH_EVIDENCE_REQUIRED')
                quote = row.get('current_quote', {})
                if type(quote) is not dict:
                    raise ValueError('RESEARCH_QUOTE_SCHEMA_REQUIRED')
                quality = row.get('quote_quality', quote.get('quality'))
                if quality in ('LIVE','FRESH') and (type(row.get('quote_observed_at')) is not int
                        or not 0 <= now-row['quote_observed_at'] <= 5):
                    raise ValueError('CURRENT_QUOTE_TIMESTAMP_REQUIRED')
                symbols.append(row['symbol'])
            if len(set(symbols)) != len(symbols):
                raise ValueError('DUPLICATE_RESEARCH_SYMBOL')
            cut = (packet['revision'], hashlib.sha256(raw.encode()).hexdigest())
            if self.last and (cut[0] < self.last[0] or cut[0] == self.last[0] and cut != self.last):
                raise ValueError('RESEARCH_ROLLBACK_OR_CONFLICT')
            finished = self.clock()
            if type(finished) is not int or finished < now or not 0 <= finished-packet['observed_at'] <= 30:
                raise ValueError('RESEARCH_CLOCK_OR_FRESHNESS_CHANGED')
            self.last = cut
            return {'board': packet['board'], 'runtime_refresh': {'state':'FRESH','age_sec':now-packet['observed_at']},
                    'source_evidence': {k:packet[k] for k in ('source_id','revision','observed_at','complete')},
                    'source_digest':cut[1], 'financial_execution_authorized':False}


def retained_hyperliquid(history):
    """Present verified local capture bytes; never authenticate them as current market evidence."""
    candidates = []
    for session in history['sessions']:
        rows = [r for r in session['records'] if r['kind'] == 'HYPERLIQUID_PUBLIC_RESPONSE']
        meta = [r for r in rows if r['value']['request']['type'] == 'metaAndAssetCtxs']
        if not meta:
            continue
        row = meta[-1]
        response = row['value']['response']
        if type(response) is not list or len(response) != 2 or type(response[0]) is not dict or type(response[1]) is not list:
            raise ValueError('RETAINED_METADATA_SCHEMA')
        universe, contexts = response
        if type(universe.get('universe')) is not list:
            raise ValueError('RETAINED_METADATA_SCHEMA')
        if len(universe['universe']) != len(contexts):
            raise ValueError('RETAINED_METADATA_INCOMPLETE')
        markets = []
        for instrument, context in zip(universe['universe'], contexts, strict=True):
            if type(instrument) is not dict or type(context) is not dict:
                raise ValueError('RETAINED_METADATA_ROW_SCHEMA')
            if instrument['name'] not in ('BTC','ETH','SOL'):
                continue
            values = [context.get(k) for k in ('markPx','dayNtlVlm','openInterest','funding')]
            if any(v is not None and (isinstance(v,bool) or not math.isfinite(float(v))) for v in values):
                raise ValueError('RETAINED_NONFINITE_MARKET')
            markets.append(dict(zip(('symbol','price','volume_24h','open_interest','funding_rate'),[instrument['name'],*values])))
        if len(markets) != 3 or len({m['symbol'] for m in markets}) != 3:
            raise ValueError('RETAINED_MARKET_ROSTER_INCOMPLETE')
        candidates.append((row['at'], session, row, markets))
    if not candidates:
        raise ValueError('NO_RETAINED_HYPERLIQUID_METADATA')
    _, session, row, markets = max(candidates, key=lambda x:(x[0],x[1]['session']))
    return {'schema':'ATLAS_RESEARCH_OBSERVATION_VIEW_V1','status':'HISTORICAL_OBSERVATION',
            'data_status':'STALE','capture_scope':session['records'][0]['value'].get('scope','UNVERIFIED_CAPTURE_SCOPE'),
            'freshness':'STALE_NOT_EXECUTABLE','authority':'LOCAL_CAPTURE_INTEGRITY_ONLY_NOT_CURRENT_AUTHENTICATION',
            'source_session':session['session'],'source_revision':row['revision'],'source_digest':row['digest'],
            'observed_at':row['value']['received_at'],'archive_status':history['status'],
            'omitted_sessions':history['omitted_sessions'],'session_status':session['status'],
            'markets':markets,'financial_execution_authorized':False,'current_signals':None}
