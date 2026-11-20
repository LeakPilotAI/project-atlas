"""Joined controller contracts over injected Windows and real framed memory IPC.

No native loaders/processes, financial workers, authorizations or installed app.
"""
import copy
from dataclasses import replace
from subprocess import list2cmdline
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import body, digest
from scripts.observation_runtime.aip06_acceptance_control import Dispatcher, GuardedScenarioBridge, OwnerLaunch, Deadline
from scripts.observation_runtime.aip06_acceptance_grade import IndependentGrader, READERS
from scripts.observation_runtime.aip06_controller_contract import (
    CONTRACT, ENTRY, ROLE, ControllerIntent, PrecreationReceipt, bootstrap_argv, controller_argv, inherited_context, verify_prepared,
)
from scripts.observation_runtime.aip06_harness import LIMITS, ROOTS, SCOPE_HASH
from scripts.observation_runtime.aip06_ipc import Channel
from scripts.observation_runtime.aip06_windows_acceptance_adapters import WindowsAcceptanceOwner
from scripts.observation_runtime.aip06_windows_endpoints import WindowsChildEndpoints
from test_aip06_native_prerequisites import plan


def owner_fixture(monkeypatch):
    import test_aip06_native_session_stop as original
    from test_aip06_physical_native_proofs import aggregate_fixture
    import scripts.observation_runtime.aip06_native_session as sessions
    p=plan();p['source_pins'][CONTRACT]='a'*64
    monkeypatch.setattr(original,'EXE',p['executable'])
    monkeypatch.setattr(sessions.secrets,'token_hex',lambda n:'b'*32)
    x=aggregate_fixture()
    x.controller.process_port=x.port;x.controller.require_ready=lambda:None
    x.controller.profile['source_pins']=p['source_pins']
    x.controller.profile['targets']={ROLE:ENTRY}
    endpoints=WindowsChildEndpoints(pipe_calls=None,clock_ns=lambda:x.now[0],output=None)
    x.protocol.command=endpoints.command
    x.intent=ControllerIntent(body(p).encode(),digest(p))
    x.before=PrecreationReceipt.capture(x.intent,paths=x.guard.paths,clock_ns=lambda:x.now[0],deadline_ns=x.now[0]+10**9)
    with x.guard.installed():x.guard.mkdir(ROOTS['E'])
    x.owner_adapter=WindowsAcceptanceOwner(controller=x.controller,guard=x.guard,intent=x.intent,precreation=x.before,
        capacity=SimpleNamespace(read=lambda **kw:x.aggregate.observe(commit=False)),clock_ns=lambda:x.now[0])
    return x


def launch(x):
    x.owner_adapter.preflight(x.intent.plan(),manifest_sha256=x.intent.sha256,deadline_ns=x.now[0]+10**9)
    x.owner_adapter.reserve(dict(LIMITS),deadline_ns=x.now[0]+10**9)
    return x.owner_adapter._launch_reserved(ENTRY,x.intent.plan()['executable'],deadline_ns=x.now[0]+10**9)


def finish(x,lease):
    with x.guard.installed():
        assert x.owner_adapter.cleanup(lease,deadline_ns=x.now[0]+10**9)
        assert x.owner_adapter.cleanup(lease,deadline_ns=x.now[0]+10**9)
        x.aggregate.close(deadline_ns=x.now[0]+10**9)
        assert not x.calls.handles
        assert all(v['closed'] for v in x.ledger.state['resources'].values())


