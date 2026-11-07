"""Guard-contained child, deliberately unclaimed by the historical leaf test.

The root keeps containment ownership; the candidate binding gets NO descendant
allowlist and must refuse the actual extra member. No unknown process is
adopted, no raw process creation and no refusal is converted into authority.
"""

import copy
import hashlib
import secrets

from app.services.paper_financial_replay import digest, strict
from scripts.observation_runtime.aip06_cleanup_providers import CimTables, StrictProcessCleanup
from scripts.observation_runtime.aip06_harness import SCOPE_HASH, need
from scripts.observation_runtime.aip06_windows_process import CancellableCalls
from scripts.observation_runtime.launch_ownership import LaunchRequest, RetainedLaunchBinding, OwnershipRefused


def candidate_refusal(*, binding, auxiliary, tables, calls, files, child, clock_ns, deadline_ns):
    """Original strict leaf binding, independent inventory and retained objects."""
    supervisor=binding.api.observe(binding.runtime_handle)
    extra=auxiliary.api.observe(auxiliary.runtime_handle)
    need(binding.api.observe(binding.parent_handle)==binding.parent
         and supervisor==binding.runtime and extra==auxiliary.runtime
         and extra['parent_pid']==supervisor['pid']
         and calls.in_job(auxiliary.runtime_handle,binding.api.job)
         and binding.api.members()=={supervisor['pid'],extra['pid']},
         'UNEXPECTED_CHALLENGE_ORIGINAL_IDENTITY_OR_COMPLETE_JOB')
    start=clock_ns()
    raw=tables.read(namespace=r'ROOT\CIMV2',query='SELECT '+','.join(StrictProcessCleanup.FIELDS)
        +f" FROM Win32_Process WHERE ProcessId={supervisor['pid']} OR ParentProcessId={supervisor['pid']}",
        fields=StrictProcessCleanup.FIELDS,deadline_ns=deadline_ns,maximum=8)
    from scripts.observation_runtime.aip06_windows_cim import filetime
    need(raw['complete'] is True and raw['error'] is None and start<=raw['started_ns']<=raw['finished_ns']
         <=clock_ns()<deadline_ns and len(raw['rows'])==2,'UNEXPECTED_CHALLENGE_INDEPENDENT_ENUMERATION')
    seen=set()
    for row in raw['rows']:
        expected={supervisor['pid']:supervisor,extra['pid']:extra}.get(row['ProcessId'])
        need(expected is not None and row['ProcessId'] not in seen
             and filetime(row['CreationDate'])//10==expected['created']//10
             and row['ParentProcessId']==expected['parent_pid']
             and row['CommandLine']==expected['command_line']
             and row['ExecutablePath'].casefold()==expected['image'].casefold(),
             'UNEXPECTED_CHALLENGE_CIM_NATIVE_CONFLICT')
        seen.add(row['ProcessId'])
    image=files.describe(child.image_handle)
    need(not image['reparse'] and image['links']==1 and image['id']==list(extra['file_id'])
         and hashlib.sha256(files.read(child.image_handle,32*1024**2)).hexdigest()==extra['sha256'],
         'UNEXPECTED_CHALLENGE_RETAINED_IMAGE_OBJECT')
    candidate=RetainedLaunchBinding(binding.api,binding.request,binding.parent_handle,binding.launch_handle)
    try:
        candidate.bind_runtime(binding.runtime_handle,{'pid':supervisor['pid'],
                    'nonce':binding.request.nonce,'role':binding.request.role})
    except OwnershipRefused as error:
        need(str(error)=='UNEXPECTED_OR_MISSING_JOB_PROCESS','UNEXPECTED_CHALLENGE_WRONG_REFUSAL')
    else:raise ValueError('UNEXPECTED_CHILD_ACCEPTED_BY_LEAF_BINDING')
    return {'schema':'AIP06_UNEXPECTED_CHALLENGE_V1','scope':SCOPE_HASH,
        'supervisor':supervisor,'expected':[supervisor['pid']], 'actual':sorted(seen),
        'auxiliary':extra,'auxiliary_nonce':auxiliary.request.nonce,'source':digest(raw),
        'at_ns':clock_ns(),'refusal':'UNEXPECTED_OR_MISSING_JOB_PROCESS',
        'ownership_accepted':False,'root_containment_preserved':True,'native_acceptance':False}


def run_guarded_challenge(services):
    port,runtime=services.port,services.runtime
    guard=port.guard;identity=runtime.identity;supervisor=identity.verify(guard.resources.channel.binding)
    pin=(supervisor['image'],tuple(supervisor['file_id']),supervisor['sha256'])
    wire=guard.resources.channel.binding
    request=LaunchRequest('acceptance_supervisor',wire['nonce'],'direct',pin,pin,
                         supervisor['command_line'],supervisor['command_line'])
    binding=RetainedLaunchBinding(identity.observer,request,identity.parent,identity.current)
    # This outer binding tracks the declared child for containment. The separate
    # historical candidate in candidate_refusal intentionally has no graph.
    binding.bind_runtime(identity.current,{'pid':supervisor['pid'],'nonce':wire['nonce'],'role':request.role})
    nonce=secrets.token_hex(16);target=port.controller.profile['targets']['query']
    child=guard.spawn([port.executable,'-B',target,'--case','direct-worker','--nonce',nonce],
                      env={'ATLAS_SYNTHETIC_STOP_NONCE':nonce})
    worker=CancellableCalls(calls=runtime.calls,allocations=port.allocations_port,clock_ns=runtime.clock)
    tables=CimTables(api=runtime.cim_api,allocations=port.allocations_port,worker=worker,clock_ns=runtime.clock)
    result=candidate_refusal(binding=binding,auxiliary=child.child.binding,tables=tables,
        calls=runtime.calls,files=runtime.files,child=child.child,clock_ns=runtime.clock,
        deadline_ns=runtime.clock()+5*10**9)
    control={'schema':'AIP06_PROBE_CLOSE_V1','scope':SCOPE_HASH,'case':'direct-worker','nonce':nonce}
    stdout,stderr=child.communicate(control,timeout=6)
    ready=strict(stdout.strip())
    need(stderr=='' and ready['nonce']==nonce and ready['pid']==result['auxiliary']['pid']
         and child.closed and child.child.binding.finished and port.all_members()==set(),
         'UNEXPECTED_CHALLENGE_NORMAL_CHILD_RELEASE_REQUIRED')
    result=copy.deepcopy(result);result['child_closed']=True
    return result
