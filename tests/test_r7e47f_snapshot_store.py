"""Native fixture-only identity-before-decision and recovery contract tests."""
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Native Windows required')
spec = importlib.util.spec_from_file_location('snapshot_fixture', ROOT/'scripts/volume_inspector/snapshot_store.py')
m = importlib.util.module_from_spec(spec)
if os.name == 'nt':
    spec.loader.exec_module(m)


def ident(pid=1000):
    return {'pid': pid, 'created': 1000, 'exe': 'a'*64, 'command': 'b'*64}


@pytest.fixture
def store(tmp_path):
    value = m.SnapshotStore.provision_synthetic(str(tmp_path/'snapshots'), str(tmp_path/'witness'))
    try:
        yield value
    finally:
        value.close()


def test_snapshot_roundtrip_and_revision_bound_restart(store):
    state = store.reserve_start('startup-one', ident())
    assert state['revision'] == 1 and state['startup']['phase'] == 'PENDING'
    assert store.admit_worker('startup-one', ident(), ident(2000))['startup']['phase'] == 'STARTING'
    pin = copy.deepcopy(store.pin)
    root, witness = store.output.root, store.witness.root
    store.close()
    reopened = m.SnapshotStore(root, witness, pin)
    try:
        assert reopened.snapshot()['revision'] == 2
        with pytest.raises(m.Refused):
            reopened.inspect('inspection-one', 'c'*64, approved=True)
        with pytest.raises(m.Refused):
            reopened.admit_worker('startup-one', ident(), ident(2000))
    finally:
        reopened.close()


@pytest.mark.parametrize('attack', ['same-bytes-replacement', 'corrupt', 'incomplete', 'hardlink'])
def test_unsafe_snapshot_rejected_before_decode_or_admission(store, monkeypatch, attack):
    path = Path(store.output.root)/'snapshot-00000000.json'
    if attack == 'same-bytes-replacement':
        path.rename(path.with_name('retained-original'))
        shutil.copyfile(path.with_name('retained-original'), path)
    elif attack == 'corrupt':
        path.write_bytes(b'{"startup":null}')
    elif attack == 'incomplete':
        path.write_bytes(b'{')
    else:
        os.link(path, path.with_name('retained-hardlink'))
    decoded = []
    monkeypatch.setattr(m.json, 'loads', lambda raw: decoded.append(raw))
    before = copy.deepcopy(store.pin)
    with pytest.raises((m.Refused, OSError)):
        store.reserve_start('startup-one', ident())
    assert decoded == []
    assert store.pin == before
    assert not (Path(store.witness.root)/'intent-00000001.json').exists()


@pytest.mark.parametrize('leaf', ['fence.sqlite3', 'fence.sqlite3-journal', 'fence.sqlite3-wal', 'fence.sqlite3-shm',
                                'snapshot-00000000.json-journal', 'snapshot-00000000.json-wal', 'snapshot-00000000.json-shm'])
def test_all_legacy_and_snapshot_sidecars_refused(store, leaf, monkeypatch):
    store.output._write(store.output.root_handle, leaf, b'SYNTHETIC_NOT_READ')
    decoded = []
    monkeypatch.setattr(m.json, 'loads', lambda raw: decoded.append(raw))
    with pytest.raises(m.Refused):
        store.reserve_start('startup-one', ident())
    assert decoded == []


def test_native_junction_refused_before_decode(store, tmp_path, monkeypatch):
    target = Path(store.output.root)/'snapshot-00000000.json'
    target.rename(target.with_name('retained-original'))
    outside = tmp_path/'synthetic-outside'
    outside.mkdir()
    result = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(target), str(outside)], capture_output=True, timeout=10, check=False)
    assert result.returncode == 0
    decoded = []
    monkeypatch.setattr(m.json, 'loads', lambda raw: decoded.append(raw))
    with pytest.raises((m.Refused, OSError)):
        store.reserve_start('startup-one', ident())
    assert decoded == []


def test_true_symlink_refused_when_native_creation_available(store, tmp_path):
    path = Path(store.output.root)/'snapshot-00000000.json'
    retained = path.with_name('retained-original')
    path.rename(retained)
    try:
        os.symlink(retained, path)
    except OSError as exc:
        if exc.winerror == 1314:
            pytest.skip('Native symlink creation privilege unavailable; no waiver')
        raise
    with pytest.raises((m.Refused, OSError)):
        store.reserve_start('startup-one', ident())


