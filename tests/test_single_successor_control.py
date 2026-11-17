"""Offline CODE-ONLY operator-support boundaries, never real local decisions."""
import json
from contextlib import nullcontext
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
    monkeypatch.setattr(control,'proposal',lambda *_:{'source_commit':'a'*40})
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
        'destination':'D:/unused','archive_sha256':'b'*64,'native_files':1200,'native_bytes':999})
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
       'previous_spec':{'OFFLINE_PREDECESSOR':True},'archive_sha256':'a'*64,
       'source_inventory_sha256':'b'*64,'native_files':1,'native_directories':1}
    rows=[{'OFFLINE_REVISION':i} for i in range(21)]
    p['previous_head']=releases.digest(rows[-1])
    spec={'OFFLINE_VERIFIED_TARGET':True};decision={'target':spec}
    writes={};events=[];failure=[None];now=[0.0]
    class Cpu:
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def pulse(self):events.append('CPU_PULSE')
    class Envelope(Cpu):
        def __init__(self,**_):pass
        def tick(self):events.append('PACE')
    class Clock:
        evidence={'bound_ms':196}
        def __init__(self,**_):self.revoked=False;events.append('CLOCK_CREATED')
        def require_operational(self,_):
            if failure[0]=='clock':raise ValueError('OFFLINE_CLOCK_REVOKED')
        def revoke(self):events.append('CLOCK_REVOKED')
    class Verifier:
        def open(self,s):events.append(('INDEPENDENT_NATIVE_READ_DOUBLE',deepcopy(s)));return nullcontext({})
    class Store:
        def __init__(self,**_):pass
        def locked(self):return nullcontext()
        def records(self):return deepcopy(rows)
        def publish(self,row):
            if failure[0]=='select':raise OSError('OFFLINE_SELECTION_UNKNOWN')
            rows.append(deepcopy(row))
        def close(self):events.append('SELECTOR_CLOSED')
    def write(path,value):
        path=str(path)
        if path in writes:raise FileExistsError('OFFLINE_SINGLE_USE_ALREADY_CONSUMED')
        writes[path]=deepcopy(value)
        # Exercise real durable test-journal append/read, not any native path.
        if path.endswith('.pending.jsonl'):
            from pathlib import Path
            Path(path).write_text(json.dumps(value))
    def copy(**kwargs):
        events.append('COPY_CALLED');assert kwargs['admission']() is True
        if failure[0]=='copy':raise OSError('OFFLINE_COPY_UNKNOWN')
        if failure[0]=='deadline':now[0]=601
        return {'files':[{'path':'offline.py','bytes':1,'sha256':'a'*64,'id':[1,2,3]}],
                'directories':[{'path':'.','id':[1,2,4]}],
                'retained_handles_after_close':1 if failure[0]=='handles' else 0}
    def readback(*_,**kwargs):
        events.append('READBACK_CALLED')
        if failure[0]=='readback':raise OSError('OFFLINE_READBACK_UNKNOWN')
        return {'layout':{'OFFLINE_LAYOUT':True}}
    monkeypatch.setattr(control,'proposal',lambda *_:p)
    monkeypatch.setattr(control,'prepared',lambda _:{})
    monkeypatch.setattr(control,'original_state',lambda _:True)
    monkeypatch.setattr(control,'verify_decision',lambda *_:decision)
    monkeypatch.setattr(control,'installation_target',lambda *_:None)
    monkeypatch.setattr(control,'write_new_json',write)
    monkeypatch.setattr(control,'installed_readback',readback)
    monkeypatch.setattr(control.time,'monotonic',lambda:now[0])
    monkeypatch.setattr(cpu,'NativeR17CpuBudget',Cpu)
    monkeypatch.setattr(pacing,'LowImpactEnvelope',Envelope)
    monkeypatch.setattr(ntp,'IndependentNtpClock',Clock)
    monkeypatch.setattr(clock_install,'_qualify_native_clock_180s',lambda *_:None)
    monkeypatch.setattr(host,'require_code_install_host_ready',lambda _:True)
    monkeypatch.setattr(copier,'_copy_prepared_code',copy)
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
    assert m.events[-1]=='CLOCK_REVOKED'
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
    assert m.events[-1]=='CLOCK_REVOKED' and len(m.rows)==21


def test_selection_is_a_different_decision_and_never_copies_again(execution_model):
    m=execution_model
    result=control.execute(m.path,'a'*64,'select','c'*64)
    assert result['receipt']['revision']==22 and len(m.rows)==22
    assert result['receipt']['selected']==m.spec and 'COPY_CALLED' not in m.events
    assert result['financial_authority'] is False and m.events[-1]=='CLOCK_REVOKED'


def test_unaccepted_clock_consumes_only_the_test_attempt_without_copy(execution_model):
    m=execution_model;m.failure[0]='clock'
    with pytest.raises(ValueError):control.execute(m.path,'a'*64,'install','b'*64)
    assert 'COPY_CALLED' not in m.events and m.p['receipt'] not in m.writes
    assert any(name.endswith('local-install-attempt.json') for name in m.writes)
    assert m.events[-1]=='CLOCK_REVOKED'
