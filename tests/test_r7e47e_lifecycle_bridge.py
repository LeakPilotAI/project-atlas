"""Native disposable registry and synthetic actions, never real services."""
import importlib.util
import os
import shutil
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Native Windows required')
spec = importlib.util.spec_from_file_location('isolated_bridge', ROOT/'scripts/volume_inspector/lifecycle_bridge.py')
m = importlib.util.module_from_spec(spec)
if os.name == 'nt':
    spec.loader.exec_module(m)


def ident(pid=1100, created=900):
    return {'pid': pid, 'created': created, 'exe': 'a'*64, 'command': 'b'*64}


@pytest.fixture
def bridge(tmp_path):
    reg = m.fence.Registry.provision(str(tmp_path/'registry'))
    world = m.FixtureWorld(ident(), ident(1200, 1000))
    b = m.IsolatedBridge(reg, world)
    try:
        yield b
    finally:
        reg.close()


def test_complete_synthetic_handoff(bridge):
    b = bridge
    ticket = b.manager_admission('startup-one')
    assert b.world.effects == []
    assert b.registry.snapshot()['startup']['phase'] == 'PENDING'
    worker = b.create_and_bind_worker(ticket)
    assert b.worker_admission(ticket, worker)['startup']['phase'] == 'STARTING'
    assert b.world.effects == ['synthetic-worker-created', 'synthetic-dependencies-admitted']
    with pytest.raises(m.fence.Refused):
        b.inspection_admission('inspection-one', approved=True)


@pytest.mark.parametrize('change', ['pid', 'created', 'exe', 'command', 'delay', 'nonce', 'operation', 'parent'])
def test_substituted_delayed_or_replayed_worker(bridge, change):
    b = bridge
    ticket = b.manager_admission('startup-one')
    worker = b.create_and_bind_worker(ticket)
    if change in {'pid', 'created'}:
        b.world.processes['worker'][change] += 1
    elif change in {'exe', 'command'}:
        b.world.processes['worker'][change] = 'c'*64
    elif change == 'delay':
        b.world.now += 30
    elif change == 'nonce':
        ticket['nonce'] = 'c'*64
    elif change == 'operation':
        ticket['operation'] = 'startup-other'
    else:
        # Parent replacement BEFORE creation/binding must also refuse.
        b.world.processes['parent']['pid'] += 1
        with pytest.raises(m.fence.Refused):
            b.create_and_bind_worker(ticket)
        return
    with pytest.raises(m.fence.Refused):
        b.worker_admission(ticket, worker)
    assert 'synthetic-dependencies-admitted' not in b.world.effects
    assert not b.registry.startup_allowed()


def test_worker_admission_single_use(bridge):
    b = bridge
    t = b.manager_admission('startup-one')
    worker = b.create_and_bind_worker(t)
    b.worker_admission(t, worker)
    with pytest.raises(m.fence.Refused):
        b.worker_admission(t, worker)
    assert b.world.effects.count('synthetic-dependencies-admitted') == 1


def test_parent_crash_reopen_retains_pending(bridge):
    b = bridge
    b.manager_admission('startup-one')
    root, instance = b.registry.output.root, b.registry.instance
    b.registry.close()
    b.registry = m.fence.Registry(root, instance)
    b.world.processes.pop('parent')
    with pytest.raises((KeyError, m.fence.Refused)):
        b.inspection_admission('inspection-one', approved=True)
    assert b.registry.snapshot()['startup']['phase'] == 'PENDING'
    assert b.world.effects == []


@pytest.mark.parametrize('damage', ['unavailable', 'corrupt', 'identity', 'permission'])
def test_unknown_storage_no_synthetic_effects(bridge, damage):
    b = bridge
    if damage == 'unavailable':
        b.registry.close()
    elif damage == 'corrupt':
        with b.registry.guard(), b.registry.database() as db:
            db.execute("UPDATE state SET value='{}'")
            db.commit()
    elif damage == 'identity':
        p = Path(b.registry.output.root)/'fence.sqlite3'
        p.rename(p.with_suffix('.retained'))
        p.write_bytes(b'not a database')
    else:
        sd = m.fence.w.descriptor('S-1-5-18')
        try:
            fn = m.fence.w.bind(m.fence.w.A, 'SetFileSecurityW', [m.fence.W.LPCWSTR, m.fence.W.DWORD, m.fence.C.c_void_p])
            m.fence.w.check(fn(str(Path(b.registry.output.root)/'fence.sqlite3'), 0x80000004, sd))
        finally:
            m.fence.w.local_free(sd)
    with pytest.raises((OSError, ValueError, sqlite3.Error)):
        b.manager_admission('startup-one')
    assert b.world.effects == []
    assert not b.registry.startup_allowed()


