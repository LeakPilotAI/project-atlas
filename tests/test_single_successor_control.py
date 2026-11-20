"""Offline CODE-ONLY operator-support boundaries, never real local decisions."""
import json
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest
from scripts import atlas_single_successor_control as control


def test_headless_or_remote_input_cannot_create_a_local_decision(monkeypatch):
    monkeypatch.setattr(control.sys,'stdin',SimpleNamespace(isatty=lambda:False))
    with pytest.raises(ValueError,match='VISIBLE_WINDOWS_LOCAL'):control.visible_local_console()


@pytest.mark.parametrize('mode',['execute-install','execute-select'])
def test_no_execution_without_explicit_local_decision_pin(mode,monkeypatch):
    monkeypatch.setattr(control,'execute',lambda *_:pytest.fail('execution reached'))
    with pytest.raises(ValueError,match='LOCAL_DECISION_PIN_REQUIRED'):
        control.main(['--proposal','unused','--proposal-sha256','a'*64,'--mode',mode])


def test_default_review_cannot_reach_console_or_native_copy(monkeypatch):
    monkeypatch.setattr(control,'proposal',lambda *_:{'source_commit':'a'*40,'timing_policy':control.timing_policy()})
    monkeypatch.setattr(control,'prepared',lambda _:{'names':['offline'],'total':1})
    monkeypatch.setattr(control,'decide',lambda *_:pytest.fail('approval reached'))
    monkeypatch.setattr(control,'execute',lambda *_:pytest.fail('copy reached'))
    assert control.main(['--proposal','unused','--proposal-sha256','a'*64])['status']=='SOURCE_AND_DEPENDENCY_PLAN_ONLY_NO_OPERATIONAL_MUTATION'


@pytest.mark.parametrize('damage',['old-scope','sid','proposal','financial','source','kind'])
def test_previous_or_wrong_local_decision_cannot_authorize_successor(monkeypatch,damage):
    from scripts.volume_inspector import windows_output as windows
    monkeypatch.setattr(windows,'current_sid',lambda:'OFFLINE_SID')
    p={'source_commit':'a'*40}
    value={'schema':'ATLAS_SUCCESSOR_WINDOWS_LOCAL_DECISION_V1','origin':'VISIBLE_WINDOWS_LOCAL_OPERATOR',
        'kind':'install','scope':control.INSTALL_SCOPE,'proposal_sha256':'b'*64,'operator_sid':'OFFLINE_SID',
        'source_commit':'a'*40,'target':None,'financial_authority':False,
        'paper_start_authorized':False,'provider_access':False}
    if damage=='old-scope':value['scope']='APPROVE_ONE_R23_CODE_ONLY_NATIVE_INSTALL_NO_FINANCIAL_START'
    elif damage=='sid':value['operator_sid']='OTHER'
    elif damage=='proposal':value['proposal_sha256']='c'*64
    elif damage=='financial':value['financial_authority']=True
    elif damage=='source':value['source_commit']='d'*40
    else:value['kind']='select'
    monkeypatch.setattr(control,'checked',lambda *_:json.dumps(value).encode())
    with pytest.raises(ValueError,match='DISTINCT_CURRENT_LOCAL_DECISION'):
        control.verify_decision('D:/offline/proposal.json','b'*64,p,'install','e'*64)


def test_unknown_action_fails_before_any_native_or_filesystem_preflight(monkeypatch):
    monkeypatch.setattr(control,'proposal',lambda *_:pytest.fail('preflight reached'))
    with pytest.raises(ValueError,match='EXACT_EXECUTION_KIND'):
        control.execute('unused','a'*64,'recovery','b'*64)


