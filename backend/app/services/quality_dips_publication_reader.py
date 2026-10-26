"""Read original authenticated scanner publications; no scanner/provider refresh.

The current source publisher and its custody remain independently enrolled ports.
This adapter never signs a ranking, modifies research evidence or adopts legacy
financial records. Actual candidate validation and ordering reuse the V5 engine.
"""
from app.services.paper_financial_replay import body, digest, number, strict


class QualityDipsPublicationReader:
    def __init__(self, *, writer, source):
        if writer is None or source is None:
            raise ValueError('QD_ACCEPTED_PUBLICATION_COMPONENTS_REQUIRED')
        self.writer, self.source = writer, source
        self.components = {'writer': writer, 'source': source}
        self._last = None
        self._verify()

    def _verify(self):
        verifier = getattr(self.writer.authority, 'verify_publication_components', None)
        if (any(getattr(self, key) is not value for key, value in self.components.items())
                or verifier is None or verifier(self.writer.binding, self.components) is not True):
            raise ValueError('QD_PUBLICATION_SOURCE_ENROLLMENT_REQUIRED')

    def read_request(self, timeout):
        if type(timeout) not in (float, int) or not 0 < timeout <= .2:
            raise ValueError('QD_BOUNDED_PUBLICATION_READ_REQUIRED')
        self._verify()
        runtime = self.writer.runtime.runtime
        if runtime.grant is None or runtime.stopped.is_set() or runtime.halted:
            raise ValueError('QD_PUBLICATION_SESSION_CLOSED')
        packet = strict(body(self.source.read_publication(timeout=timeout)))
        now, cut = runtime._now(), self.writer._cut()
        if (type(packet) is not dict or set(packet) != {'schema', 'source_id', 'revision', 'observed_at', 'bundles', 'monitors'}
                or packet['schema'] != 'QD_SCANNER_PUBLICATION_V1' or type(packet['source_id']) is not str or not packet['source_id']
                or type(packet['revision']) is not int or packet['revision'] < 1
                or type(packet['observed_at']) is not int or not 0 <= now - packet['observed_at'] <= 30
                or type(packet['bundles']) is not list or len(packet['bundles']) > 16
                or type(packet['monitors']) is not dict or len(packet['monitors']) > 16
                or len(body(packet).encode()) > 131072):
            raise ValueError('QD_CURRENT_SCANNER_PUBLICATION_REQUIRED')
        verifier = getattr(self.writer.authority, 'verify_scanner_publication', None)
        if verifier is None or verifier(self.writer.binding, packet, cut, now) is not True:
            raise ValueError('QD_SCANNER_CURRENT_CUSTODY_UNVERIFIED')
        identity = (packet['source_id'], packet['revision'], digest(packet))
        if self._last is not None and (identity[0] != self._last[0] or identity[1] < self._last[1]
                or identity[1] == self._last[1] and identity[2] != self._last[2]):
            raise ValueError('QD_SCANNER_SOURCE_ROLLBACK_OR_CONFLICT')
        self._last = identity
        positions = [p for p in cut['state']['positions'].values() if number(p['remaining']) > 0]
        if len(positions) > 1:
            raise ValueError('QD_UNEXPECTED_POSITION_COUNT')
        if positions:
            p = positions[0]
            observation = packet['monitors'].get(p['instrument']['instrument_id'])
            if (observation is None or observation.get('instrument') != p['instrument'] or observation.get('symbol') != p['symbol']
                    or type(observation.get('observed_at')) is not int or not 0 <= now - observation['observed_at'] <= 30):
                raise ValueError('QD_CURRENT_POSITION_MONITOR_UNAVAILABLE')
            return {'instrument': p['instrument'], 'bundles': [], 'observation': observation}
        if not packet['bundles']:
            return None
        candidates = [strict(runtime.engine.candidates.candidate(bundle, level='L1', now=now)) for bundle in packet['bundles']]
        if len({(c['cohort_id'], c['source_revision'], c['generation']) for c in candidates}) != 1:
            raise ValueError('QD_PUBLICATION_CROSS_COHORT')
        selected = min(candidates, key=lambda c: (c['ranking']['rank'], -number(str(c['score'])), c['ranking']['instrument_id']))
        return {'instrument': selected['execution']['instrument'], 'bundles': packet['bundles'], 'observation': None}