def test_simultaneous_startup_inspection(bridge):
    b = bridge
    barrier = threading.Barrier(2)
    def attempt(start):
        barrier.wait(5)
        try:
            if start:
                b.manager_admission('startup-one')
            else:
                b.inspection_admission('inspection-one', approved=True)
            return True
        except m.fence.Refused:
            return False
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(attempt, [True, False])) == [False, True]
    assert not b.registry.startup_allowed()
    assert b.world.effects == []


@pytest.mark.parametrize('case', ['missing', 'forged', 'revision', 'running', 'replaced', 'unreachable', 'stale', 'valid'])
def test_uncertain_recovery_authority(bridge, case):
    b = bridge
    b.inspection_admission('inspection-one', approved=True)
    b.bind_helper('inspection-one', 'c'*64)
    b.world.helper = {'id': 'c'*64, 'state': 'exited', 'pid': 0}
    authority = m.fence.FixtureRecoveryAuthority()
    proof = b.world.exit_proof('inspection-one')
    grant = authority.issue(b.registry.snapshot(), proof, approved=True)
    if case == 'missing': grant = None
    elif case == 'forged': grant['mac'] = '0'*64
    elif case == 'revision': grant['payload']['revision'] -= 1
    elif case == 'running': b.world.helper['state'] = 'running'
    elif case == 'replaced': b.world.helper['id'] = 'd'*64
    elif case == 'unreachable': b.world.helper = None
    elif case == 'stale': b.world.now += 6
    if case == 'valid':
        assert b.recover('inspection-one', authority, grant)['inspection'] is None
        assert b.registry.startup_allowed()
        with pytest.raises(m.fence.Refused):
            b.recover('inspection-one', authority, grant)
    else:
        with pytest.raises(m.fence.Refused):
            b.recover('inspection-one', authority, grant)
        with pytest.raises(m.fence.Refused):
            b.manager_admission('startup-one')
        assert b.registry.snapshot()['inspection']['phase'] == 'UNCERTAIN'
    assert b.world.effects == []


def test_external_writer_not_controlled(bridge):
    bridge.inspection_admission('inspection-one', approved=True)
    # External actions do not pass this bridge. Explicit model limitation.
    bridge.world.processes['active'] = ident(9999)
    with pytest.raises(m.fence.Refused):
        bridge.manager_admission('startup-one')
    assert bridge.world.processes['active']['pid'] == 9999


def test_real_transport_or_registry_subclass_refused(bridge):
    with pytest.raises(m.fence.Refused):
        m.IsolatedBridge(bridge.registry, object())


def test_native_main_substitution_open_precedes_rejection(bridge, tmp_path, monkeypatch):
    """A passing attack reproduction, NOT acceptance of VFS safety."""
    b = bridge
    alternate = tmp_path/'alternate.sqlite3'
    connect = sqlite3.connect
    with connect(alternate) as db:
        db.execute('CREATE TABLE synthetic_probe (value TEXT)')
        db.execute("INSERT INTO synthetic_probe VALUES ('fixture-only')")
    seen = []
    def substituted_connect(*args, **kwargs):
        target = Path(b.registry.output.root)/'fence.sqlite3'
        target.rename(target.with_suffix('.original-retained'))
        shutil.copyfile(alternate, target)
        db = connect(*args, **kwargs)
        seen.append(db.execute('SELECT value FROM synthetic_probe').fetchone()[0])
        return db
    monkeypatch.setattr(m.fence.sqlite3, 'connect', substituted_connect)
    with pytest.raises(m.fence.Refused, match='identity replaced'):
        b.registry.snapshot()
    assert seen == ['fixture-only']
    assert (Path(b.registry.output.root)/'recovery-required.json').exists()
    assert b.world.effects == []


