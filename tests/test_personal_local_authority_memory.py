"""Offline Windows/activation doubles; no real authority, accounts or handles."""
import copy
import os
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, digest
from app.services.quality_dips_personal_dependencies import PersonalSessionReservations
from test_personal_native_coordination_memory import setup as ledger_setup
from test_personal_paper_runtime import installed
from test_quality_dips_autonomous_enrollment import fixture

import scripts.observation_runtime.personal_local_authority as authority_module
import scripts.observation_runtime.personal_writer_ownership as ownership_module
from scripts.observation_runtime.personal_paper_activation import NativePersonalActivationReader
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock


def authority(monkeypatch):
    f, i = fixture(), installed()
    now, sid = [1000], ['SYNTHETIC-OPERATOR']
    value = copy.deepcopy(i.reader.value)
    value['accounts'] = {'QUALITY_DIPS': digest(f.e)}
    value['activation_id'] = 'SYNTHETIC-ONE-PILOT'
    reader, clock = object.__new__(NativePersonalActivationReader), object.__new__(LocalWindowsClock)
    monkeypatch.setattr(NativePersonalActivationReader, 'read', lambda _: copy.deepcopy(value))
    monkeypatch.setattr(LocalWindowsClock, 'require_operational', lambda *args: None)
    monkeypatch.setattr(LocalWindowsClock, '__call__', lambda _: now[0])
    native = SimpleNamespace(w=SimpleNamespace(current_sid=lambda: sid[0]))
    monkeypatch.setattr(authority_module, 'native_primitives', lambda: native)
    port = authority_module.NativePersonalOperatorAuthority(policy=i.p, enrollment=f.e,
                        reader=reader, clock=clock, runtime_id='SYNTHETIC-RUNTIME')
    grant = {**f.g, 'session_id': value['activation_id'], 'issued_at': 1000, 'expires_at': 1060}
    request = {'scope': 'LOCAL_ENROLLED', 'enrollment': f.e, 'grant': grant}
    return SimpleNamespace(**locals())


def test_native_record_verifier_and_existing_durable_session_reservation(monkeypatch):
    s = authority(monkeypatch)
    assert s.port.verify(s.request)
    _, images, ledger = ledger_setup()
    sessions = PersonalSessionReservations(ledger=ledger, authorization=s.port)
    receipt = sessions.reserve(s.request)
    assert sessions.verify(s.request, receipt)
    before = list(images.history)
    with pytest.raises(ValueError, match='REPLAY'):
        sessions.reserve(s.request)
    assert images.history == before


@pytest.mark.parametrize('damage', ['sid', 'origin', 'release', 'policy', 'account', 'expired',
                                  'action', 'revoked', 'duration', 'reused-id', 'fixture-grant', 'clock'])
def test_operator_record_and_bounded_session_refusal(monkeypatch, damage):
    s = authority(monkeypatch)
    assert s.port.verify(s.request)
    if damage == 'sid': s.sid[0] = 'FOREIGN'
    elif damage == 'origin': s.value['origin'] = 'SYNTHETIC_AUTHORITY'
    elif damage == 'release': s.value['release_digest'] = 'd' * 64
    elif damage == 'policy': s.value['policy_digest'] = 'd' * 64
    elif damage == 'account': s.request['enrollment'] = {**s.f.e, 'epoch': 'FOREIGN'}
    elif damage == 'expired': s.now[0] = 1060
    elif damage == 'action': s.value['actions'] = ['READ_ONLY']
    elif damage == 'revoked': s.port.revoke()
    elif damage == 'duration': s.grant['expires_at'] = 1061
    elif damage == 'reused-id': s.grant['session_id'] = 'ANOTHER-PILOT'
    elif damage == 'fixture-grant': s.grant['schema'] = 'QD_AUTO_SESSION_FIXTURE_V1'
    elif damage == 'clock': s.now[0] -= 1
    with pytest.raises(ValueError): s.port.verify(s.request)


def test_native_authority_defaults_to_refusal_without_native_binding():
    with pytest.raises(ValueError): authority_module.NativePersonalOperatorAuthority()


def owner(monkeypatch, result=0, enrollment=None):
    e = copy.deepcopy(fixture().e if enrollment is None else enrollment)
    now, released, closed, waits = [1000], [], [], []
    self_id = {'pid': os.getpid(), 'creation_filetime': 123, 'image': 'D:\\SYNTHETIC-only.exe'}
    e['writers'] = {k: {'schema': 'QD_OP_PROCESS_ID_V1', **self_id} for k in e['writers']}
    roots = {r['path']: r['native_id'] for r in e['resources'].values()}
    files = {p: {} for p in roots}
    class Output:
        def __init__(self, root): self.root, self.root_handle = root, root
        def _verify(self): pass
        def close(self): closed.append(self.root)
        def write_bound(self, name, data):
            assert name not in files[self.root]
            files[self.root][name] = data
    class Registry:
        def _create_mutex(self): self.mutex = 'SYNTHETIC-MUTEX'
        def wait(self, handle, timeout): waits.append(timeout); return result
        def release(self, handle): released.append(handle); return True
    def check(value):
        if not value: raise OSError('SYNTHETIC-NATIVE-FAILURE')
    native = SimpleNamespace(w=SimpleNamespace(WindowsOutput=Output, close_handle=closed.append, check=check),
                             native=SimpleNamespace(Registry=Registry, file_identity=lambda h: roots[h]))
    monkeypatch.setattr(ownership_module, 'native_primitives', lambda: native)
    monkeypatch.setattr(ownership_module, 'observe_self', lambda: copy.deepcopy(self_id))
    monkeypatch.setattr(ownership_module, 'Path', lambda p: SimpleNamespace(iterdir=lambda: iter(files[p])))
    auth = object.__new__(authority_module.NativePersonalOperatorAuthority)
    auth.enrollment, auth.clock = e, lambda: now[0]
    auth.activation = lambda action: {'SYNTHETIC_ACTION': action}
    intent = {'schema': 'SYNTHETIC-INTENT', 'operation_id': 'SYNTHETIC-ONCE'}
    port = ownership_module.NativePersonalWriterOwnership(enrollment=e, authority=auth, inception_intent=intent)
    request = {'scope': 'LOCAL_ENROLLED', 'enrollment': e, 'grant': {'SYNTHETIC': True}}
    return SimpleNamespace(**locals())