def test_native_read_handle_denies_concurrent_write_and_rename(store, monkeypatch):
    original = m.w.read_file
    attacks = []
    def read(handle, *args):
        path = Path(store.output.root)/'snapshot-00000000.json'
        # This also runs for the independent witness; both opens remain bounded.
        if m.native.file_identity(handle) == store.pin['snapshot']['id']:
            foreign = m.w.create_file(str(path), m.w.WRITE, 7, None, 3, 0, None)
            error = m.C.get_last_error()
            if foreign != m.w.INVALID:
                m.w.close_handle(foreign)
            assert foreign == m.w.INVALID
            attacks.append(error)
            try:
                path.rename(path.with_name('attack-retained'))
            except OSError as exc:
                attacks.append(exc.winerror)
            else:
                pytest.fail('Concurrent replacement was not denied')
        return original(handle, *args)
    monkeypatch.setattr(m.w, 'read_file', read)
    assert store.snapshot()['revision'] == 0
    assert attacks == [32, 32]


@pytest.mark.parametrize('surface', ['snapshot', 'commit'])
def test_identity_mismatch_never_reads_substitute_handle(store, monkeypatch, surface):
    output = store.output if surface == 'snapshot' else store.witness
    name = 'snapshot-00000000.json' if surface == 'snapshot' else 'commit-00000000.json'
    path = Path(output.root)/name
    retained = path.with_name('identity-original-retained')
    path.rename(retained)
    # Give replacement the correct protected DACL so this exercises ID refusal,
    # rather than stopping earlier at the also-valid inherited-ACL rejection.
    output._write(output.root_handle, name, retained.read_bytes())
    handle = m.w.relative_open(output.root_handle, name, output.sid, False)
    try:
        substitute_id = m.native.file_identity(handle)
    finally:
        m.w.close_handle(handle)
    original = m.w.read_file
    reads = []
    def observe(handle, *args):
        reads.append(m.native.file_identity(handle))
        return original(handle, *args)
    monkeypatch.setattr(m.w, 'read_file', observe)
    with pytest.raises(m.Refused):
        store.reserve_start('startup-one', ident())
    assert substitute_id not in reads
    assert not (Path(store.witness.root)/'intent-00000001.json').exists()


def test_stale_pin_cannot_replay_after_durable_newer_intent(store):
    pin = copy.deepcopy(store.pin)
    store.reserve_start('startup-one', ident())
    with pytest.raises(m.Refused, match='Newer publication'):
        m.SnapshotStore(store.output.root, store.witness.root, pin)


@pytest.mark.parametrize('phase', ['snapshot', 'commit'])
def test_interrupted_publication_blocks_old_state(store, monkeypatch, phase):
    obj = store.output if phase == 'snapshot' else store.witness
    original = obj._write
    def fail(directory, name, raw):
        if name == ('snapshot-00000001.json' if phase == 'snapshot' else 'commit-00000001.json'):
            raise OSError('Synthetic publication interruption')
        return original(directory, name, raw)
    monkeypatch.setattr(obj, '_write', fail)
    with pytest.raises(OSError):
        store.reserve_start('startup-one', ident())
    assert (Path(store.witness.root)/'intent-00000001.json').exists()
    with pytest.raises(m.Refused):
        store.snapshot()
    with pytest.raises(m.Refused):
        store.inspect('inspection-one', 'c'*64, approved=True)


def test_simultaneous_startup_inspection(store):
    barrier = threading.Barrier(2)
    def attempt(start):
        barrier.wait(5)
        try:
            if start:
                store.reserve_start('startup-one', ident())
            else:
                store.inspect('inspection-one', 'c'*64, approved=True)
            return True
        except m.Refused:
            return False
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(attempt, [True, False])) == [False, True]


