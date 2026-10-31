"""Mock-only acceptance. No Docker connection or production state access."""
import copy
import importlib.util
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

m = load('scripts/volume_inspector/isolated_adapter.py', 'isolated')
y = load('tests/test_r7e46y_volume_inspector.py', 'previous')

class Output:
    def __init__(self): self.values = []
    def publish(self, name, data):
        self.values.append((name, data))
        return 'd' * 64

def setup(tmp_path):
    f = m.Fence(tmp_path/'fence.sqlite',create=True)
    evidence = y.fixture()
    evidence['observed_unix'] = 1000
    spec = y.policy.plan('postgres', evidence, evidence, y.PIN, now=1000)
    spec.update(pid_mode='private', ipc_mode='private', seccomp='default', env=[], devices=[], binds=[], synthetic_only=True)
    approval = {'operation': 'test-operation', 'image': y.PIN, 'source': y.policy.EXPECTED['postgres'][0],
                    'volume': y.policy.EXPECTED['postgres'][1], 'expires': 1100, 'exclusive_window': True}
    pre = copy.deepcopy(evidence)
    helper = 'a'*64
    metadata = {'schema': 1,'service': 'postgres','status': 'METADATA_COMPLETE_COVERAGE_UNPROVEN',
                    'files': 3,'directories': 1,'logical_file_bytes': 54,'effective_configuration': 'NOT_ESTABLISHED','payloads_read': False}
    responses = {'preflight': pre, 'create': helper,
                     'inspect_created': {'id': helper,'operation': approval['operation'],'spec': spec,'state': 'created'},
                     'preflight_after_create': pre, 'start': {'id': helper, 'started': True}, 'output': json.dumps(metadata).encode(),
                     'exit': {'id': helper,'operation': approval['operation'],'state': 'exited','pid': 0,'exit': 0}, 'postflight': pre}
    docker=m.MockDocker(responses); out=Output()
    return m.Adapter(f,docker,out,clock=lambda:1000),approval,spec,evidence,responses

def run(x):
    a,approval,spec,evidence,_=x
    return a.run(approval,spec,evidence,copy.deepcopy(evidence))

def test_success(tmp_path):
    x=setup(tmp_path);assert run(x)['logical_file_bytes']==54
    assert x[0].fence.read()['state']=='COMPLETE';assert x[0].fence.startup_allowed()
    assert all(0<t<=5 and n==65536 for _,t,n in x[0].docker.calls)
    assert len(x[0].output.values)==1
    with pytest.raises(ValueError):run(x)

@pytest.mark.parametrize('field,value', [('image','sha256:'+'b'*64),('privileged',True),('mounts',[]),('seccomp','unconfined'),('pid_mode','host'),('ipc_mode','host'),('env',['PASSWORD=x']),('memory','2g'),('output_limit_bytes',999999),('operator_deadline_seconds',9999),('synthetic_only',False)])
def test_reject_launch(tmp_path,field,value):
    x=setup(tmp_path);x[2][field]=value
    with pytest.raises(ValueError):run(x)
    assert not x[0].docker.calls

@pytest.mark.parametrize('field,value',[('image','sha256:'+'b'*64),('source','b'*64),('volume','foreign'),('exclusive_window',False),('expires',999)])
def test_reject_approval(tmp_path,field,value):
    x=setup(tmp_path);x[1][field]=value
    with pytest.raises(ValueError):run(x)
    assert not x[0].docker.calls

@pytest.mark.parametrize('stage',['preflight','create','inspect_created','preflight_after_create','start','output','exit','postflight'])
@pytest.mark.parametrize('failure',[TimeoutError,ConnectionError,KeyboardInterrupt])
def test_failure_retains_fence(tmp_path,stage,failure):
    x=setup(tmp_path);x[4][stage]=failure('DO_NOT_PERSIST_SECRET')
    with pytest.raises(failure):run(x)
    f=m.Fence(tmp_path/'fence.sqlite');assert f.read()['state']=='UNCERTAIN';assert not f.startup_allowed()
    assert 'DO_NOT_PERSIST_SECRET' not in json.dumps(f.read())

