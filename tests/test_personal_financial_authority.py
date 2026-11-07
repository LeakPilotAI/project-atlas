"""Durable admission protocol over memory-native images and synthetic authority."""
import copy
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest
from app.services.personal_current_pins import PersonalCurrentPins
from app.services.personal_native_coordination import PersonalNativeCoordination
from test_personal_native_coordination_memory import Images
from test_quality_dips_autonomous_enrollment import fixture
from test_quality_dips_autonomous_paper import candidate, quote
from test_quality_dips_autonomous_paper import setup as engine_setup

from scripts.observation_runtime.personal_engine_session import NativePersonalEngineSession
from scripts.observation_runtime.personal_financial_authority import (
    NativePersonalFinancialAuthority,
    NativePersonalFinancialReadAuthority,
)
from scripts.observation_runtime.personal_local_authority import NativePersonalOperatorAuthority
from scripts.observation_runtime.personal_writer_ownership import NativePersonalWriterOwnership


def setup(tmp_path):
    n = engine_setup(tmp_path)
    images = Images(PersonalNativeCoordination.initial_image(n.m))
    ledger = PersonalNativeCoordination(manifest=n.m, images=images, path=tmp_path/'memory-only')
    n.engine.ledger = ledger
    operator = object.__new__(NativePersonalOperatorAuthority)
    operator.enrollment = copy.deepcopy(fixture().e)
    operator.clock = n.engine.clock
    operator.activation = lambda action: {'SYNTHETIC': action}
    operator.verify = lambda request: request['enrollment'] == operator.enrollment
    session = object.__new__(NativePersonalEngineSession)
    session.operator, session.manifest = operator, n.m
    original_session = n.engine.session_authority
    def verify(grant, now):
        if grant is None or not grant['issued_at'] <= now < grant['expires_at']:
            raise ValueError('SYNTHETIC_SESSION_EXPIRED')
        return original_session.verify(grant, now=now)
    session.verify = verify
    n.engine.session_authority = session
    n.engine.start(n.grant)
    source = {'schema':'QD_AUTO_OP_PIN_V1','root':operator.enrollment['resources']['source']['native_id'],
              'inception':{'id':[1,2,3],'sha256':'a'*64},'epoch':n.m['epoch'],'entries':[]}
    with ledger.connect() as db: PersonalCurrentPins.initialize(db, 'source', source)
    pins = PersonalCurrentPins(ledger=ledger, name='source', clock=operator.clock)
    owner = object.__new__(NativePersonalWriterOwnership)
    owner.read_only = False
    owner.authority, owner.enrollment, owner.ledger = operator, operator.enrollment, ledger
    @contextmanager
    def owned(context, now):
        yield SimpleNamespace(snapshot=context,check=lambda candidate, stamp: candidate == context and now <= stamp <= now+5)
    owner.lease = owned
    port = NativePersonalFinancialAuthority(operator=operator, ownership=owner, engine=n.engine, session=session, source=pins)
    b = candidate(n)
    command = n.engine.preview('once', bundles=[b], quotes=[quote(n,b)])['command']
    receipt = ledger.execute(lambda *args: command, projection_required=True)
    request = {'schema':'QD_AUTO_OP_ADMISSION_REQUEST_V1','enrollment':operator.enrollment,
               'current':source,'command':command}
    return SimpleNamespace(**locals())


def test_pending_commit_ack_and_duplicate_refusal(tmp_path):
    s = setup(tmp_path)
    with s.port.lease(s.request, s.n.now[0]) as lease:
        ident = lease.snapshot['reservation_id']
        assert s.port.custody.row(ident)[2] == 'PENDING'
        after = {**s.source, 'entries':[{'SYNTHETIC_NATIVE_BINDING': True}]}
        s.pins.advance(s.source, after)
        ack = lease.acknowledge(s.request, s.receipt, after)
        assert lease.verify_ack(ack)
        assert s.port.custody.row(ident)[2] == 'ACKNOWLEDGED'
    before = list(s.images.history)
    with pytest.raises(ValueError), s.port.lease({**s.request,'current':after}, s.n.now[0]):
        pytest.fail('already reserved operation replayed')
    assert s.images.history == before


