"""Offline physical framing + injected native ownership, never real workers."""
import copy
from types import SimpleNamespace
import pytest
from app.services.paper_financial_replay import digest
from scripts.observation_runtime.aip06_harness import SCOPE_HASH
from scripts.observation_runtime.aip06_ipc import Broker, Channel, RemoteResources
from scripts.observation_runtime.aip06_remote_handles import RetainedPeerHandles, RemoteHandleProofs
from scripts.observation_runtime.aip06_graph_evidence import validate_graph_evidence
from test_aip06_suspended_graph import staged_fixture
from test_aip06_windows_adapters import MemoryEndpoint, ACCOUNTS, Output


def fixture(f=None):
    f=staged_fixture() if f is None else f;x=f.x
    original=x.calls.duplicate
    def duplicate(source,h):
        if source != -1:
            if h not in x.calls.handles:
                error=OSError('injected closed original');error.winerror=6;raise error
            kind,value=x.calls.handles[h];local=x.calls.allocate(kind,value)
            if kind=='job':x.calls.jobs[local]=x.calls.jobs[h]
            return local
        return original(source,h)
    x.calls.duplicate=duplicate
    old_observe=f.objects_port.observe
    def observe(h):
        kind,value=x.calls.handles[h]
        if kind in ('process','parent'):return {'type':'Process',**x.calls.native(h),**x.calls.lifecycle(h)}
        if kind=='job':return {'type':'Job','members':sorted(x.calls.members(h)), 'limits':x.calls.job_limits(h)}
        if kind=='image':return {'type':'File','native':x.files.describe(h),'path':value}
        if kind=='pipe':return {'type':'Pipe'}
        return old_observe(h)
    f.objects_port.observe=observe
    p=RetainedPeerHandles(binding=f.peer,resources=x.ledger,calls=x.calls,files=x.files,
        allocations=x.alloc,allowed_path=lambda path:None,objects=f.objects_port,descendants=f.registry)
    wire={'scope':SCOPE_HASH,'session':'a'*32,'nonce':f.peer.request.nonce,
          'parent':f.peer.parent,'child':f.peer.runtime,'job':f.peer.api.job,'launch':f.peer.launch}
    a,b=MemoryEndpoint(),MemoryEndpoint();a.peer=b;b.peer=a
    a.verify_peer=p.verify_peer;a.capture_peer=p.capture_peer;a.admit_frame=p.admit_frame
    # This sender proves its original peer identity; admission and the complete
    # native graph are independently checked by the receiving parent.
    b.capture_peer=p.capture_peer;b.verify_peer=p.verify_peer
    parent=Channel(a,binding=wire,clock_ns=lambda:x.now[0],account_scope=ACCOUNTS,role='PARENT')
    child=Channel(b,binding=wire,clock_ns=lambda:x.now[0],account_scope=ACCOUNTS,role='CHILD')
    output=Output();broker=Broker(resources=x.ledger,channel=parent,peer_owner=f.owner,verifier=p,
                                output=output,clock_ns=lambda:x.now[0])
    b.after_write=lambda:broker.serve_once(deadline_ns=x.now[0]+6*10**9)
    remote=RemoteResources(child,owner=f.owner,initial=x.ledger.read(),clock_ns=lambda:x.now[0],proofs=RemoteHandleProofs(f.owner))
    for i in range(8):
        key=f.creator.reserve('pipe-'+str(i),'pipe')
        f.held.append((key,x.calls.allocate('pipe',i)))
    keys=tuple(k for k,h in f.held)
    f.registry.declared_keys[f.request.nonce]=keys
    allocations={k:{'kind':x.ledger.state['resources'][k]['kind'],'handle':h} for k,h in f.held}
    proof={**f.proof,'allocations':allocations}
    return SimpleNamespace(**locals())


def stage(z):
    value=z.remote.stage_descendant(z.proof,z.f.request,z.x.calls.native(z.f.hp))
    for k,v in z.allocations.items():z.remote.proofs.bind(k,v['handle'])
    return value


def bind(z):
    stage(z);z.remote.resume_descendant(z.f.request.nonce,z.x.calls.native(z.f.hp))
    from scripts.observation_runtime.launch_ownership import RetainedLaunchBinding
    api=z.f.observer_factory(job=z.f.job,parent=z.f.parent)
    local=RetainedLaunchBinding(api,z.f.request,z.f.parent,z.f.hp)
    local.bind_runtime(z.f.hp,{'pid':z.f.pid,'nonce':z.f.request.nonce,'role':z.f.request.role})
    z.remote.bind_reserved_process(z.f.slot,z.f.owner,local,z.f.hp)
    return local