@pytest.mark.parametrize('damage',[None,'nonce','owner','parent','manifest','raw','argv','pins'])
def test_one_joined_owner_bootstrap_shared_guard_dispatcher_refusal_and_complete_release(monkeypatch,damage):
    import test_aip06_windows_adapters as child_fixture
    x=owner_fixture(monkeypatch)
    with x.guard.installed():lease=launch(x)
    assert lease.binding.request.role=='acceptance_supervisor'
    assert lease.session.argv==x.intent.argv
    assert lease.binding.runtime['command_line']==list2cmdline(bootstrap_argv(x.intent.plan()['executable'],'b'*32))
    packet=lease.preparation_packet(x.intent.plan(),x.intent.sha256)
    if damage=='nonce':packet['nonce']='f'*32
    elif damage=='owner':packet['owner']='f'*64
    elif damage=='parent':packet['parent_owner']='f'*64
    elif damage=='manifest':packet['manifest']='f'*64
    elif damage=='raw':packet['raw']+=' '
    def channels():
        binding={'scope':SCOPE_HASH,'session':'a'*32,'nonce':'b'*32,'parent':lease.binding.parent,
                 'child':lease.binding.runtime,'job':{'name':'Local\\injected-controller'},
                 'launch':{'command':lease.binding.request.launch_command}}
        a,b=child_fixture.MemoryEndpoint(),child_fixture.MemoryEndpoint();a.peer=b;b.peer=a
        parent=Channel(a,binding=binding,clock_ns=lambda:x.now[0],account_scope=child_fixture.ACCOUNTS,role='PARENT')
        child_channel=Channel(b,binding=binding,clock_ns=lambda:x.now[0],account_scope=child_fixture.ACCOUNTS,role='CHILD')
        return SimpleNamespace(s=SimpleNamespace(ledger=x.ledger,now=x.now,controller=x.owner),
                               owner=digest(binding['child']),a=a,b=b,parent=parent,child_channel=child_channel)
    monkeypatch.setattr(child_fixture,'channels',channels)
    f=child_fixture.bootstrap_fixture(role='acceptance_supervisor',target_override=ENTRY,pins_override=x.intent.plan()['source_pins'],
        controller_command=x.intent.argv,controller_targets={ROLE:ENTRY})
    f.broker.verifier.verify_peer=lambda binding:lease.binding.verify()
    f.boot.prepare()
    f.x.parent.send('INPUT',packet,deadline_ns=x.now[0]+10**9)
    descriptor={'argv':x.intent.argv,'source_pins':x.intent.plan()['source_pins'],'targets':{ROLE:ENTRY}}
    if damage=='argv':descriptor['argv']=(*x.intent.argv[:-1],'f'*64)
    elif damage=='pins':descriptor['source_pins']={ENTRY:'f'*64}
    observed=[]
    def run(target):
        from scripts.observation_runtime.aip06_session_io import ChildSessionIO
        stream=ChildSessionIO(f.boot.guard,clock_ns=lambda:x.now[0])
        child_controller=SimpleNamespace(profile={'source_pins':x.intent.plan()['source_pins']},clock=lambda:x.now[0])
        service=SimpleNamespace(port=SimpleNamespace(controller=child_controller),runtime=SimpleNamespace(descriptor=descriptor),
                                read_input=stream.read_input,emit_output=stream.emit_output)
        f.boot.guard.processes=service;child_controller.process_port=service
        from scripts.observation_runtime.aip06_acceptance_controller import inherited_prepare,publish_prepared
        context=inherited_prepare()
        assert context.root_owner==x.owner and context.guard.resources.channel is f.x.child_channel
        publish_prepared(context)
        class Reader:
            domain='INJECTED_SOURCE_ONLY';source_path=ENTRY;source_sha256='a'*64
            def read(self,*a,**k):raise AssertionError('Missing case must refuse before any grading')
        grader=IndependentGrader(plan=x.intent.plan(),manifest_sha256=x.intent.sha256,readers={n:Reader() for n in READERS},
            clock_ns=lambda:x.now[0],output=[],owner_launch=lease)
        dispatcher=Dispatcher(adapter=GuardedScenarioBridge(child_controller,context.guard,{}),grader=grader,
            deadline=Deadline(lambda:x.now[0]))
        bound=context.bind_dispatcher(dispatcher)
        assert bound.dispatcher is dispatcher
        with pytest.raises(ValueError,match='NO_CONTROLLER_LAUNCH'):bound.run()
        with pytest.raises(ValueError,match='BINDING_MISSING'):dispatcher.run()
        with pytest.raises(ValueError,match='NO_CONTROLLER_LAUNCH'):context.require_native_execution()
        observed.append(context)
        return {'native_acceptance':False,'contract_prepared':True}
    if damage is None:
        assert f.boot.run(run)['native_acceptance'] is False and len(observed)==1
        published=next(row for row in f.output.records if row.get('schema')=='AIP06_CONTROLLER_PREPARED_V1')
        assert verify_prepared(published,binding=lease.binding,manifest=x.intent.sha256,root_owner=x.owner)==published
    else:
        reason = ('PRIVATE_CONTROLLER_INPUT_CORRELATION' if damage in ('nonce','owner','parent') else
                  'PIN_MISMATCH' if damage in ('manifest','raw') else 'INHERITED_CONTROLLER_ARGV_OR_SOURCE_PINS')
        with pytest.raises(ValueError,match=reason):f.boot.run(run)
        assert not observed and f.boot.failed
    finish(x,lease)


def test_public_native_admission_refuses_before_any_query_or_creation(monkeypatch):
    x=owner_fixture(monkeypatch);before=list(x.calls.events)
    with pytest.raises(ValueError,match='AUTHORIZATION'):x.owner_adapter.launch_controller(ENTRY,x.port.executable,deadline_ns=x.now[0]+10**9)
    assert x.calls.events==before and not x.port.sessions
    x.aggregate.close(deadline_ns=x.now[0]+10**9)


