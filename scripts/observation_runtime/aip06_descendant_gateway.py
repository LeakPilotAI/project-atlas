"""Child-side ownership forwarding. No native calls or creation at construction."""
from app.services.paper_financial_replay import body
from scripts.observation_runtime.aip06_harness import need
from scripts.observation_runtime.aip06_ipc import RemoteResources


class DescendantGateway:
    def __init__(self,port):
        need(type(port.resources) is RemoteResources,'ONE_PARENT_LEDGER_GATEWAY_REQUIRED')
        self.port,self.remote=port,port.resources
        self.pending={};self.failed=False

    def rows(self):
        """Child-side original creation handles supplement parent admission."""
        need(not self.failed, 'DESCENDANT_GATEWAY_FAILURE_LATCHED')
        identity=getattr(self.remote.channel.endpoint,'inherited_identity',None)
        attested=[]
        if identity is not None and identity.attested is not None:
            from scripts.observation_runtime.aip06_graph_evidence import validate_graph_evidence
            attested=validate_graph_evidence(identity.attested,self.remote.channel.binding,self.remote.clock())
        rows=[]
        for row in self.pending.values():
            s=row['session']
            if s.launch_handle is None or s.closed:
                continue
            native=self.port.calls.native(s.launch_handle)
            need(native == s.creation_native, 'LOCAL_DESCENDANT_BIRTH_CHANGED')
            if self.port.calls.lifecycle(s.launch_handle)['exited']:
                need(not self.port.calls.members(s.job), 'EXITED_DESCENDANT_JOB_NOT_EMPTY')
                continue
            current=s.observer.observe(s.launch_handle)
            parent=s.observer.observe(s.parent_handle)
            from scripts.observation_runtime.launch_ownership import RetainedLaunchBinding
            RetainedLaunchBinding._match(current,s.plan['request'].launch_image,
                                        s.plan['request'].launch_command,parent)
            need(parent == self.remote.channel.binding['child']
                 and self.port.calls.in_job(s.launch_handle,s.job), 'LOCAL_DESCENDANT_PARENT_OR_JOB')
            subtree=[] if s.binding is None or s.binding.descendant_graph is None else s.binding.descendant_graph()
            if not subtree and attested:
                need(any(body(current)==body(r) for r in attested),'LOCAL_CHILD_NOT_IN_ROOT_RECEIPT')
                subtree=[];parents={native['pid']}
                for _ in range(len(attested)):
                    for r in attested:
                        if r['parent_pid'] in parents and r['pid'] not in parents:
                            parents.add(r['pid']);subtree.append(r)
            need(self.port.calls.members(s.job)=={native['pid']} | {r['pid'] for r in subtree},
                 'LOCAL_DESCENDANT_UNREGISTERED_MEMBER')
            rows.extend([current,*subtree])
        need(len({r['pid'] for r in rows})==len(rows),'LOCAL_DESCENDANT_ALIAS')
        return rows

    def _run(self,operation):
        need(not self.failed,'DESCENDANT_GATEWAY_FAILURE_LATCHED')
        try:return operation()
        except BaseException:
            self.failed=True
            raise

    def plan(self,argv,options):
        def operation():
            self.remote.verify_descendants()
            return self.port.plan(argv,options)
        return self._run(operation)

    def before_create(self,session):
        def operation():
            request=session.plan['request'];nonce=request.nonce
            need(nonce not in self.pending and session.launch_handle is None
                 and not session.creation_attempted and len(session.permit['slots'])==1,
                 'DESCENDANT_DECLARE_BEFORE_CREATION_ONLY')
            endpoints=getattr(getattr(self.port,'protocol',None),'endpoints',None)
            state=None if endpoints is None else endpoints.state.get(nonce)
            bootstrap=None if state is None else state['lease'].descriptor()
            receipt=self.remote.declare_descendant(request,session.permit['slots'][0],keys=session.keys,
                                                   bootstrap=bootstrap)
            self.pending[nonce]={'session':session,'phase':'DECLARED','receipt':receipt}
            return receipt
        return self._run(operation)

    def after_create(self,session):
        def operation():
            nonce=session.plan['request'].nonce;row=self.pending[nonce]
            need(row['session'] is session and row['phase']=='DECLARED' and session.suspended
                 and self.port.calls.native(session.launch_handle)==session.creation_native,
                 'DESCENDANT_ORIGINAL_SUSPENDED_SESSION_REQUIRED')
            proof={'nonce':nonce,'parent':session.parent_handle,'launch':session.launch_handle,
                   'thread':session.thread,'tid':session.thread_id,'image':session.image_handle,'job':session.job,
                   'allocations':session.native}
            receipt=self.remote.stage_descendant(proof,session.plan['request'],session.creation_native)
            for key,item in session.native.items():
                self.remote.proofs.bind(key,item['handle'])
            row.update(phase='STAGED',receipt=receipt)
            return receipt
        return self._run(operation)

    def resume(self,session):
        def operation():
            nonce=session.plan['request'].nonce;row=self.pending[nonce]
            need(row['session'] is session and row['phase']=='STAGED' and session.suspended,
                 'STAGED_DESCENDANT_BOOTSTRAP_ONCE_ONLY')
            receipt=self.remote.resume_descendant(nonce,session.creation_native)
            row.update(phase='BOOTSTRAP',receipt=receipt)
            return receipt
        return self._run(operation)

    def release(self,session):
        def operation():
            nonce=session.plan['request'].nonce;row=self.pending[nonce]
            need(row['session'] is session and row['phase'] in ('BOOTSTRAP','RELEASED') and session.binding is not None
                 and session.binding.finished,'DESCENDANT_ORIGINAL_EXIT_BEFORE_RELEASE')
            receipt=self.remote.release_descendant(nonce)
            row.update(phase='RELEASED',receipt=receipt)
            return receipt
        return self._run(operation)
