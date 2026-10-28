"""Synthetic in-memory native I/O doubles, no filesystem, provider or enrollment."""
import copy
import hashlib
import sqlite3
import threading
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from app.services.personal_current_pins import PersonalCurrentPins
from app.services.personal_native_coordination import PersonalNativeCoordination
from app.services.personal_publication_custody import PersonalPublicationCustody
from app.services.quality_dips_personal_dependencies import PersonalSessionReservations
from test_personal_paper_inception_memory import system

import scripts.observation_runtime.personal_coordination_store as native_store


class Images:
    """Test-only acknowledged image port; never installed or operational evidence."""
    def __init__(self, image):
        self.image, self.history = image, [image]
        self.lock, self.fail = threading.RLock(), None
    @contextmanager
    def transaction(self, *, readonly):
        with self.lock:
            owner = self
            class Tx:
                def read(self):
                    return owner.image
                def publish(self, before, after):
                    assert not readonly
                    if owner.image != before:
                        raise ValueError('STALE_TEST_CAS')
                    owner.image = after
                    owner.history.append(after)
                    if owner.fail:
                        raise OSError('SYNTHETIC_COMMIT_ACK_UNCERTAIN')
            yield Tx()


def setup():
    m = system('QUALITY_DIPS').m
    images = Images(PersonalNativeCoordination.initial_image(m))
    ledger = PersonalNativeCoordination(manifest=m, images=images, path='synthetic-native-coordination')
    return m, images, ledger


def test_existing_personal_reservations_and_pins_persist_across_adapter_restart():
    m, images, ledger = setup()
    request = {'grant': {'session_id': 'SYNTHETIC_SINGLE_USE'}}
    a = SimpleNamespace(verify=lambda value: value == request)
    receipt = PersonalSessionReservations(ledger=ledger, authorization=a).reserve(request)
    reopened = PersonalNativeCoordination(manifest=m, images=images, path=ledger.path)
    assert PersonalSessionReservations(ledger=reopened, authorization=a).verify(request, receipt)
    with pytest.raises(ValueError, match='REPLAY'):
        PersonalSessionReservations(ledger=reopened, authorization=a).reserve(request)
    pin = {'entries': [], 'root': [1, 2, 3]}
    with ledger.connect() as db:
        PersonalCurrentPins.initialize(db, 'source', pin)
    pins = PersonalCurrentPins(ledger=reopened, name='source', clock=lambda: 1000)
    after = {**pin, 'entries': [{'synthetic': 'one'}]}
    pins.advance(pin, after)
    assert PersonalCurrentPins(ledger=ledger, name='source', clock=lambda: 1000).current() == after


def test_read_only_connection_has_zero_publications_and_refuses_writes():
    _, images, ledger = setup()
    before = list(images.history)
    with ledger.connect(readonly=True) as db:
        assert ledger._load(db)[0]['cash'] == '1000'
        with pytest.raises(sqlite3.OperationalError):
            db.execute('DELETE FROM inception')
    assert images.history == before


@pytest.mark.parametrize('sql', ["ATTACH DATABASE ':memory:' AS bad", "VACUUM INTO 'escape.sqlite'",
                                  "SELECT load_extension('missing')", 'PRAGMA temp_store=FILE',
                                  'PRAGMA writable_schema=ON', 'PRAGMA journal_mode=WAL'])
def test_sql_cannot_open_other_database_or_extension(sql):
    _, images, ledger = setup()
    before = list(images.history)
    with ledger.connect() as db, pytest.raises(sqlite3.DatabaseError):
        db.execute(sql)
    assert images.history == before


def test_sql_rollback_does_not_publish_an_image():
    _, images, ledger = setup()
    before = list(images.history)
    with pytest.raises(RuntimeError), ledger.connect() as db:
        db.execute("INSERT INTO personal_sessions VALUES('synthetic','{}','PENDING')")
        raise RuntimeError('SYNTHETIC_BEFORE_COMMIT')
    assert images.history == before