def test_native_sidecar_identity_continuity_not_enforced(bridge):
    reg = bridge.registry
    root = Path(reg.output.root)
    # PERSIST may retain an existing journal; preserve it, never overwrite.
    existing = root/'fence.sqlite3-journal'
    if existing.exists():
        existing.rename(root/'initial-retained-journal')
    reg.output._write(reg.output.root_handle, 'fence.sqlite3-journal', b'')
    h = m.fence.w.relative_open(reg.output.root_handle, 'fence.sqlite3-journal', reg.output.sid, False)
    try: before = m.fence.file_identity(h)
    finally: m.fence.w.close_handle(h)
    (root/'fence.sqlite3-journal').rename(root/'retained-journal')
    reg.output._write(reg.output.root_handle, 'fence.sqlite3-journal', b'')
    h = m.fence.w.relative_open(reg.output.root_handle, 'fence.sqlite3-journal', reg.output.sid, False)
    try: after = m.fence.file_identity(h)
    finally: m.fence.w.close_handle(h)
    assert before != after
    assert reg.surface()['fence.sqlite3-journal']['restricted']


def test_native_main_hardlink_refused(bridge):
    reg = bridge.registry
    root = Path(reg.output.root)
    os.link(root/'fence.sqlite3', root/'retained-hardlink')
    with pytest.raises(m.fence.Refused, match='Linked SQLite'):
        reg.surface()
    assert not reg.startup_allowed()


def test_interrupted_spawn_retains_intent_without_locks(bridge, monkeypatch):
    b = bridge
    ticket = b.manager_admission('startup-one')
    def interrupted(world):
        assert getattr(b.registry.local, 'depth', 0) == 0
        world.effects.append('synthetic-create-uncertain')
        raise TimeoutError('Synthetic interruption')
    monkeypatch.setattr(m.FixtureWorld, 'create_worker', interrupted)
    with pytest.raises(TimeoutError):
        b.create_and_bind_worker(ticket)
    assert b.registry.snapshot()['startup']['phase'] == 'PENDING'
    with pytest.raises(m.fence.Refused):
        b.inspection_admission('inspection-one', approved=True)
    assert 'synthetic-dependencies-admitted' not in b.world.effects


def test_uncertain_inspection_restart_no_helper_never_released(bridge):
    b = bridge
    b.inspection_admission('inspection-one', approved=True)
    root, instance = b.registry.output.root, b.registry.instance
    b.registry.close()
    b.registry = m.fence.Registry(root, instance)
    assert b.registry.snapshot()['inspection']['helper'] is None
    with pytest.raises(m.fence.Refused):
        b.manager_admission('startup-one')
    with pytest.raises(m.fence.Refused):
        b.recover('inspection-one', m.fence.FixtureRecoveryAuthority(), {})
    assert b.world.effects == []


def test_worker_effect_occurs_outside_registry_lock(bridge, monkeypatch):
    b = bridge
    ticket = b.manager_admission('startup-one')
    worker = b.create_and_bind_worker(ticket)
    def admitted(world):
        assert getattr(b.registry.local, 'depth', 0) == 0
        assert b.registry.snapshot()['startup']['phase'] == 'STARTING'
        world.effects.append('synthetic-dependencies-admitted')
    monkeypatch.setattr(m.FixtureWorld, 'dependencies', admitted)
    b.worker_admission(ticket, worker)
    assert len(b.world.effects) == 2


def test_concurrent_worker_creation_durable_single_use(bridge):
    b = bridge
    ticket = b.manager_admission('startup-one')
    barrier = threading.Barrier(2)
    def create(_):
        barrier.wait(5)
        try:
            return b.create_and_bind_worker(ticket)
        except (m.fence.Refused, sqlite3.IntegrityError):
            return None
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(create, [0, 1]))
    assert sum(r is not None for r in results) == 1
    assert b.world.effects == ['synthetic-worker-created']
