import sys,os
if sys.argv[1:]!=['--approved-installed-worker'] or not os.environ.get('ATLAS_AUTH_SCOPE_SHA256'):
    raise SystemExit('FRESH_EXPLICIT_OPERATOR_APPROVAL_REQUIRED_NO_NATIVE_ACTION')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from gate import validate_scope
validate_scope(os.environ['ATLAS_AUTH_SCOPE_SHA256'],os.environ['ATLAS_AUTH_APPROVED_HEAD'])
from pathlib import Path
import ctypes
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import uuid

r = Path(r'D:\Work\Project Atlas')
e = Path(__file__).parent
sys.path[:0] = [str(r / 'backend'), str(r)]
from scripts.installed_nonfinancial_launcher import read_ready
from scripts.observation_runtime.installed_acceptance_cleanup import AcceptanceController, socket_cleanup
from scripts.observation_runtime.disposable_host_owner import observe_pid, observe_handle
from scripts.support_deployment import verify_deployment, SupportLease
from scripts.release_selection_store import NativeSelectionStore
from scripts.release_selection import ReleaseSelector, NativeInstalledReleaseVerifier
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock

assert not ctypes.windll.shell32.IsUserAnAdmin()
claims = json.loads(os.environ.get('ATLAS_AUTH_HELPER_CLAIMS', '[]'))
claims.append(json.loads((e / 'helper-primary-claim.json').read_bytes()))
claims.append(observe_pid(os.getpid()))
os.environ['ATLAS_AUTH_HELPER_CLAIMS'] = json.dumps(claims)
deadline = int(os.environ['ATLAS_AUTH_DEADLINE_NS']) / 1e9
app = r'D:\AtlasRuntime\releases\2c039af29dfefd1df77e0caa3db3fdf5ed188118'
python = str(Path(app) / 'python/python.exe')
ps = r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
manifest = r / 'docs/QD_SUPPORT_DEPLOYMENT_MANIFEST_V1_2026-11-02.json'
pin = '7947f54e82d74079b378ad14c238dadb4259671ee7ed5c9d03e952d5d8327cd3'
receipt_pin = '01bb0f6efb04c706e594acb8c63759ee682e4bce2f2062882015edff36d6ce91'
baseline = 'c9bc240c11c148cd6c6f6dda7c6760aa2d2ac9547ee8c44847bf239b6382ffbc'
result = {'authorization_consumed': True, 'status': 'PREFLIGHT', 'operational_mutations_attempted': False,
          'cycles': [], 'rollback': 'NOT_NEEDED', 'financial_actions': 0, 'provider_connections': 0}