def exit_child(z):
    z.x.calls.exits[z.f.pid]=0
    for job in z.x.calls.jobs.values():job['members'].discard(z.f.pid)


def test_first_transfer_crosses_framing_fence_and_receipt_after_native_admission():
    z=fixture()
    # Full verification refuses before registration, while identity capture is
    # allowed. Do not invoke binding.verify here: its refusal is irreversible.
    assert z.x.calls.members(z.f.peer.api.job)=={20,30}
    receipt=stage(z)
    assert receipt['identity']['pid']==z.f.pid and receipt['released_to_bootstrap'] is False
    assert [r['schema'] for r in z.output.records]==['AIP06_RPC_INTENT_V1','AIP06_RPC_RESULT_V1']
    assert {r['pid'] for r in z.f.peer.verify()}=={20,30}
    assert set(z.p.live)==set(z.allocations)


@pytest.mark.parametrize('damage',['declaration','child','job','resources','receipt'])
def test_first_transfer_missing_or_conflicting_evidence_refuses(damage):
    z=fixture()
    if damage=='declaration':z.f.registry.declarations.clear()
    elif damage=='child':z.x.calls.rows[z.f.pid]['parent_pid']=999
    elif damage=='job':z.x.calls.jobs[z.f.peer.api.job]['members'].discard(z.f.pid)
    elif damage=='resources':z.proof['allocations'].pop(next(iter(z.proof['allocations'])))
    else:
        real=z.p.stage_descendant
        def wrong(*args):
            real(*args);return None
        z.p.stage_descendant=wrong
    with pytest.raises((ValueError,KeyError)):stage(z)
    assert z.remote.uncertain and not z.f.pid in z.x.calls.exits
    assert 'independent-bootstrap-release' not in z.x.calls.events


def test_final_release_requires_both_native_handle_sets_and_ledger_then_is_idempotent():
    z=fixture();bind(z);exit_child(z)
    z.remote.release_descendant(z.f.request.nonce)
    assert all(z.x.calls.closed(h) for _,h in z.f.registry.held[z.f.request.nonce])
    assert not z.x.calls.closed(z.f.hp)
    for key,h in reversed(z.f.held):
        z.x.calls.close(h)
        z.remote.close(z.f.owner,key,observer=SimpleNamespace(closed=lambda owner,k:True))
    z.x.calls.close(z.f.hp)
    owner=digest(z.f.registry.bindings[z.f.request.nonce][0].runtime)
    z.remote.close(owner,z.f.slot,observer=SimpleNamespace(closed=lambda *a:True))
    head=z.x.ledger.head
    z.remote.close(owner,z.f.slot,observer=SimpleNamespace(closed=lambda *a:True))
    assert z.x.ledger.head==head and z.x.ledger.state['resources'][z.f.slot]['closed']
    assert not z.p.live


@pytest.mark.parametrize('damage',['running','creator_handle','ledger_leak','interrupted','wrong_owner','child_resource_leak','parent_duplicate_close'])
def test_release_incomplete_evidence_never_refunds_process_slot(damage):
    z=fixture();bind(z)
    if damage=='child_resource_leak':
        owner=digest(z.f.registry.bindings[z.f.request.nonce][0].runtime)
        z.x.ledger.reserve(owner,'injected-unreleased-child-resource','handle')
    if damage=='parent_duplicate_close':
        exit_child(z)
        original=z.x.calls.close;fail=z.f.registry.held[z.f.request.nonce][0][1]
        def interrupted(h):
            if h==fail:raise OSError('injected interrupted duplicate close')
            return original(h)
        z.x.calls.close=interrupted
        with pytest.raises(OSError):z.remote.release_descendant(z.f.request.nonce)
        assert z.f.registry.failed and not z.x.ledger.state['resources'][z.f.slot]['closed']
        return
    if damage!='running':
        exit_child(z);z.remote.release_descendant(z.f.request.nonce)
    if damage=='running':
        operation=lambda:z.remote.release_descendant(z.f.request.nonce)
    else:
        for key,h in reversed(z.f.held):
            if damage in ('ledger_leak','interrupted') and key==z.f.held[0][0]:continue
            z.x.calls.close(h)
            z.remote.close(z.f.owner,key,observer=SimpleNamespace(closed=lambda *a:True))
        if damage!='creator_handle':z.x.calls.close(z.f.hp)
        owner=digest(z.f.registry.bindings[z.f.request.nonce][0].runtime)
        if damage=='wrong_owner':owner='f'*64
        operation=lambda:z.remote.close(owner,z.f.slot,observer=SimpleNamespace(closed=lambda *a:True))
    with pytest.raises((ValueError,KeyError)):operation()
    assert not z.x.ledger.state['resources'][z.f.slot]['closed']


