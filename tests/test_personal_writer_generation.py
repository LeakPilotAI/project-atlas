"""Offline original-account generation CAS and native-port orchestration.

All Windows/approval ports below are explicit doubles. No real account, native
Job, local approval, financial ACK, process exit or Stop timing is asserted.
"""
import copy
import sqlite3
from contextlib import contextmanager
from threading import RLock
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import body, digest
from app.services.personal_writer_generation import WriterGenerationJournal, accept_generation, replay
from scripts.observation_runtime import personal_writer_generation as target

OLD={'pid':100,'creation_filetime':10000,'image':r'D:\native\python.exe'}
NEW={'pid':101,'creation_filetime':20000,'image':r'D:\native\python.exe'}
ACCOUNTS={'QUALITY_DIPS':'a'*64,'HYPERLIQUID':'b'*64}


class MemoryLedger:
    def __init__(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE personal_current(name TEXT PRIMARY KEY,body TEXT,generation INTEGER)')
        self.lock=RLock();self.images=SimpleNamespace(_writer=self.exclusive)
        self.manifest={'OFFLINE':'NEVER_AN_ACCOUNT'}
    @contextmanager
    def exclusive(self):
        with self.lock:yield
    @contextmanager
    def connect(self,*,readonly=False):
        try:
            yield self.db
            if not readonly:self.db.commit()
        except BaseException:
            self.db.rollback();raise


@pytest.fixture
def journal():
    ledger=MemoryLedger()
    yield WriterGenerationJournal(ledger=ledger,accounts=ACCOUNTS)
    ledger.db.close()


def admit(journal,owner=OLD,*,fault=lambda _:None,cut=None,exclusion=None,approval=None):
    return accept_generation(journal=journal,owner=owner,fault=fault,
        inspect_cut=lambda:copy.deepcopy(cut or {'OFFLINE_FLAT':'verified_by_injected_reader'}),
        exclude_previous=exclusion or (lambda old:{'old':old,'OFFLINE_EXITED':True}),
        authorize=approval or (lambda context:{'OFFLINE_APPROVED_CONTEXT':copy.deepcopy(context),
                                              'approval_id':'OFFLINE_'+digest(context)}))


def test_full_original_generation_then_new_generation_keeps_account_identity(journal):
    first=admit(journal);old=journal.read()
    second=admit(journal,NEW)
    assert first['generation']==0 and second['generation']==1
    assert second['previous_owner']==OLD and second['owner']==NEW
    assert journal.read()['records'][:2]==old['records']
    assert journal.read()['accounts']==ACCOUNTS


@pytest.mark.parametrize('phase',['before_prepare','after_prepare','after_active'])
def test_crash_at_each_irreversible_generation_boundary_is_not_replayed(journal,phase):
    def fault(p):
        if p==phase:raise RuntimeError('OFFLINE_CRASH')
    with pytest.raises(RuntimeError):admit(journal,fault=fault)
    rows=journal.read()['records']
    assert len(rows)=={'before_prepare':0,'after_prepare':1,'after_active':2}[phase]
    if phase=='after_prepare':
        with pytest.raises(ValueError,match='UNKNOWN_PREPARED'):admit(journal,NEW)
    if phase=='after_active':
        with pytest.raises(ValueError):admit(journal,OLD)


@pytest.mark.parametrize('damage',['parent','revision','owner','generation','state','previous','scope','cut'])
def test_corrupt_or_mixed_generation_never_passes_replay(journal,damage):
    admit(journal);value=journal.read();r=value['records'][-1]
    if damage=='parent':r['parent']='e'*64
    elif damage=='revision':r['revision']=True
    elif damage=='owner':r['owner']['creation_filetime']=0
    elif damage=='generation':r['generation']=8
    elif damage=='state':r['state']='ADOPT_OLD_PID'
    elif damage=='previous':r['previous_owner']=OLD
    elif damage=='scope':r['scope_digest']='g'*64
    else:r['cut_digest']='f'*64
    with pytest.raises(ValueError):replay(value,ACCOUNTS)


def test_conflicting_independent_owner_or_approval_refuses_before_any_record(journal):
    def refuse(_):raise ValueError('OLD_STILL_ALIVE')
    admit(journal)
    before=journal.read()
    with pytest.raises(ValueError):admit(journal,NEW,exclusion=refuse)
    assert journal.read()==before
    with pytest.raises(ValueError):admit(journal,NEW,approval=refuse)
    assert journal.read()==before


@pytest.mark.parametrize('part',['cut','exclusion','approval'])
def test_changed_evidence_after_prepare_leaves_unknown_fence(journal,part):
    counts={'cut':0,'exclusion':0,'approval':0}
    def port(name):
        def call(*_):
            counts[name]+=1
            return {'version':counts[name] if name==part else 1,'approval_id':'OFFLINE_'+name}
        return call
    with pytest.raises(ValueError,match='HANDOFF_CHANGED'):
        accept_generation(journal=journal,owner=OLD,inspect_cut=port('cut'),
                          exclude_previous=port('exclusion'),authorize=port('approval'))
    assert journal.read()['records'][-1]['state']=='PREPARED'


def test_capacity_refusal_never_discards_history(journal):
    for i in range(32):admit(journal,{**OLD,'pid':100+i,'creation_filetime':10000+i})
    before=journal.read()
    with pytest.raises(ValueError,match='CAPACITY'):admit(journal,NEW)
    assert journal.read()==before


def test_stale_durable_cas_and_wrong_account_image_refuse(journal):
    before=journal.read();admit(journal)
    row=copy.deepcopy(journal.read()['records'][0])
    with pytest.raises(ValueError,match='CAS'):journal.append(before,row)
    other=WriterGenerationJournal(ledger=journal.ledger,accounts={**ACCOUNTS,'HYPERLIQUID':'c'*64})
    with pytest.raises(ValueError,match='BINDING'):other.read()


@pytest.fixture
def native_model(monkeypatch,journal):
    class Clock:
        def __call__(self):return 100
    clock=Clock()
    current=[copy.deepcopy(OLD)]
    original={lane:{'writers':{str(i):{'schema':'QD_OP_PROCESS_ID_V1',**OLD} for i in range(5 if lane=='QUALITY_DIPS' else 7)}} for lane in ACCOUNTS}
    class Job:
        def __init__(self):self.identity=copy.deepcopy(current[0]);self.bad=False
        def verify(self):
            if self.bad:raise ValueError('OFFLINE_JOB_HANDLE_OR_IDENTITY_CHANGED')
            return True
    readback=SimpleNamespace(release_digest='f'*64,clock=clock,runtime_id='OFFLINE',enrollments=original,
        readers={'QUALITY_DIPS':SimpleNamespace(source=SimpleNamespace(ledger=journal.ledger))},
        _verify=lambda:True)
    class Recovery:
        def __init__(self):self.readback=readback;self.cut={'OFFLINE_CURRENT':'FLAT_DRAINED'}
        def capture(self):return copy.deepcopy(self.cut)
    class Operator:
        accounts={k:digest(v) for k,v in original.items()};runtime_id='OFFLINE'
        def __init__(self):self.clock=clock
        def current_operator(self):return 'OFFLINE_SID'
        def activation(self,action):
            assert action=='READ_ONLY';return {'OFFLINE_READ':True}
    class Approval:
        def __init__(self):self.record=None
        def read(self):return copy.deepcopy(self.record)
    for name,cls in [('NativeOriginalSelfJob',Job),('NativeWriterRecoveryCut',Recovery),
                     ('NativePersonalOperatorAuthority',Operator),('NativeWriterHandoffReader',Approval),
                     ('PersonalNativeCoordination',MemoryLedger),('NativePersonalCoordinationImages',type(journal.ledger.images))]:
        monkeypatch.setattr(target,name,cls)
    monkeypatch.setattr(target,'_selected_source',lambda release:None)
    monkeypatch.setattr(target,'observe_self',lambda:copy.deepcopy(current[0]))
    dead=set()
    def exit_proof(identity):
        if body(identity) not in dead:raise ValueError('OFFLINE_OLD_OWNER_LIVE')
        return {'previous':identity,'OFFLINE_EXIT_PROVEN':True}
    monkeypatch.setattr(target,'verify_previous_exited',exit_proof)
    def build():
        job,recovery,operator,approval=Job(),Recovery(),Operator(),Approval()
        g=target.NativeWriterGeneration(job=job,recovery=recovery,operator=operator,approval=approval)
        # This explicit fixture record is NOT a genuine native local decision.
        def approve(context):
            approval.record={'schema':'ATLAS_PERSONAL_WRITER_HANDOFF_V1','origin':'LOCAL_OPERATOR',
                'action':'ACCEPT_NEW_WRITER_GENERATION_ONLY','operator_id':'OFFLINE_SID',
                'release_digest':g.release_digest,'runtime_id':g.runtime_id,'context':copy.deepcopy(context),
                'approval_id':'OFFLINE_DECISION_'+str(context['generation']),'issued_at':99,'expires_at':159}
        head=replay(g.journal.read(),g.journal.accounts)
        approve({'accounts':g.journal.accounts,'generation':0 if head is None else head['generation']+1,
                 'previous_owner':None if head is None else head['owner'],'new_owner':g.identity,
                 'cut_digest':digest(recovery.capture()),'previous_head':None if head is None else digest(head)})
        return g
    # journal had no records, but its account binding needs real fixture digests.
    journal.accounts=Operator.accounts;journal._binding=(journal.ledger,body(Operator.accounts))
    return SimpleNamespace(**locals())


def test_native_wrapper_composed_fresh_owner_generation_and_durable_fencing(native_model):
    m=native_model;g0=m.build();g0.accept();assert g0.verify()
    history=copy.deepcopy(g0.enrollments)
    m.current[0]=copy.deepcopy(NEW);g1=m.build()
    with pytest.raises(ValueError,match='OLD_OWNER_LIVE'):g1.accept()
    # Failed instance is terminal even if the external process later exits.
    m.dead.add(body(OLD))
    with pytest.raises(ValueError,match='SINGLE_USE'):g1.accept()
    g2=m.build();ack=g2.accept()
    assert ack['record']['generation']==1 and ack['paper_start_authorized'] is False
    with g2.scope():assert g2.verify()
    m.current[0]=copy.deepcopy(OLD)
    with pytest.raises(ValueError,match='FENCED'):g0.verify()
    assert g2.enrollments==history  # Historical writer PID assignments untouched.


@pytest.mark.parametrize('damage',['scope','time','account','sid','job','creation','approval-action','simulated-origin'])
def test_missing_or_conflicting_native_handoff_never_admits(native_model,damage):
    m=native_model;g=m.build()
    if damage=='scope':g.approval.record=None
    elif damage=='time':g.approval.record['expires_at']=99
    elif damage=='account':g.approval.record['context']['accounts']={}
    elif damage=='sid':g.approval.record['operator_id']='FOREIGN'
    elif damage=='job':g.job.bad=True
    elif damage=='creation':m.current[0]['creation_filetime']+=1
    elif damage=='approval-action':g.approval.record['action']='AUTO_PAPER'
    else:g.approval.record['origin']='DISPOSABLE_TEST'
    with pytest.raises(ValueError):g.accept()
    assert g.journal.read()['records']==[]


@pytest.mark.parametrize('phase',['before_prepare','after_prepare','after_active'])
def test_native_failure_is_terminal_and_never_returns_fake_ack(native_model,phase):
    m=native_model;g=m.build()
    def fault(p):
        if p==phase:raise RuntimeError('OFFLINE_CRASH')
    with pytest.raises(RuntimeError):g.accept(fault=fault)
    with pytest.raises(ValueError):g.verify()
    with pytest.raises(ValueError):g.accept()


def test_owned_operation_failure_poisoned_but_readonly_history_remains(native_model):
    g=native_model.build();g.accept()
    with pytest.raises(RuntimeError),g.scope():raise RuntimeError('OFFLINE_PUBLICATION_UNKNOWN')
    with pytest.raises(ValueError):g.verify()
    assert g.journal.read()['records'][-1]['state']=='ACTIVE'


def test_complete_new_owner_handoff_uses_real_generation_then_existing_operation_scope(native_model,monkeypatch):
    """Joined source orchestration; Windows/approval/account readers stay injected."""
    from threading import Lock
    from scripts.observation_runtime import personal_selected_paper_operation_issuer as operations
    m=native_model;initial=m.build();initial.accept()
    m.dead.add(body(OLD));m.current[0]=copy.deepcopy(NEW)
    successor=m.build();successor.accept()
    class ReadOnlyOwner:
        def __init__(self):self.job=successor.job;self.readback=successor.recovery.readback;self.calls=0
        def read_accounts(self):self.calls+=1;return successor.recovery.capture()
    monkeypatch.setattr(target,'NativeRecoveredReadOnlyOwner',ReadOnlyOwner)
    readonly=ReadOnlyOwner()
    owner=target.NativeRecoveredFinancialWriterOwner(readonly_owner=readonly,generation=successor)
    class Issuer:
        def __init__(self):
            self.owner=owner;self._ports=(owner,);self._session='OFFLINE_NEW_SESSION'
            self._revoke=False;self._lease_lock=Lock()
        def _verify_base(self):
            owner.require_exact_roster(qd=m.original['QUALITY_DIPS'],perp=m.original['HYPERLIQUID'])
            owner.require_financial_fence();return True
    monkeypatch.setattr(operations,'NativeSelectedPaperOperationIssuer',Issuer)
    issuer=Issuer()
    before=copy.deepcopy(m.original)
    with issuer._lease_lock,owner.financial_operation_scope(issuer):
        assert owner.verify_still_running() is True
        roster=successor.current_roster()
        assert len(roster['roles']['QUALITY_DIPS'])==5 and len(roster['roles']['HYPERLIQUID'])==7
        assert all(row['pid']==NEW['pid'] for rows in roster['roles'].values() for row in rows.values())
    assert readonly.calls>=3 and m.original==before
    assert owner._current_operation is None
    # The new owner cannot initialize an old account or start a financial session.
    assert not hasattr(owner,'observe_verified_initial_inceptions')


@pytest.mark.parametrize('actions',[None,[],['INITIALIZE_SIMULATED_ACCOUNTS'],['READ_ONLY','READ_ONLY']])
def test_recovered_owner_cannot_reuse_initial_activation_contract(native_model,monkeypatch,actions):
    from scripts.observation_runtime import personal_activation_commission as activation
    m=native_model;g=m.build();g.accept()
    class ReadOnlyOwner:
        def __init__(self):self.job=g.job;self.readback=g.recovery.readback
        def read_accounts(self):return g.recovery.capture()
    monkeypatch.setattr(target,'NativeRecoveredReadOnlyOwner',ReadOnlyOwner)
    owner=target.NativeRecoveredFinancialWriterOwner(readonly_owner=ReadOnlyOwner(),generation=g)
    with pytest.raises(ValueError,match='NO_INITIALIZATION_OR_IMPLICIT_SCOPE'):
        with activation.retain_activation_writer_guard(qd=m.original['QUALITY_DIPS'],
            perp=m.original['HYPERLIQUID'],release_digest=g.release_digest,owned_job=owner,actions=actions):
            pytest.fail('Recovered writer initialization admitted')


def test_recovered_owner_distinct_activation_guard_preserves_existing_publisher(native_model,monkeypatch):
    from scripts.observation_runtime import personal_activation_commission as activation
    m=native_model;g=m.build();g.accept()
    class ReadOnlyOwner:
        def __init__(self):self.job=g.job;self.readback=g.recovery.readback
        def read_accounts(self):return g.recovery.capture()
    monkeypatch.setattr(target,'NativeRecoveredReadOnlyOwner',ReadOnlyOwner)
    owner=target.NativeRecoveredFinancialWriterOwner(readonly_owner=ReadOnlyOwner(),generation=g)
    with activation.retain_activation_writer_guard(qd=m.original['QUALITY_DIPS'],
            perp=m.original['HYPERLIQUID'],release_digest=g.release_digest,owned_job=owner,
            actions=['READ_ONLY','CONNECT_APPROVED_DATA']) as checked:
        assert checked is owner  # Guard only. No activation record was published.


def test_native_wrapper_refuses_workspace_source_without_installation():
    with pytest.raises((ValueError,OSError)):
        target._selected_source('f'*64)


@pytest.mark.parametrize('damage',[None,'old-writers','missing-hl-role','mixed-current-process',
                                  'missing-original-account','bad-fence','unknown-writer'])
def test_versioned_qd_proof_keeps_historical_enrollment_separate_from_current_owner(damage):
    from app.services.quality_dips_autonomous_enrollment import validate_owned_snapshot
    from app.services.perp_operational_contract import WRITERS as HL_ROLES
    from test_quality_dips_autonomous_enrollment import fixture
    e=fixture().e;request={'OFFLINE_REQUEST':1}
    identity={'schema':'QD_OP_PROCESS_ID_V1',**NEW}
    roles={'QUALITY_DIPS':{k:copy.deepcopy(identity) for k in e['writers']},
           'HYPERLIQUID':{k:copy.deepcopy(identity) for k in HL_ROLES}}
    o={'schema':'QD_AUTO_NATIVE_OWNERSHIP_V5','request_digest':digest(request),
       'original_writers':copy.deepcopy(e['writers']),'writers':copy.deepcopy(roles['QUALITY_DIPS']),
       'writer_generation':{'schema':'ATLAS_NATIVE_CURRENT_WRITER_ROSTER_V1','generation':1,
            'fence_digest':'c'*64,'original_accounts':{'QUALITY_DIPS':digest(e),'HYPERLIQUID':'b'*64},'roles':roles},
       'resources':copy.deepcopy(e['resources']),'unknown_writers':[]}
    if damage=='old-writers':o['original_writers']['decision']['creation_filetime']+=1
    elif damage=='missing-hl-role':roles['HYPERLIQUID'].pop('mark')
    elif damage=='mixed-current-process':roles['HYPERLIQUID']['mark']['creation_filetime']+=1
    elif damage=='missing-original-account':o['writer_generation']['original_accounts'].pop('HYPERLIQUID')
    elif damage=='bad-fence':o['writer_generation']['fence_digest']='bad'
    elif damage=='unknown-writer':o['unknown_writers']=['FOREIGN']
    if damage is None:
        assert validate_owned_snapshot(o,request,e) is True
        assert e['writers']!=o['writers']
    else:
        with pytest.raises(ValueError):validate_owned_snapshot(o,request,e)


@pytest.mark.parametrize('value',[None,{}, {'pid':0,'creation_filetime':1,'image':'x'},
                                  {'pid':True,'creation_filetime':1,'image':'x'}])
def test_previous_process_cannot_be_adopted_from_incomplete_pid_proof(value):
    with pytest.raises(ValueError):target.verify_previous_exited(value)


def test_operator_decision_id_cannot_be_reused_for_a_different_generation(journal):
    def reused(context):return {'approval_id':'ONE_OFFLINE_DECISION','context':context}
    admit(journal,approval=reused)
    before=journal.read()
    with pytest.raises(ValueError,match='REPLAY'):admit(journal,NEW,approval=reused)
    assert journal.read()==before


@pytest.fixture
def native_process_api(monkeypatch):
    """No Win32 calls escape; ctypes only writes into test-owned buffers."""
    api=SimpleNamespace(handle=17,error=0,pids=[OLD['pid']],wait=0,observed={
        'creation_filetime':OLD['creation_filetime'],'image':OLD['image']},
        enum_ok=True,overflow=False,handle_pid=OLD['pid'],closed=[])
    class Fn:
        def __init__(self,call):self.call=call
        def __call__(self,*args):return self.call(*args)
    def enum(values,size,used):
        used._obj.value=size if api.overflow else 4*len(api.pids)
        for i,pid in enumerate(api.pids):values[i]=pid
        return api.enum_ok
    k=SimpleNamespace(OpenProcess=Fn(lambda *_:api.handle),
        GetProcessId=Fn(lambda _:api.handle_pid),WaitForSingleObject=Fn(lambda *_:api.wait),
        CloseHandle=Fn(lambda h:(api.closed.append(h) or True)))
    ps=SimpleNamespace(EnumProcesses=Fn(enum))
    monkeypatch.setattr(target.ctypes,'WinDLL',lambda name,**_:k if name=='kernel32' else ps)
    monkeypatch.setattr(target.ctypes,'get_last_error',lambda:api.error)
    from scripts.observation_runtime import atlas_r15_disposable_writer_process_audit as audit
    monkeypatch.setattr(audit,'_windows_handle_identity',lambda h:copy.deepcopy(api.observed))
    return api


@pytest.mark.parametrize('kind',['exited-held-process','absent-crosscheck','reused-pid'])
def test_exact_previous_writer_exclusion_requires_native_crosscheck(native_process_api,kind):
    a=native_process_api
    if kind=='absent-crosscheck':a.handle=0;a.error=87;a.pids=[]
    elif kind=='reused-pid':a.observed['creation_filetime']+=1
    assert target.verify_previous_exited(OLD)['previous_owner']==OLD
    assert a.closed==([] if not a.handle else [a.handle])


@pytest.mark.parametrize('damage',['alive','denied','omission-conflict','enum-error','enum-capacity',
                                  'wrong-handle','image','reuse-conflict','timeout'])
def test_ambiguous_native_previous_owner_never_becomes_exit_proof(native_process_api,monkeypatch,damage):
    a=native_process_api
    if damage=='alive':a.wait=258
    elif damage=='denied':a.handle=0;a.error=5;a.pids=[]
    elif damage=='omission-conflict':a.handle=0;a.error=87
    elif damage=='enum-error':a.enum_ok=False
    elif damage=='enum-capacity':a.overflow=True
    elif damage=='wrong-handle':a.handle_pid+=1
    elif damage=='image':a.observed['image']=r'D:\foreign.exe'
    elif damage=='reuse-conflict':a.observed['creation_filetime']+=1;a.pids=[]
    else:
        ticks=iter([0,2]);monkeypatch.setattr(target.time,'monotonic',lambda:next(ticks))
    with pytest.raises(ValueError):target.verify_previous_exited(OLD)
    assert a.closed==([] if not a.handle else [a.handle])


@pytest.fixture
def recovery_model(monkeypatch):
    clock=lambda:100
    ledgers={lane:MemoryLedger() for lane in ACCOUNTS}
    manifests={lane:{'OFFLINE_ACCOUNT':lane} for lane in ACCOUNTS}
    for lane,ledger in ledgers.items():
        ledger.manifest=manifests[lane];ledger._load=lambda db:None
        for sql in ('CREATE TABLE events(id TEXT)', 'CREATE TABLE autonomous_control(id TEXT)',
                    'CREATE TABLE autonomous_activity(id TEXT)','CREATE TABLE personal_sessions(id TEXT,state TEXT)',
                    'CREATE TABLE personal_publications(id TEXT,state TEXT)','CREATE TABLE projections(id TEXT,receipt TEXT)'):
            ledger.db.execute(sql)
        ledger.db.commit()
    class Cap:
        def __init__(self):
            self.clock=clock
            self.enrollments={lane:{'resources':{'custody':{'path':'OFFLINE_'+lane}},
                                   'inception_digest':digest(manifests[lane])} for lane in ACCOUNTS}
            self.readers={lane:SimpleNamespace(source=SimpleNamespace(ledger=ledgers[lane]),
                store=SimpleNamespace(enrollment=self.enrollments[lane])) for lane in ACCOUNTS}
            self.accounts={lane:{'source_revision':0,'report_revision':0,'observed_at':100,
                                'state':{'positions':{},'cash':'1000'}} for lane in ACCOUNTS}
        def require_readonly(self):return True
        def capture(self):return {'accounts':copy.deepcopy(self.accounts)}
        def bind_custody_readers(self,readers):self.bound=readers
    class Pins:
        def __init__(self,lane):self.ledger=ledgers[lane]
    class Portfolio:
        def __init__(self):
            self.execution_domain='LOCAL_ENROLLED';self.trust=Pins('QUALITY_DIPS');self.clock=clock
            self.authority=object()
            self.output=SimpleNamespace(root='OFFLINE_QUALITY_DIPS')
            self.manifest={'accounts':{k:digest(v) for k,v in manifests.items()}}
            self.cut={'state':{'entry_closed':True,'session':'OLD_SESSION','operations':{},
                'last_clock':100,'stop_context':{'schema':'ATLAS_DESKTOP_STOP_V1','session_id':'OLD_ID',
                    'command_id':'stop:'+digest(['OLD_SESSION','USER_SHUTDOWN']),
                    'reason':'USER_SHUTDOWN','requested_at':95},
                'finalized':{'grant_digest':'OLD_SESSION',
                    'outcomes':{lane:{'state':'ACKNOWLEDGED_FLAT_AND_DRAINED'} for lane in ACCOUNTS}}},
                'execution_domain':'LOCAL_ENROLLED'}
            self.capacity=4
        def snapshot(self):return copy.deepcopy(self.cut)
        def remaining_slots(self):return self.capacity
    class Orders:
        def __init__(self):
            self.execution_domain='LOCAL_ENROLLED';self.trust=Pins('HYPERLIQUID');self.clock=clock
            self.authority=object()
            self.output=SimpleNamespace(root='OFFLINE_HYPERLIQUID');self.manifest=manifests['HYPERLIQUID']
            self.cut={'state':{'orders':{}},'execution_domain':'LOCAL_ENROLLED'}
        def snapshot(self):return copy.deepcopy(self.cut)
    for name,cls in [('NativeTwoAccountCurrentReadback',Cap),('PersonalCurrentPins',Pins),
                     ('PortfolioControlStore',Portfolio),('RestingOrderStore',Orders)]:
        monkeypatch.setattr(target,name,cls)
    cap,portfolio,orders=Cap(),Portfolio(),Orders()
    yield SimpleNamespace(**locals())
    for ledger in ledgers.values():ledger.db.close()


def test_only_untouched_genesis_can_qualify_without_a_prior_stop_journal(recovery_model):
    m=recovery_model
    r=target.NativeWriterRecoveryCut(readback=m.cap)
    assert r.capture()['genesis_only'] is True
    m.cap.accounts['HYPERLIQUID']['source_revision']=1
    with pytest.raises(ValueError,match='DURABLE_STOP'):r.capture()


@pytest.mark.parametrize('damage',['exposure','funding','pending-publication','pending-session','projection',
                                  'orders','stop','missing-flat-ack','reservation','capacity','account','changed-cut',
                                  'missing-stop-context','wrong-stop-session','wrong-stop-grant'])
def test_native_recovery_checks_both_histories_orders_reservations_and_stop(recovery_model,damage):
    m=recovery_model
    r=target.NativeWriterRecoveryCut(readback=m.cap,portfolio=m.portfolio,orders=m.orders)
    assert r.capture()['genesis_only'] is False
    if damage=='exposure':m.cap.accounts['QUALITY_DIPS']['state']['positions']['x']={'remaining':'1'}
    elif damage=='funding':m.cap.accounts['HYPERLIQUID']['state']['positions']['x']={'remaining':'0','remaining_funding':'1'}
    elif damage in ('pending-publication','pending-session','projection'):
        table={'pending-publication':'personal_publications','pending-session':'personal_sessions','projection':'projections'}[damage]
        m.ledgers['HYPERLIQUID'].db.execute('INSERT INTO '+table+' VALUES(?,?)',('x',None))
        m.ledgers['HYPERLIQUID'].db.commit()
    elif damage=='orders':m.orders.cut['state']['orders']['x']={'state':'FILL_PENDING'}
    elif damage=='stop':m.portfolio.cut['state']['entry_closed']=False
    elif damage=='missing-flat-ack':m.portfolio.cut['state']['finalized']['outcomes']['HYPERLIQUID']['state']='UNKNOWN'
    elif damage=='reservation':m.portfolio.cut['state']['operations']['x']={'state':'RESERVED'}
    elif damage=='capacity':m.portfolio.capacity=2
    elif damage=='account':m.portfolio.manifest['accounts']['QUALITY_DIPS']='wrong'
    elif damage=='missing-stop-context':m.portfolio.cut['state'].pop('stop_context')
    elif damage=='wrong-stop-session':m.portfolio.cut['state']['stop_context']['command_id']='stop:wrong'
    elif damage=='wrong-stop-grant':m.portfolio.cut['state']['finalized']['grant_digest']='wrong'
    else:
        original=m.cap.capture
        def changed():
            v=original();m.cap.accounts['QUALITY_DIPS']['report_revision']+=1;return v
        m.cap.capture=changed
    with pytest.raises((ValueError,KeyError)):r.capture()
