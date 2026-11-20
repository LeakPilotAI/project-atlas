"""One joined, injected lifecycle. Native backends are never loaded here."""

import copy
import hashlib
import json
import threading
import time
from types import SimpleNamespace

from app.services.paper_financial_replay import body, digest
from scripts.observation_runtime.aip06_bootstrap_lease import ParentBootstrapLease
from scripts.observation_runtime.aip06_harness import ROOTS, SCOPE_HASH, need
from scripts.observation_runtime.aip06_ipc import Channel, Broker
from scripts.observation_runtime.aip06_offline_context import IsolatedFixtureContext, ContextPipes, ENTRY
from scripts.observation_runtime.aip06_pipe_transport import CreditedPipeEndpoint
from scripts.observation_runtime.aip06_remote_handles import RetainedPeerHandles
from scripts.observation_runtime.launch_ownership import RetainedLaunchBinding
from scripts.observation_runtime.aip06_unexpected_probe import candidate_refusal
from test_aip06_descendant_closure import fixture, stage, exit_child
from test_aip06_suspended_graph import staged_fixture
from test_aip06_inherited_qualification import probes
from test_aip06_physical_path import _dmtf
from test_aip06_windows_adapters import ACCOUNTS, Output


class Joined:
    def __init__(self, x=None, parent=None, fault=None):
        self.box={};self.fault=fault
        def reserve(x,owner,request):
            lease=ParentBootstrapLease(x.ledger,owner,request.nonce,lambda:x.now[0])
            descriptor=lease.reserve()
            x.aggregate.descendant_registries[owner].register_bootstrap(request.nonce,descriptor)
            self.box['lease']=lease
            assert len(x.calls.rows)==2 or parent is not None
        f=staged_fixture(x,parent,before_create=reserve,suffix='' if parent is None else '-'+str(parent.pid),
                         physical_manifest=True)
        self.z=fixture(f);self.x=self.z.x;self.f=f
        self.context=None;self.server=None;self.events=[];self.controls=[]
        self.running=threading.Event()

    def start(self):
        z,f,x=self.z,self.f,self.x
        stage(z);z.remote.resume_descendant(f.request.nonce,x.calls.native(f.hp))
        api=f.observer_factory(job=f.job,parent=f.parent);current=api.observe(f.hp)
        self.api=api;self.current=current
        wire={'scope':SCOPE_HASH,'session':'a'*32,'nonce':f.request.nonce,'parent':f.peer.runtime,
              'child':current,'job':f.job,'launch':current}
        handles=[h for k,h in f.held if x.ledger.state['resources'][k]['kind']=='pipe']
        assert len(handles)==8
        # Same eight precreation, ledger-reserved endpoints; only the byte
        # storage/API results are injected, not their ownership declarations.
        parent_handles=(handles[2],handles[1],handles[4],handles[7])
        child_handles=(handles[0],handles[3],handles[6],handles[5])
        self.self_handle=x.calls.allocate('process',f.pid)
        payload={'domain':'INJECTED_OFFLINE','native_acceptance':False,'binding':wire,
                 'now_ns':x.now[0],'accounts':copy.deepcopy(ACCOUNTS),'lease':self.box['lease'].descriptor(),
                 'self_handle':self.self_handle,'pipe_handles':child_handles,
                 'target':r'D:\reviewed\child.py','target_sha256':'a'*64}
        if self.fault=='account':payload['accounts']={'foreign':{}}
        self.context=IsolatedFixtureContext(entry_sha256=hashlib.sha256(ENTRY.read_bytes()).hexdigest(),seconds=180)
        print('JOINED_HOST_PHASE',f.pid,'isolated-start',flush=True)
        context_wire=self.context.start(payload)
        self.context_wire=context_wire
        def control(kind,raw):
            value=json.loads(raw);self.controls.append((kind,value))
            if kind=='CLOSE_SELF':
                need(value=={'key':'isolated-bootstrap-self','nonce':f.request.nonce},'JOINED_CLOSE_ORIGINAL_SELF_ONLY')
                x.calls.close(self.self_handle)
                context_wire.send('SELF_CLOSED',body({**value,'closed':True}).encode())
            elif kind=='CONTEXT_READY':
                need(value['context']==context_wire.peer and value['peer']==context_wire.context
                     and value['owner']==digest(current),'JOINED_ACTUAL_CONTEXT_IDENTITY')
                self.running.set()
            elif kind=='CLOSED':need(value=={'nonce':f.request.nonce,'guard_closed':True},'JOINED_CONTEXT_CLOSE_ACK')
            else:need(kind=='DONE' and value['guard_closed'] is True,'JOINED_UNEXPECTED_CONTEXT_CONTROL')
        pipes=ContextPipes(context_wire,parent_handles,control_handler=control)
        self.pipes=pipes;output=Output();self.output=output
        def verify(binding):
            need(body(binding)==body(wire) and api.observe(f.parent)==f.peer.runtime
                 and api.observe(f.hp)==current and api.members()=={f.pid},'JOINED_CURRENT_ORIGINAL_PEER')
        endpoint=CreditedPipeEndpoint(api=pipes,read_handle=parent_handles[0],write_handle=parent_handles[1],
            credit_read=parent_handles[2],credit_write=parent_handles[3],clock_ns=lambda:x.now[0],
            verify_peer=verify,session_tag=bytes.fromhex(f.request.nonce),capacities={'data':65536,'credit':65536})
        channel=Channel(endpoint,binding=wire,clock_ns=lambda:x.now[0],account_scope=ACCOUNTS,role='PARENT')
        self.channel=channel;self.wire=wire
        self.ready=threading.Event();self.error=None;self.exited=threading.Event()
        def serve():
            try:
                while True:
                    item=channel.receive(deadline_ns=x.now[0]+6*10**9)
                    kind,value=item['kind'],item['payload'];self.events.append(kind)
                    if kind=='HELLO':
                        local=RetainedLaunchBinding(api,f.request,f.parent,f.hp)
                        local.bind_runtime(f.hp,value)
                        z.remote.bind_reserved_process(f.slot,f.owner,local,f.hp)
                        z.remote.register_descendant_channel(wire)
                        peer=RetainedPeerHandles(binding=local,resources=z.remote,calls=x.calls,files=x.files,
                            allocations=f.creator,allowed_path=lambda path:None,objects=f.objects_port)
                        self.local=local
                        self.broker=Broker(resources=z.remote,channel=channel,peer_owner=digest(local.runtime),
                            verifier=peer,output=output,clock_ns=lambda:x.now[0])
                        channel.send('BIND',{'snapshot':copy.deepcopy(z.remote.snapshot),'roots':dict(ROOTS),
                            'source_pins':{payload['target']:payload['target_sha256']},'target':payload['target'],
                            'nonce':f.request.nonce},deadline_ns=x.now[0]+6*10**9)
                    elif kind=='REQUEST':self.broker.serve_message(item,deadline_ns=x.now[0]+6*10**9)
                    elif kind=='BOOTSTRAP':
                        if self.fault=='acquisition':value['slots'][next(k for k,v in value['slots'].items() if v['state']=='RETAINED_NATIVE')]['native']['handle']=99999
                        z.remote.forward_bootstrap(wire,value)
                    elif kind=='ACK' and not self.ready.is_set():
                        channel.send('RELEASE',{'receipt':digest(value),'target':payload['target'],
                                               'sha256':payload['target_sha256']},deadline_ns=x.now[0]+6*10**9)
                        self.ready.set()
                    elif kind=='ACK':self.ack=value
                    elif kind=='DRAIN':self.drain=value
                    elif kind=='EXIT':self.exit=value;self.exited.set();break
                    else:raise ValueError('JOINED_UNEXPECTED_PRIVATE_FRAME')
            except BaseException as error:self.error=error;self.ready.set();self.exited.set()
        self.server=threading.Thread(target=serve,name='aip06-root-private-channel');self.server.start()
        # ACK precedes guard installation. Wait for the actual pinned runner's
        # context receipt, and stop promptly on either side's explicit error.
        while time.monotonic()<context_wire.deadline:
            if self.error is not None or self.context.error is not None or self.context.executed.is_set():break
            if self.ready.is_set() and self.running.is_set():break
            self.running.wait(.002)
        if not (self.ready.is_set() and self.running.is_set() and self.error is None):
            print('JOINED_BOOTSTRAP_DIAGNOSTIC',repr(self.error),repr(self.context.error),flush=True)
            self.abort()
            raise ValueError('JOINED_BOOTSTRAP_FAILED')
        print('JOINED_HOST_PHASE',f.pid,'bootstrap-ready',flush=True)
        return self

    def prove(self):
        t=SimpleNamespace(x=self.x,f=self.f,z=self.z,pipes=self.pipes,output=self.output)
        one,two=probes(t)
        x,f=self.x,self.f
        def table(**kw):
            rows=[x.calls.rows[f.peer.runtime['pid']],x.calls.rows[f.pid]]
            return {'complete':True,'error':None,'started_ns':x.now[0],'finished_ns':x.now[0],
                'rows':[{'ProcessId':r['pid'],'ParentProcessId':r['parent_pid'],'CreationDate':_dmtf(r['created']),
                         'ExecutablePath':r['image'],'CommandLine':r['command_line']} for r in rows]}
        witness=candidate_refusal(binding=f.peer,auxiliary=self.local,tables=SimpleNamespace(read=table),
            calls=x.calls,files=x.files,child=SimpleNamespace(image_handle=f.source),clock_ns=lambda:x.now[0],
            deadline_ns=x.now[0]+5*10**9)
        assert witness['ownership_accepted'] is False and not f.peer.refused
        self.witness=witness
        print('JOINED_HOST_PHASE',f.pid,'ownership-proved',flush=True)
        return one,two,witness

    def stop(self, *, missing_ack=False, incomplete_drain=False):
        x,f,z=self.x,self.f,self.z
        request={'scope':SCOPE_HASH,'nonce':f.request.nonce,'worker':self.current,
                 'operation_id':'joined-child-stop-'+f.request.nonce}
        x.ledger.reserve_stop_request(request)
        self.channel.send('STOP',{'request':request,'revision':0,'accounts':ACCOUNTS},deadline_ns=x.now[0]+6*10**9)
        need(self.exited.wait(max(0,self.context_wire.deadline-time.monotonic())) and self.error is None,
             'JOINED_STOP_OR_DRAIN_FAILED')
        # Erasure/corruption belongs only to the injected observer. The child
        # still executes its genuine receive/ACK/drain path; absence may never
        # be reconstructed from its later normal exit or physical cleanup.
        ack=None if missing_ack else self.ack
        drain={**self.drain,'pending':1} if incomplete_drain else self.drain
        accepted=(body(ack)==body({'request':request,'revision':0,'accounts':ACCOUNTS})
             and drain=={'scope':SCOPE_HASH,'operation_id':request['operation_id'],'pending':0,'unknown':False,'orders':0})
        self.server.join(1);need(not self.server.is_alive(),'JOINED_PARENT_RECEIVE_OWNER_LEAK')
        self.pipes.pump()
        need(any(k=='DONE' for k,v in self.controls),'JOINED_CONTEXT_DONE_MISSING')
        self.context_wire.send('CONTEXT_CLOSE',body({'nonce':f.request.nonce}).encode())
        need(self.context.executed.wait(3),'JOINED_CONTEXT_CLOSE_TIMEOUT')
        self.pipes.pump()
        need(any(k=='CLOSED' for k,v in self.controls),'JOINED_CONTEXT_CLOSE_ACK_MISSING')
        self.context_result=self.context.close()
        exit_child(z)
        z.remote.release_descendant(f.request.nonce)
        self.box['lease'].release(calls=x.calls,child=SimpleNamespace(launch_handle=f.hp,
                creation_native=x.calls.native(f.hp)),deadline_ns=x.now[0]+6*10**9)
        for key,h in reversed(f.held):
            x.calls.close(h)
            z.remote.close(f.owner,key,observer=SimpleNamespace(closed=lambda owner,k:x.calls.closed(h)))
        x.calls.close(f.hp)
        z.remote.close(digest(self.local.runtime),f.slot,observer=SimpleNamespace(closed=lambda *a:x.calls.closed(f.hp)))
        x.ledger.resolve_stop(request,'CLOSED' if accepted else 'FAILED')
        assert not self.pipes.buffers[self.pipes.handles[0]]
        assert self.context_result['closed'] and all(x.ledger.state['resources'][k]['closed'] for k in self.box['lease'].keys)
        print('JOINED_HOST_PHASE',f.pid,'released',flush=True)
        need(accepted,'JOINED_ACK_OR_DRAIN_CORRELATION')
        return self.context_result

    def abort(self):
        """Only this injected context; never a process/PID termination path."""
        if self.context is None or self.context.closed:return
        if not self.context.executed.is_set() and time.monotonic()<self.context_wire.deadline:
            self.context_wire.send('ABORT',b'{}')
        # Expire the injected parent IO wait as a refusal, not an ACK. No real
        # system clock or acceptance threshold is changed.
        self.x.now[0]+=7*10**9
        if self.server is not None:self.server.join(3)
        need(self.server is None or not self.server.is_alive(),'JOINED_ABORT_RECEIVER_NOT_RELEASED')
        self.context_result=self.context.close(failed=True)
