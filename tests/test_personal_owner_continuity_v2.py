"""Offline versioned owner-boundary contracts; no native owner/account is made."""
import copy
from threading import Lock
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import body,digest
from scripts.observation_runtime import personal_owner_continuity_v2 as target
from scripts.observation_runtime import personal_native_selected_owned_job_preflight as owner_module
from scripts.observation_runtime import personal_selected_paper_operation_issuer as operation
from test_personal_native_selected_owned_job_preflight import _synthetic_inception_owner


@pytest.fixture
def current_model(monkeypatch):
    class Clock:
        now=1794900000
        def __call__(self):return self.now
    clock=Clock()
    class Images:pass
    class Ledger:
        def __init__(self):self.images=Images()
    class Pins:
        def __init__(self,ledger):self.ledger=ledger
    class Ownership:
        read_only=True
    class Projection:pass
    class FinancialAuthority:
        def __init__(self,owner,source):self.ownership,self.source=owner,source
    class NativeReader:
        def read_committed(self):
            return {'source_pin':copy.deepcopy(q.cut['source']),
                    'state':copy.deepcopy(q.state)}
    class ReadAuthority:pass
    class Presentation:pass
    class Bootstrap:pass
    class Publication:
        def __init__(self,ledger):self.ledger=ledger
        def acknowledged(self,_):return None,{'ack':'QD'}
    def account(lane):
        return {'account_id':'OFFLINE_'+lane,'epoch':'OFFLINE_'+lane,
                'release_digest':'f'*64,'lane':lane}
    def cut(lane):
        return {'source':{'root':[1,1 if lane=='QD' else 2,0],
                          'inception':{'id':[1,5,0],'sha256':'a'*64},'entries':[]},
                'reports':{'root':[1,3 if lane=='QD' else 4,0],
                           'scope':{'id':[1,6,0],'sha256':'b'*64},
                           'reports':[{'id':[1,7,0],'sha256':'c'*64}]},
                'source_revision':0,'report_revision':0,
                'state':{'positions':{},'cash':'1000'},'genesis_ack_digest':'d'*64}
    class QD:
        def __init__(self):
            self.clock=clock;self.state={'positions':{},'cash':'1000'}
            self.cut=cut('QD')
            self.bootstrap=Bootstrap();self.bootstrap.enrollment=account('QUALITY_DIPS')
            self.bootstrap.scope=lambda:{'operation_id':'SYNTHETIC_QD'}
            ledger=Ledger();self.source,self.reports=Pins(ledger),Pins(ledger)
            self.bootstrap.publication=Publication(ledger)
            own=Ownership();fin=FinancialAuthority(own,self.source)
            self.native_reader=NativeReader()
            self.native_reader.dependencies=(None,self.source,fin,clock,Projection())
            auth=ReadAuthority();auth.ownership=own;auth.bootstrap=self.bootstrap
            auth.source,auth.reports=self.source,self.reports
            self.reader=Presentation();self.reader.port=self.native_reader;self.reader.authority=auth
        def _capture(self,now):
            data=copy.deepcopy(self.cut)
            data['state_digest']=digest(self.state)
            return data,1,{}
    class HL:
        def __init__(self):
            self.clock=clock;self.data=cut('HL')
            self.bootstrap=SimpleNamespace(enrollment=account('HYPERLIQUID'))
            self.store=SimpleNamespace(authority=SimpleNamespace(ownership=Ownership()))
        def capture(self):return {**copy.deepcopy(self.data),'observed_at':clock()}
    for name,cls in {
            'PersonalRuntimeCurrent':QD,'PersonalPerpRuntimeCurrent':HL,
            'NativeVersionSafePaperOperatorClock':Clock,
            'OperationalAutonomousSelectedRead':Presentation,
            'OperationalAutonomousReader':NativeReader,
            'PersonalNativeReadAuthority':ReadAuthority,
            'NativePersonalWriterOwnership':Ownership,
            'PersonalCurrentPins':Pins,'PersonalNativeCoordination':Ledger,
            'NativePersonalCoordinationImages':Images,
            'NativePersonalFinancialReadAuthority':FinancialAuthority,
            'ProjectionTarget':Projection}.items():
        monkeypatch.setattr(target,name,cls)
    monkeypatch.setattr(target,'PersonalInceptionBootstrap',Bootstrap)
    monkeypatch.setattr(target,'PersonalPublicationCustody',Publication)
    monkeypatch.setattr(target,'validate_personal_inception',lambda e:(e['lane'],e,{}))
    monkeypatch.setattr(target,'require_installed_continuity_source',lambda release:None)
    monkeypatch.setattr(target,'require_version_safe_release_digest',lambda **_:True)
    monkeypatch.setattr(target,'verify_original_account_roots',lambda _:True)
    q,h=QD(),HL()
    cap=target.NativeTwoAccountCurrentReadback(quality_dips=q,hyperliquid=h,
                                            clock=clock,runtime_id='OFFLINE_CURRENT')
    return SimpleNamespace(**locals())