def test_commit_before_ack_is_not_blindly_repeated():
    m, images, ledger = setup()
    images.fail = True
    req = {'grant': {'session_id': 'SYNTHETIC_CRASH'}}
    a = SimpleNamespace(verify=lambda _: True)
    with pytest.raises(OSError):
        PersonalSessionReservations(ledger=ledger, authorization=a).reserve(req)
    images.fail = False
    reopened = PersonalNativeCoordination(manifest=m, images=images, path=ledger.path)
    with pytest.raises(ValueError, match='REPLAY'):
        PersonalSessionReservations(ledger=reopened, authorization=a).reserve(req)
    with reopened.connect(readonly=True) as db:
        assert db.execute('SELECT state FROM personal_sessions').fetchall() == [('PENDING',)]


def test_publication_pending_uses_the_same_durable_port_without_financial_effects():
    _, images, ledger = setup()
    custody = PersonalPublicationCustody(ledger)
    intent = {'operation_id': 'synthetic-inception', 'schema': 'PERSONAL_GENESIS_INTENT_V1'}
    with custody.reserve(intent, {'writer': 'synthetic'}, 1000) as tx:
        assert tx.check(tx.snapshot, 1000)
    assert custody.row(intent['operation_id'])[2] == 'PENDING'
    with pytest.raises(ValueError, match='NO_REPLAY'), custody.reserve(intent, {}, 1000):
        pass
    assert len(images.history) == 2


def native_double(monkeypatch):
    owner = native_store.NativePersonalCoordinationImages.__new__(native_store.NativePersonalCoordinationImages)
    files, trace = {}, []
    root, root_id, enrollment = 'D:\\SYNTHETIC-NOT-A-REAL-ROOT', [1, 2, 3], 'a' * 64
    class Output:
        root_handle = 123
        def _verify(self):
            trace.append('verify')
        def write_bound(self, name, data):
            if name in files:
                raise ValueError('SYNTHETIC_NO_REPLACE')
            binding = {'id': [1, 0, len(files) + 1], 'sha256': hashlib.sha256(data).hexdigest()}
            files[name] = (data, binding)
            trace.append(('write', name))
            if getattr(owner, 'fail_leaf', None) == name:
                raise OSError('SYNTHETIC_INTERRUPTED_PUBLICATION')
            return copy.deepcopy(binding)
        def close(self):
            pass
    output = Output()
    def read(out, name, binding=None):
        data, actual = files[name]
        if binding is not None and binding != actual:
            raise ValueError('SYNTHETIC_IDENTITY_BEFORE_READ')
        if hashlib.sha256(data).hexdigest() != actual['sha256']:
            raise ValueError('SYNTHETIC_DIGEST_BEFORE_DECODE')
        trace.append(('read', name))
        return data, copy.deepcopy(actual)
    owner.output, owner.root, owner.root_id, owner.enrollment = output, root, root_id, enrollment
    owner._binding = (output, root, tuple(root_id), enrollment)
    owner.known, owner.poisoned, owner.mutex = None, False, 456
    owner.coordinator = SimpleNamespace(wait=lambda *args: 0, release=lambda _: True)
    owner.native = SimpleNamespace(read_bound=read, native=SimpleNamespace(file_identity=lambda _: root_id),
                                   w=SimpleNamespace(check=lambda value: None, close_handle=lambda _: None))
    monkeypatch.setattr(native_store, 'Path', lambda _: SimpleNamespace(iterdir=lambda: [SimpleNamespace(name=n) for n in files]))
    return SimpleNamespace(owner=owner, files=files, trace=trace)


@contextmanager
def installation_authority(request):
    yield SimpleNamespace(check=lambda expected: expected == request)


def test_native_protocol_memory_double_preserves_every_image_and_ack_identity(monkeypatch):
    s = native_double(monkeypatch)
    auth = SimpleNamespace(lease=installation_authority)
    image = PersonalNativeCoordination.initial_image(system('QUALITY_DIPS').m)
    s.owner.initialize(image, authorization=auth)
    with s.owner.transaction(readonly=False) as tx:
        tx.publish(image, image + b'synthetic-next-image')
        assert tx.read() == image + b'synthetic-next-image'
    assert {'0001-intent.json', '0001-commit.json', '0001-ack.json', '0002-ack.json'} <= set(s.files)
    assert s.files['0001-page-0001.bin'][0] == image[:native_store.PAGE]
    writes = [t for t in s.trace if isinstance(t, tuple) and t[0] == 'write']
    with s.owner.transaction(readonly=True) as tx:
        tx.read()
    assert [t for t in s.trace if isinstance(t, tuple) and t[0] == 'write'] == writes