def test_exact_self_roster_nested_native_and_inception_lease_closes_handles(monkeypatch):
    s = owner(monkeypatch)
    with s.port.lease(s.request, s.now[0]) as outer:
        assert outer.check(outer.snapshot, s.now[0])
        assert outer.snapshot['writers'] == s.e['writers']
        with s.port.lease(s.request, s.now[0]) as inner:
            assert inner.check(inner.snapshot, s.now[0])
            with pytest.raises(ValueError, match='BEFORE_DRAIN'): s.port.close()
    context = {'schema': 'PERSONAL_GENESIS_WRITER_V1', 'intent_digest': digest(s.intent),
               'process': s.port.identity}
    with s.port.lease(context, s.now[0]) as lease:
        assert lease.check(context, s.now[0])
    s.port.close()
    assert len(s.released) == 3 and len(s.closed) == 7
    assert all(not values for values in s.files.values())


@pytest.mark.parametrize('damage', ['process', 'root', 'namespace', 'revocation', 'expiry', 'snapshot'])
def test_writer_lease_changes_refuse_and_release_only_owned_mutex(monkeypatch, damage):
    s = owner(monkeypatch)
    try:
        with pytest.raises(ValueError), s.port.lease(s.request, s.now[0]) as lease:
            if damage == 'process': s.self_id['creation_filetime'] += 1
            elif damage == 'root': s.roots[s.e['resources']['source']['path']] = [9, 9, 9]
            elif damage == 'namespace': s.files[s.e['resources']['control']['path']]['unknown'] = b'X'
            elif damage == 'revocation': s.auth.activation = lambda action: {'CHANGED': True}
            elif damage == 'expiry': s.now[0] += 31
            elif damage == 'snapshot': lease.snapshot['unknown_writers'] = ['FOREIGN']
        assert len(s.released) == 1
    finally:
        s.port.close()


@pytest.mark.parametrize('result', [258, 128])
def test_competing_or_abandoned_writer_refuses_without_financial_effects(monkeypatch, result):
    s = owner(monkeypatch, result)
    try:
        with pytest.raises(ValueError), s.port.lease(s.request, s.now[0]):
            pytest.fail('writer admitted')
        assert all(not s.files[s.e['resources'][r]['path']] for r in ('source', 'projection', 'report'))
        assert len(s.released) == int(result == 128)
        if result == 128:
            assert 'unknown-writer.json' in s.files[s.e['resources']['control']['path']]
            with pytest.raises(ValueError), s.port.lease(s.request, s.now[0]):
                pytest.fail('abandoned writer adopted')
    finally:
        s.port.close()


@pytest.mark.parametrize('damage', [None, 'projection', 'session', 'publication', 'foreign', 'missing'])
def test_native_drain_reads_durable_pending_state_without_publication(monkeypatch, damage):
    s = owner(monkeypatch)
    _, images, ledger = ledger_setup()
    s.port.ledger = s.port._ledger = ledger
    runtime = {'schema': 'QD_AUTO_LOCAL_RUNTIME_V3', 'scope': 'LOCAL_ENROLLED',
        'process_identity': {'pid': s.self_id['pid'], 'created': 123, 'image': s.self_id['image']},
        'writer_roster': ['decision', 'source', 'projection', 'report', 'coordination'],
        'reader_enrollment': {'schema': 'QD_AUTO_OP_READ_ENROLLMENT_V1',
            'account_id': s.e['account_id'], 'epoch': s.e['epoch'],
            **{r + '_root': s.e['resources'][r]['native_id'] for r in ('source', 'projection', 'report')}}}
    request = {'enrollment': runtime, 'grant': {'engine_grant': {'session_id': 'one'}}}
    reserved = {'scope': 'LOCAL_ENROLLED', 'enrollment': s.e, 'grant': {'session_id': 'one'}}
    with ledger.connect() as db:
        if damage != 'missing':
            if damage == 'foreign': reserved['enrollment'] = {}
            db.execute('INSERT INTO personal_sessions VALUES(?,?,?)',
                       ('one', body(reserved), 'PENDING' if damage == 'session' else 'ACKNOWLEDGED'))
        if damage == 'projection': db.execute("INSERT INTO projections VALUES('pending','{}',NULL)")
        if damage == 'publication':
            db.execute("INSERT INTO personal_publications VALUES('unknown','{}','{}','UNKNOWN',NULL,NULL,NULL)")
    before = list(images.history)
    try:
        if damage:
            with pytest.raises(ValueError): s.port.drain(request, now=1000)
        else:
            assert s.port.drain(request, now=1000) == {
                'schema': 'QD_AUTO_DRAIN_V3', 'enrollment_digest': digest(runtime),
                'session_id': 'one', 'pending': 0, 'unknown': False}
        assert images.history == before
    finally:
        s.port.close()