def test_two_original_accounts_use_current_readers_without_financial_grants(current_model):
    result=current_model.cap.capture()
    assert set(result['accounts'])=={'QUALITY_DIPS','HYPERLIQUID'}
    assert result['financial_write_authority'] is False
    assert result['paper_start_authority'] is False


def test_current_readers_accept_append_only_reports_and_keep_original_genesis(current_model):
    m=current_model;m.cap.capture()
    m.q.cut['reports']['reports'].append({'id':[1,8,0],'sha256':'e'*64})
    m.q.cut['report_revision']=1
    m.h.data['reports']['reports'].append({'id':[1,9,0],'sha256':'f'*64})
    m.h.data['report_revision']=1
    assert m.cap.capture()['accounts']['HYPERLIQUID']['report_revision']==1


@pytest.mark.parametrize('damage',['source-prefix','report-prefix','genesis','same-revision-state',
                                  'account','release','clock','reader'])
def test_conflicting_or_changed_two_account_evidence_refuses(current_model,damage):
    m=current_model;m.cap.capture()
    if damage=='source-prefix':m.h.data['source']['root']=[9,99,0]
    elif damage=='report-prefix':m.q.cut['reports']['reports'][0]['sha256']='e'*64
    elif damage=='genesis':m.h.data['genesis_ack_digest']='c'*64
    elif damage=='same-revision-state':m.q.state['cash']='999'
    elif damage=='account':m.q.bootstrap.enrollment['account_id']='WRONG'
    elif damage=='release':m.cap.release_digest='a'*64
    elif damage=='clock':m.q.clock=lambda:123
    else:m.cap.readers['HYPERLIQUID']=object()
    with pytest.raises((ValueError,AttributeError)):m.cap.capture()


def test_double_collect_rejects_a_changed_account_between_independent_lanes(current_model):
    m=current_model;old=m.h.capture
    def changed():
        result=old();m.q.state['cash']='999';return result
    m.h.capture=changed
    with pytest.raises(ValueError,match='TWO_ACCOUNT_CUT_CHANGED'):m.cap.capture()


def test_two_account_capture_refuses_expired_observation(current_model):
    m=current_model;old=m.h.capture
    def delayed():m.clock.now+=6;return old()
    m.h.capture=delayed
    with pytest.raises(ValueError,match='CAPTURE_EXPIRED'):m.cap.capture()


@pytest.mark.parametrize('damage',['projection','source-authority','read-authority','read-only-boolean'])
def test_current_readback_never_accepts_a_self_certified_qd_port(current_model,damage):
    m=current_model
    if damage in ('projection','source-authority'):
        ports=list(m.q.native_reader.dependencies)
        ports[4 if damage=='projection' else 2]=object()
        m.q.native_reader.dependencies=tuple(ports)
    elif damage=='read-authority':m.q.reader.authority=object()
    else:m.q.reader.authority.ownership=SimpleNamespace(read_only=True)
    with pytest.raises(ValueError,match='CONCRETE_NATIVE_READ_CHAIN'):m.cap.capture()


def test_unaccepted_version_safe_clock_cannot_be_treated_as_a_current_readback(current_model,monkeypatch):
    monkeypatch.setattr(target,'require_version_safe_release_digest',lambda **_:False)
    with pytest.raises(ValueError,match='NATIVE_CLOCK_RELEASE_REFUSED'):current_model.cap.capture()


