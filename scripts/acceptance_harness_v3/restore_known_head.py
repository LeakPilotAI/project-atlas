import json,sys,uuid,os,time
from pathlib import Path
_live_root=Path(__file__).parent
if not os.environ.get('ATLAS_AUTH_SCOPE_SHA256') or not (_live_root/'single-use-claim.json').exists():
    raise SystemExit('NO_LIVE_EXPLICITLY_APPROVED_ACCEPTANCE_SESSION')
r=Path(r'D:\Work\Project Atlas')
e=Path(__file__).parent
sys.path[:0]=[str(r/'backend'),str(r)]
from scripts.support_deployment import verify_deployment,SupportLease,sha,encoded
from scripts.release_selection import ReleaseSelector,NativeInstalledReleaseVerifier
from scripts.release_selection_store import NativeSelectionStore
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock

assert len(sys.argv)==3 and sys.argv[1]=='--execute-approved-known-head-rollback'
live=json.loads((e/'single-use-claim.json').read_bytes())
assert live['scope_sha256']==os.environ['ATLAS_AUTH_SCOPE_SHA256'] and live['approved_checkpoint']==os.environ['ATLAS_AUTH_APPROVED_HEAD'] and time.perf_counter_ns()<int(os.environ['ATLAS_AUTH_DEADLINE_NS'])
m=json.loads((r/'docs/QD_SUPPORT_DEPLOYMENT_MANIFEST_V1_2026-11-02.json').read_bytes())
assert sha(encoded(m))=='7947f54e82d74079b378ad14c238dadb4259671ee7ed5c9d03e952d5d8327cd3'
assert Path(sys.executable)==Path(m['runtime']['python'])
receipt=verify_deployment(m,expected_receipt_sha256='01bb0f6efb04c706e594acb8c63759ee682e4bce2f2062882015edff36d6ce91')
clock=store=None
try:
    operation=uuid.uuid4().hex
    clock=LocalWindowsClock(expected_source='time.windows.com,0x9',runtime_id='qd-code-selection-'+operation)
    with SupportLease(receipt):
        store=NativeSelectionStore(root=m['selection'],native_root=receipt['selection_id'])
        selector=ReleaseSelector(store=store,verifier=NativeInstalledReleaseVerifier(),clock=clock)
        result=selector.change({'schema':'QD_CODE_SELECTION_AUTHORIZATION_V1','domain':'WINDOWS_LOCAL','action':'ROLLBACK',
            'operation':operation,'expected_head':sys.argv[2],'target':None,
            'restores':'c9bc240c11c148cd6c6f6dda7c6760aa2d2ac9547ee8c44847bf239b6382ffbc'},approved=True)
        result['final_current']=selector.current()
        assert result['final_current']=={'head':result['head'],'selected':None}
        print(json.dumps(result),flush=True)
finally:
    if store is not None:store.close()
    if clock is not None:clock.revoke()