def test_declined_local_review_never_writes_an_approval_or_attempt(monkeypatch):
    from scripts.volume_inspector import windows_output as windows
    monkeypatch.setattr(control,'visible_local_console',lambda:True)
    monkeypatch.setattr(control,'proposal',lambda *_:{'source_commit':'a'*40,'receipt':'D:/unused',
        'destination':'D:/unused','archive_sha256':'b'*64,'native_files':1200,'native_bytes':999,
        'timing_policy':control.timing_policy(),'control_source_sha256':'c'*64})
    monkeypatch.setattr(control,'prepared',lambda _:None)
    monkeypatch.setattr(control,'original_state',lambda _:True)
    monkeypatch.setattr(control,'installation_target',lambda *_:None)
    monkeypatch.setattr(windows,'current_sid',lambda:'OFFLINE_SID')
    monkeypatch.setattr('builtins.input',lambda *_:'DECLINE')
    monkeypatch.setattr(control,'write_new_json',lambda *_:pytest.fail('decision/attempt write'))
    with pytest.raises(ValueError,match='OPERATOR_DECLINED'):control.decide('unused','a'*64,'install')


@pytest.fixture
def execution_model(tmp_path,monkeypatch):
    """Explicit fake physical interfaces. Only failure journals use tmp_path."""
    from scripts.observation_runtime import atlas_r17_cpu_budget as cpu
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    from scripts import install_version_safe_candidate as clock_install
    from scripts.observation_runtime import native_install_host_admission as host
    from scripts import atlas_r13_low_impact_installer as pacing
    from scripts import native_install_candidate as copier
    from scripts import release_selection_store as selectors
    from scripts import release_selection as releases
    p={'source_commit':'f'*40,'destination':str(tmp_path/'candidate'),'receipt':str(tmp_path/'receipt.json'),
       'previous_spec':{'OFFLINE_PREDECESSOR':True,'root':str(tmp_path/'predecessor')},'archive_sha256':'a'*64,
       'source_inventory_sha256':'b'*64,'native_files':1,'native_directories':1}
    rows=[{'OFFLINE_REVISION':i} for i in range(21)]
    p['previous_head']=releases.digest(rows[-1])
    spec={'OFFLINE_VERIFIED_TARGET':True};decision={'target':spec}
    writes={};events=[];failure=[None];now=[0.0]
    class Cpu:
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def pulse(self):
            events.append('CPU_PULSE')
            if failure[0]=='io-pre-admission-delay' and kernel.priority==0x40:
                now[0]+=160
                failure[0]='io-pre-admission-delay-observed'
    # Keep the REAL constructor, priority lifecycle, cadence and deadline checks.
    real_envelope=pacing.LowImpactEnvelope
    class Kernel:
        priority=0x20
        def GetCurrentProcess(self):return 123
        def GetPriorityClass(self,_):return self.priority
        def SetPriorityClass(self,_,priority):
            self.priority=priority;events.append(('PRIORITY',priority))
            if failure[0]=='priority' and priority==0x40:return 0
            if failure[0]=='io-priority-delay' and priority==0x40:now[0]+=160
            return 1
    kernel=Kernel()
    def wait(seconds):now[0]+=seconds;events.append(('PACED_SLEEP',seconds))
    def envelope(**kwargs):
        events.append(('REAL_ENVELOPE',deepcopy(kwargs)))
        return real_envelope(kernel=kernel,monotonic=lambda:now[0],wait=wait,**kwargs)
    class Clock:
        evidence={'bound_ms':196}
        def __init__(self,**_):self.revoked=False;events.append('CLOCK_CREATED')
        def require_operational(self,_):
            if failure[0]=='clock':raise ValueError('OFFLINE_CLOCK_REVOKED')
        def revoke(self):events.append('CLOCK_REVOKED')
    class Verifier:
        @contextmanager
        def open(self,s):
            events.append(('INDEPENDENT_NATIVE_READ_DOUBLE',deepcopy(s)))
            now[0]+=(450 if failure[0]=='slow-predecessor' else 140 if failure[0]=='expensive-predecessor' else 16)
            events.append('PREDECESSOR_RETAINED')
            try:yield {'files':[{'path':'offline.py'}],'directories':[{'path':'.'}]}
            finally:
                events.append('PREDECESSOR_HANDLES_CLOSED')
                if failure[0]=='cleanup-timeout':now[0]=1201
                if failure[0]=='cleanup':raise OSError('OFFLINE_CLOSE_FAILED')
    class Store:
        def __init__(self,**_):pass
        @contextmanager
        def locked(self):yield
        def records(self):return deepcopy(rows)
        def publish(self,row):
            if failure[0]=='select':raise OSError('OFFLINE_SELECTION_UNKNOWN')
            rows.append(deepcopy(row))
        def close(self):events.append('SELECTOR_CLOSED')
    def write(path,value):
        path=str(path)
        if path in writes:raise FileExistsError('OFFLINE_SINGLE_USE_ALREADY_CONSUMED')
        writes[path]=deepcopy(value)
        if failure[0]=='ack-late' and path==p['receipt']:now[0]=796
        # Exercise real durable test-journal append/read, not any native path.
        if path.endswith('.pending.jsonl'):
            from pathlib import Path
            Path(path).write_text(json.dumps(value))
    def copy(**kwargs):
        events.append('COPY_CALLED');assert kwargs['admission']() is True; assert 'LIVE_PREDECESSOR_NAMESPACE_BOUNDARY' in events and 'PREDECESSOR_HANDLES_CLOSED' not in events
        for _ in range(128):assert kwargs['admission']() is True
        if failure[0]=='mid-copy-clock':
            failure[0]='clock'
            kwargs['admission'](force=True)
        if failure[0]=='copy':raise OSError('OFFLINE_COPY_UNKNOWN')
        if failure[0]=='deadline':now[0]=1201
        if failure[0]=='copy-reserve':now[0]=650;kwargs['admission']()
        return {'files':[{'path':'offline.py','bytes':1,'sha256':'a'*64,'id':[1,2,3]}],
                'directories':[{'path':'.','id':[1,2,4]}],
                'retained_handles_after_close':1 if failure[0]=='handles' else 0}
    def readback(*_,**kwargs):
        events.append('READBACK_CALLED')
        assert kwargs['timeout']==180
        if failure[0]=='readback-deadline':now[0]=790
        if failure[0]=='readback':raise OSError('OFFLINE_READBACK_UNKNOWN')
        return {'layout':{'OFFLINE_LAYOUT':True}}
    monkeypatch.setattr(control,'proposal',lambda *_:p)
    plan={'names':['offline.py'],'directories':[],'runtime':{'offline.py':{'bytes':1}},'dependencies':{}}
    def prepared(_):
        if failure[0]=='slow-inputs':now[0]+=450
        return deepcopy(plan)
    monkeypatch.setattr(control,'prepared',prepared)
    monkeypatch.setattr(control,'original_state',lambda _:True)
    monkeypatch.setattr(control,'verify_decision',lambda *_:decision)
    monkeypatch.setattr(control,'installation_target',lambda *_:None)
    monkeypatch.setattr(control,'write_new_json',write)
    monkeypatch.setattr(control,'installed_readback',readback)
    monkeypatch.setattr(control.time,'monotonic',lambda:now[0])
    monkeypatch.setattr(cpu,'NativeR17CpuBudget',Cpu)
    monkeypatch.setattr(pacing,'LowImpactEnvelope',envelope)
    monkeypatch.setattr(pacing,'_selector_unchanged',lambda:events.append('HISTORICAL_SELECTOR_CHECK'))
    monkeypatch.setattr(ntp,'IndependentNtpClock',Clock)
    def qualify(*_):now[0]+=580 if failure[0]=='slow-clock' else 180
    monkeypatch.setattr(clock_install,'_qualify_native_clock_180s',qualify)
    monkeypatch.setattr(host,'require_code_install_host_ready',lambda _:True)
    monkeypatch.setattr(copier,'_copy_prepared_code',copy)
    def namespace(root,files,directories,bound):
        assert str(root)==p['previous_spec']['root']
        assert files=={'offline.py'} and directories=={'.'}
        assert events.count('PREDECESSOR_RETAINED')>events.count('PREDECESSOR_HANDLES_CLOSED')
        if failure[0]=='slow-namespace':now[0]+=420
        if failure[0]=='namespace':raise ValueError('OFFLINE_NAMESPACE_SUBSTITUTION')
        assert bound() is True
        events.append('LIVE_PREDECESSOR_NAMESPACE_BOUNDARY')
    monkeypatch.setattr(copier,'_verify_namespace',namespace)
    monkeypatch.setattr(releases,'NativeInstalledReleaseVerifier',Verifier)
    monkeypatch.setattr(selectors,'NativeSelectionStore',Store)
    path=str(tmp_path/'proposal.json')
    return SimpleNamespace(**locals())