@pytest.mark.parametrize('stage,value',[('create',{}),('inspect_created',{}),('preflight_after_create',{}),('start',{}),('exit',{}),('postflight',{})])
def test_malformed_and_replacement(tmp_path,stage,value):
    x=setup(tmp_path);x[4][stage]=value
    with pytest.raises(ValueError):run(x)
    assert not x[0].fence.startup_allowed()

@pytest.mark.parametrize('raw',[b'bad',b'x'*65537,b'{"secret":"password"}',b'[]',b'{}'], ids=['invalid','oversized','secret-field','array','empty'])
def test_bad_output_not_published(tmp_path,raw):
    x=setup(tmp_path);x[4]['output']=raw
    with pytest.raises((ValueError,TypeError)):run(x)
    assert x[0].output.values==[];assert not x[0].fence.startup_allowed()

def test_concurrent_authorization(tmp_path):
    x=setup(tmp_path)
    def authorize(_):
        try: m.Fence(tmp_path/'fence.sqlite').authorize(x[1],1000);return True
        except ValueError:return False
    with ThreadPoolExecutor(2) as pool:assert sum(pool.map(authorize,range(2)))==1
    assert not x[0].fence.startup_allowed()

def test_recovery(tmp_path):
    x=setup(tmp_path);x[4]['output']=TimeoutError()
    with pytest.raises(TimeoutError):run(x)
    proof={'id': 'a'*64,'operation': 'test-operation','state': 'exited','pid': 0,'observed': 1000}
    x[0].recover(proof,1000,operator_approved=True)
    assert x[0].fence.read()['state']=='FAILED';assert x[0].fence.startup_allowed()
    with pytest.raises(ValueError):run(x)

@pytest.mark.parametrize('field,value',[('id','b'*64),('operation','replacement'),('state','running'),('pid',10),('observed',990),('observed',1001)])
def test_reject_recovery(tmp_path,field,value):
    x=setup(tmp_path);x[4]['output']=ConnectionError()
    with pytest.raises(ConnectionError):run(x)
    proof={'id': 'a'*64,'operation': 'test-operation','state': 'exited','pid': 0,'observed': 1000};proof[field]=value
    with pytest.raises(ValueError):x[0].recover(proof,1000,operator_approved=True)
    assert not x[0].fence.startup_allowed()

def test_no_approval_or_unknown_helper_recovery(tmp_path):
    x=setup(tmp_path);x[4]['create']=TimeoutError()
    with pytest.raises(TimeoutError):run(x)
    with pytest.raises(ValueError):x[0].recover({},1000,operator_approved=True)
    assert not x[0].fence.startup_allowed()

def test_malformed_fence_blocks(tmp_path):
    f=m.Fence(tmp_path/'fence.sqlite',create=True)
    with sqlite3.connect(f.path) as db:db.execute("UPDATE fence SET record='{}'")
    assert not f.startup_allowed()

def test_untrusted_transport(tmp_path):
    with pytest.raises(TypeError):m.Adapter(m.Fence(tmp_path/'fence.sqlite',create=True),object(),Output())

def test_output_failure_preserved(tmp_path):
    x=setup(tmp_path)
    def fail(*_):raise PermissionError('secret')
    x[0].output.publish=fail
    with pytest.raises(PermissionError):run(x)
    assert not x[0].fence.startup_allowed()

def test_platform_output(tmp_path):
    if os.name=='nt':
        with pytest.raises(PermissionError):m.ProtectedOutput(tmp_path)
    else:
        os.chmod(tmp_path,0o700);out=m.ProtectedOutput(tmp_path)
        value={'schema': 1,'service': 'postgres','status': 'METADATA_COMPLETE_COVERAGE_UNPROVEN','files': 1,'directories': 0,'logical_file_bytes': 54,'effective_configuration': 'NOT_ESTABLISHED','payloads_read': False}
        digest=out.publish('evidence.json',value)
        assert (tmp_path/'evidence.json.commit').read_text()==digest
        with pytest.raises(FileExistsError):out.publish('evidence.json',value)
        os.chmod(tmp_path,0o755)
        with pytest.raises(PermissionError):m.ProtectedOutput(tmp_path)

