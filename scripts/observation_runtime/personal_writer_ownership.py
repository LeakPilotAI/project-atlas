"""Single-process QD writer leases using existing native roots and mutex.

Checks only the explicitly enrolled Atlas writer roster. This is cooperative
same-user exclusion, not a claim to detect/block every malicious same-user or
administrator process. No process enumeration, termination or root creation.
"""
import os
from contextlib import contextmanager
from pathlib import Path
from threading import RLock, get_ident

from app.services.paper_financial_replay import body, digest, strict
from app.services.perp_operational_contract import (
    validate_enrollment as validate_hl_enrollment,
)
from app.services.quality_dips_autonomous_enrollment import validate_enrollment

from scripts.observation_runtime.personal_local_authority import (
    NativePersonalOperatorAuthority,
)
from scripts.observation_runtime.personal_paper_inception import native_primitives
from scripts.observation_runtime.quality_dips_read_service import observe_self


class NativePersonalWriterOwnership:
    def __init__(self, *, enrollment=None, authority=None, inception_intent=None, ledger=None, read_only=False,
                 generation=None):
        if enrollment is None or type(authority) is not NativePersonalOperatorAuthority:
            raise ValueError('PERSONAL_WRITER_INSTALLED_AUTHORITY_REQUIRED')
        self._lane = ('HYPERLIQUID' if type(enrollment) is dict
                      and enrollment.get('schema') == 'PERP_AUTO_NATIVE_ENROLLMENT_V1'
                      else 'QUALITY_DIPS')
        self.enrollment = (validate_hl_enrollment(enrollment)
                           if self._lane == 'HYPERLIQUID'
                           else validate_enrollment(enrollment))
        if body(authority.enrollment) != body(self.enrollment):
            raise ValueError('PERSONAL_WRITER_ENROLLMENT_CONFLICT')
        self.authority, self.native = authority, native_primitives()
        if type(read_only) is not bool or read_only and inception_intent is not None:
            raise ValueError('PERSONAL_READ_ONLY_OWNERSHIP_SCOPE')
        self.read_only = self._read_only = read_only
        self.generation = self._generation = generation
        # Inception may acquire ownership before coordination is installed.
        # Runtime drain always requires the actual existing native ledger.
        self.ledger, self._ledger = ledger, ledger
        self._enrollment, self._authority = body(self.enrollment), authority
        self.inception_intent = strict(body(inception_intent)) if inception_intent is not None else None
        self._intent = body(self.inception_intent)
        self.outputs, self.mutex, self.active, self.poisoned = {}, None, 0, False
        self.lock = RLock()
        raw = observe_self()
        self.identity = {'schema': 'QD_OP_PROCESS_ID_V1', **raw}
        if (raw['pid'] != os.getpid() or not raw['image'].startswith('D:\\')
                or not read_only and generation is None and any(p != self.identity for p in self.enrollment['writers'].values())):
            raise ValueError('PERSONAL_WRITER_EXACT_SELF_ROSTER_REQUIRED')
        if generation is not None:
            self._verify_generation()
        self._identity = body(self.identity)
        try:
            for role, resource in self.enrollment['resources'].items():
                self.outputs[role] = self.native.w.WindowsOutput(resource['path'])
            control = self.outputs['control']
            self.coordinator = self.native.native.Registry.__new__(self.native.native.Registry)
            self.coordinator.output = control
            self.coordinator.root_id = self.enrollment['resources']['control']['native_id']
            self.coordinator._create_mutex()
            self.mutex = self.coordinator.mutex
            self._verify()
        except BaseException:
            self.close()
            raise

    def _verify(self):
        if (self.poisoned or not self.mutex
                or getattr(self, '_lane', 'QUALITY_DIPS') != (
                    'HYPERLIQUID' if self.enrollment.get('schema') ==
                    'PERP_AUTO_NATIVE_ENROLLMENT_V1' else 'QUALITY_DIPS')
                or self.authority is not self._authority
                or self.read_only is not self._read_only
                or getattr(self,'generation',None) is not getattr(self,'_generation',None)
                or body(self.enrollment) != self._enrollment or body(self.identity) != self._identity
                or body(self.inception_intent) != self._intent
                or {'schema': 'QD_OP_PROCESS_ID_V1', **observe_self()} != self.identity):
            raise ValueError('PERSONAL_WRITER_CLOSED_UNKNOWN_OR_CHANGED')
        if getattr(self,'generation',None) is not None:
            self._verify_generation()
        for role, output in self.outputs.items():
            resource = self.enrollment['resources'][role]
            output._verify()
            if (str(output.root) != resource['path']
                    or self.native.native.file_identity(output.root_handle) != resource['native_id']):
                raise ValueError('PERSONAL_WRITER_NATIVE_RESOURCE_CHANGED')
        if list(Path(self.outputs['control'].root).iterdir()):
            raise ValueError('PERSONAL_WRITER_UNRESOLVED_CONTROL_NAMESPACE')

    def close(self):
        with self.lock:
            if self.active:
                raise ValueError('PERSONAL_WRITER_CLOSE_BEFORE_DRAIN')
            if self.mutex:
                self.native.w.close_handle(self.mutex)
                self.mutex = None
            for output in self.outputs.values():
                output.close()
            self.outputs.clear()

    def drain(self, request, *, now):
        from app.services.personal_native_coordination import PersonalNativeCoordination

        request = strict(body(request))
        if (type(self.ledger) is not PersonalNativeCoordination or self.ledger is not self._ledger
                or set(request) != {'enrollment', 'grant'}):
            raise ValueError('PERSONAL_WRITER_NATIVE_DRAIN_REQUIRED')
        with self.lease(request, now) as lease:
            # Same native transaction lock as every admitted coordination write.
            # No repairs, schema creation, pending acknowledgement or replay.
            with self.ledger.connect(readonly=True) as db:
                db.execute('BEGIN')
                self.ledger._load(db)
                pending = db.execute('SELECT COUNT(*) FROM projections WHERE receipt IS NULL').fetchone()[0]
                pending += db.execute("SELECT COUNT(*) FROM personal_sessions WHERE state!='ACKNOWLEDGED' OR state IS NULL").fetchone()[0]
                pending += db.execute("SELECT COUNT(*) FROM personal_publications WHERE state!='ACKNOWLEDGED' OR state IS NULL").fetchone()[0]
                session = request['grant']['engine_grant']['session_id']
                row = db.execute('SELECT body,state FROM personal_sessions WHERE id=?', (session,)).fetchone()
                if row is None or row[1] != 'ACKNOWLEDGED':
                    raise ValueError('PERSONAL_WRITER_SESSION_NOT_ACKNOWLEDGED')
                reserved = strict(row[0])
                if (reserved.get('scope') != 'LOCAL_ENROLLED'
                        or body(reserved.get('enrollment')) != self._enrollment
                        or reserved.get('grant', {}).get('session_id') != session):
                    raise ValueError('PERSONAL_WRITER_SESSION_BINDING')
            if pending or not lease.check(lease.snapshot, self.authority.clock()):
                raise ValueError('PERSONAL_WRITER_PENDING_OR_UNKNOWN_DRAIN')
            return {'schema': 'QD_AUTO_DRAIN_V3', 'enrollment_digest': digest(request['enrollment']),
                    'session_id': session, 'pending': 0, 'unknown': False}

    def _context(self, request):
        e = self.enrollment
        if set(request) == {'schema', 'reader_enrollment'} and request['schema'] == 'PERSONAL_NATIVE_READ_LEASE_V1':
            read = request['reader_enrollment']
            expected_read_schema = ('PERP_AUTO_OP_READ_ENROLLMENT_V1'
                                    if getattr(self, '_lane', 'QUALITY_DIPS') == 'HYPERLIQUID'
                                    else 'QD_AUTO_OP_READ_ENROLLMENT_V1')
            if (read.get('schema') != expected_read_schema
                    or read.get('account_id') != e['account_id'] or read.get('epoch') != e['epoch']
                    or any(read.get(role + '_root') != e['resources'][role]['native_id']
                           for role in ('source', 'projection', 'report'))):
                raise ValueError('PERSONAL_WRITER_READ_SCOPE')
            return 'READ_ONLY', request
        if self.read_only:
            raise ValueError('PERSONAL_READ_ONLY_NO_WRITER_ADMISSION')
        if request.get('schema') == 'PERSONAL_GENESIS_WRITER_V1':
            if (set(request) != {'schema', 'intent_digest', 'process'} or self.inception_intent is None
                    or request['intent_digest'] != digest(self.inception_intent)
                    or request['process'] != self.identity):
                raise ValueError('PERSONAL_WRITER_INCEPTION_CONTEXT')
            return 'INITIALIZE_SIMULATED_ACCOUNTS', request
        # Perpetual native ownership here is ONLY for original FS1/FS3
        # simulated opening. All later trading requires the distinct audited
        # Hyperliquid financial operation issuer and durable Stop owner.
        if getattr(self, '_lane', 'QUALITY_DIPS') == 'HYPERLIQUID':
            raise ValueError('PERSONAL_HL_FIRST_INCEPTION_ONLY_NO_RUNTIME_WRITER')
        if set(request) == {'scope', 'enrollment', 'grant'}:
            if request['scope'] != 'LOCAL_ENROLLED' or body(request['enrollment']) != self._enrollment:
                raise ValueError('PERSONAL_WRITER_NATIVE_SCOPE')
            if getattr(self,'generation',None) is not None:
                roster=self.generation.current_roster()
                return 'AUTO_PAPER',{'schema':'QD_AUTO_NATIVE_OWNERSHIP_V5',
                    'request_digest':digest(request),'original_writers':e['writers'],
                    'writers':roster['roles']['QUALITY_DIPS'],'writer_generation':roster,
                    'resources':e['resources'],'unknown_writers':[]}
            return 'AUTO_PAPER', {'schema': 'QD_AUTO_NATIVE_OWNERSHIP_V4',
                'request_digest': digest(request), 'writers': e['writers'],
                'resources': e['resources'], 'unknown_writers': []}
        if set(request) == {'enrollment', 'grant'}:
            runtime = request['enrollment']
            read = runtime.get('reader_enrollment', {})
            expected = {'pid': self.identity['pid'], 'created': self.identity['creation_filetime'],
                        'image': self.identity['image']}
            if (runtime.get('schema') != 'QD_AUTO_LOCAL_RUNTIME_V3' or runtime.get('scope') != 'LOCAL_ENROLLED'
                    or runtime.get('process_identity') != expected
                    or runtime.get('writer_roster') != ['decision', 'source', 'projection', 'report', 'coordination']
                    or read.get('schema') != 'QD_AUTO_OP_READ_ENROLLMENT_V1'
                    or read.get('account_id') != e['account_id'] or read.get('epoch') != e['epoch']
                    or any(read.get(role + '_root') != e['resources'][role]['native_id']
                           for role in ('source', 'projection', 'report'))):
                raise ValueError('PERSONAL_WRITER_RUNTIME_SCOPE')
            return 'AUTO_PAPER', {'schema': 'QD_AUTO_WRITERS_V3', 'verified': True,
                'process_identity': expected, 'writer_roster': runtime['writer_roster'],
                'resources': read, 'unknown_writers': []}
        raise ValueError('PERSONAL_WRITER_REQUEST_UNSUPPORTED')

    def _verify_generation(self):
        from scripts.observation_runtime.personal_writer_generation import NativeWriterGeneration
        g=self.generation
        if (type(g) is not NativeWriterGeneration or self.read_only
                or self.inception_intent is not None or g.verify() is not True
                or g.enrollments.get(self._lane)!=self.enrollment
                or {'schema':'QD_OP_PROCESS_ID_V1',**g.identity}!=self.identity
                or g.clock is not self.authority.clock):
            raise ValueError('PERSONAL_WRITER_EXACT_SUCCESSOR_GENERATION_REQUIRED')
        return True

    @contextmanager
    def lease(self, request, now):
        request=strict(body(request))
        action,_snapshot=self._context(request)
        if action=='AUTO_PAPER':
            if getattr(self,'generation',None) is None:
                raise ValueError('PERSONAL_WRITER_UNFENCED_FINANCIAL_LEASE_REFUSED')
            self._verify_generation()
            # Lock ordering is generation -> original writer mutex -> image.
            with self.generation.scope():
                with self._lease(request,now) as lease:yield lease
        else:
            with self._lease(request,now) as lease:yield lease

    @contextmanager
    def _lease(self, request, now):
        request = strict(body(request))
        with self.lock:
            self._verify()
            action, snapshot = self._context(request)
            record = self.authority.activation(action)
            # Two successive trusted UTC samples can legitimately straddle
            # a one-second boundary while the original native activation is
            # verified. Reject rollback and anything older than ONE second;
            # do not weaken original owner, SID, lease or NTP requirements.
            checked_at = self.authority.clock()
            if (type(now) is not int or type(checked_at) is not int
                    or not now <= checked_at <= now + 1):
                raise ValueError('PERSONAL_WRITER_CLOCK')
            result = self.coordinator.wait(self.mutex, 500)
            if result not in (0, 128):
                raise ValueError('PERSONAL_WRITER_BUSY')
            self.active += 1
            try:
                if result == 128:
                    self.poisoned = True
                    if action == 'READ_ONLY':
                        raise ValueError('PERSONAL_READ_ABANDONED_WRITER_NO_MUTATION')
                    # Never clear/repair this record. If publication itself
                    # fails, the instance still refuses; recovery is not implied.
                    self.outputs['control'].write_bound('unknown-writer.json', body({
                        'schema': 'PERSONAL_ABANDONED_WRITER_V1', 'enrollment': digest(self.enrollment),
                        'process': self.identity, 'status': 'UNKNOWN'}).encode())
                    raise ValueError('PERSONAL_WRITER_ABANDONED_NO_REPLAY')
                self._verify()
                owner, thread, sealed = self, get_ident(), body(snapshot)

                class Lease:
                    def __init__(self):
                        self.snapshot = strict(sealed)

                    def check(self, candidate, stamp):
                        owner._verify()
                        verified_at = owner.authority.clock()
                        return (get_ident() == thread and owner.active > 0
                            and type(stamp) is int and now <= stamp <= now + 30
                            and type(verified_at) is int
                            and stamp <= verified_at <= stamp + 1
                            and body(candidate) == sealed and body(self.snapshot) == sealed
                            and owner.authority.activation(action) == record)

                lease = Lease()
                yield lease
                if not lease.check(snapshot, self.authority.clock()):
                    raise ValueError('PERSONAL_WRITER_LEASE_CHANGED')
            finally:
                self.active -= 1
                self.native.w.check(self.coordinator.release(self.mutex))
