"""Injected source validation only; no Windows loaders or financial children."""
import copy
import json
import ntpath

import pytest

from scripts.observation_runtime.aip06_harness import ROOTS
from test_aip06_native_session_stop import fixture,EXE


def pair():
    x=fixture()
    # BASE is diagnostics; repository is two components above it.
    target=ntpath.join(ntpath.dirname(ntpath.dirname(ntpath.dirname(ROOTS['P']))),'tests','perp_order_crash_child.py')
    x.controller.profile['targets'].update(race_one=target,race_two=target)
    x.controller.profile['source_pins'][target]='a'*64
    read=x.io.read_bytes;x.io.read_bytes=lambda p,maximum_bytes=65536:read(p)
    with x.guard.installed():
        x.guard.mkdir(ROOTS['P'])
        x.commands=[]
        for i in (0,1):
            path=ntpath.join(ROOTS['P'],f'global-race-{i}.json')
            value={'root':ROOTS['P'],'confinement':ROOTS['P'],'barrier':ntpath.join(ROOTS['P'],'go'),
                   'ready':ntpath.join(ROOTS['P'],f'ready-{i}'),'operation':{'same':'original'}}
            x.guard.write(path,json.dumps(value).encode())
            x.commands.append([EXE,'-B',target,'--config',path,'--phase','none'])
    return x


def test_pair_declaration_is_inert_and_assigns_exact_commands_in_either_order():
    x=pair();before=list(x.calls.events)
    with x.guard.installed():
        receipt=x.port.declare_race_pair(x.commands)
        assert not receipt['processes_created'] and x.calls.events==before
        assert x.port._role(x.commands[1])=='race_two'
        assert x.port._role(x.commands[0])=='race_one'
        assert x.port.race_roles.used=={'race_one','race_two'}
    assert not x.calls.handles


def test_duplicate_target_without_explicit_pair_still_refuses():
    x=pair()
    with x.guard.installed(),pytest.raises(ValueError,match='UNAMBIGUOUS'):x.port._role(x.commands[0])


@pytest.mark.parametrize('damage',['same-command','phase','foreign-target','source-profile','same-ready',
                                  'different-operation','foreign-owner','replaced-file','hardlink','barrier-exists'])
def test_invalid_pair_never_admits_creation(damage):
    x=pair();argv=copy.deepcopy(x.commands)
    if damage=='same-command':argv[1]=argv[0]
    elif damage=='phase':argv[0][-1]='financial-after-ack'
    elif damage=='foreign-target':argv[0][2]=r'D:\foreign.py'
    elif damage=='source-profile':x.controller.profile['targets']['race_two']=r'D:\foreign.py'
    elif damage=='foreign-owner':x.guard.owned_files.remove(argv[1][4])
    elif damage=='replaced-file':x.io.rows[argv[1][4]]['id']=[1,999,0]
    elif damage=='hardlink':x.io.rows[argv[1][4]]['links']=2
    elif damage=='barrier-exists':x.io.add(ntpath.join(ROOTS['P'],'go'),'file')
    else:
        value=json.loads(x.io.data[argv[1][4]])
        if damage=='same-ready':value['ready']=json.loads(x.io.data[argv[0][4]])['ready']
        else:value['operation']={'different':True}
        x.io.data[argv[1][4]]=json.dumps(value).encode()
    with x.guard.installed(),pytest.raises(ValueError):x.port.declare_race_pair(argv)
    assert not x.calls.handles and not x.port.sessions


@pytest.mark.parametrize('damage',['changed-bytes','changed-id','replay','changed-parent','unknown-command'])
def test_race_claim_failure_latches_and_never_falls_back_to_pid_or_unused_role(damage):
    x=pair()
    with x.guard.installed():
        x.port.declare_race_pair(x.commands);argv=copy.deepcopy(x.commands[0])
        if damage=='changed-bytes':x.io.data[argv[4]]+=b' '
        elif damage=='changed-id':x.io.rows[argv[4]]['id']=[1,999,0]
        elif damage=='replay':assert x.port._role(argv)=='race_one'
        elif damage=='changed-parent':x.guard.owner='f'*64
        else:argv[4]=x.commands[1][4]+'-unregistered'
        with pytest.raises(ValueError):x.port._role(argv)
        assert x.port.race_roles.failed
        with pytest.raises(ValueError):x.port._role(x.commands[1])


def test_two_real_guard_launch_paths_keep_distinct_reservations_ancestry_jobs_and_handles():
    x=pair()
    with x.guard.installed():
        x.port.declare_race_pair(x.commands)
        one=x.guard.spawn(x.commands[0]);two=x.guard.spawn(x.commands[1])
        assert one.plan['name']=='race_one' and two.plan['name']=='race_two'
        assert not set(one.keys).intersection(two.keys)
        assert one.identity()['pid']!=two.identity()['pid']
        assert one.identity()['parent_pid']==two.identity()['parent_pid']==10
        assert one.child.job!=two.child.job and one.child.binding is not two.child.binding
        assert one.child.binding.runtime_handle!=two.child.binding.runtime_handle
        one.communicate();two.communicate()
        assert one.closed and two.closed and not x.calls.handles and x.port.all_members()==set()
        assert all(row['closed'] for row in x.ledger.state['resources'].values())


