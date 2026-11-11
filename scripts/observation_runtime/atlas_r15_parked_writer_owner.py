"""Real installed R15 PARKED preactivation owner: Windows Job + 12 held native roots.

This is a *nonfinancial* bootstrap admission experiment closing the gap
between an installed Job child and native account-root handle identity:
the SAME live process proves both, before any financial activation exists.

The child holds original empty native PAPER directory handles and does not
open credentials, providers, operator activation, ledgers or write accounts.
Its sole named event is a random one-shot READY signal (never a financial
activation); the actual owned Job is explicitly stopped and closed before
this function returns. No installed persistent owner is authorized here.
"""
import ctypes
import json
import os
import secrets
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

from scripts.observation_runtime.atlas_r15_native_job_admission_preflight import (
    BELOW_NORMAL_PRIORITY_CLASS, CREATE_SUSPENDED,
    _exact_process, _exited_creation_filetime, _wait_exit,
)
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    RELEASE, SELECTED_HEAD, selected_code,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    ROLES, inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_native_job import (
    AdmissionFailure, launch_contained_child,
)
from scripts.observation_runtime.personal_native_windows_api import (
    PROCESS_INFORMATION, STARTUPINFOW, WindowsJobAPI,
)

SCHEMA="ATLAS_R15_PARKED_OWNER_COOPERATIVE_STOP_JOB_AND_HANDLES_V2"
IMAGE=str(RELEASE/"python/python.exe")
WAIT_OBJECT_0=0
DETACHED_PROCESS=0x00000008  # Real headless child; no conhost.exe in owned Job.

# Only installed R15 source modules, stdlib and original empty native account
# directories are available. There is intentionally no runtime/start command.
CHILD=r'''
import ctypes,json,os,sys,time
from contextlib import ExitStack
from ctypes import wintypes
from pathlib import Path
root=Path.cwd()
sys.path[:0]=[str(root/'backend'),str(root),str(root/'python/Lib/site-packages')]
from scripts.observation_runtime import personal_paper_inception as installed_source
native_primitives=installed_source.native_primitives
info=json.loads(sys.argv[1])
if (set(info)!={'selected_head','installed_root','ready_event','stop_event','roots'}
        or str(root).casefold()!=info['installed_root'].casefold()
        or Path(installed_source.__file__).resolve()!=root/'scripts/observation_runtime/personal_paper_inception.py'
        or type(info['selected_head']) is not str or len(info['selected_head'])!=64
        or type(info['roots']) is not dict
        or set(info['roots'])!={'QUALITY_DIPS','HYPERLIQUID'}):
    raise ValueError('R15_PARKED_BOOTSTRAP_AUTHENTIC_INSTALLED_RELEASE_REQUIRED')
native=native_primitives()
ids=set()
with ExitStack() as owned:
    for lane in ('QUALITY_DIPS','HYPERLIQUID'):
        roles=info['roots'][lane]
        if set(roles)!={'source','projection','report','control','coordination','custody'}:
            raise ValueError('R15_PARKED_BOOTSTRAP_SIX_NATIVE_ROLES_REQUIRED')
        for role,entry in roles.items():
            path=Path(entry['path'])
            if (type(entry['native_id']) is not list
                    or len(entry['native_id'])!=3
                    or not path.is_dir() or path.is_symlink()
                    or path.is_junction() or any(path.iterdir())):
                raise ValueError('R15_PARKED_BOOTSTRAP_EMPTY_NATIVE_ROOT_REQUIRED')
            out=owned.enter_context(native.w.WindowsOutput(str(path)))
            token=tuple(native.native.file_identity(out.root_handle))
            if token!=tuple(entry['native_id']) or token in ids or any(path.iterdir()):
                raise ValueError('R15_PARKED_BOOTSTRAP_WINDOWS_HANDLE_CHANGED')
            ids.add(token)
    if len(ids)!=12:
        raise ValueError('R15_PARKED_BOOTSTRAP_TWELVE_DISTINCT_NATIVE_ROOT_HANDLES_REQUIRED')
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenEventW.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.LPCWSTR]
    k.OpenEventW.restype=wintypes.HANDLE
    k.SetEvent.argtypes=[wintypes.HANDLE]
    k.SetEvent.restype=wintypes.BOOL
    k.CloseHandle.argtypes=[wintypes.HANDLE]
    k.CloseHandle.restype=wintypes.BOOL
    event=k.OpenEventW(0x0002,False,info['ready_event'])
    if not event:
        raise ValueError('R15_PARKED_BOOTSTRAP_ORIGINAL_PARENT_EVENT_NOT_OPEN')
    try:
        if not k.SetEvent(event):
            raise ValueError('R15_PARKED_BOOTSTRAP_PARENT_READY_NOT_SIGNALED')
    finally:k.CloseHandle(event)
    # The STOP event is a nonfinancial local lifetime control only. No
    # activation, trading or provider dispatch endpoint exists in this child.
    k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    k.WaitForSingleObject.restype=wintypes.DWORD
    stop=k.OpenEventW(0x00100000,False,info['stop_event'])
    if not stop:
        raise ValueError('R15_PARKED_BOOTSTRAP_STOP_EVENT_MISSING')
    try:
        if k.WaitForSingleObject(stop,12000)!=0:
            raise ValueError('R15_PARKED_BOOTSTRAP_BOUNDED_STOP_NOT_RECEIVED')
    finally:k.CloseHandle(stop)
'''