@pytest.mark.parametrize('damage',['stale','missing_parent','duplicate','wrong_peer'])
def test_authenticated_recursive_graph_receipt_refuses_ambiguity(damage):
    z=fixture();stage(z);e=z.p.graph_evidence()
    assert validate_graph_evidence(e,z.wire,z.x.now[0])
    if damage=='stale':e['at_ns']-=7*10**9
    elif damage=='missing_parent':e['rows'][0]['parent_pid']=999
    elif damage=='duplicate':e['rows'].append(copy.deepcopy(e['rows'][0]))
    else:e['peer']={**e['peer'],'created':1}
    with pytest.raises(ValueError):validate_graph_evidence(e,z.wire,z.x.now[0])


def test_unregistered_or_replayed_forwarded_channel_cannot_be_adopted():
    z=fixture();bind(z)
    nested={**z.wire,'parent':z.f.peer.runtime,'child':z.f.registry.bindings[z.f.request.nonce][0].runtime,
            'launch':z.f.registry.bindings[z.f.request.nonce][0].launch,'nonce':z.f.request.nonce,'job':z.f.job}
    with pytest.raises(ValueError,match='PRE_REGISTERED'):
        z.p.forward_operation(z.wire,{'wire':nested,'request':{}})
    z.p.register_descendant_channel(z.wire,nested)
    with pytest.raises(ValueError,match='ALREADY_REGISTERED'):z.p.register_descendant_channel(z.wire,nested)
    changed={**nested,'child':{**nested['child'],'created':999}}
    with pytest.raises(ValueError,match='ANCESTRY'):z.p.forward_operation(z.wire,{'wire':changed,'request':{}})
    with pytest.raises(ValueError,match='ANCESTRY'):
        z.p.forward_operation(z.wire,{'wire':{**nested,'job':z.x.aggregate.job},'request':{}})


def recursive_fixture():
    from dataclasses import replace
    from subprocess import list2cmdline
    from scripts.observation_runtime.aip06_child_bootstrap import InheritedIdentity
    z=fixture();local=bind(z)
    nested={**z.wire,'parent':z.f.peer.runtime,'child':local.runtime,'launch':local.launch,
            'nonce':z.f.request.nonce,'job':z.f.job}
    z.remote.register_descendant_channel(nested)
    q=RetainedPeerHandles(binding=local,resources=z.remote,calls=z.x.calls,files=z.x.files,
        allocations=z.f.creator,allowed_path=lambda path:None,objects=z.f.objects_port)
    a,b=MemoryEndpoint(),MemoryEndpoint();a.peer=b;b.peer=a
    a.capture_peer=q.capture_peer;a.verify_peer=q.verify_peer;a.admit_frame=q.admit_frame
    identity=InheritedIdentity(observer=local.api,current_handle=z.f.hp,parent_handle=z.f.parent,job_handle=z.f.job)
    identity.clock=lambda:z.x.now[0]
    identity.descendants=lambda: [] if identity.attested is None else validate_graph_evidence(identity.attested,nested,z.x.now[0])
    b.capture_peer=identity.capture;b.verify_peer=identity.verify;b.admit_frame=identity.admit_frame
    parent=Channel(a,binding=nested,clock_ns=lambda:z.x.now[0],account_scope=ACCOUNTS,role='PARENT')
    child=Channel(b,binding=nested,clock_ns=lambda:z.x.now[0],account_scope=ACCOUNTS,role='CHILD')
    broker=Broker(resources=z.remote,channel=parent,peer_owner=digest(local.runtime),verifier=q,
                  output=Output(),clock_ns=lambda:z.x.now[0])
    b.after_write=lambda:broker.serve_once(deadline_ns=z.x.now[0]+6*10**9)
    remote=RemoteResources(child,owner=digest(local.runtime),initial=z.remote.snapshot,
                           clock_ns=lambda:z.x.now[0],proofs=RemoteHandleProofs(digest(local.runtime)))
    argv=[z.f.request.launch_image[0],'-B',r'D:\reviewed\child.py']
    request=replace(z.f.request,nonce='e'*32,launch_command=list2cmdline(argv),runtime_command=list2cmdline(argv))
    slot='second-generation-launch';remote.reserve(remote.owner,slot,'launch')
    values={}
    for index,kind in enumerate(('job','handle','image','thread',*('pipe',)*8)):
        key='grandchild-'+kind+str(index);remote.reserve(remote.owner,key,kind)
        values[key]={'kind':kind,'handle':None}
    remote.declare_descendant(request,slot,keys=tuple(values))
    calls=z.x.calls
    job=calls.create_job('injected-grandchild',calls.job_limits(z.f.job))
    parent_handle=calls.allocate('process',z.f.pid)
    image=z.x.files.open_image(request.launch_image[0])
    hp,ht,pid,tid=calls.create_suspended(executable=request.launch_image[0],argv=argv)
    calls.rows[pid]['parent_pid']=z.f.pid
    z.x.suspends[calls.handles[ht]]=1
    for group in (z.x.aggregate.job,z.f.peer.api.job,z.f.job,job):calls.assign(group,hp)
    for key,h in zip(values,(job,parent_handle,image,ht,*(calls.allocate('pipe',i) for i in range(8))),strict=True):values[key]['handle']=h
    proof={'nonce':request.nonce,'parent':parent_handle,'launch':hp,'thread':ht,'tid':tid,'image':image,'job':job,'allocations':values}
    remote.stage_descendant(proof,request,calls.native(hp))
    return SimpleNamespace(**locals())