@pytest.mark.parametrize('readonly',[True,False])
def test_read_snapshot_lock_order_and_no_financial_write_inside_snapshot(tmp_path,readonly):
    s=setup(tmp_path);active=[0];owners=[0];original=s.ledger.connect
    @contextmanager
    def owned(context,now):
        owners[0]+=1
        try:yield SimpleNamespace(snapshot=context,check=lambda value,stamp:value==context)
        finally:owners[0]-=1
    @contextmanager
    def view():
        assert owners[0]>0  # Native ownership always precedes image mutex.
        active[0]+=1
        try:yield
        finally:active[0]-=1
    @contextmanager
    def connect(*,readonly=False):
        assert readonly or not active[0]
        with original(readonly=readonly) as db:yield db
    s.owner.lease=owned
    s.ledger.read_view=view
    s.ledger.connect=connect
    request={**s.request,'command':None} if readonly else s.request
    with s.port.lease(request,s.n.now[0]) as lease:
        if readonly:
            assert active[0]>0 and lease.snapshot['status']=='READ_ACCEPTED'
        else:
            assert active[0]==0 and lease.snapshot['status']=='PENDING'
            after={**s.source,'entries':[{'SYNTHETIC_NATIVE_BINDING':True}]}
            s.pins.advance(s.source,after)
            assert lease.verify_ack(lease.acknowledge(s.request,s.receipt,after))
    assert active[0]==owners[0]==0


@pytest.mark.parametrize('damage', ['foreign', 'stale', 'manual', 'unreserved', 'session', 'revoked'])
def test_bad_admission_refuses_before_any_new_publication(tmp_path, damage):
    s = setup(tmp_path)
    request = copy.deepcopy(s.request)
    if damage == 'foreign': request['enrollment']['epoch'] = 'FOREIGN'
    elif damage == 'stale': request['current']['entries'] = [{}]
    elif damage == 'manual': request['command']['manual'] = True
    elif damage == 'unreserved': request['command']['operation_id'] = 'OTHER'
    elif damage == 'session': s.n.now[0] = s.n.grant['expires_at']
    else: s.operator.verify = lambda request: False
    before = list(s.images.history)
    with pytest.raises(ValueError), s.port.lease(request, s.n.now[0]): pytest.fail('invalid operation admitted')
    assert s.images.history == before


@pytest.mark.parametrize('damage', ['receipt', 'pin', 'source-change', 'expiry'])
def test_unacknowledged_operation_stays_uncertain_and_cannot_replay(tmp_path, damage):
    s = setup(tmp_path)
    with pytest.raises(ValueError), s.port.lease(s.request, s.n.now[0]) as lease:
        after = {**s.source, 'entries':[{'SYNTHETIC_NATIVE_BINDING': True}]}
        s.pins.advance(s.source, after)
        receipt, pin = copy.deepcopy(s.receipt), copy.deepcopy(after)
        if damage == 'receipt': receipt['source_revision'] += 1
        elif damage == 'pin': pin['entries'] = []
        elif damage == 'source-change': pin['root'] = [9,9,9]
        else: s.n.now[0] += 6
        with pytest.raises(ValueError): lease.acknowledge(s.request, receipt, pin)
        # Simulate a failed native outcome under an available session. UNKNOWN
        # is durable refusal evidence; it does not clear or replay the operation.
        lease.mark_unknown(s.request)
        ident = lease.snapshot['reservation_id']
        assert s.port.custody.row(ident)[2] == 'UNKNOWN'
    assert s.port.custody.row(ident)[2] == 'UNKNOWN'
    before = list(s.images.history)
    with pytest.raises(ValueError), s.port.lease({**s.request,'current':after}, s.n.now[0]):
        pytest.fail('uncertain operation replayed')
    assert s.images.history == before


def test_default_refusal():
    with pytest.raises(ValueError): NativePersonalFinancialAuthority()


def test_separate_read_authority_never_reserves_or_accepts_a_command(tmp_path):
    s=setup(tmp_path)
    s.operator.enrollment['inception_digest']=digest(s.ledger.manifest)
    s.owner.read_only=True
    port=NativePersonalFinancialReadAuthority(operator=s.operator,ownership=s.owner,source=s.pins)
    request={**s.request,'enrollment':s.operator.enrollment,'command':None}
    before=list(s.images.history)
    with port.lease(request,s.n.now[0]) as lease:
        assert lease.snapshot['status']=='READ_ACCEPTED'
        with pytest.raises(ValueError): lease.acknowledge(request,s.receipt,s.source)
    assert s.images.history==before
    with pytest.raises(ValueError),port.lease({**request,'command':s.command},s.n.now[0]):
        pytest.fail('read authority granted financial publication')
    assert s.images.history==before
    with pytest.raises(ValueError): NativePersonalFinancialReadAuthority()