def validate_parked_proof(row):
    if (type(row) is not dict or set(row)!={
            'schema','status','selected_native_head','installed_release',
            'child_process_native_identity_verified',
            'suspended_before_native_job_assignment',
            'ready_from_same_parked_job_child',
            'twelve_existing_account_root_handles_held_while_job_active',
            'same_parked_job_worker_matches_both_12_role_rosters',
            'actual_job_kill_on_close_verified_before_handoff',
            'stopped_owned_job_cannot_be_reused_for_paper_activation',
            'same_owned_child_retained_across_three_liveness_observations',
            'cooperative_stop_signaled_and_child_exited_cleanly',
            'owned_job_active_children_before_stop',
            'owned_job_active_children_after_stop',
            'parked_process_exited_before_return',
            'original_native_roots_unchanged_after_stop',
            'persistent_writer_enrolled','native_financial_accounts_created',
            'operator_activation_accepted','provider_calls',
            'paper_start_authorized','live_trading_authorized'}
            or row['schema']!=SCHEMA
            or row['status']!='PARKED_R15_PREACTIVATION_COOPERATIVE_STOP_NONFINANCIAL_PASS'
            or row['selected_native_head']!=SELECTED_HEAD
            or row['installed_release']!=str(RELEASE)
            or type(row['owned_job_active_children_before_stop']) is not int
            or row['owned_job_active_children_before_stop']!=1
            or type(row['owned_job_active_children_after_stop']) is not int
            or row['owned_job_active_children_after_stop']!=0
            or type(row['native_financial_accounts_created']) is not int
            or row['native_financial_accounts_created']!=0
            or type(row['provider_calls']) is not int
            or row['provider_calls']!=0
            or any(row[k] is not True for k in (
                'child_process_native_identity_verified',
                'suspended_before_native_job_assignment',
                'ready_from_same_parked_job_child',
                'twelve_existing_account_root_handles_held_while_job_active',
                'same_parked_job_worker_matches_both_12_role_rosters',
                'actual_job_kill_on_close_verified_before_handoff',
                'stopped_owned_job_cannot_be_reused_for_paper_activation',
                'same_owned_child_retained_across_three_liveness_observations',
                'cooperative_stop_signaled_and_child_exited_cleanly',
                'parked_process_exited_before_return',
                'original_native_roots_unchanged_after_stop'))
            or any(row[k] is not False for k in (
                'persistent_writer_enrolled','operator_activation_accepted',
                'paper_start_authorized','live_trading_authorized'))):
        raise ValueError('R15_PARKED_JOB_NONFINANCIAL_NATIVE_PROOF_REFUSED')
    return row


