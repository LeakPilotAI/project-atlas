"""Synthetic authority/local NTFS handoff tests; no production authentication."""
import copy
import importlib.util
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Native Windows required')
spec = importlib.util.spec_from_file_location('manual_fixture', ROOT/'scripts/volume_inspector/manual_handoff.py')
m = importlib.util.module_from_spec(spec)
if os.name == 'nt': spec.loader.exec_module(m)


def ident():
    return {'pid': 1000, 'created': 1000, 'exe': 'a'*64, 'command': 'b'*64}


@pytest.fixture
def handoff(tmp_path):
    store = m.s.SnapshotStore.provision_synthetic(str(tmp_path/'snapshots'), str(tmp_path/'witness'))
    authority = m.ManualFixtureAuthority()
    obj = m.Handoff.provision_synthetic(store, str(tmp_path/'handoff'), authority)
    try: yield obj
    finally: obj.close()


def reopen(obj, authority=None):
    return m.Handoff.reopen_synthetic(obj.store.output.root, obj.store.witness.root, obj.output.root,
                                     obj.root_id, obj.authority if authority is None else authority)


def test_durable_progression_and_restart(handoff):
    h = handoff
    state = h.inspect_synthetic('inspection-one', 'c'*64, approved=True)
    proof = h.authority.recovery.attest_exit('c'*64, 'inspection-one', 1000)
    grant = h.authority.recovery.approve(state, proof, approved=True)
    assert h.recover_synthetic(proof, grant, 1001)['revision'] == 2
    r = reopen(h)
    try:
        assert r.store.snapshot()['revision'] == 2
        assert r._current()[0] == 2
        assert r.start_synthetic('startup-one', ident())['startup']['phase'] == 'PENDING'
    finally: r.close()


@pytest.mark.parametrize('case', ['none', 'wrong-type', 'unavailable'])
def test_missing_authority_refuses_reopen(handoff, case):
    authority = None if case == 'none' else object() if case == 'wrong-type' else m.ManualFixtureAuthority()
    if case == 'unavailable': authority.available = False
    with pytest.raises(m.Refused):
        m.Handoff.reopen_synthetic(handoff.store.output.root, handoff.store.witness.root, handoff.output.root,
                                  handoff.root_id, authority)


def test_authority_unavailable_no_startup_intent(handoff):
    handoff.authority.available = False
    with pytest.raises(m.Refused): handoff.start_synthetic('startup-one', ident())
    assert handoff.store.snapshot()['startup'] is None
    assert not (Path(handoff.output.root)/'intent-00000001.json').exists()


@pytest.mark.parametrize('case', ['proof-forged', 'grant-forged', 'replay', 'wrong-helper', 'wrong-operation', 'stale',
                                'future', 'running', 'revision', 'foreign-authority', 'no-approval'])
def test_manual_recovery_rejects_bad_evidence(handoff, case):
    h = handoff
    state = h.inspect_synthetic('inspection-one', 'c'*64, approved=True)
    proof = h.authority.recovery.attest_exit('d'*64 if case == 'wrong-helper' else 'c'*64,
                                           'inspection-other' if case == 'wrong-operation' else 'inspection-one', 1000)
    if case == 'running': proof['facts']['state'] = 'running'
    if case == 'no-approval':
        with pytest.raises(m.Refused): h.authority.recovery.approve(state, proof)
        return
    grant = h.authority.recovery.approve(state, proof, approved=True)
    if case == 'proof-forged': proof['signature'] = '0'*64
    if case == 'grant-forged': grant['signature'] = '0'*64
    if case == 'revision': grant['payload']['revision'] -= 1
    if case == 'foreign-authority': h.authority.recovery = m.s.SyntheticAuthority()
    if case == 'replay':
        h.recover_synthetic(proof, grant, 1001)
        with pytest.raises(m.Refused): h.recover_synthetic(proof, grant, 1001)
        assert h._current()[0] == 2
    else:
        now = 1006 if case == 'stale' else 999 if case == 'future' else 1001
        with pytest.raises(m.Refused): h.recover_synthetic(proof, grant, now)
        assert h.store.snapshot()['inspection']['phase'] == 'UNCERTAIN'
        assert not (Path(h.output.root)/'intent-00000002.json').exists()


@pytest.mark.parametrize('phase', ['before-effect', 'after-state-commit', 'authority-lost'])
def test_interrupted_handoff_retains_startup_prohibition(handoff, monkeypatch, phase):
    h = handoff
    original = h.output._write
    def interrupt(directory, name, raw):
        if name == 'ack-00000001.json' and phase == 'after-state-commit':
            raise OSError('Synthetic ack storage failure')
        original(directory, name, raw)
        if name == 'intent-00000001.json':
            if phase == 'before-effect': raise OSError('Synthetic reservation interruption')
            if phase == 'authority-lost': h.authority.available = False
    monkeypatch.setattr(h.output, '_write', interrupt)
    with pytest.raises((OSError, m.Refused)): h.start_synthetic('startup-one', ident())
    assert (Path(h.output.root)/'intent-00000001.json').exists()
    h.authority.available = True
    with pytest.raises(m.Refused): reopen(h)
    with pytest.raises(m.Refused): h.inspect_synthetic('inspection-one', 'c'*64, approved=True)


@pytest.mark.parametrize('surface', ['snapshot', 'witness', 'handoff'])
def test_partial_storage_rollback_refused(handoff, surface):
    h = handoff
    h.inspect_synthetic('inspection-one', 'c'*64, approved=True)
    if surface == 'snapshot':
        source = Path(h.store.output.root)/'snapshot-00000000.json'
        target = source.with_name('snapshot-00000001.json')
        target.write_bytes(source.read_bytes())
    elif surface == 'witness':
        target = Path(h.store.witness.root)/'commit-00000001.json'
        target.rename(target.with_name('retained-commit'))
    else:
        root = Path(h.output.root)
        for name in ('intent-00000001.json', 'ack-00000001.json'):
            (root/name).rename(root/('retained-'+name))
    with pytest.raises((m.Refused, OSError)): reopen(h)