@pytest.mark.parametrize('attack', ['forged-proof', 'forged-grant', 'no-grant', 'revision', 'stale', 'future', 'wrong-helper', 'running', 'pid-bool', 'no-authority', 'valid'])
def test_authenticated_recovery_requires_both_roles(store, attack):
    state = store.inspect('inspection-one', 'c'*64, approved=True)
    authority = m.SyntheticAuthority()
    proof = authority.attest_exit('c'*64, 'inspection-one', 1000)
    if attack == 'wrong-helper':
        proof = authority.attest_exit('d'*64, 'inspection-one', 1000)
    if attack == 'running': proof['facts']['state'] = 'running'
    if attack == 'pid-bool': proof['facts']['pid'] = False
    grant = authority.approve(state, proof, approved=True)
    if attack == 'forged-proof': proof['signature'] = '0'*64
    if attack == 'forged-grant': grant['signature'] = '0'*64
    if attack == 'no-grant': grant = None
    if attack == 'revision': grant['payload']['revision'] -= 1
    now = 1006 if attack == 'stale' else 999 if attack == 'future' else 1001
    if attack == 'no-authority': authority = object()
    if attack == 'valid':
        assert store.recover(authority, proof, grant, now)['event'] == 'EXIT_PROVEN_FAILED'
        with pytest.raises(m.Refused): store.recover(authority, proof, grant, now)
        with pytest.raises(m.Refused): store.inspect('inspection-one', 'c'*64, approved=True)
    else:
        with pytest.raises(m.Refused): store.recover(authority, proof, grant, now)
        assert store.snapshot()['inspection']['phase'] == 'UNCERTAIN'
        with pytest.raises(m.Refused): store.reserve_start('startup-one', ident())


def test_explicit_operator_and_production_refusal(store):
    authority = m.SyntheticAuthority()
    with pytest.raises(m.Refused): authority.approve(store.snapshot(), {})
    with pytest.raises(m.Refused): store.production_admission()


@pytest.mark.parametrize('damage', ['absent', 'bool-revision', 'bad-root', 'bad-digest'])
def test_malformed_or_substituted_authority_pin_refused(store, damage):
    pin = copy.deepcopy(store.pin)
    if damage == 'absent': pin = None
    elif damage == 'bool-revision': pin['revision'] = False
    elif damage == 'bad-root': pin['root_id'][2] += 1
    else: pin['snapshot']['sha256'] = 'x'*64
    with pytest.raises(m.Refused):
        m.SnapshotStore(store.output.root, store.witness.root, pin)


def test_corruption_failure_remains_latched_after_same_identity_repair(store):
    target = Path(store.output.root)/'snapshot-00000000.json'
    original = target.read_bytes()
    pin = copy.deepcopy(store.pin)
    target.write_bytes(b'CORRUPT_FIXTURE')
    with pytest.raises(m.Refused): store.snapshot()
    target.write_bytes(original)
    assert (Path(store.witness.root)/'recovery-required.json').exists()
    with pytest.raises(m.Refused):
        m.SnapshotStore(store.output.root, store.witness.root, pin)


def test_local_witness_and_pin_rollback_is_not_independent_authority(store):
    """Expected boundary reproduction: privileged local rollback is NOT solved."""
    old = copy.deepcopy(store.pin)
    store.inspect('inspection-one', 'c'*64, approved=True)
    intent = Path(store.witness.root)/'intent-00000001.json'
    intent.rename(intent.with_name('retained-hidden-intent'))
    # A compromised caller replacing its independently trusted pin can present
    # old genuine files. Local immutable files alone cannot identify the future.
    rolled = m.SnapshotStore(store.output.root, store.witness.root, old)
    try:
        assert rolled.snapshot()['revision'] == 0
        with pytest.raises(m.Refused): rolled.production_admission()
    finally:
        rolled.close()


def test_committed_snapshot_replacement_during_publication_refused(store, monkeypatch):
    original = store.output._write
    def substituted(directory, name, raw):
        original(directory, name, raw)
        if name == 'snapshot-00000001.json':
            path = Path(store.output.root)/name
            path.write_bytes(b'{"unauthorized":true}')
    monkeypatch.setattr(store.output, '_write', substituted)
    with pytest.raises(m.Refused, match='Publication substitution'):
        store.reserve_start('startup-one', ident())
    assert (Path(store.witness.root)/'intent-00000001.json').exists()
    with pytest.raises(m.Refused): store.snapshot()