def _signal_parked_stop(kernel, handle):
    """One native local cooperative request, never financial Stop dispatch."""
    kernel.SetEvent.argtypes=[wintypes.HANDLE]
    kernel.SetEvent.restype=wintypes.BOOL
    if not kernel.SetEvent(handle):
        raise ValueError('R15_PARKED_OWNER_COOPERATIVE_STOP_SIGNAL_REFUSED')
    return True


def inspect():
    if os.name!='nt' or sys.platform!='win32':
        raise ValueError('R15_PARKED_OWNER_WINDOWS_REQUIRED')
    selection=selected_code()
    if (selection.get('revision')!=14
            or selection.get('selected_native_head')!=SELECTED_HEAD
            or selection.get('financial_authority') is not False
            or not Path(IMAGE).is_file()):
        raise ValueError('R15_PARKED_OWNER_SELECTED_RELEASE_REFUSED')
    before=inspect_two_lane_native_roots()
    if (before['native_root_total']!=12
            or before['native_root_ids_verified']!=12
            or before['existing_empty_root_namespaces']!=12
            or before['all_twelve_distinct_and_empty'] is not True):
        raise ValueError('R15_PARKED_OWNER_NATIVE_ACCOUNT_PRE_ENROLLMENT_REQUIRED')
    entries={}
    for lane in ('QUALITY_DIPS','HYPERLIQUID'):
        existing=before['lanes'][lane]['roots']
        if set(existing)!=set(ROLES):
            raise ValueError('R15_PARKED_OWNER_SIX_ROLES_REQUIRED')
        entries[lane]={
            role:{'path':existing[role]['path'],'native_id':existing[role]['native_id']}
            for role in ROLES}
    api=WindowsJobAPI()
    k=api.kernel32
    k.CreateEventW.argtypes=[
        ctypes.c_void_p,wintypes.BOOL,wintypes.BOOL,wintypes.LPCWSTR]
    k.CreateEventW.restype=wintypes.HANDLE
    k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    k.WaitForSingleObject.restype=wintypes.DWORD
    k.IsProcessInJob.argtypes=[
        wintypes.HANDLE,wintypes.HANDLE,ctypes.POINTER(wintypes.BOOL)]
    k.IsProcessInJob.restype=wintypes.BOOL
    name='Local\\AtlasR15ParkedProof-'+secrets.token_hex(16)
    stop_name='Local\\AtlasR15ParkedStop-'+secrets.token_hex(16)
    signal=k.CreateEventW(None,False,False,name)
    if not signal:
        raise ctypes.WinError(ctypes.get_last_error())
    stop=None
    owner=None
    verified={}
    try:
        stop=k.CreateEventW(None,False,False,stop_name)
        if not stop:
            raise ctypes.WinError(ctypes.get_last_error())
        args=json.dumps({
            'selected_head':SELECTED_HEAD,'installed_root':str(RELEASE),
            'ready_event':name,'stop_event':stop_name,'roots':entries},sort_keys=True,separators=(',',':'))
        command=subprocess.list2cmdline([
            IMAGE,'-I','-B','-S','-c',CHILD,args])
        if len(command)>28000:
            raise ValueError('R15_PARKED_OWNER_BOUNDED_ARGUMENT_REQUIRED')
        def creator(candidate):
            if candidate!=command:
                raise ValueError('R15_PARKED_OWNER_EXACT_CHILD_REQUIRED')
            startup=STARTUPINFOW()
            startup.cb=ctypes.sizeof(startup)
            process=PROCESS_INFORMATION()
            line=ctypes.create_unicode_buffer(command)
            if not k.CreateProcessW(
                    IMAGE,line,None,None,False,
                    CREATE_SUSPENDED|DETACHED_PROCESS|BELOW_NORMAL_PRIORITY_CLASS,
                    None,str(RELEASE),ctypes.byref(startup),ctypes.byref(process)):
                raise ctypes.WinError(ctypes.get_last_error())
            return process.hProcess,process.hThread
        api.suspended_creator=creator
        def suspended_check(process,thread):
            verified.update(_exact_process(api,process))
            return True
        try:
            owner=launch_contained_child(api,command,verify_suspended=suspended_check)
        except AdmissionFailure as exc:
            if not exc.cleanup.closed:exc.cleanup.close()
            raise ValueError('R15_PARKED_OWNER_JOB_ADMISSION_REFUSED') from exc
        if int(k.WaitForSingleObject(signal,7000))!=WAIT_OBJECT_0:
            raise ValueError('R15_PARKED_OWNER_CHILD_NOT_READY')
        current=_exact_process(api,owner.process,expected_pid=verified['pid'])
        if current!=verified:
            raise ValueError('R15_PARKED_OWNER_PROCESS_INCARCATION_CHANGED')
        membership=wintypes.BOOL()
        if not k.IsProcessInJob(owner.process,owner.job,ctypes.byref(membership)):
            raise ctypes.WinError(ctypes.get_last_error())
        # Only the exact installed worker may remain in the owned Job.
        # DETACHED_PROCESS avoids an implicit console-host descendant.
        if not membership.value or api.active_processes(owner.job)!=1:
            raise ValueError('R15_PARKED_OWNER_CHILD_NOT_EXACT_OWNED_JOB')
        if inspect_two_lane_native_roots()!=before:
            raise ValueError('R15_PARKED_OWNER_ROOTS_CHANGED_WHILE_RUNNING')
        # The future activation must retain this SAME Job and process, not
        # adopt an unrelated live PID. Verify both complete 5+7 R15 native
        # enrollment SCHEMAS while the real installed child remains parked.
        # The synthetic candidate acceptance ID is explicitly nonoperational,
        # never supplied to an actual activation publisher or account writer.
        from copy import deepcopy
        from app.services.quality_dips_autonomous_enrollment import (
            WRITERS as QD_WRITERS, validate_enrollment as validate_qd,
        )
        from app.services.perp_operational_contract import (
            WRITERS as HL_WRITERS, validate_enrollment as validate_hl,
        )
        from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import inspect as draft
        from scripts.observation_runtime.personal_native_writer_lifetime import retain_live_enrollment_writers
        from scripts.observation_runtime.personal_r15_owned_job_activation import RetainedSelectedR15OwnerJob
        from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import ARTIFACT
        source=draft()
        candidate={}
        for lane,roles,validator in (
            ('QUALITY_DIPS',QD_WRITERS,validate_qd),
            ('HYPERLIQUID',HL_WRITERS,validate_hl)):
            item=deepcopy(source['accounts'][lane]['provisional_r15_native_enrollment_unaccepted'])
            identity={'schema':'QD_OP_PROCESS_ID_V1',**verified}
            item['writers']={role:deepcopy(identity) for role in roles}
            item['acceptance_id']='DISPOSABLE_PARKED_JOB_NO_FINANCIAL_AUTHORITY'
            candidate[lane]=validator(item)
        qd,hl=candidate['QUALITY_DIPS'],candidate['HYPERLIQUID']
        with retain_live_enrollment_writers(qd,hl,release_digest=ARTIFACT) as live:
            job_binding=RetainedSelectedR15OwnerJob(child=owner,qd=qd,perp=hl)
            job_binding.require_exact_roster(qd=qd,perp=hl)
            pure=job_binding.nonfinancial_handoff_readback()
            if (pure['writer_roles_examined']!=12
                    or pure['genuine_activation_or_owner_lease_issued'] is not False
                    or pure['paper_start_authorized'] is not False
                    or live.verify_still_running() is not True):
                raise ValueError('R15_PARKED_OWNER_UNACCEPTED_WRITER_HANDOFF_REFUSED')
        # One full retained owner session: revalidate the SAME native process
        # and original resources at three distinct monotonic observations.
        for index in range(3):
            job_binding.require_exact_roster(qd=qd,perp=hl)
            if (_exact_process(api,owner.process,expected_pid=verified['pid'])!=verified
                    or api.active_processes(owner.job)!=1
                    or inspect_two_lane_native_roots()!=before):
                raise ValueError('R15_PARKED_OWNER_MONITORED_LIFETIME_CHANGED')
            if index!=2:
                time.sleep(.35)
        # Cooperative Stop: signal the local parked-only event, then require
        # normal exit and automatic release of all 12 native root handles.
        # If Stop fails, finally executes owned Job termination as fallback.
        _signal_parked_stop(k, stop)
        code=_wait_exit(api,owner.process,timeout_ms=5000)
        if code!=0 or _exited_creation_filetime(api,owner.process)!=verified['creation_filetime']:
            raise ValueError('R15_PARKED_OWNER_COOPERATIVE_STOP_NOT_DURABLY_CLOSED')
        deadline=time.monotonic()+2
        while api.active_processes(owner.job) and time.monotonic()<deadline:
            time.sleep(.025)
        if api.active_processes(owner.job)!=0:
            raise ValueError('R15_PARKED_OWNER_JOB_DID_NOT_DRAIN')
        # Even though PROCESS_HANDLE remains owned until finally, an exited
        # process can NEVER be used as an enrolled financial writer. Prove the
        # same job-binding object now refuses its own expired native identity.
        try:
            job_binding.require_exact_roster(qd=qd,perp=hl)
        except ValueError:
            pass
        else:
            raise ValueError('R15_PARKED_OWNER_EXPIRED_JOB_REUSED')
        if inspect_two_lane_native_roots()!=before or selected_code()!=selection:
            raise ValueError('R15_PARKED_OWNER_ROOT_OR_RELEASE_CHANGED')
        return validate_parked_proof({
            'schema':SCHEMA,
            'status':'PARKED_R15_PREACTIVATION_COOPERATIVE_STOP_NONFINANCIAL_PASS',
            'selected_native_head':SELECTED_HEAD,
            'installed_release':str(RELEASE),
            'child_process_native_identity_verified':True,
            'suspended_before_native_job_assignment':True,
            'ready_from_same_parked_job_child':True,
            'twelve_existing_account_root_handles_held_while_job_active':True,
            'same_parked_job_worker_matches_both_12_role_rosters':True,
            'actual_job_kill_on_close_verified_before_handoff':True,
            'stopped_owned_job_cannot_be_reused_for_paper_activation':True,
            'same_owned_child_retained_across_three_liveness_observations':True,
            'cooperative_stop_signaled_and_child_exited_cleanly':True,
            'owned_job_active_children_before_stop':1,
            'owned_job_active_children_after_stop':0,
            'parked_process_exited_before_return':True,
            'original_native_roots_unchanged_after_stop':True,
            'persistent_writer_enrolled':False,
            'native_financial_accounts_created':0,
            'operator_activation_accepted':False,
            'provider_calls':0,
            'paper_start_authorized':False,
            'live_trading_authorized':False,
        })
    finally:
        # Emergency kill-on-close remains mandatory when the cooperative
        # Stop signal cannot be sent/acknowledged. All local HANDLEs must be
        # closed even when Job cleanup itself reports an error.
        try:
            if owner is not None:
                owner.close()
                if not owner.closed:
                    raise ValueError('R15_PARKED_OWNER_HANDLES_NOT_CLOSED')
        finally:
            try:
                if stop is not None:
                    api.close_handle(stop)
            finally:
                api.close_handle(signal)


if __name__=='__main__':
    print(json.dumps(inspect(),sort_keys=True))
