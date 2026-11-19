"""Offline Windows/activation doubles; no real authority, accounts or handles."""
import copy
import os
from types import SimpleNamespace
from contextlib import nullcontext

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


def test_explicit_two_lane_activation_matches_exact_existing_qd_enrollment(monkeypatch):
    """A native two-account activation may authorize QD, but never by omission."""
    s = authority(monkeypatch)
    pair = {'QUALITY_DIPS': digest(s.f.e), 'HYPERLIQUID': 'a' * 64}
    s.value['accounts'] = copy.deepcopy(pair)
    bound = authority_module.NativePersonalOperatorAuthority(
        policy=s.i.p, enrollment=s.f.e, reader=s.reader,
        clock=s.clock, runtime_id='SYNTHETIC-RUNTIME', accounts=pair)
    assert bound.accounts == pair
    assert bound.verify(s.request) is True

    # A changed second account must invalidate the original activation.
    s.value['accounts']['HYPERLIQUID'] = 'b' * 64
    with pytest.raises(ValueError, match='PERSONAL_EXPLICIT_ACTIVATION_REQUIRED'):
        bound.verify(s.request)
    s.value['accounts'] = copy.deepcopy(pair)
    bound.accounts['HYPERLIQUID'] = 'b' * 64
    with pytest.raises(ValueError, match='PERSONAL_LOCAL_AUTHORITY_REVOKED_OR_CHANGED'):
        bound.verify(s.request)


def test_two_lane_binding_requires_explicit_complete_pair(monkeypatch):
    s = authority(monkeypatch)
    qd = digest(s.f.e)
    for bad in (
        {'QUALITY_DIPS': qd},
        {'QUALITY_DIPS': 'b' * 64, 'HYPERLIQUID': 'a' * 64},
        {'QUALITY_DIPS': qd, 'HYPERLIQUID': 'not-a-digest'},
        {'QUALITY_DIPS': qd, 'HYPERLIQUID': 'a' * 64, 'EXTRA': 'x'},
    ):
        with pytest.raises(ValueError, match='PERSONAL_NATIVE_OPERATOR_TWO_ACCOUNT_BINDING_REQUIRED'):
            authority_module.NativePersonalOperatorAuthority(
                policy=s.i.p, enrollment=s.f.e, reader=s.reader,
                clock=s.clock, runtime_id='SYNTHETIC-RUNTIME', accounts=bad)
    # The existing separately scoped QD-only activation still uses its
    # historical one-account binding unless the two-lane pair is explicit.
    assert s.port.accounts == {'QUALITY_DIPS': qd}
    assert s.port.verify(s.request) is True


def test_native_authority_defaults_to_refusal_without_native_binding():
    with pytest.raises(ValueError): authority_module.NativePersonalOperatorAuthority()


def owner(monkeypatch, result=0, enrollment=None, read_only=False, historical_writer=False,
          inception=False, with_fence=None):
    e = copy.deepcopy(fixture().e if enrollment is None else enrollment)
    now, released, closed, waits = [1000], [], [], []
    self_id = {'pid': os.getpid(), 'creation_filetime': 123, 'image': 'D:\\SYNTHETIC-only.exe'}
    e['writers'] = {k: {'schema': 'QD_OP_PROCESS_ID_V1', **self_id} for k in e['writers']}
    if historical_writer:
        e['writers'] = {k:{**value,'pid':value['pid']+1} for k,value in e['writers'].items()}
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
    if with_fence is None:with_fence=not (read_only or historical_writer or inception)
    generation=None
    if with_fence:
        from scripts.observation_runtime import personal_writer_generation as generations
        class Generation:
            identity=copy.deepcopy(self_id)
            enrollments={'QUALITY_DIPS':e}
            def __init__(self):self.clock=auth.clock
            def verify(self):return True
            def scope(self):return nullcontext()
            def current_roster(self):
                return {'roles':{'QUALITY_DIPS':{k:{'schema':'QD_OP_PROCESS_ID_V1',**self.identity}
                                                 for k in e['writers']}}}
        monkeypatch.setattr(generations,'NativeWriterGeneration',Generation)
        generation=Generation()
    port = ownership_module.NativePersonalWriterOwnership(enrollment=e, authority=auth,
                  inception_intent=intent if inception else None, read_only=read_only,generation=generation)
    request = {'scope': 'LOCAL_ENROLLED', 'enrollment': e, 'grant': {'SYNTHETIC': True}}
    return SimpleNamespace(**locals())