@pytest.mark.parametrize('damage',['entry','role','path','hash','executable','extra','no-target'])
def test_controller_command_is_closed_and_never_promotes_a_generic_worker(damage):
    p=plan();p['source_pins'][CONTRACT]='a'*64;intent=ControllerIntent(body(p).encode(),digest(p));argv=list(intent.argv);targets={ROLE:ENTRY}
    if damage=='entry':argv[2]=r'D:\foreign.py'
    elif damage=='role':argv[4]='outer-owner'
    elif damage=='path':argv[6]=r'D:\AtlasRuntime\manifest.json'
    elif damage=='hash':argv[8]='wrong'
    elif damage=='executable':argv[0]=r'C:\python.exe'
    elif damage=='extra':argv.append('--run-financial')
    else:targets={}
    with pytest.raises(ValueError):controller_argv(argv,targets)


@pytest.mark.parametrize('damage',['missing-intent','replay','wrong-pin','different-source','nonroot'])
def test_precreation_declaration_refusals_happen_before_process_creation(monkeypatch,damage):
    x=owner_fixture(monkeypatch)
    with x.guard.installed():
        if damage=='missing-intent':
            with pytest.raises(ValueError,match='EXPLICIT_CONTROLLER_INTENT'):x.port._role(x.intent.argv)
        else:
            x.intent.declare(x.port)
            if damage=='replay':assert x.port._role(x.intent.argv)==ROLE
            if damage=='wrong-pin':argv=(*x.intent.argv[:-1],'f'*64)
            else:argv=x.intent.argv
            if damage=='different-source':x.controller.profile['source_pins']={ENTRY:'f'*64}
            if damage=='nonroot':x.guard.owner='f'*64
            with pytest.raises(ValueError):x.port._role(argv)
    assert not x.port.sessions and not any(e=='create-suspended' for e in x.calls.events)


@pytest.mark.parametrize('damage',['stale','parent','extra-root','wrong-manifest','missing-e'])
def test_precreation_receipt_does_not_adopt_or_reinitialize_roots(monkeypatch,damage):
    x=owner_fixture(monkeypatch);receipt=x.before
    if damage=='stale':x.now[0]+=61*10**9
    elif damage=='parent':receipt=replace(receipt,parent='[]')
    elif damage=='wrong-manifest':receipt=replace(receipt,manifest='f'*64)
    elif damage=='missing-e':x.guard.paths.bound.pop('E')
    else:
        with x.guard.installed():x.guard.mkdir(ROOTS['P'])
    with pytest.raises(ValueError):receipt.bind(x.intent,guard=x.guard,clock_ns=lambda:x.now[0],deadline_ns=x.now[0]+10**9)
    assert not x.port.sessions


@pytest.mark.parametrize('damage',['direct-command','logical-argv','receipt','binding','session','image','birth','job'])
def test_both_physical_and_logical_launch_identity_are_mandatory(monkeypatch,damage):
    x=owner_fixture(monkeypatch)
    with x.guard.installed():lease=launch(x)
    if damage=='direct-command':
        x.calls.rows[lease.binding.runtime['pid']]['command_line']=list2cmdline(x.intent.argv)
    elif damage=='logical-argv':lease.session.argv=(*x.intent.argv[:-1],'f'*64)
    elif damage=='receipt':lease.session.receipt['owner']='f'*64
    elif damage=='binding':lease=replace(lease,binding=copy.copy(lease.binding))
    elif damage=='session':lease=OwnerLaunch(lease.binding,lease.manifest_sha256)
    elif damage=='image':x.calls.rows[lease.binding.runtime['pid']]['image']=r'D:\foreign.exe'
    elif damage=='birth':x.calls.rows[lease.binding.runtime['pid']]['created']+=1
    else:x.calls.jobs[lease.session.job]['members'].add(999)
    with pytest.raises(ValueError):lease.verify(x.intent.plan(),x.intent.sha256)
    # Injected handles only; this test deliberately preserves failed evidence.


def test_reservation_abort_is_one_shot_without_refunding_or_creating_a_child(monkeypatch):
    x=owner_fixture(monkeypatch)
    with x.guard.installed():
        x.owner_adapter.reserve(dict(LIMITS),deadline_ns=x.now[0]+10**9)
        head=x.ledger.head
        assert x.owner_adapter.cleanup(None,deadline_ns=x.now[0]+10**9)
        with pytest.raises(ValueError):x.owner_adapter._launch_reserved(ENTRY,x.port.executable,deadline_ns=x.now[0]+10**9)
        assert x.ledger.head==head and not x.port.sessions
    x.aggregate.close(deadline_ns=x.now[0]+10**9)


def test_initializer_captures_all_absent_roots_before_its_first_create():
    import ast,inspect
    from scripts.observation_runtime.aip06_native_controller import NativeController
    source=ast.parse(inspect.getsource(NativeController))
    method=next(n for n in source.body[0].body if isinstance(n,ast.FunctionDef) and n.name=='initialize')
    captures=[n.lineno for n in ast.walk(method) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='capture']
    creates=[n.lineno for n in ast.walk(method) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='mkdir']
    assert len(captures)==1 and captures[0]<min(creates)


