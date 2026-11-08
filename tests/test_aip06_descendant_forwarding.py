"""Offline precreation declaration RPC; no child or Windows backend."""
from dataclasses import replace
import pytest
from test_aip06_windows_adapters import rpc_fixture
from test_launch_ownership import setup


def test_declaration_round_trip_is_versioned_and_not_a_financial_ack():
    f=rpc_fixture();_,request,_=setup();request=replace(request,role='acceptance_worker')
    seen=[]
    def declare(wire,value,slot):
        seen.append((wire,value,slot))
        return {'schema':'AIP06_DESCENDANT_DECLARED_V1','owner':f.x.owner,'nonce':request.nonce,
                'slot':slot,'financial_ack':False}
    f.verifier.declare_descendant=declare
    result=f.remote.declare_descendant(request,'prior-slot')
    assert result['financial_ack'] is False and seen[0][2]=='prior-slot'
    assert f.remote.revision==1 and f.broker.last==1


def test_conflicting_declaration_receipt_latches_remote_uncertainty():
    f=rpc_fixture();_,request,_=setup();request=replace(request,role='acceptance_worker')
    f.verifier.declare_descendant=lambda *a:{'financial_ack':True}
    with pytest.raises(ValueError):f.remote.declare_descendant(request,'prior-slot')

@pytest.mark.parametrize('method',['stage','resume','release','graph'])
def test_ownership_rpc_round_trips_and_rejects_changed_receipts(method):
    from scripts.observation_runtime.aip06_harness import SCOPE_HASH
    f=rpc_fixture();_,req,_=setup();req=replace(req,role='acceptance_worker');identity={'pid':30,'created':30000,'image':'d:/synthetic/python.exe'}
    f.verifier.capture_peer=f.verifier.verify_peer
    from app.services.paper_financial_replay import digest
    values={
      'stage':{'schema':'AIP06_SUSPENDED_STAGE_V1','scope':SCOPE_HASH,'nonce':req.nonce,'identity':identity,
               'request':digest(vars(req)),'released_to_bootstrap':False,'financial_ack':False},
      'resume':{'schema':'AIP06_STAGED_BOOTSTRAP_RELEASE_V1','scope':SCOPE_HASH,'nonce':req.nonce,'identity':identity,'financial_ack':False,'guard_release':False},
      'release':{'schema':'AIP06_DESCENDANT_RELEASE_V1','scope':SCOPE_HASH,'nonce':req.nonce,'owner':f.x.owner,'duplicates_closed':True,'financial_ack':False},
      'graph':{'scope':SCOPE_HASH,'peer':f.x.child_channel.binding['child'],'members':[10,20], 'at_ns':f.x.s.now[0],'source_head':f.x.s.ledger.head}}
    names={'stage':'stage_descendant','resume':'resume_descendant','release':'release_descendant','graph':'verify_descendants'}
    setattr(f.verifier,names[method],lambda *a:values[method])
    operations={'stage':lambda:f.remote.stage_descendant({'nonce':req.nonce},req,identity),
                'resume':lambda:f.remote.resume_descendant(req.nonce,identity),
                'release':lambda:f.remote.release_descendant(req.nonce),'graph':f.remote.verify_descendants}
    assert operations[method]()==values[method]
    if method=='graph':values[method]['at_ns']-=7*10**9
    else:values[method]['financial_ack']=True
    with pytest.raises(ValueError):operations[method]()
    assert f.remote.uncertain
    with pytest.raises(ValueError,match='UNKNOWN'):f.remote.read()


def test_parent_graph_uses_real_registry_and_refuses_stale_retained_identity():
    from test_aip06_suspended_graph import staged_fixture
    from scripts.observation_runtime.aip06_remote_handles import RetainedPeerHandles
    f=staged_fixture();f.registry.stage_suspended(f.proof)
    p=RetainedPeerHandles.__new__(RetainedPeerHandles)
    p.binding=f.peer;p.resources=f.x.ledger;p.calls=f.x.calls;p.owner=f.owner;p.descendants=f.registry;p.failed=False
    wire={'parent':f.peer.parent,'child':f.peer.runtime}
    result=p.verify_descendants(wire,None)
    assert result['members']==[10,20,30]
    assert f.x.calls.members(f.peer.api.job)=={20,30}
    f.x.calls.rows[20]['created']+=1
    with pytest.raises(ValueError):p.verify_descendants(wire,None)
    f.x.calls.rows[20]['created']-=1
    with pytest.raises(ValueError):p.verify_descendants(wire,None)


