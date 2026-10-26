"""Handle-bound immutable order-control journal, reusing FS2 native primitives.

No financial engine, issuer, operational provisioning or recovery/adoption path.
Unpinned tails and abandoned mutexes refuse. Custody.advance must be durable CAS;
local hashes or the supplied native handles are not independent rollback custody.
"""
import copy
import importlib.util
from itertools import islice
from pathlib import Path

from app.services.paper_financial_replay import (
    body,
    digest,
    strict,
    text,
    validate_manifest,
)
from app.services.perp_resting_order import transition

_spec = importlib.util.spec_from_file_location('resting_fs2', Path(__file__).with_name('financial_record_store.py'))
f = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(f)


class RestingOrderStore:
    PIN_TEST = 'PERP_RESTING_TEST_PIN_V1'
    PIN_OP = 'PERP_RESTING_OP_PIN_V1'
    SCOPE_SCHEMA = 'PERP_RESTING_SCOPE_V1'
    RECORD_SCHEMA = 'PERP_RESTING_RECORD_V1'
    ACK_SCHEMA = 'PERP_RESTING_ACK_V1'
    LEAF = 'order'
    fold = staticmethod(transition)
    guard = f.FinancialRecordStore.guard
    close = f.FinancialRecordStore.close
    _read = f.FinancialRecordStore._read
    _latch = f.FinancialRecordStore._latch

    @classmethod
    def provision_disposable(cls, root, scope, *, confinement):
        confinement, root = Path(confinement).absolute(), Path(root).absolute()
        repo = Path(__file__).resolve().parents[2]
        if (confinement.parent != repo / 'logs/diagnostics' or not confinement.name.startswith('perp-order-custody-')
                or confinement.drive.upper() != 'D:' or not root.is_relative_to(confinement)
                or scope.get('execution_domain') != 'DISPOSABLE_TEST'):
            raise ValueError('CONFINED_DISPOSABLE_ORDER_ROOT_REQUIRED')
        with f.w.WindowsOutput.create_root(str(root)) as output:
            binding = output.write_bound('scope.json', f.encoded(scope))
            return {'schema': cls.PIN_TEST, 'root': f.native.file_identity(output.root_handle), 'scope': binding, 'entries': []}

    def _validate_manifest(self, manifest):
        validate_manifest(manifest)
        if manifest['strategy'] != 'HYPERLIQUID_PAPER':
            raise ValueError('RESTING_PERPETUAL_ACCOUNT_REQUIRED')

    def _initial(self):
        return {'revision': 0, 'last_clock': self.manifest['opened_at'], 'orders': {}}

    def __init__(self, root, *, trust, authority, clock, manifest, execution_domain):
        if any(x is None for x in (trust, authority, clock)) or execution_domain not in ('DISPOSABLE_TEST', 'LOCAL_ENROLLED'):
            raise ValueError('RESTING_ACCEPTED_DEPENDENCIES_REQUIRED')
        self._validate_manifest(manifest)
        self.trust, self.authority, self.clock, self.manifest, self.execution_domain = trust, authority, clock, strict(body(manifest)), execution_domain
        self.poisoned, self.mutex = False, None
        self.output = f.w.WindowsOutput(str(root))
        try:
            pin = self.trust.current()
            f.require_identity(pin['root'])
            if f.native.file_identity(self.output.root_handle) != pin['root']:
                raise ValueError('RESTING_NATIVE_ROOT_SUBSTITUTED')
            self.coordinator = f.native.Registry.__new__(f.native.Registry)
            self.coordinator.output, self.coordinator.root_id = self.output, pin['root']
            self.coordinator._create_mutex()
            self.mutex = self.coordinator.mutex
            self.snapshot()
        except BaseException:
            self.close()
            raise

    def _load(self):
        pin = copy.deepcopy(self.trust.current())
        schema = self.PIN_TEST if self.execution_domain == 'DISPOSABLE_TEST' else self.PIN_OP
        if (type(pin) is not dict or set(pin) != {'schema', 'root', 'scope', 'entries'} or pin['schema'] != schema
                or type(pin['entries']) is not list or len(pin['entries']) > 128
                or f.native.file_identity(self.output.root_handle) != pin['root']):
            raise ValueError('RESTING_PIN_OR_CAPACITY_REFUSED')
        scope = self._read('scope.json', pin['scope'])
        if (set(scope) != {'schema', 'execution_domain', 'epoch', 'manifest_digest', 'writer_id'}
                or scope['schema'] != self.SCOPE_SCHEMA or scope['execution_domain'] != self.execution_domain
                or scope['epoch'] != self.manifest['epoch'] or scope['manifest_digest'] != digest(self.manifest)
                or self.authority.verify_scope(scope, pin, self.clock()) is not True):
            raise ValueError('RESTING_ENROLLMENT_AUTHORITY_REFUSED')
        text(scope['writer_id'])
        state = self._initial()
        head, expected, operations = digest(scope), {'scope.json'}, {}
        for revision, binding in enumerate(pin['entries'], 1):
            leaf = f'{revision:04d}-{self.LEAF}.json'
            record = self._read(leaf, binding)
            if set(record) != {'schema', 'revision', 'parent', 'event', 'state_digest'} or record['schema'] != self.RECORD_SCHEMA or record['revision'] != revision or record['parent'] != head:
                raise ValueError('RESTING_REVISION_OR_CHAIN_REFUSED')
            state = self.fold(scope, self.manifest, state, record['event'])
            if digest(state) != record['state_digest']:
                raise ValueError('RESTING_CONTROL_REPLAY_MISMATCH')
            head = digest(record)
            identity = digest(record['event'])
            if identity in operations:
                raise ValueError('RESTING_DUPLICATE_EVENT_REFUSED')
            operations[identity] = {'schema': self.ACK_SCHEMA, 'event_digest': identity, 'head': head,
                                    'revision': revision, 'state_digest': digest(state)}
            expected.add(leaf)
        if {p.name for p in islice(Path(self.output.root).iterdir(), 130)} != expected or body(self.trust.current()) != body(pin):
            raise ValueError('RESTING_UNPINNED_TAIL_OR_CUSTODY_CHANGED')
        return pin, scope, state, head, operations

    def snapshot(self):
        if self.poisoned or not self.mutex:
            raise ValueError('RESTING_CLOSED_OR_UNCERTAIN')
        _, _, state, head, _ = self._load()
        return strict(body({'state': state, 'head': head, 'execution_domain': self.execution_domain}))

    def verify_ack(self, receipt):
        operations = self._load()[4]
        return type(receipt) is dict and operations.get(receipt.get('event_digest')) == receipt

    def apply(self, event, reservation, *, fault=lambda phase: None):
        with self.guard():
            pin, scope, state, head, operations = self._load()
            if digest(event) in operations:
                return copy.deepcopy(operations[digest(event)])
            if len(pin['entries']) >= 128:
                raise ValueError('RESTING_CONTROL_CAPACITY_EXHAUSTED')
            self.trust.check_clock(event['at'])
            if event['at'] != self.clock() or self.authority.verify_event(scope, event, state, reservation) is not True:
                raise ValueError('RESTING_DURABLE_RESERVATION_OR_CLOCK_REQUIRED')
            after = self.fold(scope, self.manifest, state, strict(body(event)))
            record = {'schema': self.RECORD_SCHEMA, 'revision': after['revision'], 'parent': head,
                      'event': strict(body(event)), 'state_digest': digest(after)}
            fault('before_publication')
            try:
                leaf = f'{after["revision"]:04d}-{self.LEAF}.json'
                binding = self.output.write_bound(leaf, f.encoded(record))
                self._read(leaf, binding)
                fault('after_record_before_pin')
                updated = {**pin, 'entries': [*pin['entries'], binding]}
                self.trust.advance(pin, updated)
                fault('after_pin')
                if body(self.trust.current()) != body(updated):
                    raise ValueError('RESTING_CUSTODY_ACK_MISSING')
                return {'schema': self.ACK_SCHEMA, 'event_digest': digest(event), 'head': digest(record),
                        'revision': after['revision'], 'state_digest': digest(after)}
            except BaseException:
                self.poisoned = True
                self._latch()
                raise