@pytest.mark.parametrize('leaf', ['0001-intent.json', '0001-page-0001.bin', '0001-commit.json', '0001-ack.json'])
def test_native_partial_or_ack_uncertainty_refuses_without_adoption(monkeypatch, leaf):
    s = native_double(monkeypatch)
    s.owner.fail_leaf = leaf
    with pytest.raises(OSError):
        s.owner.initialize(b'synthetic-image', authorization=SimpleNamespace(lease=installation_authority))
    assert s.owner.poisoned and 'unknown.json' in s.files
    s.owner.poisoned = False  # Simulated restart, not recovery/adoption.
    with pytest.raises(ValueError, match='NAMESPACE'):
        s.owner._load()


def test_native_snapshot_capacity_refuses_before_publication(monkeypatch):
    s = native_double(monkeypatch)
    with pytest.raises(ValueError, match='CAPACITY'):
        s.owner._publish(None, b'x' * (native_store.MAX_IMAGE + 1), initial=True)
    assert not s.files


def test_native_cumulative_capacity_and_reservation_refusal_before_effect(monkeypatch):
    s = native_double(monkeypatch)
    s.owner.initialize(b'synthetic-image', authorization=SimpleNamespace(lease=installation_authority))
    assert s.owner.remaining_commits() == 127
    with s.owner.transaction(readonly=False) as tx:
        tx.publish(b'synthetic-image', b'synthetic-next')
    assert s.owner.remaining_commits() == 126
    before = copy.deepcopy(s.files)
    monkeypatch.setattr(native_store, 'MAX_REVISIONS', 2)
    with pytest.raises(ValueError, match='REVISION_CAPACITY'), s.owner.transaction(readonly=False) as tx:
        tx.publish(b'synthetic-next', b'cannot-publish')
    assert s.files == before


def test_native_stop_reserve_enforced_before_intent_and_never_reset(monkeypatch):
    s = native_double(monkeypatch)
    monkeypatch.setattr(native_store, 'MAX_REVISIONS', 4)
    s.owner.initialize(b'initial', authorization=SimpleNamespace(lease=installation_authority))
    s.owner.reserve_stop_capacity(stop_commits=2, stop_bytes=128)
    s.owner.require_operation_capacity(commits=1, growth_bytes=10)
    with s.owner.transaction(readonly=False) as tx:
        tx.publish(b'initial', b'second')
    before = copy.deepcopy(s.files)
    with pytest.raises(ValueError, match='CAPACITY'):
        s.owner.require_operation_capacity(commits=1, growth_bytes=0)
    with pytest.raises(ValueError, match='RESERVE'), s.owner.transaction(readonly=False) as tx:
        tx.publish(b'second', b'forbidden')
    assert s.files == before and not s.owner.poisoned
    s.owner.begin_reserved_stop()
    with s.owner.transaction(readonly=False) as tx:
        tx.publish(b'second', b'stop')
    with pytest.raises(ValueError, match='RESERVATION'):
        s.owner.reserve_stop_capacity(stop_commits=1, stop_bytes=128)
    assert s.owner.remaining_commits() == 1


def test_native_stop_byte_reserve_and_competing_thread_refuse_without_writes(monkeypatch):
    s = native_double(monkeypatch)
    s.owner.initialize(b'initial', authorization=SimpleNamespace(lease=installation_authority))
    s.owner.reserve_stop_capacity(stop_commits=2, stop_bytes=128)
    before = copy.deepcopy(s.files)
    with pytest.raises(ValueError, match='RESERVE'), s.owner.transaction(readonly=False) as tx:
        tx.publish(b'initial', b'x' * (native_store.MAX_IMAGE - 127))
    errors = []
    def competing():
        try: s.owner.begin_reserved_stop()
        except ValueError as exc: errors.append(str(exc))
    t = threading.Thread(target=competing)
    t.start(); t.join(timeout=2)
    assert not t.is_alive() and errors == ['PERSONAL_COORDINATION_STOP_OWNER_REQUIRED']
    assert s.files == before