def test_code_only_copy_ack_readback_and_one_use_are_joined_offline(execution_model):
    m=execution_model
    result=control.execute(m.path,'a'*64,'install','b'*64)
    assert result['status']=='SUCCESSOR_INSTALLED_UNSELECTED_CODE_ONLY'
    assert len(m.rows)==21 and m.events.count('COPY_CALLED')==1
    receipt=m.writes[m.p['receipt']]
    assert all(receipt[k] is False for k in ('selected','financial_effects','provider_connections','operational_acceptance'))
    assert m.events[-2:]==['CLOCK_REVOKED','PREDECESSOR_HANDLES_CLOSED']
    assert ('PACED_SLEEP',0.06) in m.events
    assert m.kernel.priority==0x20
    with pytest.raises(FileExistsError):control.execute(m.path,'a'*64,'install','b'*64)
    assert m.events.count('COPY_CALLED')==1


@pytest.mark.parametrize('failure',['copy','readback','handles','deadline'])
def test_partial_copy_or_readback_never_publishes_install_receipt(execution_model,failure):
    m=execution_model;m.failure[0]=failure
    with pytest.raises((ValueError,OSError)):control.execute(m.path,'a'*64,'install','b'*64)
    assert m.p['receipt'] not in m.writes
    from pathlib import Path
    journal=Path(m.p['receipt']).with_suffix('.pending.jsonl').read_text()
    assert 'REFUSED_PRESERVE_PARTIAL_NO_RETRY' in journal
    assert m.events[-2:]==['CLOCK_REVOKED','PREDECESSOR_HANDLES_CLOSED'] and len(m.rows)==21