def test_absent_original_twelve_root_evidence_never_becomes_current_acceptance(current_model,monkeypatch):
    monkeypatch.setattr(target,'verify_original_account_roots',lambda _:False)
    with pytest.raises(ValueError,match='ORIGINAL_NATIVE_RESOURCE_EVIDENCE_MISSING'):
        current_model.cap.capture()


@pytest.mark.parametrize('wrong',['q-writer','h-writer'])
def test_cold_recovery_cannot_inherit_writable_native_ports(current_model,wrong):
    m=current_model
    port=m.q.reader.authority.ownership if wrong=='q-writer' else m.h.store.authority.ownership
    port.read_only=False
    with pytest.raises(ValueError,match='READONLY_NATIVE_LEASES'):m.cap.require_readonly()


def test_fresh_readonly_owner_retains_new_identity_and_never_adopts_old_writers(current_model,monkeypatch):
    m=current_model
    identity={'pid':123,'creation_filetime':456,'image':r'D:\OFFLINE_ONLY.exe'}
    class Job:
        def __init__(self):self.identity=copy.deepcopy(identity);self.revoked=False
        def verify(self):
            if self.revoked:raise ValueError('MOCK_JOB_REVOKED')
            return True
    monkeypatch.setattr(target,'NativeOriginalSelfJob',Job)
    monkeypatch.setattr(target,'observe_self',lambda:copy.deepcopy(identity))
    job=Job();recovered=target.NativeRecoveredReadOnlyOwner(original_self_job=job,readback=m.cap)
    before=body(m.cap.enrollments)
    result=recovered.read_accounts()
    assert result['observer_identity']==identity
    assert result['writer_admission_authorized'] is False
    assert body(m.cap.enrollments)==before
    with pytest.raises(ValueError,match='CANNOT_ADOPT_FINANCIAL_WRITERS'):
        recovered.require_exact_roster(qd={},perp={})
    job.revoked=True
    with pytest.raises(ValueError,match='MOCK_JOB_REVOKED'):recovered.read_accounts()
    job.revoked=False
    with pytest.raises(ValueError,match='IDENTITY_CHANGED'):recovered.read_accounts()


def test_new_continuity_module_cannot_claim_to_be_installed_in_frozen_r23():
    with pytest.raises(ValueError):target.require_installed_continuity_source('f'*64)


@pytest.mark.parametrize('bad',['missing-job','missing-handle-proof','foreign-process'])
def test_recovery_cannot_adopt_unverified_or_exited_process_identity(current_model,monkeypatch,bad):
    identity={'pid':123,'creation_filetime':456,'image':r'D:\OFFLINE_READER.exe'}
    class Job:
        identity={'pid':122,'creation_filetime':455,'image':r'D:\OLD_OFFLINE_WRITER.exe'}
        def verify(self):return bad!='missing-handle-proof'
    monkeypatch.setattr(target,'NativeOriginalSelfJob',Job)
    monkeypatch.setattr(target,'observe_self',lambda:identity)
    with pytest.raises(ValueError):
        target.NativeRecoveredReadOnlyOwner(
            original_self_job=None if bad=='missing-job' else Job(),
            readback=current_model.cap)


def warm_model(monkeypatch):
    """Reuse existing explicitly synthetic state-machine fixture, never native."""
    owner,observed,q,h,_=_synthetic_inception_owner(monkeypatch)
    owner._current_readback=None;owner._current_operation=None
    owner.release_digest=owner._original_qd['release_digest']
    clock=lambda:1794900000
    for n,bootstrap in enumerate((q,h),1):
        bootstrap.clock=clock
        bootstrap.current.update(source={'entries':[],'root':[1,n,0]},
                                 reports={'reports':[{'id':[1,n+2,0],'sha256':'a'*64}]})
    owner.observe_verified_initial_inceptions(qd_bootstrap=q,hl_bootstrap=h)
    class Readback:
        def __init__(self):
            self.release_digest=owner.release_digest;self.clock=clock;self.runtime_id='MOCK_RUNTIME'
            self.enrollments={'QUALITY_DIPS':owner._original_qd,'HYPERLIQUID':owner._original_perp}
            self.bad=False;self.calls=0
        def capture(self):
            self.calls+=1
            if self.bad:raise ValueError('MOCK_CURRENT_REPLAY_REFUSED')
            accounts={}
            for lane,bootstrap in zip(('QUALITY_DIPS','HYPERLIQUID'),(q,h),strict=True):
                _,ack=bootstrap.publication.acknowledged(bootstrap.scope()['operation_id'])
                accounts[lane]={'source':copy.deepcopy(bootstrap.current['source']),
                                'reports':copy.deepcopy(bootstrap.current['reports']),
                                'genesis_ack_digest':digest(ack),'source_revision':0,'report_revision':0}
            return {'accounts':accounts}
    monkeypatch.setattr(target,'NativeTwoAccountCurrentReadback',Readback)
    cap=Readback()
    return SimpleNamespace(**locals())