def test_recursive_physical_rpc_keeps_one_ledger_and_current_complete_native_roster():
    t=recursive_fixture()
    assert {r['pid'] for r in t.z.f.peer.verify()}=={20,30,40}
    assert {r['pid'] for r in t.local.verify()}=={30,40}
    assert {r['pid'] for r in t.z.x.guard.ownership.verify()}=={20,30,40}
    assert t.remote.verify_descendants()['members']==[10,20,30,40]
    assert t.remote.state==t.z.x.ledger.state and t.remote.recovered is False
    assert len(t.z.x.aggregate.descendant_registries)==2
    assert t.identity.verify(t.nested)['pid']==30


@pytest.mark.parametrize('damage',['stale','unregistered','missing_job','changed_birth','foreign_parent'])
def test_recursive_roster_and_inherited_peer_reject_missing_or_conflicting_evidence(damage):
    t=recursive_fixture();calls=t.z.x.calls
    if damage=='stale':
        t.z.x.now[0]+=7*10**9
        operation=lambda:t.identity.verify(t.nested)
    else:
        if damage=='unregistered':calls.jobs[t.z.f.job]['members'].add(999)
        elif damage=='missing_job':calls.jobs[t.z.f.job]['members'].remove(t.pid)
        elif damage=='changed_birth':calls.rows[t.pid]['created']+=100
        else:calls.rows[t.pid]['parent_pid']=10
        operation=t.z.f.peer.verify
    with pytest.raises(ValueError):operation()


def test_recursive_release_closes_child_reservations_before_ancestor_originals():
    from scripts.observation_runtime.launch_ownership import RetainedLaunchBinding
    t=recursive_fixture();z=t.z;calls=t.calls
    t.remote.resume_descendant(t.request.nonce,calls.native(t.hp))
    api=z.f.observer_factory(job=t.job,parent=t.parent_handle)
    bound=RetainedLaunchBinding(api,t.request,t.parent_handle,t.hp)
    bound.bind_runtime(t.hp,{'pid':t.pid,'nonce':t.request.nonce,'role':t.request.role})
    t.remote.bind_reserved_process(t.slot,t.remote.owner,bound,t.hp)
    calls.exits[t.pid]=0
    for group in calls.jobs.values():group['members'].discard(t.pid)
    t.remote.release_descendant(t.request.nonce)
    for key,row in t.values.items():
        t.remote.proofs.bind(key,row['handle'])
        calls.close(row['handle'])
        t.remote.close(t.remote.owner,key,observer=SimpleNamespace(closed=lambda *a:True))
    calls.close(t.hp)
    t.remote.close(digest(bound.runtime),t.slot,observer=SimpleNamespace(closed=lambda *a:True))
    assert {r['pid'] for r in z.f.peer.verify()}=={20,30}
    exit_child(z);z.remote.release_descendant(z.f.request.nonce)
    for key,h in reversed(z.f.held):
        calls.close(h)
        z.remote.close(z.f.owner,key,observer=SimpleNamespace(closed=lambda *a:True))
    calls.close(z.f.hp)
    z.remote.close(digest(t.local.runtime),z.f.slot,observer=SimpleNamespace(closed=lambda *a:True))
    assert {r['pid'] for r in z.f.peer.verify()}=={20}
    assert not z.p.live and not z.p.forwarded[z.f.request.nonce][1].verifier.live
    assert all(r['closed'] for r in z.x.ledger.state['resources'].values()
               if r['owner'] in (digest(t.local.runtime),digest(bound.runtime)))
