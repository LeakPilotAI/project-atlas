"""Child-side ownership forwarding. No native calls or creation at construction."""
from scripts.observation_runtime.aip06_harness import need
from scripts.observation_runtime.aip06_ipc import RemoteResources


class DescendantGateway:
    def __init__(self,port):
        need(type(port.resources) is RemoteResources,'ONE_PARENT_LEDGER_GATEWAY_REQUIRED')
        self.port,self.remote=port,port.resources
        self.pending={};self.failed=False

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
            receipt=self.remote.declare_descendant(request,session.permit['slots'][0])
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
                   'thread':session.thread,'tid':session.thread_id,'image':session.image_handle,'job':session.job}
            receipt=self.remote.stage_descendant(proof,session.plan['request'],session.creation_native)
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
            need(row['session'] is session and row['phase']=='BOOTSTRAP' and session.binding is not None
                 and session.binding.finished,'DESCENDANT_ORIGINAL_EXIT_BEFORE_RELEASE')
            receipt=self.remote.release_descendant(nonce)
            row.update(phase='RELEASED',receipt=receipt)
            return receipt
        return self._run(operation)