def test_selection_is_a_different_decision_and_never_copies_again(execution_model):
    m=execution_model
    result=control.execute(m.path,'a'*64,'select','c'*64)
    assert result['receipt']['revision']==22 and len(m.rows)==22
    assert result['receipt']['selected']==m.spec and 'COPY_CALLED' not in m.events
    assert result['financial_authority'] is False and m.events[-2:]==['CLOCK_REVOKED','PREDECESSOR_HANDLES_CLOSED']


def test_unaccepted_clock_does_not_consume_attempt_or_copy(execution_model):
    m=execution_model;m.failure[0]='clock'
    with pytest.raises(ValueError):control.execute(m.path,'a'*64,'install','b'*64)
    assert 'COPY_CALLED' not in m.events and m.p['receipt'] not in m.writes
    assert not m.writes
    assert m.events[-2:]==['CLOCK_REVOKED','PREDECESSOR_HANDLES_CLOSED']


@pytest.mark.parametrize('failure',['slow-predecessor','slow-clock','slow-inputs','priority'])
def test_preflight_cost_and_real_priority_failure_preserve_unused_approval(execution_model,failure):
    m=execution_model;m.failure[0]=failure
    with pytest.raises(ValueError):control.execute(m.path,'a'*64,'install','b'*64)
    assert not m.writes and 'COPY_CALLED' not in m.events


@pytest.mark.parametrize('failure',['copy-reserve','readback-deadline','cleanup','cleanup-timeout'])
def test_reservations_and_final_cleanup_cannot_return_pass(execution_model,failure):
    m=execution_model;m.failure[0]=failure
    with pytest.raises((ValueError,OSError)):control.execute(m.path,'a'*64,'install','b'*64)
    from pathlib import Path
    rows=Path(m.p['receipt']).with_suffix('.pending.jsonl').read_text().splitlines()
    assert json.loads(rows[-1])['stage']=='REFUSED_PRESERVE_PARTIAL_NO_RETRY'
    assert len(m.rows)==21 and m.kernel.priority==0x20


def test_real_invalid_envelope_configuration_refuses_before_any_write(execution_model,monkeypatch):
    from scripts import atlas_r14_low_impact_installer as original
    m=execution_model
    monkeypatch.setattr(original,'MAX_SECONDS',600)
    with pytest.raises(ValueError,match='ORIGINAL_R23_PACING_CHANGED'):
        control.execute(m.path,'a'*64,'install','b'*64)
    assert not m.writes and 'CLOCK_CREATED' not in m.events