def test_actual_fallback_body_cannot_bind_even_an_ephemeral_loopback_socket_under_guard():
    import ast
    from pathlib import Path
    from scripts.observation_runtime.aip06_fixture_guard import audit
    runtime=Path('logs/diagnostics/qd-native-install-2e13e1d5b0f44498/candidate/python/Lib')
    tree=ast.parse((runtime/'socket.py').read_text())
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_fallback_socketpair')
    attempts=[]
    class Socket:
        def bind(self,address):attempts.append(address);audit('socket.bind',(self,address))
        def close(self):attempts.append('closed')
        def listen(self):raise AssertionError('Guard must refuse before listen')
    namespace={'AF_INET':2,'AF_INET6':23,'SOCK_STREAM':1,'_LOCALHOST':'127.0.0.1','_LOCALHOST_V6':'::1',
               'socket':lambda *args:Socket()}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(runtime/'socket.py'),'exec'),namespace)
    x=fixture()
    with x.guard.installed(),pytest.raises(ValueError,match='NO_NETWORK_TRANSPORT'):
        namespace['_fallback_socketpair']()
    assert attempts==[('127.0.0.1',0),'closed'] and not x.calls.handles


def test_static_default_runtime_review_never_upgrades_to_compatible():
    from pathlib import Path
    from scripts.observation_runtime.aip06_async_review import review_sources,require_compatible
    root=Path('logs/diagnostics/qd-native-install-2e13e1d5b0f44498/candidate/python/Lib')
    result=review_sources(socket_source=(root/'socket.py').read_bytes(),
        proactor_source=(root/'asyncio/proactor_events.py').read_bytes(),policy_source=(root/'asyncio/windows_events.py').read_bytes())
    assert result['default_proactor'] and result['self_socketpair'] and result['fallback_binds_tcp']
    assert result['runtime_socketpair_branch']=='UNEXECUTED' and result['compatible'] is False
    with pytest.raises(ValueError,match='SEPARATE_EVIDENCE'):require_compatible(result)
    with pytest.raises(ValueError,match='NOT_NATIVE_AUTHORITY'):require_compatible({**result,'compatible':True})


def plan():
    from scripts.observation_runtime.aip06_acceptance_plan import candidate_plan,ENTRY
    return candidate_plan(source_pins={ENTRY:'a'*64},runtime_inventory={
        'path':ntpath.join(ntpath.dirname(ROOTS['E']),'INJECTED-INVENTORY.json'),'sha256':'b'*64,
        'files':1,'directories':1,'read_bytes':1,'native_identity_accepted':False,'complete_acl_accepted':False},
        async_review={'compatible':False,'native_execution':False})


def test_canonical_manifest_decode_is_deterministic_and_has_all_three_full_stop_slots():
    import hashlib
    from app.services.paper_financial_replay import body
    from scripts.observation_runtime.aip06_acceptance_plan import decode_plan,phase_budgets,schedule
    value=plan();raw=body(value).encode()
    assert decode_plan(raw,hashlib.sha256(raw).hexdigest())==value
    assert sum(phase_budgets().values())==600
    samples=[row for row in schedule() if row['id'].startswith('STOP-')]
    assert [row['sample'] for row in samples]==[1,2,3]
    assert all(row['deadline_ns']==8*10**9 and row['reader']=='COLD_AFTER_ORIGINAL_WRITER_EXIT' for row in samples)
    assert len([row for row in schedule() if row['id'].startswith('F')])==12


@pytest.mark.parametrize('field',['schema','scope','native_authority','authorization','entry','working_directory','executable',
                                   'roots','limits','network','environment','case_environment','excluded_native_launch_cases','schedule',
                                   'phase_budgets','source_pins','runtime_inventory','async_review','gates','outer_owner'])
def test_changed_candidate_contract_cannot_grant_native_execution(field):
    from scripts.observation_runtime.aip06_acceptance_plan import validate_plan
    value=plan();value[field]=True
    with pytest.raises((ValueError,TypeError,AttributeError)):validate_plan(value)


def test_candidate_controller_preparation_never_runs_a_backend_or_consumes_a_grant():
    import hashlib
    from app.services.paper_financial_replay import body
    from scripts.observation_runtime.aip06_acceptance_controller import prepare
    from scripts.observation_runtime.aip06_acceptance_plan import require_execution_ready,decode_plan
    value=plan();raw=body(value).encode();pin=hashlib.sha256(raw).hexdigest()
    assert prepare(raw,pin)==value
    with pytest.raises(ValueError,match='NO_CONTROLLER_LAUNCH'):require_execution_ready(value)
    with pytest.raises(ValueError,match='PIN_MISMATCH'):decode_plan(raw,'f'*64)
    with pytest.raises(ValueError):decode_plan(raw+b' ',hashlib.sha256(raw+b' ').hexdigest())
    assert value['authorization']=='PENDING' and value['native_authority'] is False


def test_actual_race_start_uses_only_existing_guarded_launch_options():
    import ast
    from pathlib import Path
    tree=ast.parse(Path('tests/test_perp_order_crash_race_native.py').read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='start')
    call=next(n for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
              and isinstance(n.func.value,ast.Name) and n.func.value.id=='guarded' and n.func.attr=='popen')
    assert {k.arg for k in call.keywords}=={'stdout','stderr','text','env'}
    # Hidden/suspended native creation remains owned by the existing guarded
    # adapter; a legacy Popen creationflags option must not reach this port.
    from scripts.observation_runtime.aip06_windows_process import Win32ProcessCalls
    import inspect
    assert '0x4 | 0x8' in inspect.getsource(Win32ProcessCalls.create_suspended)
