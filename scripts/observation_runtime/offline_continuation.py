"""FIXTURE-ONLY immutable continuation of already committed FS1 event streams.

No command dispatch, financial writer, operational enrollment or runtime hook.
Native DACL/security custody and multi-store operational continuation are NOT
implemented here. Caller-injected fixture custody is never operational authority.
"""
import os
from itertools import islice
from pathlib import Path

from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import (
    body,
    digest,
    number,
    replay_verified_events,
    strict,
    validate_manifest,
)

LANES = {'QUALITY_DIPS', 'HYPERLIQUID'}
MAX_SEGMENTS = 16
MAX_RECORDS = 128
MAX_BYTES = 2 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[2] / 'logs/diagnostics'


class Uncertain(ValueError):
    """Preserve the archive; no automatic repair, adoption or financial replay."""


def identity(stat):
    return [stat.st_dev, stat.st_ino]


class OfflineContinuation:
    def __init__(self, root, *, custody, manifests):
        self.root = Path(root).absolute()
        self.custody = custody
        self.manifests = strict(body(manifests))
        self._namespace()
        if custody is None or set(manifests) != LANES:
            raise ValueError('EXPLICIT_FIXTURE_CUSTODY_AND_TWO_ACCOUNTS_REQUIRED')
        for lane, manifest in manifests.items():
            validate_manifest(manifest)
            if (manifest['schema'] not in ('PAPER_EPOCH_FIXTURE_V1', 'PAPER_EPOCH_AUTONOMOUS_QD_V1',
                                           'PAPER_EPOCH_PERP_FIXTURE_V2')
                    or manifest['currency'] != ('USD' if lane == 'QUALITY_DIPS' else 'USDC')):
                raise ValueError('FIXTURE_ONLY_SEPARATE_CURRENCY_ACCOUNTS_REQUIRED')
        if custody.verify_scope(str(self.root), self.manifests) is not True:
            raise ValueError('EXPLICIT_SYNTHETIC_SCOPE_ENROLLMENT_REQUIRED')
        if len({m['epoch'] for m in manifests.values()}) != 2:
            raise ValueError('DISTINCT_ACCOUNT_EPOCHS_REQUIRED')

    def _namespace(self):
        if (self.root.name != 'archive' or self.root.parent.parent != ROOT
                or not self.root.parent.name.startswith('continuation-fixture-')
                or any(p.is_symlink() or p.is_junction() for p in (self.root, *self.root.parents))):
            raise ValueError('NEW_CONFINED_SYNTHETIC_ARCHIVE_REQUIRED')

    def _write(self, name, value):
        self._namespace()
        raw = body(value).encode()
        if len(raw) > MAX_BYTES:
            raise ValueError('BOUNDED_SEGMENT_BYTES_REQUIRED')
        with (self.root / name).open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
            stat = os.fstat(stream.fileno())  # Original creation handle, not path reopen.
            return {'identity': identity(stat), 'digest': digest(value), 'bytes': len(raw)}

    def _read(self, name, binding):
        self._namespace()
        path = self.root / name
        if path.is_symlink() or path.is_junction():
            raise Uncertain('SUBSTITUTED_SEGMENT_NAMESPACE')
        with path.open('rb') as stream:
            stat = os.fstat(stream.fileno())
            if identity(stat) != binding['identity'] or stat.st_nlink != 1 or stat.st_size > MAX_BYTES:
                raise Uncertain('SEGMENT_IDENTITY_OR_SIZE_CHANGED')
            raw = stream.read(MAX_BYTES + 1)
        value = strict(raw)
        if len(raw) != binding['bytes'] or body(value).encode() != raw or digest(value) != binding['digest']:
            raise Uncertain('SEGMENT_BYTES_OR_DIGEST_CHANGED')
        return value

    def create(self):
        with self.custody.lease():
            if self.custody.verify_scope(str(self.root), self.manifests) is not True:
                raise Uncertain('FIXTURE_SCOPE_REVOKED_BEFORE_CREATION')
            if self.custody.current() is not None:
                raise Uncertain('NO_SECOND_INCEPTION_OR_ADOPTION')
            self.root.mkdir(exist_ok=False)
            scope = {'schema': 'OFFLINE_CONTINUATION_SCOPE_V1', 'execution': 'FIXTURE_ONLY',
                     'manifests': self.manifests, 'max_segments': MAX_SEGMENTS, 'max_records': MAX_RECORDS}
            bound = self._write('scope.json', scope)
            pin = {'schema': 'OFFLINE_CONTINUATION_PIN_V1', 'scope': bound,
                   'root_identity': identity(self.root.stat()), 'segments': []}
            if self.custody.compare_and_swap(None, pin) is not True:
                raise Uncertain('CREATION_CUSTODY_UNCERTAIN')
        return self.read()

    def _load(self):
        self._namespace()
        if self.custody.verify_scope(str(self.root), self.manifests) is not True:
            raise Uncertain('FIXTURE_SCOPE_REVOKED')
        pin = strict(body(self.custody.current()))
        if (type(pin) is not dict or set(pin) != {'schema','scope','root_identity','segments'}
                or pin['schema'] != 'OFFLINE_CONTINUATION_PIN_V1'
                or self.custody.verify_current(pin) is not True
                or identity(self.root.stat()) != pin['root_identity']
                or type(pin['segments']) is not list or len(pin['segments']) > MAX_SEGMENTS):
            raise Uncertain('ACCEPTED_FIXTURE_CURRENT_CUT_REQUIRED')
        scope = self._read('scope.json', pin['scope'])
        if scope != {'schema':'OFFLINE_CONTINUATION_SCOPE_V1','execution':'FIXTURE_ONLY',
                     'manifests':self.manifests,'max_segments':MAX_SEGMENTS,'max_records':MAX_RECORDS}:
            raise Uncertain('FOREIGN_ACCOUNT_OR_SCOPE')
        expected = {'scope.json'}
        rows = {lane: [] for lane in LANES}
        requests = {}
        previous = digest(scope)
        states = self._replay(rows)
        for index, segment in enumerate(pin['segments'], 1):
            names = {stage: f'{index:04d}-{stage}.json' for stage in ('intent','record','commit','ack')}
            expected.update(names.values())
            if type(segment) is not dict or set(segment) != set(names):
                raise Uncertain('INCOMPLETE_SEGMENT_BINDING')
            values = {stage: self._read(name, segment[stage]) for stage, name in names.items()}
            intent, record, commit, ack = (values[k] for k in names)
            if (set(record) != {'schema','index','request_id','previous','opening_digest','boundary','rows'}
                    or record['schema'] != 'OFFLINE_CONTINUATION_SEGMENT_V1'
                    or type(record['index']) is not int or record['index'] != index
                    or record['previous'] != previous or record['opening_digest'] != digest(states)
                    or intent != {'schema':'OFFLINE_CONTINUATION_INTENT_V1','record_digest':digest(record)}
                    or commit != {'schema':'OFFLINE_CONTINUATION_COMMIT_V1','record':segment['record'],
                                  'intent':segment['intent']}
                    or ack != {'schema':'OFFLINE_CONTINUATION_ACK_V1','commit':segment['commit']}
                    or record['request_id'] in requests):
                raise Uncertain('SEGMENT_CONTINUITY_OR_ACK_CONFLICT')
            prefix = strict(body(pin))
            prefix['segments'] = prefix['segments'][:index-1]
            self._boundary(record['boundary'], prefix, states)
            self._batch(record['rows'])
            if index > 1 and any(number(p['remaining']) > 0 for s in states.values() for p in s['state']['positions'].values()):
                raise Uncertain('ROLLOVER_REQUIRES_FLAT_PREDECESSOR')
            for lane in LANES:
                rows[lane].extend(record['rows'][lane])
            states = self._replay(rows)
            requests[record['request_id']] = digest(record['rows'])
            previous = digest(record)
        # Unpinned intent/record or missing ACK is UNKNOWN, never auto-adopted.
        if ({p.name for p in islice(self.root.iterdir(), len(expected)+1)} != expected
                or self.custody.current() != pin or self.custody.verify_current(pin) is not True
                or self.custody.verify_scope(str(self.root), self.manifests) is not True):
            raise Uncertain('INCOMPLETE_PUBLICATION_OR_CHANGED_CURRENT_CUT')
        return pin, rows, states, requests, previous

    def _boundary(self, value, pin, cuts):
        if (type(value) is not dict or set(value) != {'schema','predecessor_pin_digest','cuts_digest','state','proof'}
                or value['schema'] != 'OFFLINE_CONTINUATION_BOUNDARY_V1'
                or value['predecessor_pin_digest'] != digest(pin) or value['cuts_digest'] != digest(cuts)
                or value['state'] != 'FINAL_FLAT_DRAINED_NO_RESTING_OR_UNKNOWN'
                or self.custody.verify_boundary(value) is not True):
            raise Uncertain('EXPLICIT_FIXTURE_DRAIN_AND_CONTINUATION_AUTHORITY_REQUIRED')

    def _replay(self, rows):
        states = {}
        for lane in LANES:
            state, head, _ = replay_verified_events(self.manifests[lane], rows[lane])
            audit_financial_events(self.manifests[lane], rows[lane], state)
            states[lane] = {'state':state,'head':head}
        return states

    @staticmethod
    def _batch(rows):
        if (type(rows) is not dict or set(rows) != LANES
                or any(type(value) is not list for value in rows.values())
                or not 1 <= sum(map(len, rows.values())) <= MAX_RECORDS):
            raise ValueError('BOUNDED_NONEMPTY_TWO_ACCOUNT_RECORD_BATCH_REQUIRED')
        size = 0
        for group in rows.values():
            for row in group:
                if (type(row) is not dict or set(row) != {'schema','revision','operation_id','command','parent','digest','receipt'}
                        or type(row['revision']) is not int
                        or any(type(row[k]) is not str or len(row[k]) > 32768 for k in
                               ('schema','operation_id','command','parent','digest','receipt'))):
                    raise ValueError('BOUNDED_CANONICAL_RECORD_FIELDS_REQUIRED')
                size += sum(len(row[k].encode()) for k in ('command','receipt'))
        if size > MAX_BYTES - 4096:
            raise ValueError('BOUNDED_SEGMENT_BYTES_REQUIRED')

    def read(self):
        _, rows, cuts, _, _ = self._load()
        return {'schema':'OFFLINE_CONTINUATION_VIEW_V1','accounts':cuts,'rows':rows,
                'startup_authorized':False,'execution':'FIXTURE_ONLY'}

    def inspect_recovery(self):
        """Read-only classification; UNKNOWN never returns an invented financial cut."""
        try:
            return {'status':'ACKNOWLEDGED','view':self.read(),'admission_authorized':False}
        except (ValueError, OSError, KeyError, TypeError) as error:
            return {'status':'UNKNOWN','view':None,'reason':str(error),'admission_authorized':False}

    def publish_committed_fixture_records(self, request_id, rows, *, fault=lambda phase: None):
        # This does not execute commands. FS1 recomputes/audits supplied receipts.
        if type(request_id) is not str or not 1 <= len(request_id) <= 128:
            raise ValueError('BOUNDED_EXPLICIT_REQUEST_ID_REQUIRED')
        self._batch(rows)
        rows = strict(body(rows))
        with self.custody.lease():
            pin, prior_rows, cuts, requests, previous = self._load()
            if request_id in requests:
                if requests[request_id] != digest(rows):
                    raise Uncertain('DUPLICATE_REQUEST_CONFLICT')
                return self.read()
            if len(pin['segments']) >= MAX_SEGMENTS:
                raise ValueError('SEGMENT_CAPACITY_NO_RESET')
            if pin['segments'] and any(number(p['remaining']) > 0 for c in cuts.values() for p in c['state']['positions'].values()):
                raise Uncertain('ROLLOVER_REQUIRES_FLAT_PREDECESSOR')
            merged = {lane: prior_rows[lane] + rows[lane] for lane in LANES}
            self._replay(merged)  # Includes duplicate IDs,global revision and independent audit.
            boundary = self.custody.boundary(pin, cuts)
            self._boundary(boundary, pin, cuts)
            record = {'schema':'OFFLINE_CONTINUATION_SEGMENT_V1','index':len(pin['segments'])+1,
                      'request_id':request_id,'previous':previous,'opening_digest':digest(cuts),'boundary':boundary,'rows':rows}
            if len(body(record).encode()) > MAX_BYTES:
                raise ValueError('BOUNDED_SEGMENT_BYTES_REQUIRED')
            bindings = {}
            def put(stage, value):
                bindings[stage] = self._write(f"{record['index']:04d}-{stage}.json", value)
                fault(stage)
            fault('before_intent')
            put('intent', {'schema':'OFFLINE_CONTINUATION_INTENT_V1','record_digest':digest(record)})
            put('record', record)
            put('commit', {'schema':'OFFLINE_CONTINUATION_COMMIT_V1',
                           'record':bindings['record'],'intent':bindings['intent']})
            next_pin = strict(body(pin))
            # Expected ACK binding cannot be guessed: commit currentness first,
            # then ACK publication and final custody CAS. Any crash here is UNKNOWN.
            next_pin['segments'].append(dict(bindings))
            if self.custody.compare_and_swap(pin, next_pin) is not True:
                raise Uncertain('COMMIT_CUSTODY_UNCERTAIN')
            fault('current_commit')
            put('ack', {'schema':'OFFLINE_CONTINUATION_ACK_V1','commit':bindings['commit']})
            final_pin = strict(body(next_pin))
            final_pin['segments'][-1] = bindings
            if self.custody.compare_and_swap(next_pin, final_pin) is not True:
                raise Uncertain('ACK_CUSTODY_UNCERTAIN')
            fault('acknowledged')
            return self.read()