def test_real_envelope_rejects_600_and_validates_original_500_without_native_entry():
    from scripts.atlas_r13_low_impact_installer import LowImpactEnvelope
    with pytest.raises(ValueError,match='BOUNDED_LOW_RESOURCE_POLICY'):
        LowImpactEnvelope(max_seconds=600,kernel=object())
    guard=LowImpactEnvelope(max_seconds=500,check_every=32,pace_every=128,pause_seconds=0.06,kernel=object())
    assert guard.started is None and guard.pace_every==128 and guard.check_every==32


@pytest.mark.parametrize('elapsed',[600,601,float('nan'),float('inf'),-1])
def test_total_clock_failure_refuses(elapsed,monkeypatch):
    now=[0.0];monkeypatch.setattr(control.time,'monotonic',lambda:now[0])
    budget=control.ExecutionBudget();now[0]=elapsed
    with pytest.raises(ValueError,match='DEADLINE|MONOTONIC'):budget.remaining()


def test_full_final_readback_and_cleanup_are_reserved_before_copy(execution_model):
    m=execution_model
    budget=control.ExecutionBudget()
    m.now[0]=240
    budget.begin_installation()
    m.now[0]=490
    with control.pacing_envelope() as envelope:
        with pytest.raises(ValueError,match='RESERVATION_EXHAUSTED'):
            budget.copy_admission(m.plan,16,envelope)
    assert not m.writes


def test_new_proposal_cannot_reuse_old_decision_even_with_same_application(monkeypatch):
    from scripts.volume_inspector import windows_output as windows
    monkeypatch.setattr(windows,'current_sid',lambda:'OFFLINE_SID')
    value={'schema':'ATLAS_SUCCESSOR_WINDOWS_LOCAL_DECISION_V1','origin':'VISIBLE_WINDOWS_LOCAL_OPERATOR',
        'kind':'install','scope':control.INSTALL_SCOPE,'proposal_sha256':'a'*64,'operator_sid':'OFFLINE_SID',
        'source_commit':'f'*40,'target':None,'financial_authority':False,'paper_start_authorized':False,'provider_access':False}
    monkeypatch.setattr(control,'checked',lambda *_:json.dumps(value).encode())
    with pytest.raises(ValueError,match='DISTINCT_CURRENT_LOCAL_DECISION'):
        control.verify_decision('D:/offline/new/proposal.json','b'*64,{'source_commit':'f'*40},'install','c'*64)


@pytest.mark.parametrize('damage',[None,'old-schema','wrong-controller','short-readback','long-total','fast-pacing'])
def test_real_v3_proposal_validation_requires_exact_phased_contract(tmp_path,monkeypatch,damage):
    import hashlib
    from pathlib import Path
    monkeypatch.setattr(control,'ROOT',tmp_path)
    directory=tmp_path/'logs/diagnostics/atlas-single-successor-offline-review'
    directory.mkdir(parents=True)
    p={'schema':'ATLAS_SINGLE_SUCCESSOR_CODE_ONLY_PROPOSAL_V3','source_commit':'f'*40,
       'destination':str(Path('D:/AtlasRuntime/releases')/('f'*40)),
       'receipt':str(tmp_path/'logs/diagnostics'/('qd-unselected-release-'+'f'*40+'.json')),
       'control_source_sha256':hashlib.sha256(Path(control.__file__).read_bytes()).hexdigest(),
       'previous_head':control.R23_HEAD,'previous_spec':{'release':control.R23_SOURCE,'artifact_digest':control.R23_ARTIFACT},
       'limits':{'seconds':1200,'entries':40000,'bytes':1024**3,'processors':2},
       'timing_policy':control.timing_policy(),'financial_authority':False,'paper_start_authorized':False,
       'provider_access':False,'automatic_startup':False}
    if damage=='old-schema':p['schema']='ATLAS_SINGLE_SUCCESSOR_CODE_ONLY_PROPOSAL_V1'
    elif damage=='wrong-controller':p['control_source_sha256']='0'*64
    elif damage=='short-readback':p['timing_policy']['readback_seconds']=40
    elif damage=='long-total':p['timing_policy']['overall_seconds']=1201
    elif damage=='fast-pacing':p['timing_policy']['pause_seconds']=0.01
    path=directory/'proposal.json';raw=json.dumps(p).encode();path.write_bytes(raw)
    pin=hashlib.sha256(raw).hexdigest()
    if damage is None:assert control.proposal(path,pin)==p
    else:
        with pytest.raises(ValueError,match='EXACT_CODE_ONLY_PROPOSAL'):control.proposal(path,pin)