def test_exact_self_roster_nested_native_and_inception_lease_closes_handles(monkeypatch):
    s = owner(monkeypatch)
    with s.port.lease(s.request, s.now[0]) as outer:
        assert outer.check(outer.snapshot, s.now[0])
        assert outer.snapshot['writers'] == s.e['writers']
        assert outer.snapshot['original_writers']==s.e['writers']
        assert outer.snapshot['schema']=='QD_AUTO_NATIVE_OWNERSHIP_V5'
        with s.port.lease(s.request, s.now[0]) as inner:
            assert inner.check(inner.snapshot, s.now[0])
            with pytest.raises(ValueError, match='BEFORE_DRAIN'): s.port.close()
    s.port.close()
    assert len(s.released) == 2 and len(s.closed) == 7
    assert all(not values for values in s.files.values())
    genesis=owner(monkeypatch,inception=True)
    context={'schema':'PERSONAL_GENESIS_WRITER_V1','intent_digest':digest(genesis.intent),
             'process':genesis.port.identity}
    with genesis.port.lease(context,genesis.now[0]) as lease:
        assert lease.check(context,genesis.now[0])
    genesis.port.close()
    assert len(genesis.released)==1 and len(genesis.closed)==7


def test_unfenced_original_writer_cannot_receive_a_financial_runtime_lease(monkeypatch):
    s=owner(monkeypatch,with_fence=False)
    with pytest.raises(ValueError,match='UNFENCED'),s.port.lease(s.request,s.now[0]):
        pytest.fail('Unfenced financial writer admitted')
    assert s.waits==[] and s.released==[]
    s.port.close()


def test_read_only_restart_preserves_historical_writer_and_cannot_admit_operations(monkeypatch):
    with pytest.raises(ValueError, match='EXACT_SELF_ROSTER'):
        owner(monkeypatch,historical_writer=True)
    s=owner(monkeypatch,read_only=True,historical_writer=True)
    original=copy.deepcopy(s.port.enrollment)
    read={'schema':'QD_AUTO_OP_READ_ENROLLMENT_V1','account_id':s.e['account_id'],'epoch':s.e['epoch'],
          **{r+'_root':s.e['resources'][r]['native_id'] for r in ('source','projection','report')}}
    with s.port.lease({'schema':'PERSONAL_NATIVE_READ_LEASE_V1','reader_enrollment':read},s.now[0]) as lease:
        assert lease.check(lease.snapshot,s.now[0])
    with pytest.raises(ValueError,match='NO_WRITER_ADMISSION'),s.port.lease(s.request,s.now[0]):
        pytest.fail('reader acquired financial writer admission')
    assert s.port.enrollment==original and all(not values for values in s.files.values())
    s.port.read_only=False
    with pytest.raises(ValueError),s.port.lease(s.request,s.now[0]):
        pytest.fail('mode mutation granted writer authority')
    s.port.close()


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


def _hl_postinception_fixture(monkeypatch, *, phase="CURRENT_READBACK_ONLY"):
    """Disposable role doubles: never genuine account ACKs or source rights."""
    from test_personal_paper_inception_memory import system
    from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
        RetainedSelectedNativeOwnerPreflight,
    )
    from scripts.observation_runtime import personal_version_safe_release_clock as clock_module

    s = authority(monkeypatch)
    hl = system("HYPERLIQUID")
    qd = copy.deepcopy(s.f.e)
    assert qd["release_digest"] == hl.n["release_digest"]
    pair = {"QUALITY_DIPS": digest(qd), "HYPERLIQUID": digest(hl.n)}
    s.value["accounts"] = copy.deepcopy(pair)
    s.value["release_digest"] = hl.n["release_digest"]
    s.value["actions"] = ["READ_ONLY", "CONNECT_APPROVED_DATA"]
    original = object.__new__(RetainedSelectedNativeOwnerPreflight)
    original._phase = phase
    original.release_digest = hl.n["release_digest"]
    admitted = [True]
    monkeypatch.setattr(
        RetainedSelectedNativeOwnerPreflight, "require_exact_roster",
        lambda self, *, qd, perp: (
            admitted[0] and qd == s.f.e and perp == hl.n),
    )
    monkeypatch.setattr(
        RetainedSelectedNativeOwnerPreflight, "verify_still_running",
        lambda self: admitted[0],
    )
    # Construct exact native class identities with inert time/Windows doubles.
    monkeypatch.setattr(clock_module, "NativeVersionSafePaperOperatorClock",
                        LocalWindowsClock)
    monkeypatch.setattr(clock_module, "require_version_safe_release_digest",
                        lambda **_: True)
    port = authority_module.NativePersonalOperatorAuthority(
        policy=s.i.p, enrollment=hl.n, reader=s.reader, clock=s.clock,
        runtime_id="SYNTHETIC-RUNTIME", accounts=pair,
        clock_profile=clock_module.PROFILE,
        postinception_owner=original, qd_enrollment=qd,
    )
    return SimpleNamespace(**locals(), i=s.i, reader=s.reader,
                           clock=s.clock, now=s.now, value=s.value)


