"""Offline independent review of the successor correction. No native writes.

Every Windows, approval, clock and publisher port is explicitly injected.
These cases establish source sequencing/refusal, never native commissioning.
"""
import copy
from builtins import ExceptionGroup
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import digest
from scripts.observation_runtime import personal_native_original_self_job as jobs
from scripts.observation_runtime import personal_owner_continuity_v2 as owners
from scripts.observation_runtime import personal_activation_commission as activation


@pytest.fixture
def admission_model(monkeypatch):
    from scripts.observation_runtime import personal_release_identity as releases
    from scripts.observation_runtime import personal_version_safe_release_clock as clocks
    from scripts.observation_runtime import personal_native_financial_release_origin as origins
    from scripts import release_selection_store as selectors
    head=['OFFLINE_HEAD'];events=[]
    class Release:
        artifact_digest='f'*64
        source_commit='f'*40
        root=Path(jobs.__file__).absolute().parents[2]
        def __init__(self):self.closed=False;events.append('FULL_PREPARATION_BEFORE_MANIFESTS')
        def verify(self,*,release_digest):
            if self.closed or release_digest!=self.artifact_digest:raise ValueError('OFFLINE_RETAINED_HANDLE_LOST')
            events.append('RETAINED_CONTINUITY')
            return {'source_commit':self.source_commit,'process':{'pid':123,'creation_filetime':456,'image':r'D:\fixture.exe'}}
    class Store:
        def __init__(self,**_):pass
        def locked(self):return nullcontext()
        def records(self):return []
        def close(self):events.append('SELECTOR_CLOSED')
    def origin(**kwargs):
        assert kwargs['release_digest']=='f'*64
        return {'selected_code_release':'f'*40,'selected_artifact_digest_bound':True,
                'financial_writer_lease_issued':False,'financial_activation_published':False,
                'paper_start_authorized':False,'live_trading_authorized':False}
    monkeypatch.setattr(releases,'NativePersonalReleaseIdentity',Release)
    monkeypatch.setattr(selectors,'NativeSelectionStore',Store)
    monkeypatch.setattr(clocks,'admit_version_safe_clock_source',lambda **_:(head[0],{}))
    monkeypatch.setattr(origins,'validate_origin',origin)
    release=Release();ticket=jobs.NativeFinancialReleaseAdmission(release=release)
    return SimpleNamespace(**locals())


def test_retained_admission_never_reopens_full_release_inside_fresh_window(admission_model):
    m=admission_model
    for _ in range(8):m.ticket.verify(release_digest='f'*64)
    assert m.events.count('FULL_PREPARATION_BEFORE_MANIFESTS')==1
    assert m.events.count('SELECTOR_CLOSED')==9


@pytest.mark.parametrize('damage',['closed','head','digest','release-port','module-root'])
def test_retained_release_handle_or_selection_failure_latches_terminal(admission_model,damage):
    m=admission_model
    if damage=='closed':m.release.closed=True
    elif damage=='head':m.head[0]='OTHER_HEAD'
    elif damage=='release-port':m.ticket.release=object()
    elif damage=='module-root':m.release.root=Path('D:/Other')
    with pytest.raises(ValueError):m.ticket.verify(release_digest='e'*64 if damage=='digest' else 'f'*64)
    # An ordinary mismatch never returns an origin/financial proof.
    assert m.events.count('FULL_PREPARATION_BEFORE_MANIFESTS')==1


@pytest.mark.parametrize('fake',[None,True,{},SimpleNamespace(verify=lambda **_:True)])
def test_json_and_boolean_cannot_replace_retained_native_release(fake):
    with pytest.raises(ValueError):jobs.NativeFinancialReleaseAdmission(release=fake)