def test_late_result_quarantined(tmp_path):
    x=setup(tmp_path)
    times=iter([0,0,41])
    x[0].monotonic=lambda:next(times)
    with pytest.raises(TimeoutError):run(x)
    assert not x[0].fence.startup_allowed()

@pytest.mark.parametrize('field,value', [('source','b'*64),('volume','foreign'),('stopped',False)])
def test_preflight_drift(tmp_path,field,value):
    x=setup(tmp_path);x[4]['preflight']={**x[4]['preflight'],field:value}
    with pytest.raises((ValueError,KeyError)):run(x)
    assert not x[0].fence.startup_allowed()

@pytest.mark.parametrize('field,value', [('privileged',True),('seccomp','unconfined'),('pid_mode','host'),('binds',['/']),('mounts',[]),('read_only_rootfs',False),('cap_drop',[]),('network','host'),('pids_limit',999),('env',['secret']),('memory','1g')])
def test_created_controls_tamper(tmp_path,field,value):
    x=setup(tmp_path)
    x[4]['inspect_created']=copy.deepcopy(x[4]['inspect_created'])
    x[4]['inspect_created']['spec'][field]=value
    with pytest.raises(ValueError):run(x)
    assert not any(method=='start' for method,_,_ in x[0].docker.calls)
    assert not x[0].fence.startup_allowed()

@pytest.mark.parametrize('field,value',[('schema',True),('files',False),('directories',-1),('logical_file_bytes',float('nan')),('payloads_read',True),('service','secret'),('effective_configuration','password'),('status','INCOMPLETE')])
def test_metadata_scalar_restrictions(tmp_path,field,value):
    x=setup(tmp_path);v=json.loads(x[4]['output']);v[field]=value
    with pytest.raises(ValueError):m.safe_metadata(json.dumps(v).encode())

def test_state_transition_and_replacement_guard(tmp_path):
    x=setup(tmp_path);f=x[0].fence;state=f.authorize(x[1],1000)
    with pytest.raises(ValueError):f.transition(state,{**state,'state':'COMPLETE'})
    with pytest.raises(ValueError):f.transition(state,{**state,'state':'UNCERTAIN','operation':'foreign'})
    uncertain=f.transition(state,{**state,'state':'UNCERTAIN','helper':'a'*64})
    with pytest.raises(ValueError):f.transition(uncertain,{**uncertain,'helper':'b'*64})

def test_crash_before_helper_identity_retains_prohibition(tmp_path):
    x=setup(tmp_path);f=x[0].fence;s=f.authorize(x[1],1000)
    f.transition(s,{**s,'state':'UNCERTAIN'})
    reopened=m.Fence(f.path);assert not reopened.startup_allowed()
    with pytest.raises(ValueError):x[0].recover({},1000,operator_approved=True)

def test_no_recovery_without_approval(tmp_path):
    x=setup(tmp_path);x[4]['exit']=ConnectionError()
    with pytest.raises(ConnectionError):run(x)
    with pytest.raises(ValueError):x[0].recover({},1000)
    assert not x[0].fence.startup_allowed()

def test_failed_attempt_audited_without_raw_error(tmp_path):
    x=setup(tmp_path);x[2]['env']=['SUPER_SECRET']
    with pytest.raises(ValueError):run(x)
    with x[0].fence.connect() as db:rows=db.execute('SELECT record FROM audit').fetchall()
    assert rows and 'SUPER_SECRET' not in str(rows)

def test_fence_corrupt_database_blocks(tmp_path):
    path=tmp_path/'corrupt.sqlite';path.write_bytes(b'not a database')
    f=object.__new__(m.Fence);f.path=path
    assert not f.startup_allowed()

@pytest.mark.skipif(os.name!='posix',reason='POSIX private-directory/atomic-link implementation needs native POSIX; Windows DACL remains BLOCKED')
def test_posix_output_integrity_and_redaction(tmp_path):
    import hashlib
    os.chmod(tmp_path,0o700);out=m.ProtectedOutput(tmp_path)
    value={'schema': 1,'service': 'postgres','status': 'METADATA_COMPLETE_COVERAGE_UNPROVEN','files': 1,'directories': 0,'logical_file_bytes': 54,'effective_configuration': 'NOT_ESTABLISHED','payloads_read': False}
    digest=out.publish('result.json',value)
    assert hashlib.sha256((tmp_path/'result.json').read_bytes()).hexdigest()==digest
    assert (tmp_path/'result.json.commit').read_text()==digest
    assert (tmp_path/'result.json.commit.pending').exists()
    with pytest.raises(ValueError):out.publish('secret.json',{'password':'DO_NOT_PERSIST'})
    assert not (tmp_path/'secret.json').exists()