@pytest.mark.parametrize("phase", [
    "INITIAL_READBACK_ONLY", "CURRENT_READBACK_ONLY",
])
def test_hl_original_postinception_data_only_source_activation(monkeypatch, phase):
    s = _hl_postinception_fixture(monkeypatch, phase=phase)
    try:
        record = s.port.activation("CONNECT_APPROVED_DATA")
        assert record["actions"] == ["READ_ONLY", "CONNECT_APPROVED_DATA"]
        assert record["accounts"] == s.pair
        assert s.port.activation("READ_ONLY") == record
        for action in (
            "INITIALIZE_SIMULATED_ACCOUNTS", "AUTO_PAPER",
            "SHUTDOWN_FLATTEN", "EMERGENCY_STOP", "LIVE_ORDER",
        ):
            with pytest.raises(ValueError, match="POSTINCEPTION_DATA_ONLY"):
                s.port.activation(action)
        assert s.port._postinception_owner is s.original
        assert s.port._lane == "HYPERLIQUID"
    finally:
        s.hl.ledger.db.close()


def test_hl_first_inception_operator_cannot_take_data_or_financial_actions(
        monkeypatch):
    s = _hl_postinception_fixture(monkeypatch)
    try:
        original = authority_module.NativePersonalOperatorAuthority(
            policy=s.i.p, enrollment=s.hl.n,
            reader=s.reader, clock=s.clock,
            runtime_id="SYNTHETIC-RUNTIME",
            accounts=s.pair,
        )
        for action in ("CONNECT_APPROVED_DATA", "AUTO_PAPER",
                       "SHUTDOWN_FLATTEN"):
            with pytest.raises(ValueError, match="FIRST_INCEPTION_ONLY"):
                original.activation(action)
    finally:
        s.hl.ledger.db.close()


@pytest.mark.parametrize("damage", [
    "lost_job", "wrong_phase", "changed_release", "roster_lost",
    "clock_changed", "expired_record", "wrong_scope",
])
def test_hl_data_activation_requires_original_acknowledged_two_account_owner(
        monkeypatch, damage):
    s = _hl_postinception_fixture(monkeypatch)
    try:
        if damage in ("lost_job", "roster_lost"):
            s.admitted[0] = False
        elif damage == "wrong_phase":
            s.original._phase = "PREINCEPTION"
        elif damage == "changed_release":
            s.original.release_digest = "f" * 64
        elif damage == "clock_changed":
            s.port.clock = object()
        elif damage == "expired_record":
            s.now[0] = s.value["expires_at"]
        else:
            s.value["actions"] = ["READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS"]
        with pytest.raises((ValueError,AttributeError,TypeError)):
            s.port.activation("CONNECT_APPROVED_DATA")
    finally:
        s.hl.ledger.db.close()


@pytest.mark.parametrize("damage", [
    "preinception", "missing_pair", "wrong_qd", "wrong_release",
])
def test_hl_postinception_factory_rejects_unverified_original_account_admission(
        monkeypatch, damage):
    s = _hl_postinception_fixture(monkeypatch)
    try:
        kwargs = {
            "policy": s.i.p, "enrollment": s.hl.n, "reader": s.reader,
            "clock": s.clock, "runtime_id": "SYNTHETIC-RUNTIME",
            "accounts": copy.deepcopy(s.pair),
            "clock_profile": s.clock_module.PROFILE,
            "postinception_owner": s.original,
            "qd_enrollment": copy.deepcopy(s.qd),
        }
        if damage == "preinception":
            s.original._phase = "PREINCEPTION"
        elif damage == "missing_pair":
            kwargs["accounts"].pop("QUALITY_DIPS")
        elif damage == "wrong_qd":
            kwargs["qd_enrollment"]["account_id"] = "FOREIGN"
        else:
            s.original.release_digest = "f" * 64
        with pytest.raises(ValueError):
            authority_module.NativePersonalOperatorAuthority(**kwargs)
    finally:
        s.hl.ledger.db.close()