controller = None
lifecycle = None
ready = None
selection = None
retained_actions=[]
from capture import collect as collect_cleanup
from scripts.observation_runtime.installed_acceptance_sequence import PreselectionCut, run_cycle
from scripts.observation_runtime.acceptance_http_probe import probe
def remaining(): return deadline - time.perf_counter()
def save(): (e / 'worker-result.json').write_text(json.dumps(result, indent=2))
def timing(event, cycle=0, **details):
    row=dict(event=event,cycle=cycle,utc_ns=time.time_ns(),monotonic_ns=time.perf_counter_ns(),**details)
    with (e/'worker-timing.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    return row

def run(command, name, maximum=180):
    if remaining() < 35: raise ValueError('GLOBAL_DEADLINE_CLEANUP_RESERVE')
    env = dict(os.environ)
    for k in ('PYTHONPATH', 'PYTHONHOME'): env.pop(k, None)
    env.update(PYTHONDONTWRITEBYTECODE='1', PSModulePath=r'C:\Windows\System32\WindowsPowerShell\v1.0\Modules',
               PSModuleAnalysisCachePath=str(e / 'ps-module-analysis.cache'), TEMP=str(e / 'temp'), TMP=str(e / 'temp'))
    child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
    claim=observe_pid(child.pid)
    assert claim['created']==observe_handle(int(child._handle))
    try:
        out,err=child.communicate(timeout=min(maximum,remaining()-30))
    except subprocess.TimeoutExpired as exc:
        (e/(name+'-partial-stdout.log')).write_bytes(exc.output or b'')
        (e/(name+'-partial-stderr.log')).write_bytes(exc.stderr or b'')
        retained_actions.append(child)
        raise ValueError('EXACT_OWNED_ACTION_TIMEOUT_PRESERVE_PARTIAL_NO_RETRY') from None
    finally:
        if child.returncode is not None:
            for stream in (child.stdout,child.stderr):stream.close()
            child._handle.Close()
    (e / (name + '-stdout.log')).write_bytes(out)
    (e / (name + '-stderr.log')).write_bytes(err)
    if child.returncode or err or len(out) > 8*1024**2:
        raise ValueError(name + '_REFUSED:' + err.decode(errors='replace')[-1600:] + out.decode(errors='replace')[-600:])
    return out

def cli(action, name, *args):
    raw = run([python, '-I', '-B', str(r / 'scripts/support_deployment.py'),
        '--execute-approved-support-deployment', '--action', action, '--manifest', str(manifest),
        '--manifest-sha256', pin, *args], name)
    return json.loads(raw)

def read_line(seconds):
    return json.loads(read_ready(controller, seconds=min(seconds, max(1, remaining() - 25))))

try:
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=r).decode().strip() == os.environ['ATLAS_AUTH_APPROVED_HEAD']
    with (e / 'single-use-claim.json').open('x') as f:
        json.dump({'approved_checkpoint':os.environ['ATLAS_AUTH_APPROVED_HEAD'],'scope_sha256':os.environ['ATLAS_AUTH_SCOPE_SHA256'],'deadline_ns':int(os.environ['ATLAS_AUTH_DEADLINE_NS'])},f)
    run([python, '-I', '-B', str(e / 'clock_preflight.py')], 'clock-preflight', 180)
    run([sys.executable, '-I', '-B', str(e / 'native_preflight.py')], 'native-preflight', 220)
    run([ps, '-NoProfile', '-NonInteractive', '-File', str(e / 'metadata_preflight.ps1')], 'metadata-preflight', 20)
    n = json.loads((e / 'native-preflight-result.json').read_bytes())
    assert n['accepted'] and json.loads((e / 'metadata-preflight-result.json').read_bytes())['accepted']
    if remaining() < 300: raise ValueError('INSUFFICIENT_REMAINING_BOUNDED_DEPLOYMENT_BUDGET')
    result['status'] = 'ALL_PREFLIGHT_PASSED'
    clock_rows=[json.loads((e/('observation-'+str(index)+'.json')).read_bytes()) for index in range(1,json.loads((e/'summary.json').read_bytes())['observations']+1)]
    result['preflight_clock']=next(row['evidence'] for row in reversed(clock_rows) if row['accepted'])
    result['support_preflight_verified']=True
    save()
    m=json.loads(manifest.read_bytes())
    protected_before={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in
        [*Path(m['control']).iterdir(),*Path(m['selection']).iterdir(),
         Path(m['application']['receipt']),Path(m['application']['receipt']).with_suffix('.pending.jsonl')]
        if f.is_file()}
    result['existing_journal_and_receipt_hashes_before']=protected_before
    receipt = verify_deployment(json.loads(manifest.read_bytes()), expected_receipt_sha256=receipt_pin)
    result['reused_receipt_sha256']=receipt_pin
    result['support_installation_repeated']=False
    # Last retained actual installed READY endpoint, pinned in the new scope.
    scope=json.loads((e/'proposal.json').read_bytes())
    endpoint=scope['preselection_endpoint']
    assert endpoint['address']=='127.0.0.1' and endpoint['port']==52159
    boundary=time.perf_counter_ns()
    preselection=collect_cleanup(repo=r,evidence=e,port=endpoint['port'],after_ns=boundary,label='preselection',run=run)
    result['preselection_cut']=preselection
    def select_with_verified_cut():
        result['operational_mutations_attempted']=True
        return cli('select','release-select','--support-receipt-sha256',receipt_pin,
                   '--operation',uuid.uuid4().hex,'--expected-head',baseline)
    selection=PreselectionCut(address=endpoint['address'],port=endpoint['port'],after_ns=boundary,
                              packet=preselection).dispatch(select_with_verified_cut)
    assert selection['receipt']['revision']==7 and selection['receipt']['previous']==baseline
    result['selection'] = selection
    binding = selection['desktop_binding']
    (e / 'binding.json').write_text(json.dumps(binding))
    result['status'] = 'EXACT_RELEASE_SELECTED'
    save()
    env = dict(os.environ)
    env.update(PSModulePath=r'C:\Windows\System32\WindowsPowerShell\v1.0\Modules',
               PSModuleAnalysisCachePath=str(e / 'ps-module-analysis.cache'), TEMP=str(e / 'temp'), TMP=str(e / 'temp'))
    timing('controller_launch_requested')
    controller = subprocess.Popen([ps, '-NoProfile', '-NonInteractive', '-File', str(e / 'controller.ps1')],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
    controller_claim = observe_pid(controller.pid)
    assert controller_claim['created'] == observe_handle(int(controller._handle))
    result['controller_claim'] = controller_claim
    lifecycle = AcceptanceController(controller, controller_claim)
    for cycle in (1,2):
        ready=read_line(180)
        observed_ns=time.perf_counter_ns()  # Conservative origin, before diagnostics.
        result['in_progress_cycle']={'cycle':cycle,'ready':ready}
        def notify(ticket, cycle=cycle):
            print(json.dumps({'stage':'BROWSER_REQUIRED','cycle':cycle,'url':ticket['url'],
                              'ready_ns':ticket['ready_ns'],'deadline_ns':ticket['deadline_ns'],
                              'request_path':str(e/('cycle-'+str(cycle)+'-browser-request.json'))}),flush=True)
        def diagnose(ready):
            port=int(ready['url'].rstrip('/').rsplit(':',1)[-1])
            diagnostics={'pages':[]}
            for page in ('/dashboard','/dashboard/perps','/quality_dips.html','/dashboard/investment','/dashboard/archive','/dashboard/command-center'):
                response=probe(port=port,path=page)
                headers={k.lower():v for k,v in response['headers'].items()}
                assert response['status']==200 and b'<html' in response['data'].lower() and "connect-src 'self'" in headers['content-security-policy']
                diagnostics['pages'].append(page)
            response=probe(port=port,path='/api/investments/quality-dips/selected-paper');data=json.loads(response['data'])
            assert response['status']==200 and data['cash'] is data['positions'] is None and data['startup_authorized'] is False
            diagnostics['selected_account'] = data
            response=probe(port=port,path='/anything',method='POST'); assert response['status']==403
            diagnostics['financial_post_status'] = 403
            diagnostics['all_probe_peer_eof_and_client_handles_closed']=True
            return diagnostics
        def collect_cycle(current,after,cycle=cycle):
            port=int(current['url'].rstrip('/').rsplit(':',1)[-1])
            proof=collect_cleanup(repo=r,evidence=e,port=port,after_ns=after,label='cycle-'+str(cycle),run=run)
            proof['port']=port
            return proof
        sample=run_cycle(controller=lifecycle,ready=ready,
                         expected={'release':binding['release'],'head':binding['head'],'image':python},
                         cycle=cycle,root=e,domain='WINDOWS_LOCAL',ready_ns=observed_ns,
                         notify=notify,diagnose=diagnose,collect=collect_cycle,final=cycle==2)
        sample['port']=sample['cleanup']['port']
        result['cycles'].append(sample);result.pop('in_progress_cycle',None)
        ready=None
        if cycle==2:
            result['controller_exit_code']=lifecycle.final_result['exit_code']
            controller=None
        save()
    result['final_port_readbacks']=[]
    for completed in result['cycles']:
        proof=collect_cleanup(repo=r,evidence=e,port=completed['port'],after_ns=lifecycle.stopped_ns,label='final-port-'+str(completed['cycle']),run=run)
        result['final_port_readbacks'].append(proof)
        if not proof['crosscheck']['cleanup_clear'] or not proof['socket_process']['accepted']:
            raise ValueError('FINAL_PORT_OR_PROCESS_READBACK_UNRESOLVED')
    result['status'] = 'TWO_INSTALLED_CYCLES_ACCEPTED'
    save()
except Exception as exc:
    result.update(status='REFUSED_PRESERVE_EVIDENCE', error_type=type(exc).__name__, error=str(exc))
    save()
finally:
    if controller is not None:
        if lifecycle is None:
            result['cleanup_error']='OWNERSHIP_NOT_ESTABLISHED_RETAIN_ORIGINAL_SUPERVISOR_HANDLE'
        else:
            try:
                if lifecycle.host_id is not None and not lifecycle.stop_attempted:
                    result['failure_cleanup_stop']=lifecycle.stop()
                    if ready is not None and lifecycle.stopped_ns is not None:
                        port=int(ready['url'].rstrip('/').rsplit(':',1)[-1])
                        result['failure_cleanup_cut']=collect_cleanup(repo=r,evidence=e,port=port,
                            after_ns=lifecycle.stopped_ns,label='failure-cleanup',run=run)
            except Exception as exc:result['cleanup_stop_error']=str(exc)
            # An audit/Stop error never skips EOF/reaping. An ambiguous Stop is
            # never sent again; a drain timeout retains the original handle.
            try:
                drained=lifecycle.finish()
                (e/'controller-cleanup-stdout.log').write_bytes(drained['stdout'])
                (e/'controller-cleanup-stderr.log').write_bytes(drained['stderr'])
                result['controller_cleanup_exit']=drained['exit_code']
                result['controller_cleanup_accepted']=drained['accepted']
            except Exception as exc:result['cleanup_error']=str(exc)
    if selection is not None and remaining()>30:
        try:
            result['rollback']=json.loads(run([python,'-I','-B',str(e/'restore_known_head.py'),
                '--execute-approved-known-head-rollback',selection['head']], 'known-head-rollback',60))
            result['final_selection']=result['rollback']['final_current']
            assert result['final_selection']['selected'] is None and result['rollback']['receipt']['revision']==8
            assert result['rollback']['receipt']['restores']==baseline
        except Exception as exc:
            result['rollback']={'status':'UNRESOLVED_PRESERVE_NO_RETRY','error':str(exc)}
            result['final_readback_error']=str(exc)
    try:
        if not result.get('support_preflight_verified'):raise ValueError('NATIVE_PREFLIGHT_NOT_PASSED_NO_ADDITIONAL_READBACK')
        verify_deployment(json.loads(manifest.read_bytes()),expected_receipt_sha256=receipt_pin)
        result['final_support_receipt_ack_preserved']=True
        if 'protected_before' in locals():
            assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in protected_before.items())
            result['all_original_journal_and_receipt_bytes_unchanged']=True
    except Exception as exc:result['final_readback_error']=str(exc)
    for action in retained_actions:
        try:
            action.communicate(timeout=max(1,min(5,remaining()-10)))
            for stream in (action.stdout,action.stderr):stream.close()
            action._handle.Close()
        except Exception as exc:result['retained_action_drain_error']=str(exc)
    result['remaining_seconds'] = remaining()
    save()
    print(json.dumps({'stage': result['status'], 'error': result.get('error'), 'remaining_seconds': remaining()}), flush=True)
sys.exit(0 if result['status'] == 'TWO_INSTALLED_CYCLES_ACCEPTED' and 'final_readback_error' not in result and 'retained_action_drain_error' not in result and result.get('rollback',{}).get('receipt',{}).get('revision')==8 else 2)