def test_real_helper_shape_projected_without_names(tmp_path):
    import stat
    x=setup(tmp_path)
    tree=y.SyntheticTree({'': [('PG_VERSION',y.meta(stat.S_IFREG,5))]})
    actual=y.helper.inspect(tree,'postgres')
    x[4]['output']=json.dumps(actual).encode()
    result=run(x)
    assert result['logical_file_bytes']==5
    assert 'PG_VERSION' not in json.dumps(x[0].output.values)

def test_duplicate_output_keys_rejected():
    with pytest.raises(ValueError):m.safe_metadata(b'{"schema":1,"schema":1}')

def test_missing_fence_never_reinitialized(tmp_path):
    path=tmp_path/'absent.sqlite'
    with pytest.raises(sqlite3.Error):m.Fence(path)
    assert not path.exists()

def test_partial_initialization_not_repaired(tmp_path):
    path=tmp_path/'partial.sqlite';path.write_bytes(b'')
    with pytest.raises(sqlite3.Error):m.Fence(path)
    with pytest.raises(FileExistsError):m.Fence(path,create=True)

@pytest.mark.parametrize('field,value',[('pid',False),('exit',False),('state','running')])
def test_typed_exit_proof(tmp_path,field,value):
    x=setup(tmp_path);x[4]['exit'][field]=value
    with pytest.raises(ValueError):run(x)
    assert not x[0].fence.startup_allowed()

def test_startup_guard_blocks_active_and_uncertain(tmp_path):
    x=setup(tmp_path);f=x[0].fence
    with f.startup_guard():pass
    state=f.authorize(x[1],1000)
    with pytest.raises(ValueError), f.startup_guard():pass
    f.transition(state,{**state,'state':'UNCERTAIN'})
    with pytest.raises(ValueError), f.startup_guard():pass

def test_startup_guard_serializes_inspection_admission(tmp_path):
    x=setup(tmp_path);f=x[0].fence
    def attempt():
        with pytest.raises(sqlite3.OperationalError):
            f.authorize(x[1],1000)
    with ThreadPoolExecutor(1) as pool, f.startup_guard():
        pool.submit(attempt).result(timeout=3)
    assert f.read()['state']=='NOT_AUTHORIZED'

def test_preconditions_crash_restart_blocks_startup(tmp_path):
    x=setup(tmp_path);x[0].fence.authorize(x[1],1000)
    restarted=m.Fence(tmp_path/'fence.sqlite')
    assert not restarted.startup_allowed()
    with pytest.raises(ValueError), restarted.startup_guard():pass

def test_actual_child_interruption_persists_fence(tmp_path):
    import subprocess
    import sys
    x=setup(tmp_path);x[0].fence.authorize(x[1],1000)
    code='''import importlib.util,os,sys
spec=importlib.util.spec_from_file_location('child',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
f=m.Fence(sys.argv[2]);s=f.read();s=f.transition(s,{**s,'state':'UNCERTAIN','helper':'a'*64});f.transition(s,{**s,'state':'IN_PROGRESS'});os._exit(17)
'''
    p=subprocess.run([sys.executable,'-I','-B','-c',code,str(ROOT/'scripts/volume_inspector/isolated_adapter.py'),str(x[0].fence.path)],capture_output=True,timeout=10,check=False)
    assert p.returncode==17,p.stderr
    f=m.Fence(x[0].fence.path);assert f.read()['state']=='IN_PROGRESS';assert not f.startup_allowed()
    assert len(list(tmp_path.glob('*.sqlite')))==1

def test_rejected_spec_boolean_substitution(tmp_path):
    x=setup(tmp_path);x[2]['privileged']=0
    with pytest.raises(ValueError):run(x)
    assert not x[0].docker.calls