def test_native_restricted_token_denies_snapshot_and_witness(store):
    c, W, w = m.C, m.native.W, m.w
    normal, restricted, everyone = W.HANDLE(), W.HANDLE(), c.c_void_p()
    convert = w.bind(w.A, 'ConvertStringSidToSidW', [W.LPCWSTR, c.POINTER(c.c_void_p)])
    restrict = w.bind(w.A, 'CreateRestrictedToken', [W.HANDLE, W.DWORD, W.DWORD, c.c_void_p, W.DWORD, c.c_void_p, W.DWORD, c.POINTER(w.SidAttr), c.POINTER(W.HANDLE)])
    impersonate = w.bind(w.A, 'ImpersonateLoggedOnUser', [W.HANDLE])
    revert = w.bind(w.A, 'RevertToSelf', [])
    try:
        w.check(w.open_token(w.process(), 0xE, c.byref(normal)))
        w.check(convert('S-1-1-0', c.byref(everyone)))
        entry = w.SidAttr(everyone, 0)
        w.check(restrict(normal, 1, 0, None, 0, None, 1, c.byref(entry), c.byref(restricted)))
        w.check(impersonate(restricted))
        try:
            for path in (Path(store.output.root)/'snapshot-00000000.json', Path(store.witness.root)/'commit-00000000.json'):
                for access in (w.READ, w.WRITE):
                    handle = w.create_file(str(path), access, 7, None, 3, 0, None)
                    error = c.get_last_error()
                    if handle != w.INVALID: w.close_handle(handle)
                    assert handle == w.INVALID and error == 5
        finally:
            w.check(revert())
    finally:
        if normal: w.close_handle(normal)
        if restricted: w.close_handle(restricted)
        if everyone: w.local_free(everyone)


CHILD = '''import importlib.util,json,sys,os
s=importlib.util.spec_from_file_location('s',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
pin=json.loads(sys.argv[4]);r=m.SnapshotStore(sys.argv[2],sys.argv[3],pin)
parent={'pid':1000,'created':1000,'exe':'a'*64,'command':'b'*64}
r.reserve_start('crashed-parent',parent)
if sys.argv[6]=='worker':r.admit_worker('crashed-parent',parent,{**parent,'pid':2000})
open(sys.argv[5],'w').write(json.dumps(r.pin));os._exit(23)
'''


@pytest.mark.parametrize('phase', ['parent', 'worker'])
def test_actual_fixture_process_exit_preserves_startup_fence(store, tmp_path, phase):
    witness_pin = tmp_path/'independent-fixture-pin.json'
    result = subprocess.run([sys.executable, '-I', '-B', '-c', CHILD, str(ROOT/'scripts/volume_inspector/snapshot_store.py'),
                             store.output.root, store.witness.root, json.dumps(store.pin), str(witness_pin), phase],
                            capture_output=True, timeout=15, check=False)
    assert result.returncode == 23, result.stderr
    reopened = m.SnapshotStore(store.output.root, store.witness.root, json.loads(witness_pin.read_text()))
    try:
        assert reopened.snapshot()['startup']['phase'] == ('PENDING' if phase == 'parent' else 'STARTING')
        with pytest.raises(m.Refused): reopened.inspect('inspection-one', 'c'*64, approved=True)
    finally:
        reopened.close()


def test_actual_process_crash_after_reservation_leaves_uncertainty(store):
    child = '''import importlib.util,json,sys,os
s=importlib.util.spec_from_file_location('s',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
r=m.SnapshotStore(sys.argv[2],sys.argv[3],json.loads(sys.argv[4]))
original=r.output._write
def crash(directory,name,raw):os._exit(24)
r.output._write=crash
r.reserve_start('crashed-publication',{'pid':1000,'created':1000,'exe':'a'*64,'command':'b'*64})
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', child, str(ROOT/'scripts/volume_inspector/snapshot_store.py'),
                             store.output.root, store.witness.root, json.dumps(store.pin)], capture_output=True, timeout=15, check=False)
    assert result.returncode == 24, result.stderr
    assert (Path(store.witness.root)/'intent-00000001.json').exists()
    with pytest.raises(m.Refused): store.snapshot()
    assert (Path(store.witness.root)/'recovery-required.json').exists()
