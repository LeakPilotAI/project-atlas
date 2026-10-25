"""Source-derived IEX/QD planning, through the existing V5 decision engine.

No source discovery, scanner refresh, issuer default or financial write. The
accepted reader supplies original ranking/monitor evidence, never a trade command.
"""
from app.services.paper_financial_replay import body, digest, strict
from app.services.paper_market_observers import IEXMarketObserver
from app.services.quality_dips_autonomous_paper import NoFill
from app.services.quality_dips_iex_input import IEXPaperQuotes
from app.services.quality_dips_unified_writer import EnrolledQualityDipsWriter


class QualityDipsUnifiedPlanner:
    def __init__(self, *, writer, observer, quotes, reader):
        if (type(writer) is not EnrolledQualityDipsWriter or type(observer) is not IEXMarketObserver
                or type(quotes) is not IEXPaperQuotes or quotes.feed is not observer.feed or reader is None):
            raise ValueError('QD_UNIFIED_EXISTING_COMPONENTS_REQUIRED')
        self.writer, self.observer, self.quotes, self.reader = writer, observer, quotes, reader
        self.components = {'writer': writer, 'observer': observer, 'quotes': quotes, 'reader': reader}
        self.last = None
        self._verify()

    def _verify(self):
        verifier = getattr(self.writer.authority, 'verify_planner_components', None)
        if (any(getattr(self, key) is not value for key, value in self.components.items())
                or self.quotes.feed is not self.observer.feed
                or verifier is None or verifier(self.writer.binding, self.components) is not True):
            raise ValueError('QD_UNIFIED_PLANNER_SOURCE_AUTHORITY_REQUIRED')

    async def next_proposal(self, observation, cut):
        self._verify()
        if (self.observer.verify_observation(observation) is not True
                or observation['connection'] != 'CONNECTED' or observation['session'] != 'OPEN'
                or body(self.writer._cut()) != body(cut)):
            raise ValueError('QD_UNIFIED_OBSERVATION_OR_SOURCE_CHANGED')
        r = self.writer.runtime.runtime
        if r.grant is None or r.stopped.is_set() or r.halted:
            raise ValueError('QD_UNIFIED_CANDIDATE_ADMISSION_CLOSED')
        request = self.reader.read_request(timeout=.2)
        verifier = getattr(self.writer.authority, 'verify_decision_source', None)
        if verifier is None or verifier(self.writer.binding, request, observation, cut) is not True:
            raise ValueError('QD_UNIFIED_RANKING_MONITOR_SOURCE_UNVERIFIED')
        if request is None:
            self.last = {'state': 'NO_SIGNAL', 'source_head': cut['head']}
            return None
        request = strict(body(request))
        if set(request) != {'instrument', 'bundles', 'observation'}:
            raise ValueError('QD_UNIFIED_DECISION_REQUEST_SCHEMA')
        # Use the actual cache-to-executable-L1 path. V5 re-verifies ranking,
        # instrument, session, source revisions, liquidity and financial risk.
        frame = self.quotes.frame(session_id=r.grant['engine_grant']['session_id'],
                                  sequence=r.sequence + 1, **request)
        if self.observer.verify_observation(observation) is not True:
            raise ValueError('QD_UNIFIED_QUOTE_CHANGED_DURING_PLANNING')
        try:
            proposal = self.writer.propose(frame, observation)
        except NoFill as error:
            # Only these explicit strategy decisions mean a healthy no-trade scan.
            # Missing authority, corrupt sources and UNKNOWN are not caught here.
            if str(error) not in {'HOLD_EXISTING_POSITION', 'NO_ELIGIBLE_CANDIDATE',
                                  'PAUSED_ENTRIES_CLOSED', 'NO_SUPPORTED_FILL_QUANTITY'}:
                raise
            self.last = {'state': 'NO_TRADE', 'reason': str(error), 'source_head': cut['head']}
            return None
        self.last = {'state': 'PROPOSED', 'source_head': cut['head'], 'frame_digest': digest(frame),
                     'operation_id': proposal['operation_id']}
        return proposal
