"""Bind accepted QD publications and the existing authenticated IEX input.

No provider connection, ranking creation, instrument enrollment or authority
default. The underlying publication/execution verifiers must already be accepted.
"""
from app.investment.alpaca_iex import IEXFeed
from app.investment.quality_dips_candidate_evidence import CandidateEvidenceAdapter
from app.services.paper_financial_replay import body, digest, strict
from app.services.paper_source_publication import QualityDipsSourcePublication
from app.services.quality_dips_autonomous_paper import l1_price
from app.services.quality_dips_iex_input import IEXPaperQuotes
from app.services.quality_dips_publication_reader import QualityDipsPublicationReader

from scripts.observation_runtime.personal_engine_session import NativePersonalEngineSession
from scripts.observation_runtime.personal_local_authority import NativePersonalOperatorAuthority


class NativePersonalMarketInputs:
    def __init__(self, *, operator=None, session=None, source=None):
        if (type(operator) is not NativePersonalOperatorAuthority
                or type(session) is not NativePersonalEngineSession or session.operator is not operator
                or type(source) is not IEXPaperQuotes or type(source.feed) is not IEXFeed
                or source.feed.clock is not operator.clock or source.authority is None):
            raise ValueError('PERSONAL_MARKET_NATIVE_DEPENDENCIES_REQUIRED')
        self.operator, self.session, self.source = operator, session, source
        self._ports = operator, session, source, source.feed, source.authority
        self._grant = None
        self._reader = None

    def bind_session(self, grant):
        grant = strict(body(grant))
        self.session.verify(grant, now=self.operator.clock())
        if self._grant is not None and body(grant) != self._grant:
            raise ValueError('PERSONAL_MARKET_SESSION_REBIND_REFUSED')
        if self.source.session_id != grant['session_id']:
            raise ValueError('PERSONAL_MARKET_SESSION_SOURCE')
        reader = self.source.decision_reader
        if (type(reader) is not QualityDipsPublicationReader or type(reader.source) is not QualityDipsSourcePublication
                or self._reader is not None and reader is not self._reader):
            raise ValueError('PERSONAL_MARKET_PUBLICATION_BINDING')
        self._reader = reader
        self._grant = body(grant)

    def _check(self, now):
        if (any(a is not b for a, b in zip((self.operator, self.session, self.source,
                self.source.feed, self.source.authority), self._ports, strict=True))
                or self._grant is None or type(now) is not int or now != self.operator.clock()
                or self.source.decision_reader is not self._reader
                or self.source.session_id != strict(self._grant)['session_id']):
            raise ValueError('PERSONAL_MARKET_CHANGED_OR_UNBOUND')
        self.session.verify(strict(self._grant), now=now)
        self.operator.activation('CONNECT_APPROVED_DATA')

    def _publication(self, now):
        self._check(now)
        reader = self.source.decision_reader
        if type(reader) is not QualityDipsPublicationReader or type(reader.source) is not QualityDipsSourcePublication:
            raise ValueError('PERSONAL_MARKET_ACCEPTED_PUBLICATION_REQUIRED')
        reader._verify()
        # read_current reuses native archive custody and source provenance. This
        # never invokes the legacy scanner, refreshes a provider or writes data.
        packet = strict(body(reader.source.read_current()))
        if (packet.get('schema') != 'QD_SCANNER_PUBLICATION_V1' or type(packet.get('bundles')) is not list
                or type(packet.get('monitors')) is not dict or len(packet['bundles']) > 16
                or len(packet['monitors']) > 16 or any(type(item) is not dict for item in packet['bundles'])
                or any(type(item) is not dict for item in packet['monitors'].values())):
            raise ValueError('PERSONAL_MARKET_PUBLICATION_SHAPE')
        for ident, monitor in packet['monitors'].items():
            instrument = monitor.get('instrument')
            if (type(instrument) is not dict or instrument.get('instrument_id') != ident
                    or monitor.get('symbol') != instrument.get('symbol')
                    or type(monitor.get('observed_at')) is not int
                    or not 0 <= now-monitor['observed_at'] <= 30):
                raise ValueError('PERSONAL_MARKET_MONITOR_NOT_CURRENT')
        return packet

    @staticmethod
    def _proof(schema, value, packet, quote=None):
        return {'schema':schema,'verified':True,'binding':digest(value),
                'receipt_id':'personal-source:'+digest({'source':packet['source_id'],
                    'revision':packet['revision'],'packet':digest(packet),'quote':quote})}

    def verify_current(self, bundle, *, now):
        packet = self._publication(now)
        if body(bundle) not in [body(item) for item in packet['bundles']]:
            raise ValueError('PERSONAL_MARKET_RANKING_NOT_CURRENT')
        return self._proof('QD_RANKING_VERIFIED_V1', bundle, packet)

    def verify(self, evidence, *, now):
        evidence = strict(body(evidence))
        self._check(now)
        if set(evidence) == {'instrument','quote'}:
            packet = self._publication(now)
            if not any(item['instrument'] == evidence['instrument'] and item['quote'] == evidence['quote']
                       for item in packet['bundles']):
                raise ValueError('PERSONAL_MARKET_INSTRUMENT_OR_RESEARCH_QUOTE')
            quote = self.source.quote(evidence['instrument'])
            return self._proof('QD_EXECUTION_VERIFIED_V1', evidence, packet, quote['sequence'])
        if set(evidence) in ({'bundles','quotes','observation'}, {'bundles','quotes','observation','shutdown_mode'}):
            if self.source.verify_source_request(evidence, now=now) is not True:
                raise ValueError('PERSONAL_MARKET_REQUEST_NOT_ISSUED')
            if 'shutdown_mode' in evidence:
                self.operator.activation('SHUTDOWN_FLATTEN')
                # Graceful Stop needs fresh executable BID evidence, not a new
                # fundamental ranking. It never makes a new entry candidate.
                return {'schema':'QD_AUTO_SOURCE_PROOF_V1','verified':True,'binding':digest(evidence),
                        'receipt_id':'personal-stop-source:'+digest(evidence)}
            packet = self._publication(now)
            if evidence['bundles']:
                if any(body(item) not in [body(b) for b in packet['bundles']] for item in evidence['bundles']):
                    raise ValueError('PERSONAL_MARKET_REQUEST_RANKING_CHANGED')
            elif evidence['observation'] is not None:
                observation = evidence['observation']
                ident = observation['instrument']['instrument_id']
                if packet['monitors'].get(ident) != observation:
                    raise ValueError('PERSONAL_MARKET_POSITION_MONITOR_CHANGED')
            else:
                quote = evidence['quotes'][0]
                monitor = packet['monitors'].get(quote['instrument_id'])
                if (packet['bundles'] or monitor is None
                        or monitor['instrument'].get('symbol') != quote['symbol']):
                    raise ValueError('PERSONAL_MARKET_NO_ENTRY_EVIDENCE_MISSING')
            return self._proof('QD_AUTO_SOURCE_PROOF_V1', evidence, packet)
        raise ValueError('PERSONAL_MARKET_EVIDENCE_SCHEMA')

    def preflight(self):
        now = self.operator.clock()
        packet = self._publication(now)
        adapter = CandidateEvidenceAdapter(ranking_authority=self, execution_authority=self)
        for bundle in packet['bundles']:
            adapter.candidate(bundle, level='L1', now=now)
        instruments = [item['instrument'] for item in packet['bundles']]
        if not instruments:
            instruments = [item['instrument'] for item in packet['monitors'].values()]
        if not instruments:
            raise ValueError('PERSONAL_MARKET_NO_CURRENT_OBSERVATION_SCOPE')
        quotes = [self.source.quote(instrument) for instrument in instruments]
        end = self.operator.clock()
        if not now <= end <= now+5 or self._publication(end) != packet:
            raise ValueError('PERSONAL_MARKET_PREFLIGHT_CLOCK_CHANGED')
        for instrument, quote in zip(instruments, quotes, strict=True):
            l1_price(self.session.manifest, quote, instrument, strict(self._grant), end, 'ENTRY')
        return {'publication_digest':digest(packet),'quotes_digest':digest(quotes),
                'observed_at':end,'symbols':sorted({item['symbol'] for item in instruments})}