def test_native_custody_orphan_or_corrupt_ack_refuses(monkeypatch):
    s = native_double(monkeypatch)
    s.owner.initialize(b'synthetic-image', authorization=SimpleNamespace(lease=installation_authority))
    data, binding = s.files['0001-ack.json']
    s.files['0001-ack.json'] = (data + b'corrupt', binding)
    with pytest.raises(ValueError, match='DIGEST'):
        s.owner._load()


def test_existing_engine_entry_partial_full_reconciles_on_immutable_image_port(tmp_path):
    from app.services.paper_financial_replay import number
    from test_quality_dips_autonomous_paper import candidate, entry, monitor
    from test_quality_dips_autonomous_paper import setup as engine_setup
    n = engine_setup(tmp_path)
    images = Images(PersonalNativeCoordination.initial_image(n.m))
    ledger = PersonalNativeCoordination(manifest=n.m, images=images, path=tmp_path/'native-coordination')
    n.engine.ledger = ledger
    n.engine.start(n.grant)
    b = candidate(n)
    assert entry(n)['filled']
    assert monitor(n, b, 'partial', '110', {'fundamentals_score': 60})['filled']
    assert monitor(n, b, 'full', '120', {'classification': 'THESIS_BROKEN'})['filled']
    with ledger.connect(readonly=True) as db:
        state, head, ops = ledger._load(db)
        assert len(ops) == 3 and state['revision'] == 3
        assert number(state['cash']) == number('1015.9136')
        assert number(state['gross']) == 16 and number(state['costs']) == number('0.0864')
        assert all(number(p['remaining']) == 0 and number(p['remaining_entry_costs']) == 0
                   for p in state['positions'].values())
    n.engine.reconcile()
    reopened = PersonalNativeCoordination(manifest=n.m, images=images, path=ledger.path)
    with reopened.connect(readonly=True) as db:
        again, again_head, again_ops = reopened._load(db)
    assert again == state and again_head == head and again_ops == ops
    # All prior byte images remain retained; restarting does not erase capacity.
    assert len(images.history) > 4


@pytest.mark.parametrize('damage', ['missing-page', 'missing-ack', 'foreign-root', 'orphan-page', 'stale-head'])
def test_native_snapshot_chain_refuses_conflicting_or_incomplete_evidence(monkeypatch, damage):
    s = native_double(monkeypatch)
    s.owner.initialize(b'synthetic-image', authorization=SimpleNamespace(lease=installation_authority))
    if damage == 'missing-page':
        del s.files['0001-page-0001.bin']
    elif damage == 'missing-ack':
        del s.files['0001-ack.json']
    elif damage == 'foreign-root':
        s.owner.root_id = [3, 2, 1]
    elif damage == 'orphan-page':
        s.files['0001-page-0002.bin'] = s.files['0001-page-0001.bin']
    else:
        s.owner.known = {'revision': 2, 'head': 'foreign', 'ack': {}}
    with pytest.raises((ValueError, KeyError)):
        s.owner._load()


def test_installed_assembly_defaults_to_refusal_without_native_clock_and_activation():
    from scripts.observation_runtime.personal_paper_activation import (
        compose_installed_personal_qd,
    )
    with pytest.raises(ValueError, match='INSTALLED_NATIVE_DEPENDENCIES_REQUIRED'):
        compose_installed_personal_qd()


def test_installed_assembly_rejects_synthetic_activation_without_native_io():
    from test_personal_paper_runtime import installed

    from scripts.observation_runtime.personal_paper_activation import (
        compose_installed_personal_qd,
    )
    i = installed()
    with pytest.raises(ValueError, match='INSTALLED_NATIVE_DEPENDENCIES_REQUIRED'):
        compose_installed_personal_qd(policy=i.p, enrollment={}, runtime_dependencies={},
                                    native_dependencies={}, store=object(), native_reader=object(),
                                    installation=i.i, local_clock=object(), runtime_id='synthetic')
