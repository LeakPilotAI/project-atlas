"""Handle-bound immutable personal coordination images, not financial authority.

Uses existing protected native publication/read and bounded mutex primitives.
No SQLite disk VFS, sidecars, fixture pins, root creation or default enrollment.
The personal same-user threat model does NOT provide independent anti-rollback.
An incomplete tail or abandoned writer refuses; there is no adoption/repair API.
"""
import hashlib
import re
from contextlib import contextmanager
from pathlib import Path
from threading import get_ident

from app.services.paper_financial_replay import (
    body,
    digest,
    event_stream_record,
    strict,
)
from app.services.personal_native_coordination import (
    MAX_IMAGE,
    PersonalNativeCoordination,
)
from app.services.quality_dips_autonomous_enrollment import validate_enrollment

from scripts.observation_runtime.personal_paper_inception import native_primitives

MAX_REVISIONS = 128
PAGE = 32768


class NativePersonalCoordinationImages:
    def __init__(self, *, root, native_root, enrollment_digest):
        if (not isinstance(root, str) or not root.startswith('D:\\')
                or type(native_root) is not list or len(native_root) != 3
                or any(type(v) is not int or v < 0 for v in native_root)
                or type(enrollment_digest) is not str or not re.fullmatch('[0-9a-f]{64}', enrollment_digest)):
            raise ValueError('PERSONAL_COORDINATION_ENROLLED_RESOURCE_REQUIRED')
        self.native = native_primitives()
        self.output = self.native.w.WindowsOutput(root)
        self.root = root
        self.root_id, self.enrollment = list(native_root), enrollment_digest
        self._binding = (self.output, root, tuple(native_root), enrollment_digest)
        self.known, self.poisoned, self.mutex = None, False, None
        self._stop_capacity = None
        try:
            if self.native.native.file_identity(self.output.root_handle) != self.root_id:
                raise ValueError('PERSONAL_COORDINATION_FOREIGN_ROOT')
            self.coordinator = self.native.native.Registry.__new__(self.native.native.Registry)
            self.coordinator.output, self.coordinator.root_id = self.output, self.root_id
            self.coordinator._create_mutex()
            self.mutex = self.coordinator.mutex
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.mutex:
            self.native.w.close_handle(self.mutex)
            self.mutex = None
        self.output.close()

    def _inventory(self):
        if self.poisoned or not self.mutex:
            raise ValueError('PERSONAL_COORDINATION_CLOSED_OR_UNKNOWN')
        if (self.output is not self._binding[0] or self.root != self._binding[1]
                or tuple(self.root_id) != self._binding[2] or self.enrollment != self._binding[3]):
            raise ValueError('PERSONAL_COORDINATION_RESOURCE_BINDING_CHANGED')
        self.output._verify()
        if self.native.native.file_identity(self.output.root_handle) != self.root_id:
            raise ValueError('PERSONAL_COORDINATION_ROOT_CHANGED')
        names = {p.name for p in Path(self.root).iterdir()}
        if len(names) > MAX_REVISIONS * (MAX_IMAGE // PAGE + 3):
            raise ValueError('PERSONAL_COORDINATION_ENTRY_CAPACITY')
        if any(not re.fullmatch(r'\d{4}-(?:intent|commit|ack)\.json|\d{4}-page-\d{4}\.bin', n) for n in names):
            raise ValueError('PERSONAL_COORDINATION_UNKNOWN_NAMESPACE')
        return names

    def _read(self, name, binding=None):
        return self.native.read_bound(self.output, name, binding)

    def _load(self, *, empty=False):
        names = self._inventory()
        if not names:
            if empty and self.known is None:
                return None, {'revision': 0, 'ack': None, 'head': self.enrollment}
            raise ValueError('PERSONAL_COORDINATION_NOT_INITIALIZED_OR_ROLLED_BACK')
        revisions = {int(n[:4]) for n in names}
        if not 1 <= max(revisions) <= MAX_REVISIONS or revisions != set(range(1, max(revisions) + 1)):
            raise ValueError('PERSONAL_COORDINATION_REVISION_GAP')
        used, previous, image, pin = set(), self.enrollment, None, None
        for revision in sorted(revisions):
            prefix = f'{revision:04d}'
            intent_name, commit_name, ack_name = (prefix + '-' + x + '.json' for x in ('intent', 'commit', 'ack'))
            if not {intent_name, commit_name, ack_name} <= names:
                raise ValueError('PERSONAL_COORDINATION_INCOMPLETE_UNKNOWN')
            intent_raw, intent_id = self._read(intent_name)
            intent = strict(intent_raw.decode())
            if (set(intent) != {'schema', 'root', 'enrollment', 'revision', 'previous', 'bytes', 'sha256'}
                    or intent['schema'] != 'PERSONAL_NATIVE_COORDINATION_INTENT_V1'
                    or intent['root'] != self.root_id or intent['enrollment'] != self.enrollment
                    or type(intent['revision']) is not int or intent['revision'] != revision
                    or intent['previous'] != previous or type(intent['bytes']) is not int
                    or not 0 < intent['bytes'] <= MAX_IMAGE):
                raise ValueError('PERSONAL_COORDINATION_INTENT_CONFLICT')
            commit_raw, commit_id = self._read(commit_name)
            commit = strict(commit_raw.decode())
            count = (intent['bytes'] + PAGE - 1) // PAGE
            if (set(commit) != {'schema', 'intent', 'pages'}
                    or commit['schema'] != 'PERSONAL_NATIVE_COORDINATION_COMMIT_V1'
                    or commit['intent'] != intent_id or type(commit['pages']) is not list
                    or len(commit['pages']) != count):
                raise ValueError('PERSONAL_COORDINATION_COMMIT_CONFLICT')
            blocks = []
            for index, binding in enumerate(commit['pages'], 1):
                leaf = f'{prefix}-page-{index:04d}.bin'
                block, _ = self._read(leaf, binding)
                if len(block) != min(PAGE, intent['bytes'] - (index - 1) * PAGE):
                    raise ValueError('PERSONAL_COORDINATION_PAGE_LENGTH')
                blocks.append(block)
                used.add(leaf)
            image = b''.join(blocks)
            if hashlib.sha256(image).hexdigest() != intent['sha256']:
                raise ValueError('PERSONAL_COORDINATION_IMAGE_DIGEST')
            ack_raw, ack_id = self._read(ack_name)
            ack = strict(ack_raw.decode())
            if ack != {'schema': 'PERSONAL_NATIVE_COORDINATION_ACK_V1', 'commit': commit_id,
                       'image_digest': intent['sha256']}:
                raise ValueError('PERSONAL_COORDINATION_ACK_UNKNOWN')
            previous = digest({'ack': ack_id, 'revision': revision, 'image': intent['sha256']})
            pin = {'revision': revision, 'ack': ack_id, 'head': previous}
            used.update((intent_name, commit_name, ack_name))
        if used != names or self._inventory() != names:
            raise ValueError('PERSONAL_COORDINATION_NAMESPACE_RACE_OR_ORPHAN')
        if self.known and (pin['revision'] < self.known['revision']
                           or pin['revision'] == self.known['revision'] and pin != self.known):
            raise ValueError('PERSONAL_COORDINATION_OBSERVED_ROLLBACK')
        self.known = pin
        return image, pin

    @contextmanager
    def _writer(self):
        self._inventory()
        result = self.coordinator.wait(self.mutex, 500)
        if result not in (0, 128):
            raise ValueError('PERSONAL_COORDINATION_WRITER_BUSY')
        try:
            if result == 128:
                # Writer-only latch; read operations never consume an abandoned
                # mutex or publish files. The non-schema filename blocks restart.
                self._poison()
                raise ValueError('PERSONAL_COORDINATION_ABANDONED_WRITER')
            yield
        finally:
            self.native.w.check(self.coordinator.release(self.mutex))

    def _publish(self, before, image, *, initial=False):
        if type(image) is not bytes or not 0 < len(image) <= MAX_IMAGE:
            raise ValueError('PERSONAL_COORDINATION_IMAGE_CAPACITY')
        current, pin = self._load(empty=initial)
        if current != before or initial != (pin['revision'] == 0):
            raise ValueError('PERSONAL_COORDINATION_STALE_CAS')
        if pin['revision'] >= MAX_REVISIONS:
            raise ValueError('PERSONAL_COORDINATION_REVISION_CAPACITY')
        reservation = getattr(self, '_stop_capacity', None)
        if reservation is not None:
            ceiling, byte_ceiling = reservation['limits'][reservation['phase']]
            if (get_ident() != reservation['thread'] or pin['revision'] >= ceiling
                    or len(image) > byte_ceiling):
                raise ValueError('PERSONAL_COORDINATION_STOP_RESERVE_PROTECTED')
        revision = pin['revision'] + 1
        prefix = f'{revision:04d}'
        checksum = hashlib.sha256(image).hexdigest()
        intent = {'schema': 'PERSONAL_NATIVE_COORDINATION_INTENT_V1', 'root': self.root_id,
                  'enrollment': self.enrollment, 'revision': revision, 'previous': pin['head'],
                  'bytes': len(image), 'sha256': checksum}
        try:
            intent_id = self.output.write_bound(prefix + '-intent.json', body(intent).encode())
            pages = [self.output.write_bound(f'{prefix}-page-{n // PAGE + 1:04d}.bin', image[n:n+PAGE])
                     for n in range(0, len(image), PAGE)]
            commit_id = self.output.write_bound(prefix + '-commit.json', body({
                'schema': 'PERSONAL_NATIVE_COORDINATION_COMMIT_V1', 'intent': intent_id, 'pages': pages}).encode())
            self.output.write_bound(prefix + '-ack.json', body({
                'schema': 'PERSONAL_NATIVE_COORDINATION_ACK_V1', 'commit': commit_id, 'image_digest': checksum}).encode())
            after, _ = self._load()
            if after != image:
                raise ValueError('PERSONAL_COORDINATION_ACK_READBACK')
        except BaseException:
            self._poison()
            raise

    def _poison(self):
        self.poisoned = True
        try:
            self.output.write_bound('unknown.json', b'PERSONAL_COORDINATION_OUTCOME_UNCERTAIN')
        except (OSError, ValueError):
            # Incomplete files already refuse; retain the original failure if
            # storage itself prevents publishing the additional refusal latch.
            pass

    def initialize(self, image, *, authorization):
        # Installer calls this explicitly. No directories or approvals are made.
        request = {'schema': 'PERSONAL_COORDINATION_INSTALL_V1', 'root': self.root_id,
                   'enrollment': self.enrollment, 'image_digest': hashlib.sha256(image).hexdigest()}
        with authorization.lease(request) as lease, self._writer():
            if lease.check(request) is not True:
                raise ValueError('PERSONAL_COORDINATION_INSTALL_REFUSED')
            self._publish(None, image, initial=True)
            if lease.check(request) is not True:
                self._poison()
                raise ValueError('PERSONAL_COORDINATION_INSTALL_UNCERTAIN')

    @contextmanager
    def transaction(self, *, readonly):
        if type(readonly) is not bool:
            raise ValueError('PERSONAL_COORDINATION_ACCESS_MODE_REQUIRED')
        @contextmanager
        def scope():
            if readonly:
                yield
            else:
                with self._writer():
                    yield
        with scope():
            _, pin = self._load()
            owner = self
            class Transaction:
                def read(self):
                    return owner._load()[0]
                def publish(self, before, after):
                    if readonly:
                        raise ValueError('PERSONAL_COORDINATION_READ_ONLY')
                    owner._publish(before, after)
            yield Transaction()
            if readonly and self._load()[1] != pin:
                raise ValueError('PERSONAL_COORDINATION_READ_CUT_CHANGED')

    def remaining_commits(self):
        # Capacity is cumulative across restarts; this never resets/adopts a cut.
        return MAX_REVISIONS - self._load()[1]['revision']

    def reserve_stop_capacity(self, *, stop_commits, stop_bytes):
        """One process-local admission ceiling over cumulative durable capacity.

        No capacity is replenished on restart. Session replay remains prohibited
        by durable reservations. This reserves storage, not financial authority.
        Caller must separately verify the operation's worst-case write budget.
        """
        if (getattr(self, '_stop_capacity', None) is not None
                or type(stop_commits) is not int or not 1 <= stop_commits < MAX_REVISIONS
                or type(stop_bytes) is not int or not 1 <= stop_bytes < MAX_IMAGE):
            raise ValueError('PERSONAL_COORDINATION_STOP_RESERVATION_REFUSED')
        with self._writer():
            image, pin = self._load()
            if pin['revision'] >= MAX_REVISIONS-stop_commits or len(image) >= MAX_IMAGE-stop_bytes:
                raise ValueError('PERSONAL_COORDINATION_NO_STOP_HEADROOM')
            self._stop_capacity = {'thread': get_ident(), 'phase': 'RUN', 'limits': {
                'RUN': (MAX_REVISIONS-stop_commits, MAX_IMAGE-stop_bytes),
                'STOP': (MAX_REVISIONS, MAX_IMAGE)}}

    def begin_reserved_stop(self):
        with self._writer():
            reservation = getattr(self, '_stop_capacity', None)
            if reservation is None or get_ident() != reservation['thread']:
                raise ValueError('PERSONAL_COORDINATION_STOP_OWNER_REQUIRED')
            self._load()
            reservation['phase'] = 'STOP'

    def require_operation_capacity(self, *, commits, growth_bytes):
        reservation = getattr(self, '_stop_capacity', None)
        if (reservation is None or get_ident() != reservation['thread']
                or type(commits) is not int or commits < 1
                or type(growth_bytes) is not int or growth_bytes < 0):
            raise ValueError('PERSONAL_COORDINATION_OPERATION_BUDGET_REQUIRED')
        image, pin = self._load()
        limit, size = reservation['limits'][reservation['phase']]
        if pin['revision'] + commits > limit or len(image) + growth_bytes > size:
            raise ValueError('PERSONAL_COORDINATION_OPERATION_EXCEEDS_RESERVED_CAPACITY')


def open_existing_personal_coordination(*, enrollment=None, manifest=None, native_reader=None):
    """Bind the actual native mirror to an independently read FS2 source cut.

    Existing-only: never initializes/resets a missing image or imports a fixture
    database. Ownership of the returned native handles belongs to the caller.
    All original runtime/enrollment/source authority checks remain mandatory.
    """
    if any(v is None for v in (enrollment, manifest, native_reader)):
        raise ValueError('PERSONAL_COORDINATION_NATIVE_READBACK_REQUIRED')
    e = validate_enrollment(enrollment)
    if (body(native_reader.enrollment) != body(e) or digest(manifest) != e['inception_digest']
            or native_reader.verify_resources() is not True):
        raise ValueError('PERSONAL_COORDINATION_NATIVE_ENROLLMENT_CONFLICT')
    before = native_reader.read_committed()
    resource = e['resources']['coordination']
    images = NativePersonalCoordinationImages(root=resource['path'], native_root=resource['native_id'],
                                              enrollment_digest=digest(e))
    try:
        ledger = PersonalNativeCoordination(manifest=manifest, images=images,
                                             path=Path(resource['path'])/'coordination.image')
        with ledger.connect(readonly=True) as db:
            state, head, _ = ledger._load(db)
            rows = [event_stream_record(*row) for row in db.execute('SELECT * FROM events ORDER BY revision')]
            if db.execute('SELECT 1 FROM projections WHERE receipt IS NULL').fetchone():
                raise ValueError('PERSONAL_COORDINATION_UNACKNOWLEDGED_NATIVE_EFFECT')
        if (before.get('schema') != 'QD_AUTO_OP_READ_V1' or before.get('manifest') != manifest
                or before.get('state') != state or before.get('head') != head or before.get('rows') != rows
                or native_reader.read_committed() != before):
            raise ValueError('PERSONAL_COORDINATION_NATIVE_FINANCIAL_PARITY_REFUSED')
        return ledger
    except BaseException:
        images.close()
        raise