def test_concurrent_startup_and_inspection_one_winner(handoff):
    barrier = threading.Barrier(2)
    def attempt(start):
        barrier.wait(5)
        try:
            if start: handoff.start_synthetic('startup-one', ident())
            else: handoff.inspect_synthetic('inspection-one', 'c'*64, approved=True)
            return True
        except m.Refused: return False
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(attempt, [True, False])) == [False, True]


@pytest.mark.parametrize('damage', ['corrupt', 'stale-ack', 'wrong-root', 'missing-ack', 'gap'])
def test_handoff_integrity_and_identity_refusal(handoff, damage):
    h = handoff
    h.inspect_synthetic('inspection-one', 'c'*64, approved=True)
    root = Path(h.output.root)
    if damage == 'corrupt': (root/'ack-00000001.json').write_bytes(b'{')
    elif damage == 'stale-ack':
        (root/'ack-00000001.json').write_bytes((root/'ack-00000000.json').read_bytes())
    elif damage == 'wrong-root':
        wrong = copy.deepcopy(h.root_id); wrong[2] += 1
        with pytest.raises(m.Refused): m.Handoff(h.store, h.output.root, wrong, h.authority)
        return
    elif damage == 'missing-ack': (root/'ack-00000001.json').rename(root/'retained-ack')
    else:
        for name in ('ack-00000001.json', 'intent-00000001.json'):
            (root/name).rename(root/name.replace('00000001', '00000002'))
    with pytest.raises((m.Refused, ValueError, OSError)): reopen(h)


def test_local_fixture_never_production_authority(handoff):
    with pytest.raises(m.Refused): handoff.production_admission()
    with pytest.raises(m.Refused): handoff.store.production_admission()


def test_repaired_corruption_cannot_clear_manual_review(handoff):
    h = handoff
    path = Path(h.output.root)/'ack-00000000.json'
    initial = path.read_bytes()
    path.write_bytes(b'INCOMPLETE')
    with pytest.raises(ValueError): h._current()
    assert (Path(h.output.root)/'manual-review-required.json').exists()
    path.write_bytes(initial)
    with pytest.raises(m.Refused): reopen(h)


def test_native_restricted_token_denies_handoff_receipt(handoff):
    c, W, w = m.s.C, m.s.native.W, m.s.w
    normal, restricted, everyone = W.HANDLE(), W.HANDLE(), c.c_void_p()
    convert = w.bind(w.A, 'ConvertStringSidToSidW', [W.LPCWSTR, c.POINTER(c.c_void_p)])
    restrict = w.bind(w.A, 'CreateRestrictedToken', [W.HANDLE, W.DWORD, W.DWORD, c.c_void_p, W.DWORD, c.c_void_p,
                                                 W.DWORD, c.POINTER(w.SidAttr), c.POINTER(W.HANDLE)])
    impersonate = w.bind(w.A, 'ImpersonateLoggedOnUser', [W.HANDLE])
    revert = w.bind(w.A, 'RevertToSelf', [])
    try:
        w.check(w.open_token(w.process(), 0xE, c.byref(normal)))
        w.check(convert('S-1-1-0', c.byref(everyone)))
        entry = w.SidAttr(everyone, 0)
        w.check(restrict(normal, 1, 0, None, 0, None, 1, c.byref(entry), c.byref(restricted)))
        w.check(impersonate(restricted))
        try:
            for access in (w.READ, w.WRITE):
                handle = w.create_file(str(Path(handoff.output.root)/'ack-00000000.json'), access, 7, None, 3, 0, None)
                error = c.get_last_error()
                if handle != w.INVALID: w.close_handle(handle)
                assert handle == w.INVALID and error == 5
        finally:
            w.check(revert())
    finally:
        if normal: w.close_handle(normal)
        if restricted: w.close_handle(restricted)
        if everyone: w.local_free(everyone)


CHILD = '''import importlib.util,sys,json,os
s=importlib.util.spec_from_file_location('m',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
a=m.ManualFixtureAuthority();h=m.Handoff.reopen_synthetic(sys.argv[2],sys.argv[3],sys.argv[4],json.loads(sys.argv[5]),a)
original=h.output._write
def fail(directory,name,raw):
 if name=='ack-00000001.json':os._exit(24)
 original(directory,name,raw)
if sys.argv[6]=='interrupt':h.output._write=fail
h.start_synthetic('crash-startup',{'pid':1000,'created':1000,'exe':'a'*64,'command':'b'*64});os._exit(23)
'''


@pytest.mark.parametrize('phase', ['committed', 'interrupt'])
def test_actual_child_crash_and_durable_handoff(handoff, phase):
    h = handoff
    result = subprocess.run([sys.executable, '-I', '-B', '-c', CHILD, str(ROOT/'scripts/volume_inspector/manual_handoff.py'),
                             h.store.output.root, h.store.witness.root, h.output.root, json.dumps(h.root_id), phase],
                            capture_output=True, timeout=15, check=False)
    assert result.returncode == (23 if phase == 'committed' else 24), result.stderr
    if phase == 'committed':
        r = reopen(h)
        try:
            assert r.store.snapshot()['startup']['phase'] == 'PENDING'
            assert r._current()[0] == 1
        finally: r.close()
    else:
        assert (Path(h.output.root)/'intent-00000001.json').exists()
        with pytest.raises(m.Refused): reopen(h)