def test_missing_registry_and_failed_release_do_not_emit_success():
    from scripts.observation_runtime.aip06_remote_handles import RetainedPeerHandles
    p=RetainedPeerHandles.__new__(RetainedPeerHandles);p.verify_peer=lambda wire:None;p.descendants=None
    p.capture_peer=p.verify_peer
    with pytest.raises(ValueError):p.release_descendant({},'x')
    from types import SimpleNamespace
    def fail(*a,**kw):raise ValueError('original release failed')
    p.descendants=SimpleNamespace(release=fail,finished=set());p.resources=SimpleNamespace(clock=lambda:1)
    with pytest.raises(ValueError,match='original release failed'):p.release_descendant({},'x')


def test_gateway_phase_order_and_receipt_failure_are_latched():
    from types import SimpleNamespace
    from scripts.observation_runtime.aip06_descendant_gateway import DescendantGateway
    f=rpc_fixture();g=DescendantGateway(SimpleNamespace(resources=f.remote));g.port.plan=lambda *a:'plan'
    f.verifier.verify_descendants=lambda *a:{}
    with pytest.raises(ValueError):g.plan(('exact',),{})
    assert g.failed and f.remote.uncertain
    with pytest.raises(ValueError,match='LATCHED'):g.plan(('exact',),{})


def test_concrete_gateway_forwards_the_ordered_session_lifecycle():
    from types import SimpleNamespace
    from app.services.paper_financial_replay import digest
    from scripts.observation_runtime.aip06_harness import SCOPE_HASH
    from scripts.observation_runtime.aip06_descendant_gateway import DescendantGateway
    f=rpc_fixture();_,req,_=setup();req=replace(req,role='acceptance_worker')
    f.verifier.capture_peer=f.verifier.verify_peer
    identity={'pid':30,'created':30000,'image':'d:/synthetic/python.exe'}
    f.verifier.declare_descendant=lambda wire,value,slot,keys:{'schema':'AIP06_DESCENDANT_DECLARED_V1','owner':f.x.owner,'nonce':req.nonce,'slot':slot,'financial_ack':False}
    f.verifier.stage_descendant=lambda wire,proof:{'schema':'AIP06_SUSPENDED_STAGE_V1','scope':SCOPE_HASH,'nonce':req.nonce,'identity':identity,'request':digest(vars(req)),'released_to_bootstrap':False,'financial_ack':False}
    f.verifier.resume_descendant=lambda wire,nonce:{'schema':'AIP06_STAGED_BOOTSTRAP_RELEASE_V1','scope':SCOPE_HASH,'nonce':nonce,'identity':identity,'financial_ack':False,'guard_release':False}
    f.verifier.release_descendant=lambda wire,nonce:{'schema':'AIP06_DESCENDANT_RELEASE_V1','scope':SCOPE_HASH,'nonce':nonce,'owner':f.x.owner,'duplicates_closed':True,'financial_ack':False}
    g=DescendantGateway(SimpleNamespace(resources=f.remote,calls=SimpleNamespace(native=lambda h:identity)))
    s=SimpleNamespace(plan={'request':req},permit={'slots':['prior-slot']},launch_handle=None,creation_attempted=False,suspended=True,keys=(),native={})
    g.before_create(s)
    s.launch_handle=11;s.creation_attempted=True;s.creation_native=identity
    s.parent_handle=12;s.thread=13;s.thread_id=31;s.image_handle=14;s.job=15
    g.after_create(s);g.resume(s)
    s.binding=SimpleNamespace(finished=True)
    result=g.release(s)
    assert result['financial_ack'] is False and g.pending[req.nonce]['phase']=='RELEASED'
    assert f.remote.revision==4 and f.broker.last==4
    with pytest.raises(ValueError):g.resume(s)
    assert g.failed