def test_inherited_input_cannot_adopt_a_plain_object_or_root_guard():
    with pytest.raises(ValueError,match='INHERITED_CONTROLLER_GUARD'):
        inherited_context(SimpleNamespace(),{}, {})


def test_large_manifest_does_not_increase_the_private_guard_input_limit():
    from test_aip06_acceptance_control import fixture
    x=fixture();x.owner.launch_controller(x.control.plan['entry'],x.control.plan['executable'],deadline_ns=x.clock()+10**9)
    p=copy.deepcopy(x.files.plan)
    p['source_pins'].update({str(ENTRY)+str(i)+'.py':'a'*64 for i in range(600)})
    intent=ControllerIntent(body(p).encode(),digest(p))
    lease=replace(x.launch,manifest_sha256=intent.sha256,intent=intent)
    lease.session.argv=intent.argv
    with pytest.raises(ValueError,match='EXISTING_GUARD_CAP'):lease.preparation_packet(p,intent.sha256)


def test_formal_controller_role_cannot_be_reserved_as_a_financial_worker():
    from test_aip06_native_session_stop import fixture
    from scripts.observation_runtime.launch_ownership import LaunchRequest
    x=fixture();image=(x.port.executable,(1,2,3),'a'*64)
    request=LaunchRequest('acceptance_worker','b'*32,'direct',image,image,'same','same')
    with pytest.raises(ValueError,match='DECLARED_PRELAUNCH'):
        x.guard.ownership.prepare(ROLE,request,parent_owner=x.owner)
    assert ROLE not in x.guard.ownership.prepared


@pytest.mark.parametrize('field',['owner','root_owner','manifest','native_acceptance','schema'])
def test_preparation_publication_is_exact_and_cannot_claim_native_pass(monkeypatch,field):
    x=owner_fixture(monkeypatch)
    with x.guard.installed():lease=launch(x)
    report={'schema':'AIP06_CONTROLLER_PREPARED_V1','manifest':x.intent.sha256,'owner':digest(lease.binding.runtime),
            'root_owner':x.owner,'native_acceptance':False}
    report[field]=True if field=='native_acceptance' else 'wrong'
    with pytest.raises(ValueError,match='PREPARATION_PUBLICATION'):
        verify_prepared(report,binding=lease.binding,manifest=x.intent.sha256,root_owner=x.owner)
    finish(x,lease)


@pytest.mark.parametrize('damage',[None,'missing','duplicate','wrong-owner','native-pass'])
def test_concrete_endpoint_requires_one_correlated_preparation_frame(monkeypatch,damage):
    x=owner_fixture(monkeypatch)
    with x.guard.installed():lease=launch(x)
    child=lease.session;old=child.channel
    report={'schema':'AIP06_CONTROLLER_PREPARED_V1','manifest':x.intent.sha256,'owner':digest(lease.binding.runtime),
            'root_owner':x.owner,'native_acceptance':False}
    if damage=='wrong-owner':report['owner']='f'*64
    elif damage=='native-pass':report['native_acceptance']=True
    records=[] if damage=='missing' else [{'payload':report}] * (2 if damage=='duplicate' else 1)
    child.channel=SimpleNamespace(saved_outputs=records,send=lambda *a,**kw:None,
        receive=lambda **kw:{'payload':{'target':ENTRY,'result':None}})
    endpoints=WindowsChildEndpoints(pipe_calls=None,clock_ns=lambda:x.now[0],output=None)
    endpoints.state[child.plan['request'].nonce]={'child':child,'closed':False,'port':x.port}
    if damage is None:
        assert endpoints.communicate(child,None,deadline_ns=x.now[0]+10**9,maximum_bytes=65536)==('','')
    else:
        with pytest.raises(ValueError):endpoints.communicate(child,None,deadline_ns=x.now[0]+10**9,maximum_bytes=65536)
    child.channel=old
    finish(x,lease)


def test_private_kernel_staging_also_requires_the_original_installed_guard(monkeypatch):
    x=owner_fixture(monkeypatch)
    with x.guard.installed():x.owner_adapter.reserve(dict(LIMITS),deadline_ns=x.now[0]+10**9)
    before=list(x.calls.events)
    with pytest.raises(ValueError,match='ORIGINAL_ROOT_GUARD_MUST_BE_INSTALLED'):
        x.owner_adapter._launch_reserved(ENTRY,x.port.executable,deadline_ns=x.now[0]+10**9)
    assert before==x.calls.events and not x.port.sessions
    assert x.owner_adapter.cleanup(None,deadline_ns=x.now[0]+10**9)
    x.aggregate.close(deadline_ns=x.now[0]+10**9)