def test_entry_deadline_includes_input_preparation_before_owner_and_clock(execution_model):
    m=execution_model;m.failure[0]='slow-inputs'
    with pytest.raises(ValueError,match='RESERVATION_EXHAUSTED'):
        control.execute(m.path,'a'*64,'install','b'*64)
    assert not m.writes and 'COPY_CALLED' not in m.events


def test_current_predecessor_elapsed_must_be_genuine_positive_measurement(execution_model):
    m=execution_model;budget=control.ExecutionBudget()
    for bad in (0,-1,True,None,float('nan'),float('inf')):
        with pytest.raises(ValueError,match='CURRENT_PREDECESSOR_TIMING'):
            budget.copy_admission(m.plan,bad,None)


@pytest.mark.parametrize('failure',['slow-namespace','namespace','expensive-predecessor','io-pre-admission-delay'])
def test_phased_native_boundary_and_budget_refuse_before_consumption(execution_model,failure):
    m=execution_model;m.failure[0]=failure
    with pytest.raises((ValueError,OSError)):
        control.execute(m.path,'a'*64,'install','b'*64)
    assert m.writes=={} and 'COPY_CALLED' not in m.events
    assert m.events[-2:]==['CLOCK_REVOKED','PREDECESSOR_HANDLES_CLOSED']
    assert len(m.rows)==21


@pytest.mark.parametrize('failure',['mid-copy-clock','ack-late'])
def test_phased_clock_and_ack_failure_preserve_original_journal(execution_model,failure):
    m=execution_model;m.failure[0]=failure
    with pytest.raises(ValueError):
        control.execute(m.path,'a'*64,'install','b'*64)
    from pathlib import Path
    rows=Path(m.p['receipt']).with_suffix('.pending.jsonl').read_text().splitlines()
    assert json.loads(rows[-1])['stage']=='REFUSED_PRESERVE_PARTIAL_NO_RETRY'
    assert 'PREDECESSOR_HANDLES_CLOSED'==m.events[-1] and len(m.rows)==21


def test_two_phase_budget_has_separate_real_origins_and_cannot_restart(execution_model):
    m=execution_model
    budget=control.ExecutionBudget()
    m.now[0]=263.219
    assert budget.remaining()>300
    b_origin=budget.begin_installation()
    assert b_origin==263.219
    assert budget.remaining()>599
    with pytest.raises(ValueError,match='CANNOT_RESTART'):
        budget.begin_installation()
    m.now[0]=862
    assert 0<budget.remaining()<2
    m.now[0]=863.219
    with pytest.raises(ValueError,match='DEADLINE'):
        budget.remaining()


def test_unqualified_or_restarted_io_scope_is_never_accepted(execution_model):
    m=execution_model
    budget=control.ExecutionBudget()
    with control.pacing_envelope() as envelope:
        with pytest.raises(ValueError,match='PACED_IO'):
            budget.io_remaining(envelope)
        budget.begin_installation()
        m.now[0]=500
        with pytest.raises(ValueError,match='PACED_IO'):
            budget.io_remaining(envelope)
    with pytest.raises(ValueError,match='PACED_IO'):
        budget.io_remaining(envelope)


def test_phased_forecast_accepts_actual_measured_v2_preflight_with_fresh_b(execution_model):
    m=execution_model
    budget=control.ExecutionBudget()
    m.now[0]=263.219
    budget.begin_installation()
    with control.pacing_envelope() as envelope:
        allocation=budget.copy_admission(m.plan,78.375,envelope)
        assert allocation['copy_reserved_seconds']>=250.125
        assert allocation['readback_reserved_seconds']==180
        assert allocation['terminal_reserved_seconds']==30
        assert allocation['io_ack_reserved_seconds']==15
