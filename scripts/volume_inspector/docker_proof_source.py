"""Read-only DI proof adapter; NO Docker executable/socket/lifecycle API.

Actual daemon generation/transport authenticity must be supplied by a reviewed
reader. Included reader is synthetic; local capability failure is not exit proof.
"""
import copy
import importlib.util
import json
import secrets
from pathlib import Path

spec = importlib.util.spec_from_file_location('source_contracts', Path(__file__).with_name('native_recovery.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
Refused = r.Refused


class SyntheticReader:
    def __init__(self, daemon, container, image):
        self.daemon, self.container, self.image = daemon, container, image
        self.available, self.cached, self.delay = True, False, 0
        self.calls = []
        self.replacements = {}

    def read(self, kind, identity, nonce, clock):
        if kind not in {'daemon', 'container', 'image'}:
            raise Refused('Read-only scope violation')
        self.calls.append((kind, identity))
        if self.available is not True:
            raise ConnectionError('Synthetic Docker unavailable')
        if type(clock) is r.FixtureClock:
            clock.value += self.delay
        value = self.replacements.get(len(self.calls), getattr(self, kind))
        return r.s.encoded({'request': '0'*64 if self.cached else nonce, 'payload': copy.deepcopy(value)})


class RecordedUnavailableReader:
    """A real recorded capability failure can ONLY produce unavailability."""
    def __init__(self, record):
        if not isinstance(record, dict) or record.get('available') is not False:
            raise Refused('Only recorded unavailable capability accepted')
        self.record_digest = r.s.sha(r.s.encoded(record))
        self.calls = []

    def read(self, kind, identity, _nonce, _clock):
        self.calls.append((kind, identity))
        raise ConnectionError('Recorded Engine unavailable')


class DockerProofAdapter:
    """Fresh before/after daemon and helper observations; never recovery authority."""
    def __init__(self, reader, expected, output, clock):
        if type(reader) not in (SyntheticReader, RecordedUnavailableReader) or type(clock) not in (r.Clock, r.FixtureClock):
            raise Refused('Reviewed synthetic/recorded read-only reader required')
        if not isinstance(expected, dict) or set(expected) != {'daemon', 'helper'}:
            raise Refused('Exact source/helper plan required')
        daemon = expected['daemon']
        if (not isinstance(daemon, dict) or set(daemon) != {'id', 'epoch', 'endpoint'}
                or any(not isinstance(daemon[k], str) or len(daemon[k]) != 64 or any(c not in 'abcdef0123456789' for c in daemon[k]) for k in ('id', 'epoch'))
                or daemon['endpoint'] != 'npipe:////./pipe/dockerDesktopLinuxEngine'):
            raise Refused('Pinned local source identity and connection epoch required')
        helper = expected['helper']
        # Reuse strict immutable helper/image/ownership validator; no collection.
        r.ExitCollector(r.MockDocker(None, None), helper, output, clock)
        lock = json.loads(Path(__file__).with_name('helper-image-lock.json').read_text())
        if helper['manifest'] != lock['proposed_manifest_digest']:
            raise Refused('Helper manifest differs from approved pinned image')
        self.reader, self.expected = reader, copy.deepcopy(expected)
        self.output, self.clock = output, clock

    def _read(self, kind, identity):
        nonce, begin = secrets.token_hex(32), self.clock.now()
        raw = self.reader.read(kind, identity, nonce, self.clock)
        now = self.clock.now()
        if type(raw) is not bytes or len(raw) > 65536 or not 0 <= now-begin <= 2:
            raise Refused('Read response bound/deadline')
        reply = json.loads(raw)
        if not isinstance(reply, dict) or set(reply) != {'request', 'payload'} or reply['request'] != nonce:
            raise Refused('Uncorrelated or cached source response')
        return reply['payload']

    def collect(self):
        began = self.clock.now()
        result = {'source': 'SYNTHETIC_READ_ONLY' if type(self.reader) is SyntheticReader else 'RECORDED_UNAVAILABLE',
                  'observed': began, 'status': 'UNKNOWN', 'reason': 'UNVERIFIED', 'fingerprint': None}
        try:
            before = self._read('daemon', self.expected['daemon']['id'])
            if before != self.expected['daemon']:
                raise Refused('Daemon identity/generation unavailable or changed')
            first = self._read('container', self.expected['helper']['id'])
            image = self._read('image', self.expected['helper']['image'])
            second = self._read('container', self.expected['helper']['id'])
            after = self._read('daemon', self.expected['daemon']['id'])
            now = self.clock.now()
            if not 0 <= now-began <= 5 or after != before:
                raise Refused('Source restart/reconnection or evidence deadline')
            if first != second:
                result.update(status='REPLACED', reason='CONTAINER_CHANGED_DURING_OBSERVATION')
            else:
                collector = r.ExitCollector(r.MockDocker(first, image), self.expected['helper'], self.output, self.clock)
                proof = collector.collect()
                result.update(status=proof['status'], reason=proof['reason'], fingerprint=proof['fingerprint'])
        except ConnectionError:
            result.update(reason='ENGINE_UNAVAILABLE')
        except (ValueError, TypeError, KeyError, OverflowError):
            result.update(status='UNKNOWN', reason='SOURCE_IDENTITY_FRESHNESS_OR_SCHEMA_UNVERIFIED', fingerprint=None)
        result['observed'] = self.clock.now()
        self.output._write(self.output.root_handle, 'source-audit-'+secrets.token_hex(32)+'.json', r.s.encoded(result))
        return result

    def production_recovery(self):
        raise Refused('Read-only proof adapter is not connected to production recovery')