def test_original_owner_explicit_handoff_preserves_initial_acks_and_uses_current_reads(monkeypatch):
    m=warm_model(monkeypatch)
    result=m.owner.accept_current_readback(readback=m.cap)
    assert result['initial_acks_preserved'] and not result['paper_start_authorized']
    assert m.owner._phase=='CURRENT_READBACK_ONLY'
    # The actual initial-reader callback now refuses any re-use. Current mode
    # must re-audit through the concrete bound current-reader port instead.
    m.q.verify_publication=lambda:pytest.fail('INITIAL_READER_REUSED_AFTER_HANDOFF')
    assert m.owner.verify_still_running()
    assert m.owner.require_current_clock(clock=m.clock,runtime_id='MOCK_RUNTIME')
    with pytest.raises(ValueError,match='ONE_CURRENT_FINANCIAL_CLOCK'):
        m.owner.require_current_clock(clock=lambda:0,runtime_id='MOCK_RUNTIME')


@pytest.mark.parametrize('damage',['foreign-enrollment','wrong-clock','changed-genesis'])
def test_current_handoff_refuses_incomplete_or_conflicting_original_binding(monkeypatch,damage):
    m=warm_model(monkeypatch)
    if damage=='foreign-enrollment':m.cap.enrollments={}
    elif damage=='wrong-clock':m.cap.clock=lambda:1
    else:
        real=m.cap.capture
        def bad():
            result=real();result['accounts']['HYPERLIQUID']['genesis_ack_digest']='f'*64
            return result
        m.cap.capture=bad
    with pytest.raises(ValueError):m.owner.accept_current_readback(readback=m.cap)
    assert m.owner._phase=='INITIAL_READBACK_ONLY'


@pytest.mark.parametrize('fail',['body','expired','current-readback'])
def test_owned_operation_failure_is_terminal_without_private_phase_recovery(monkeypatch,fail):
    m=warm_model(monkeypatch);m.owner.accept_current_readback(readback=m.cap)
    class Issuer:
        _session='MOCK_SESSION';_ports=();_revoke=False
        def __init__(self):self.owner=m.owner;self._lease_lock=Lock()
        def _verify_base(self):return True
    monkeypatch.setattr(operation,'NativeSelectedPaperOperationIssuer',Issuer)
    issuer=Issuer();mono=[10.0]
    monkeypatch.setattr(owner_module.time,'monotonic',lambda:mono[0])
    with issuer._lease_lock,pytest.raises(ValueError):
        with m.owner.financial_operation_scope(issuer):
            assert m.owner.verify_still_running()
            if fail=='body':raise ValueError('MOCK_OPERATION_UNCERTAIN')
            if fail=='expired':mono[0]+=6
            else:m.cap.bad=True
    assert m.owner._phase=='CURRENT_READBACK_UNKNOWN'
    assert m.owner._current_operation is None
    with pytest.raises(ValueError,match='CURRENT_UNCERTAIN_RECONCILIATION'):
        m.owner.verify_still_running()