@pytest.fixture
def read_activation_model(monkeypatch):
    from test_personal_r16_owned_job_activation import rosters
    from scripts.observation_runtime import personal_existing_native_resource_evidence as metadata
    from scripts.observation_runtime import personal_version_safe_release_clock as clocks
    _,qd,hl=rosters()
    for e in (qd,hl):e['release_digest']='f'*64
    identity={'pid':8181,'creation_filetime':123456,'image':r'D:\new-fixture.exe'}
    class Job:
        def __init__(self):self.identity=copy.deepcopy(identity);self.valid=True
        def verify(self):
            if not self.valid:raise ValueError('OFFLINE_NATIVE_JOB_LOST')
            return True
    roots={'lanes':{lane:{'roots':{role:{'path':r['path'],'native_id':r['native_id'],
           'native_identity_verified':True,'existing_empty_namespace_verified':False}
           for role,r in e['resources'].items()}} for lane,e in [('QUALITY_DIPS',qd),('HYPERLIQUID',hl)]}}
    events=[];head=['HEAD']
    monkeypatch.setattr(owners,'NativeOriginalSelfJob',Job)
    monkeypatch.setattr(owners,'observe_self',lambda:copy.deepcopy(identity))
    def original(release,admission=None):events.append('ONE_DEEP_ADMISSION');return {'origin':'OFFLINE'}
    monkeypatch.setattr(owners,'require_installed_continuity_source',original)
    monkeypatch.setattr(clocks,'require_native_version_safe_clock_source',lambda *,deep:(head[0] if deep is False else pytest.fail('deep reopen')))
    monkeypatch.setattr(activation,'verify_enrollment_native_roots',lambda e:events.append('NATIVE_ROOT_IDS_ACLS'))
    monkeypatch.setattr(metadata,'inspect_two_lane_native_roots',lambda:copy.deepcopy(roots))
    job=Job();guard=owners.NativeReadOnlyRecoveryActivationGuard(job=job,qd=qd,perp=hl,release_digest='f'*64)
    return SimpleNamespace(**locals())


def test_fresh_read_activation_precedes_reader_writer_without_claiming_historical_pids_live(read_activation_model):
    m=read_activation_model
    assert all(p['pid']!=m.identity['pid'] for p in m.qd['writers'].values())
    with activation.retain_activation_writer_guard(qd=m.qd,perp=m.hl,release_digest='f'*64,
            owned_job=m.guard,actions=['READ_ONLY']) as guard:
        assert guard is m.guard and guard.verify_still_running()
    assert m.events.count('ONE_DEEP_ADMISSION')==1
    assert not hasattr(m.guard,'financial_operation_scope')
    assert not hasattr(m.guard,'generation')


@pytest.mark.parametrize('actions',[None,[],['AUTO_PAPER'],['READ_ONLY','AUTO_PAPER'],
                                  ['INITIALIZE_SIMULATED_ACCOUNTS'],['CONNECT_APPROVED_DATA']])
def test_recovery_bootstrap_cannot_publish_financial_source_or_initialization_grants(read_activation_model,actions):
    m=read_activation_model
    with pytest.raises(ValueError,match='STRICTLY_READ_ONLY'):
        with activation.retain_activation_writer_guard(qd=m.qd,perp=m.hl,release_digest='f'*64,
                owned_job=m.guard,actions=actions):pytest.fail('broader activation admitted')


@pytest.mark.parametrize('damage',['job','process','root-id','alias','unverified','head','admission'])
def test_readonly_bootstrap_missing_native_identity_stays_blocked(read_activation_model,damage):
    m=read_activation_model
    if damage=='job':m.job.valid=False
    elif damage=='process':m.identity['creation_filetime']+=1
    elif damage=='head':m.head[0]='OTHER'
    elif damage=='admission':m.guard._release_admission=object()
    else:
        root=m.roots['lanes']['HYPERLIQUID']['roots']['source']
        if damage=='root-id':root['native_id']=[9,9,9]
        elif damage=='alias':m.guard.enrollments['HYPERLIQUID']['resources']['source']['native_id']=m.qd['resources']['source']['native_id']
        else:root['native_identity_verified']=False
    with pytest.raises(ValueError):m.guard.verify_still_running()


