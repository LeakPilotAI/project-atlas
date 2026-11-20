"""Pinned injected child for the isolated source harness, never an OS worker."""

import copy
import json
from types import SimpleNamespace

from app.services.paper_financial_replay import body, digest
from scripts.observation_runtime.aip06_bootstrap_lease import InheritedBootstrapLease, ObserverBatch
from scripts.observation_runtime.aip06_child_bootstrap import ChildBootstrap, InheritedIdentity
from scripts.observation_runtime.aip06_fixture_guard import FixtureGuard, current, require_fixture
from scripts.observation_runtime.aip06_harness import FixturePaths, WorkerOwnership, need, SCOPE_HASH
from scripts.observation_runtime.aip06_ipc import Channel, RemoteResources
from scripts.observation_runtime.aip06_offline_context import ContextPipes
from scripts.observation_runtime.aip06_pipe_transport import CreditedPipeEndpoint
from scripts.observation_runtime.aip06_remote_handles import RemoteHandleProofs
from scripts.observation_runtime.aip06_stop import ChildStopEndpoint


def run(wire, payload):
    need(payload['domain']=='INJECTED_OFFLINE' and payload['native_acceptance'] is False,
         'INJECTED_CHILD_DOMAIN_REQUIRED')
    need(current() is None,'ISOLATED_CHILD_INHERITED_PARENT_GUARD')
    binding=payload['binding'];now=lambda:payload['now_ns']
    handles=tuple(payload['pipe_handles']);pipes=ContextPipes(wire,handles)
    observer=SimpleNamespace(job=binding['job'],parent=2,
        observe=lambda h:copy.deepcopy(binding['child'] if h==1 else binding['parent']),
        members=lambda:{binding['child']['pid']})
    identity=InheritedIdentity(observer=observer,current_handle=1,parent_handle=2,job_handle=binding['job'])
    def verify(value):return identity.verify(value)
    endpoint=CreditedPipeEndpoint(api=pipes,read_handle=handles[0],write_handle=handles[1],credit_read=handles[2],credit_write=handles[3],
        clock_ns=now,verify_peer=verify,session_tag=bytes.fromhex(binding['nonce']),
        capacities={'data':65536,'credit':65536})
    channel=Channel(endpoint,binding=binding,clock_ns=now,account_scope=payload['accounts'],role='CHILD')
    lease=InheritedBootstrapLease(payload['lease'],binding,now)
    batch=ObserverBatch(lease)
    owner=digest(binding['child']);key='isolated-bootstrap-self'
    lease.reserve(owner,key,'handle');lease.bind_native_handle(key,payload['self_handle'])
    lease.seal(retained=(key,*batch.slots))
    def factory(**kw):
        remote=RemoteResources(kw['channel'],owner=kw['owner'],initial=kw['initial'],clock_ns=now,
                               proofs=RemoteHandleProofs(owner))
        guard=FixtureGuard(resources=remote,paths=FixturePaths(SimpleNamespace()),
            ownership=WorkerOwnership(remote,all_members=lambda:set()),owner=owner,
            io=SimpleNamespace(close_cache=lambda:None),processes=SimpleNamespace(),clock_ns=now)
        guard.bootstrap_export=lease.evidence
        return guard
    target=payload['target'];pins={target:payload['target_sha256']}
    boot=ChildBootstrap(channel=channel,identity=identity,target=target,source_pins=pins,
        verify_source=lambda path:{'path':path,'file_id':[1,2,3],'sha256':pins[path],'closed':True},
        guard_factory=factory,clock_ns=now)
    boot.prepare()
    def execute(path):
        guard=require_fixture('isolated-joined-source-child')
        need(current() is guard and guard.owner==owner,'ISOLATED_CHILD_GUARD_IDENTITY')
        wire.send('CONTEXT_READY',body({'context':wire.context,'peer':wire.peer,'owner':owner,
                      'parent_owner':digest(binding['parent']),'bootstrap':digest(lease.descriptor),
                      'native_acceptance':False}).encode())
        stop=ChildStopEndpoint(guard,channel)
        command=json.loads(stop.receive(deadline_ns=now()+6*10**9))
        stop.drained({'scope':SCOPE_HASH,'operation_id':command['operation_id'],
                     'pending':0,'unknown':False,'orders':0},deadline_ns=now()+6*10**9)
        wire.send('CLOSE_SELF',body({'key':key,'nonce':binding['nonce']}).encode())
        while not pipes.control:
            pipes.pump();pipes.pause()
        kind,raw=pipes.control.pop(0)
        need(kind=='SELF_CLOSED' and json.loads(raw)=={'key':key,'nonce':binding['nonce'],'closed':True},
             'ISOLATED_CHILD_NATIVE_RELEASE_WITNESS')
        class Closed:
            def closed(self,who,which):return who==owner and which==key
        lease.close(owner,key,observer=Closed())
        return {'domain':'INJECTED_OFFLINE','native_acceptance':False,'context':wire.context}
    boot.run(execute)
    need(current() is None,'ISOLATED_CHILD_GUARD_NOT_RELEASED')
    wire.send('DONE',body({'context':wire.context,'guard_closed':True,'native_acceptance':False}).encode())
    while not pipes.control:
        pipes.pump();pipes.pause()
    kind,raw=pipes.control.pop(0)
    need(kind=='CONTEXT_CLOSE' and json.loads(raw)=={'nonce':binding['nonce']}
         and not pipes.buffers[handles[0]],'ISOLATED_CONTEXT_TERMINAL_DRAIN')
    wire.send('CLOSED',body({'nonce':binding['nonce'],'guard_closed':True}).encode())