def test_quiescent_audit_brackets_owned_pending_without_self_certified_success(monkeypatch):
    m=warm_model(monkeypatch);m.owner.accept_current_readback(readback=m.cap)
    class Issuer:
        _session='MOCK_SESSION';_ports=();_revoke=False
        def __init__(self):self.owner=m.owner;self._lease_lock=Lock()
        def _verify_base(self):return True
    monkeypatch.setattr(operation,'NativeSelectedPaperOperationIssuer',Issuer)
    issuer=Issuer();calls=m.cap.calls
    with issuer._lease_lock,m.owner.financial_operation_scope(issuer):
        m.cap.bad=True  # Model only: in-flight replay is not a clean idle cut.
        assert m.owner.verify_still_running()  # Native identity continuity still checked.
        m.cap.bad=False
    assert m.cap.calls==calls+2
    assert m.owner._phase=='CURRENT_READBACK_ONLY'


def test_idle_current_readback_failure_is_latched_and_cannot_be_silently_retried(monkeypatch):
    m=warm_model(monkeypatch);m.owner.accept_current_readback(readback=m.cap)
    m.cap.bad=True
    with pytest.raises(ValueError,match='MOCK_CURRENT_REPLAY_REFUSED'):m.owner.verify_still_running()
    m.cap.bad=False
    with pytest.raises(ValueError,match='CURRENT_UNCERTAIN_RECONCILIATION'):
        m.owner.verify_still_running()


def test_unowned_operation_scope_is_rejected_before_account_readback(monkeypatch):
    m=warm_model(monkeypatch);m.owner.accept_current_readback(readback=m.cap)
    calls=m.cap.calls
    with pytest.raises(ValueError,match='EXACT_SERIAL_OPERATION'),m.owner.financial_operation_scope(object()):
        pytest.fail('UNKNOWN_OPERATION_ADMITTED')
    assert m.cap.calls==calls and m.owner._phase=='CURRENT_READBACK_ONLY'


def test_operation_scope_does_not_replace_the_independent_financial_authority(monkeypatch):
    m=warm_model(monkeypatch);m.owner.accept_current_readback(readback=m.cap)
    class Issuer:
        _session='MOCK_SESSION';_ports=();_revoke=False
        def __init__(self):self.owner=m.owner;self._lease_lock=Lock()
        def _verify_base(self):return False
    monkeypatch.setattr(operation,'NativeSelectedPaperOperationIssuer',Issuer)
    issuer=Issuer()
    with issuer._lease_lock,pytest.raises(ValueError,match='OPERATION_AUTHORITY_REFUSED'):
        with m.owner.financial_operation_scope(issuer):
            pytest.fail('OWNER_SCOPE_MINTED_FINANCIAL_AUTHORITY')
    assert m.owner._phase=='CURRENT_READBACK_ONLY' and m.owner._current_operation is None


@pytest.mark.parametrize('damage',[None,'root-alias','unknown-custody','missing-root'])
def test_native_root_metadata_boundary_closes_all_handles_on_failure(monkeypatch,damage):
    from test_personal_r16_owned_job_activation import rosters
    from scripts.observation_runtime import personal_paper_inception as inception
    _,qd,hl=rosters()
    enrollments={'QUALITY_DIPS':qd,'HYPERLIQUID':hl}
    if damage=='root-alias':hl['resources']['source']['native_id']=qd['resources']['source']['native_id']
    elif damage=='missing-root':hl['resources'].pop('custody')
    roots={v['path']:(lane,role,v['native_id']) for lane,e in enrollments.items()
           for role,v in e['resources'].items()}
    opened=[];closed=[]
    class Output:
        def __init__(self,path):self.root=path;self.root_handle=path;opened.append(path)
        def _verify(self):return True
        def close(self):closed.append(self.root)
    native=SimpleNamespace(w=SimpleNamespace(WindowsOutput=Output),
                           native=SimpleNamespace(file_identity=lambda handle:roots[handle][2]))
    monkeypatch.setattr(target,'native_primitives',lambda:native)
    def path(value):
        names=[SimpleNamespace(name='UNAPPROVED.json')] if (
            damage=='unknown-custody' and roots[str(value)][:2]==('HYPERLIQUID','custody')) else []
        return SimpleNamespace(iterdir=lambda:iter(names))
    monkeypatch.setattr(inception,'Path',path)
    if damage is None:assert target.verify_original_account_roots(enrollments)
    else:
        with pytest.raises(ValueError):target.verify_original_account_roots(enrollments)
    assert opened==closed