@pytest.mark.parametrize('outcome',['success','publisher-failure','missing-admission','wrong-clock'])
def test_original_activation_can_borrow_prequalified_clock_and_never_repeat_deep_scan(admission_model,monkeypatch,outcome):
    from test_personal_r16_owned_job_activation import rosters
    from scripts.observation_runtime import personal_native_selected_owned_job_preflight as native_owner
    from scripts.observation_runtime import personal_native_financial_release_origin as origin
    m=admission_model;_,qd,hl=rosters()
    for e in (qd,hl):e['release_digest']='f'*64
    accounts={'QUALITY_DIPS':digest(qd),'HYPERLIQUID':digest(hl)}
    policy=json.loads((Path(__file__).parents[1]/'docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json').read_bytes())
    record={'schema':'ATLAS_PERSONAL_ACTIVATION_V1','origin':'LOCAL_OPERATOR','actions':['READ_ONLY'],
            'accounts':accounts,'release_digest':'f'*64,'policy_digest':digest(policy)}
    values={'record':record,'policy':policy,'accounts':accounts,'quality_dips_enrollment':qd,'hyperliquid_enrollment':hl}
    class Owner:
        release_digest='f'*64;_phase='INITIAL_READBACK_ONLY'
        _initial_cuts=(None,None);_initial_bootstraps=(None,None)
        def __init__(self):
            self._release_admission=m.ticket if outcome!='missing-admission' else None
            self.origin=m.ticket.verify(release_digest='f'*64)
        def require_exact_roster(self,**_):return True
        def verify_still_running(self):return True
    class Clock:
        def __init__(self):self.revoked=False
        def require_operational(self,runtime):assert runtime=='OFFLINE_RUNTIME'
        def revoke(self):self.revoked=True
    clock=Clock();events=[]
    monkeypatch.setattr(native_owner,'RetainedSelectedNativeOwnerPreflight',Owner)
    monkeypatch.setattr(activation,'NativeVersionSafePaperOperatorClock',Clock)
    monkeypatch.setattr(activation,'require_version_safe_release_digest',lambda **_:True)
    monkeypatch.setattr(activation,'current_sid',lambda:'OFFLINE_SID')
    monkeypatch.setattr(activation,'read_bounded_activation_input',lambda path,*,role:copy.deepcopy(values[role]))
    monkeypatch.setattr(activation,'verify_enrollment_native_roots',lambda e:None)
    monkeypatch.setattr(origin,'require_selected_native_origin',lambda **_:pytest.fail('deep origin repeated in fresh window'))
    def publish(**kwargs):
        assert kwargs['clock'] is clock;events.append('CONTROL_RECORD_ONLY')
        if outcome=='publisher-failure':raise ValueError('OFFLINE_UNKNOWN_PUBLICATION')
        return {'status':'OFFLINE_ONLY_NOT_NATIVE_ACCEPTANCE'}
    monkeypatch.setattr(activation,'publish_personal_activation',publish)
    args=dict(root=r'D:\AtlasCustody\PersonalPaper\offline-review',record_path='x',policy_path='x',
        release_digest='f'*64,accounts_path='x',expected_clock_source=activation.SOURCE,runtime_id='OFFLINE_RUNTIME',
        qd_enrollment_path='x',perp_enrollment_path='x',clock_profile=activation.VERSION_SAFE_NTP_PROFILE,
        owned_job=Owner(),prequalified_clock=object() if outcome=='wrong-clock' else clock)
    if outcome=='success':
        assert activation.commission(**args)['status']=='OFFLINE_ONLY_NOT_NATIVE_ACCEPTANCE'
        assert clock.revoked is False
    else:
        with pytest.raises(ValueError):activation.commission(**args)
        if outcome=='publisher-failure':assert clock.revoked is True
    assert m.events.count('FULL_PREPARATION_BEFORE_MANIFESTS')==1


def test_native_root_close_failure_attempts_every_acquired_handle(monkeypatch):
    from test_personal_r16_owned_job_activation import rosters
    _,qd,hl=rosters();opened=[];attempted=[]
    roots={r['path']:r['native_id'] for e in (qd,hl) for r in e['resources'].values()}
    class Output:
        def __init__(self,path):self.root=self.root_handle=path;opened.append(path)
        def close(self):
            attempted.append(self.root)
            if self.root==opened[0]:raise OSError('OFFLINE_CLOSE_FAILED')
    native=SimpleNamespace(w=SimpleNamespace(WindowsOutput=Output),
                           native=SimpleNamespace(file_identity=lambda h:roots[h]))
    monkeypatch.setattr(owners,'native_primitives',lambda:native)
    monkeypatch.setattr(owners,'verify_all_native_inception_roots',lambda *_:True)
    with pytest.raises(ExceptionGroup,match='HANDLE_CLEANUP_FAILED'):
        owners.verify_original_account_roots({'QUALITY_DIPS':qd,'HYPERLIQUID':hl})
    assert attempted==opened and len(attempted)==6
