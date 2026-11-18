"""One pinned successor's Windows-local CODE-ONLY decisions/execution.

Operator support, excluded from the application payload. No default proposal,
approval PIN, install, selection, launcher, financial or provider action.
Each execution consumes its own create-new local decision/attempt record.
"""
import argparse
import ctypes
import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

from scripts import release_selection as releases
from scripts.build_release_candidate import source_bytes
from scripts.install_verified_release import (
    installation_target,
    installed_readback,
    write_new_json,
)
from scripts.native_install_plan import prepare_install_inputs

ROOT=Path('D:/Work/Project Atlas')
INSTALL_SCOPE='APPROVE_ONE_ATLAS_R22_TO_R23_CODE_ONLY_INSTALL_NO_FINANCIAL_START'
SELECT_SCOPE='APPROVE_ONE_ATLAS_R22_TO_R23_CODE_ONLY_SELECTION_NO_FINANCIAL_START'
R22_SOURCE='2f0fcfd9741b8fd524f2e5921a79998373a689c9'
R22_ARTIFACT='5b23187f39316cd4e4d81659fec70758d9db661051604f4d91379938c5e92a51'
R22_HEAD='86649902c02cfe99be2e5714091d8d4e6ff9b483df6cfa645566e44d40e7f92b'
FROZEN_SUCCESSOR_SOURCE='8463f1da3786647677629ae10da5e95c8940e688'
FROZEN_ARCHIVE=ROOT/'logs/diagnostics/atlas-r22-tracked-successor-20261118-r01/candidate/atlas-source.zip'
FROZEN_ARCHIVE_SHA='f415fc9837b3ee684450a120dbeb2034a9753e93c6ebeb13c22df9ceae437094'
FROZEN_SOURCE_INVENTORY_SHA='831ce5fc3a69e0c8ade7f433dc3d4706d33dee99cba00bc15a645f0bfb4feffb'
FROZEN_NATIVE_FILES=10802
FROZEN_NATIVE_DIRECTORIES=915
FROZEN_NATIVE_BYTES=267897262
FROZEN_SOURCE_FILES=1236
FROZEN_DEPENDENCY_FILES=9566



def timing_policy():
    # New, separately approved two-phase contract. Never reinterpret a V2 decision.
    return {'phase_a_seconds':600,'phase_b_seconds':600,'overall_seconds':1200,
        'paced_io_seconds':500,'check_every':32,'pace_every':128,
        'pause_seconds':0.06,'readback_seconds':180,'terminal_reserve_seconds':30,
        'io_ack_reserve_seconds':15,'minimum_copy_seconds':150,
        'copy_predecessor_factor':3,'copy_fixed_margin_seconds':15}


class ExecutionBudget:
    """One monotonic invocation; A and B each have their own nonrenewable 600s cap."""
    def __init__(self):
        self.started=time.monotonic()
        if not math.isfinite(self.started):
            raise ValueError('SUCCESSOR_MONOTONIC_ORIGIN_REQUIRED')
        self.last=self.started
        self.phase_b_started=None

    def remaining(self,*,reserve=0):
        now=time.monotonic()
        if (type(now) not in (int,float) or not math.isfinite(now)
                or now<self.last or type(reserve) not in (int,float)
                or not math.isfinite(reserve) or reserve<0):
            raise ValueError('SUCCESSOR_MONOTONIC_OR_RESERVATION_INVALID')
        self.last=now
        phase_origin=self.started if self.phase_b_started is None else self.phase_b_started
        phase_elapsed=now-phase_origin
        overall_elapsed=now-self.started
        if (phase_elapsed+reserve>=600 or overall_elapsed+reserve>=1200):
            raise ValueError('SUCCESSOR_PHASE_OR_TOTAL_DEADLINE_OR_RESERVATION_EXHAUSTED')
        return min(600-phase_elapsed,1200-overall_elapsed)

    def begin_installation(self):
        if self.phase_b_started is not None:
            raise ValueError('SUCCESSOR_INSTALL_PHASE_CANNOT_RESTART')
        self.remaining()
        self.phase_b_started=self.last  # Same original living process; no saved phase-A permit.
        return self.phase_b_started

    def io_remaining(self,envelope,*,reserve=0):
        self.remaining()
        now=envelope.monotonic()
        started=envelope.started
        if (self.phase_b_started is None or started is None
                or type(now) not in (int,float) or not math.isfinite(now)
                or type(started) not in (int,float) or not math.isfinite(started)
                or now<started or type(reserve) not in (int,float)
                or not math.isfinite(reserve) or reserve<0 or now-started+reserve>=500):
            raise ValueError('SUCCESSOR_PACED_IO_DEADLINE_OR_RESERVATION_EXHAUSTED')
        return 500-(now-started)

    def copy_admission(self,plan,predecessor_seconds,envelope):
        if (type(predecessor_seconds) not in (int,float) or not math.isfinite(predecessor_seconds)
                or predecessor_seconds<=0):
            raise ValueError('SUCCESSOR_CURRENT_PREDECESSOR_TIMING_REQUIRED')
        names=plan['names'];deps=plan['dependencies'];runtime=plan['runtime']
        sizes={name:(deps if name in deps else runtime)[name]['bytes'] for name in names}
        if any(type(v) is not int or v<0 for v in sizes.values()):
            raise ValueError('SUCCESSOR_EXACT_COPY_SIZE_REQUIRED')
        chunks=lambda n:math.ceil(n/65536)
        calls=(1+len(plan['directories'])+4*len(names)+len(deps)
               +sum(chunks(sizes[n]) for n in deps)+2*sum(chunks(n) for n in sizes.values())
               +len(plan['directories'])+1)
        pacing=(calls//128)*0.06
        copy_seconds=max(150,3*predecessor_seconds+pacing+15)
        self.remaining(reserve=copy_seconds+180+30)
        self.io_remaining(envelope,reserve=copy_seconds+180+15)
        return {'copy_reserved_seconds':copy_seconds,'pacing_seconds':pacing,
                'budget_calls':calls,'readback_reserved_seconds':180,'terminal_reserved_seconds':30,
                'io_ack_reserved_seconds':15}


def pacing_envelope():
    from scripts.atlas_r13_low_impact_installer import LowImpactEnvelope
    from scripts.atlas_r14_low_impact_installer import (
        CHECK_EVERY,
        MAX_SECONDS,
        PACE_EVERY,
        PAUSE_SECONDS,
    )
    if (CHECK_EVERY,PACE_EVERY,PAUSE_SECONDS,MAX_SECONDS)!=(32,128,0.06,500):
        raise ValueError('SUCCESSOR_PINNED_PACING_CHANGED')
    return LowImpactEnvelope(check_every=CHECK_EVERY,pace_every=PACE_EVERY,
                             pause_seconds=PAUSE_SECONDS,max_seconds=MAX_SECONDS)


def checked(path,pin,maximum=8*1024**2):
    path=Path(path)
    raw=source_bytes(path.parent,path.name,maximum_bytes=maximum)
    if type(pin) is not str or re.fullmatch('[0-9a-f]{64}',pin) is None or hashlib.sha256(raw).hexdigest()!=pin:
        raise ValueError('SUCCESSOR_PINNED_INPUT_CHANGED')
    return raw


def proposal(path,pin):
    path=Path(path).absolute()
    if path.parent.parent!=ROOT/'logs/diagnostics' or not path.parent.name.startswith('atlas-single-successor-'):
        raise ValueError('SUCCESSOR_EXACT_REVIEW_ROOT_REQUIRED')
    for parent in path.parents:
        if parent.exists() and (not parent.is_dir() or parent.is_symlink() or parent.is_junction()):
            raise ValueError('SUCCESSOR_REVIEW_ANCESTOR_ALIAS_REFUSED')
    p=releases.strict(checked(path,pin))
    source=p.get('source_commit')
    if (p.get('schema')!='ATLAS_R22_TO_R23_CODE_ONLY_PROPOSAL_V1'
            or type(source) is not str or re.fullmatch('[0-9a-f]{40}',source) is None
            or p.get('destination')!=str(Path('D:/AtlasRuntime/releases')/source)
            or p.get('receipt')!=str(ROOT/'logs/diagnostics'/('qd-unselected-release-'+source+'.json'))
            or p.get('control_source_sha256')!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            or p.get('source_commit')!=FROZEN_SUCCESSOR_SOURCE
            or p.get('archive')!=str(FROZEN_ARCHIVE)
            or p.get('archive_sha256')!=FROZEN_ARCHIVE_SHA
            or p.get('source_inventory_sha256')!=FROZEN_SOURCE_INVENTORY_SHA
            or p.get('source_files')!=FROZEN_SOURCE_FILES
            or p.get('dependency_files')!=FROZEN_DEPENDENCY_FILES
            or p.get('native_files')!=FROZEN_NATIVE_FILES
            or p.get('native_directories')!=FROZEN_NATIVE_DIRECTORIES
            or p.get('native_bytes')!=FROZEN_NATIVE_BYTES
            or p.get('installation_authorized') is not False
            or p.get('selection_authorized') is not False
            or p.get('old_decision_not_authorized_for_this_proposal') is not True
            or p.get('old_controller_consumed_decisions_not_redeemable') is not True
            or p.get('old_controller_source_unchanged') is not True
            or p.get('review_only') is not True
            or p.get('live_trading_authorized') is not False
            or p.get('account_creation_authorized') is not False
            or p.get('local_operator_install_decision_created') is not False
            or p.get('local_operator_select_decision_created') is not False
            or p.get('native_target_installed') is not False
            or p.get('new_native_selection_created') is not False
            or p.get('new_account_namespaces_initialized') is not False
            or p.get('required_explicit_local_install_scope')!=INSTALL_SCOPE
            or p.get('required_distinct_explicit_local_select_scope')!=SELECT_SCOPE
            or p.get('control_source')!=str(ROOT/'scripts/atlas_r22_successor_code_only_control.py')
            or p.get('previous_head')!=R22_HEAD
            or p.get('previous_spec',{}).get('release')!=R22_SOURCE
            or p.get('previous_spec',{}).get('artifact_digest')!=R22_ARTIFACT
            or p.get('limits')!={'seconds':1200,'entries':40000,'bytes':1024**3,'processors':2}
            or p.get('timing_policy')!=timing_policy()
            or p.get('financial_authority') is not False or p.get('paper_start_authorized') is not False
            or p.get('provider_access') is not False or p.get('automatic_startup') is not False):
        raise ValueError('SUCCESSOR_EXACT_CODE_ONLY_PROPOSAL_REQUIRED')
    return p


def prepared(p):
    dep=releases.strict(checked(p['dependency_receipt'],p['dependency_receipt_sha256'],16*1024**2))
    result=prepare_install_inputs(archive=p['archive'],archive_sha256=p['archive_sha256'],
        source_commit=p['source_commit'],dependency_receipt=dep,dependency_digest=p['dependency_inventory_sha256'],
        inventory_digest=p['source_inventory_sha256'],require_tracked=True)
    if (len(result['names'])!=p['native_files'] or len(result['directories'])+1!=p['native_directories']
            or result['total']!=p['native_bytes']):
        raise ValueError('SUCCESSOR_EXACT_NATIVE_INVENTORY_CHANGED')
    return result


def original_state(p):
    from scripts.observation_runtime.personal_existing_native_resource_evidence import (
        inspect_two_lane_native_roots,
    )
    from scripts.observation_runtime.personal_version_safe_release_clock import (
        SELECTOR_NATIVE,
    )
    from scripts.release_selection_store import NativeSelectionStore
    store=NativeSelectionStore(root=r'D:\AtlasRuntime\selection',native_root=list(SELECTOR_NATIVE))
    try:
        with store.locked():rows=store.records()
        if len(rows)!=22 or releases.digest(rows[-1])!=p['previous_head'] or rows[-1]['selected']!=p['previous_spec']:
            raise ValueError('SUCCESSOR_ORIGINAL_R22_REVISION22_REQUIRED')
    finally:store.close()
    roots=inspect_two_lane_native_roots()
    if roots['all_twelve_distinct_and_empty'] is not True or roots['lanes']!=p['original_roots']:
        raise ValueError('SUCCESSOR_TWELVE_ORIGINAL_EMPTY_FINANCIAL_ROOTS_REQUIRED')
    for name,pin in p['protected_original_sha256'].items():checked(name,pin)
    return True


def installed_spec(p):
    raw=source_bytes(Path(p['receipt']).parent,Path(p['receipt']).name,maximum_bytes=8*1024**2)
    receipt=releases.strict(raw)
    if (receipt.get('source_commit')!=p['source_commit'] or receipt.get('release_path')!=p['destination']
            or receipt.get('archive_sha256')!=p['archive_sha256']
            or receipt.get('inventory_sha256')!=p['source_inventory_sha256']
            or len(receipt.get('files',[]))!=p['native_files']
            or len(receipt.get('directories',[]))!=p['native_directories']
            or any(receipt.get(k) is not False for k in ('selected','financial_effects','provider_connections','operational_acceptance'))
            or releases.digest(receipt['files'])!=receipt.get('artifact_digest')):
        raise ValueError('SUCCESSOR_GENUINE_NEW_NATIVE_RECEIPT_REQUIRED')
    content=[{k:row[k] for k in ('path','bytes','sha256')}
             for row in sorted(receipt['files'],key=lambda r:r['path'])]
    if releases.digest(content)!=p['expected_content_sha256']:
        raise ValueError('SUCCESSOR_INSTALLED_CONTENT_INVENTORY_CHANGED')
    spec=releases.validate_spec({'schema':'QD_INSTALLED_RELEASE_REFERENCE_V1','domain':'WINDOWS_LOCAL',
        'release':p['source_commit'],'root':p['destination'],'receipt':p['receipt'],
        'receipt_sha256':hashlib.sha256(raw).hexdigest(),'artifact_digest':receipt['artifact_digest']},'WINDOWS_LOCAL')
    journal=Path(p['receipt']).with_suffix('.pending.jsonl')
    raw_journal=source_bytes(journal.parent,journal.name,maximum_bytes=128*1024)
    rows=raw_journal.splitlines()
    if (len(rows)!=2 or releases.strict(rows[0])!={
            'schema':'ATLAS_SUCCESSOR_UNSELECTED_CODE_INSTALL_INTENT_V1',
            'source_commit':p['source_commit'],'archive_sha256':p['archive_sha256'],
            'target':p['destination'],'financial_authority':False,'selection_allowed':False,'paper_start_authorized':False}):
        raise ValueError('SUCCESSOR_EXACT_TWO_STAGE_NATIVE_INSTALL_REQUIRED')
    releases.validate_native_install_ack(spec,receipt,raw_journal)
    return spec


def visible_local_console():
    if os.name!='nt' or not sys.stdin.isatty():
        raise ValueError('SUCCESSOR_VISIBLE_WINDOWS_LOCAL_OPERATOR_REQUIRED')
    k=ctypes.WinDLL('kernel32',use_last_error=True);u=ctypes.WinDLL('user32',use_last_error=True)
    k.GetConsoleWindow.restype=ctypes.c_void_p
    u.IsWindowVisible.argtypes=[ctypes.c_void_p];u.IsWindowVisible.restype=ctypes.c_int
    window=k.GetConsoleWindow()
    if not window or not u.IsWindowVisible(window):
        raise ValueError('SUCCESSOR_VISIBLE_WINDOWS_LOCAL_OPERATOR_REQUIRED')
    return True


def decision_path(path,kind):return Path(path).parent/('local-'+kind+'-decision.json')


def decide(path,pin,kind):
    visible_local_console()
    p=proposal(path,pin);prepared(p);original_state(p)
    scope=INSTALL_SCOPE if kind=='install' else SELECT_SCOPE
    target=None
    if kind=='install':installation_target(p['source_commit'],p['receipt'])
    elif kind=='select':
        target=installed_spec(p)
        with releases.NativeInstalledReleaseVerifier().open(target):pass
    else:raise ValueError('SUCCESSOR_EXACT_DECISION_KIND_REQUIRED')
    from scripts.volume_inspector.windows_output import current_sid
    print(json.dumps({'scope':scope,'source':p['source_commit'],'destination':p['destination'],
        'archive_sha256':p['archive_sha256'],'files':p['native_files'],'bytes':p['native_bytes'],
        'proposal_sha256':pin,'control_source_sha256':p['control_source_sha256'],
        'timing_policy':p['timing_policy'],'preflight_may_refuse_without_consuming_decision':True,
        'target':target,'financial_authority':False,'paper_start_authorized':False},indent=2))
    if input('Type the entire scope above to approve this ONE code-only action: ').strip()!=scope:
        raise ValueError('SUCCESSOR_LOCAL_OPERATOR_DECLINED')
    visible_local_console();original_state(p)
    if target is not None and installed_spec(p)!=target:raise ValueError('SUCCESSOR_SELECTION_TARGET_CHANGED')
    value={'schema':'ATLAS_SUCCESSOR_WINDOWS_LOCAL_DECISION_V1','origin':'VISIBLE_WINDOWS_LOCAL_OPERATOR',
        'kind':kind,'scope':scope,'proposal_sha256':pin,'operator_sid':current_sid(),
        'source_commit':p['source_commit'],'target':target,'financial_authority':False,
        'paper_start_authorized':False,'provider_access':False}
    dest=decision_path(path,kind);write_new_json(dest,value)
    return {'decision_path':str(dest),'decision_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
            'execution_performed':False}


def verify_decision(path,pin,p,kind,decision_pin):
    from scripts.volume_inspector.windows_output import current_sid
    value=releases.strict(checked(decision_path(path,kind),decision_pin))
    expected={'schema':'ATLAS_SUCCESSOR_WINDOWS_LOCAL_DECISION_V1','origin':'VISIBLE_WINDOWS_LOCAL_OPERATOR',
        'kind':kind,'scope':INSTALL_SCOPE if kind=='install' else SELECT_SCOPE,'proposal_sha256':pin,
        'operator_sid':current_sid(),'source_commit':p['source_commit'],
        'target':None if kind=='install' else installed_spec(p),
        'financial_authority':False,'paper_start_authorized':False,'provider_access':False}
    if value!=expected:raise ValueError('SUCCESSOR_DISTINCT_CURRENT_LOCAL_DECISION_REQUIRED')
    return value


def execute(path,pin,kind,decision_pin):
    # This function is never called by --review or --local-approve-*.
    if kind not in ('install','select'):raise ValueError('SUCCESSOR_EXACT_EXECUTION_KIND_REQUIRED')
    budget=ExecutionBudget()  # Phase A begins at real function entry.
    envelope=pacing_envelope()  # Real constructor validated before any attempt.
    from scripts.install_version_safe_candidate import _qualify_native_clock_180s
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,
    )
    from scripts.observation_runtime.atlas_r17_cpu_budget import NativeR17CpuBudget
    from scripts.observation_runtime.native_install_host_admission import (
        require_code_install_host_ready,
    )
    journal=None
    def event(value):
        with journal.open('ab') as stream:
            stream.write(b'\n'+json.dumps(value,sort_keys=True,allow_nan=False).encode());stream.flush();os.fsync(stream.fileno())
    try:
      with NativeR17CpuBudget() as cpu:
        p=proposal(path,pin);plan=prepared(p);original_state(p)
        decision=verify_decision(path,pin,p,kind,decision_pin)
        if kind=='install':installation_target(p['source_commit'],p['receipt'])
        attempt=Path(path).parent/('local-'+kind+'-attempt.json')
        if os.path.lexists(attempt):raise FileExistsError('SUCCESSOR_SINGLE_USE_ALREADY_CONSUMED')
        identity='successor-code-'+kind+'-'+p['source_commit']
        budget.remaining(reserve=180+30)
        predecessor_started=time.monotonic()
        # Same living parent/native release handles retain exact predecessor custody
        # across the two phases; no serialized preflight receipt can replace them.
        with releases.NativeInstalledReleaseVerifier().open(p['previous_spec']) as predecessor_receipt:
            predecessor_seconds=time.monotonic()-predecessor_started
            budget.remaining(reserve=180+30)
            clock=IndependentNtpClock(runtime_id=identity)
            try:
                _qualify_native_clock_180s(clock,identity)
                budget.remaining(reserve=30)
                last=None;phase_reserve=30;io_reserve=0;paced=False
                def admission(force=False):
                    nonlocal last
                    budget.remaining(reserve=phase_reserve)
                    cpu.pulse()
                    if paced:
                        envelope.tick()
                        budget.io_remaining(envelope,reserve=io_reserve)
                    now=time.monotonic()
                    if force or last is None or now-last>=30:
                        clock.require_operational(identity)
                        if clock.evidence.get('bound_ms',1001)>1000:raise ValueError('SUCCESSOR_CLOCK_UNACCEPTED')
                        original_state(p);verify_decision(path,pin,p,kind,decision_pin)
                        require_code_install_host_ready(Path(p['destination']).parent)
                        last=now
                    budget.remaining(reserve=phase_reserve)
                    if paced:budget.io_remaining(envelope,reserve=io_reserve)
                    return True
                admission(force=True)
                if kind=='select':
                    spec=decision['target']
                    with releases.NativeInstalledReleaseVerifier().open(spec):
                        admission(force=True)
                        row={'schema':'QD_RELEASE_SELECTION_RECEIPT_V1','domain':'WINDOWS_LOCAL','revision':23,
                             'action':'SELECT','operation':hashlib.sha256((pin+decision_pin).encode()).hexdigest()[:32],
                             'previous':p['previous_head'],'selected':spec,'restores':None}
                        from scripts.observation_runtime.personal_version_safe_release_clock import (
                            SELECTOR_NATIVE,
                        )
                        from scripts.release_selection_store import NativeSelectionStore
                        store=NativeSelectionStore(root=r'D:\AtlasRuntime\selection',native_root=list(SELECTOR_NATIVE))
                        try:
                            with store.locked():
                                rows=store.records()
                                if len(rows)!=22 or releases.digest(rows[-1])!=p['previous_head']:
                                    raise ValueError('SUCCESSOR_SELECTION_STALE_PREDECESSOR')
                                clock.require_operational(identity)
                                budget.remaining(reserve=30)
                                write_new_json(attempt,{'decision_sha256':decision_pin,'kind':kind,'status':'SINGLE_USE_CONSUMED'})
                                store.publish(row)
                                if store.records()[-1]!=row:raise ValueError('SUCCESSOR_SELECTION_ACK_UNKNOWN')
                        finally:store.close()
                        result={'status':'SUCCESSOR_SELECTED_CODE_ONLY','receipt':row,'financial_authority':False}
                else:
                  from scripts.native_install_candidate import (
                      _copy_prepared_code,
                      _verify_namespace,
                  )
                  # Still in A, with the SAME retained predecessor context.
                  def native_boundary():
                      budget.remaining(reserve=30)
                      cpu.pulse()
                      clock.require_operational(identity)
                      return True
                  _verify_namespace(Path(p['previous_spec']['root']),
                      {row['path'] for row in predecessor_receipt['files']},
                      {row['path'] for row in predecessor_receipt['directories']},
                      native_boundary)
                  admission(force=True)
                  installation_target(p['source_commit'],p['receipt'])
                  budget.remaining(reserve=30)
                  # B starts exactly once, not by resetting A, the global clock,
                  # predecessor retention, or the qualified NTP capability.
                  budget.begin_installation()
                  with envelope:
                    paced=True
                    phase_reserve=180+30
                    io_reserve=180+15
                    admission(force=True)
                    allocation=budget.copy_admission(plan,predecessor_seconds,envelope)
                    # Recheck after real priority, clock and host admission costs.
                    admission(force=True)
                    budget.remaining(reserve=allocation['copy_reserved_seconds']+phase_reserve)
                    budget.io_remaining(envelope,reserve=allocation['copy_reserved_seconds']+io_reserve)
                    write_new_json(attempt,{'decision_sha256':decision_pin,'kind':kind,'status':'SINGLE_USE_CONSUMED'})
                    pending=Path(p['receipt']).with_suffix('.pending.jsonl')
                    write_new_json(pending,{'schema':'ATLAS_SUCCESSOR_UNSELECTED_CODE_INSTALL_INTENT_V1',
                    'source_commit':p['source_commit'],'archive_sha256':p['archive_sha256'],
                    'target':p['destination'],'financial_authority':False,'selection_allowed':False,'paper_start_authorized':False})
                    journal=pending
                    plan['started']=budget.phase_b_started
                    copied=_copy_prepared_code(destination=Path(p['destination']),archive_sha256=p['archive_sha256'],
                        source_commit=p['source_commit'],prepared=plan,admission=admission)
                    if (len(copied['files'])!=p['native_files'] or len(copied['directories'])!=p['native_directories']
                            or copied['retained_handles_after_close']!=0):
                        raise ValueError('SUCCESSOR_NATIVE_COPY_COUNTS_OR_CLEANUP_INCOMPLETE')
                    receipt={'schema':'ATLAS_QD_D_RUNTIME_INSTALLATION_V1','stage':'D_RUNTIME_LAYOUT_VERIFIED',
                        'release_path':p['destination'],'source_commit':p['source_commit'],'files':copied['files'],
                        'directories':copied['directories'],'archive_sha256':p['archive_sha256'],
                        'inventory_sha256':p['source_inventory_sha256'],'selected':False,'financial_effects':False,
                        'provider_connections':False,'operational_acceptance':False}
                    artifact=releases.digest(receipt['files'])
                    budget.remaining(reserve=180+30)
                    budget.io_remaining(envelope,reserve=180+15)
                    phase_reserve=30
                    io_reserve=15
                    clock.require_operational(identity)
                    readback=installed_readback(Path(p['destination']),receipt,artifact,timeout=180)
                    receipt.update(layout=readback['layout'],artifact_digest=artifact)
                    admission(force=True)
                    raw=json.dumps(receipt,sort_keys=True,allow_nan=False).encode()
                    event({'stage':'UNSELECTED_CODE_INSTALL_VERIFIED','receipt_sha256':hashlib.sha256(raw).hexdigest()})
                    write_new_json(Path(p['receipt']),receipt)
                    budget.io_remaining(envelope)
                    budget.remaining(reserve=30)
                    result={'status':'SUCCESSOR_INSTALLED_UNSELECTED_CODE_ONLY','artifact_digest':artifact,
                            'receipt_sha256':hashlib.sha256(raw).hexdigest(),'financial_authority':False,
                            'timing_allocation':allocation}
                  paced=False
            finally:clock.revoke()
        budget.remaining()
      budget.remaining()  # Includes native handle, clock, priority/affinity cleanup.
      return result
    except BaseException:
        if journal is not None:event({'stage':'REFUSED_PRESERVE_PARTIAL_NO_RETRY'})
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proposal',required=True);parser.add_argument('--proposal-sha256',required=True)
    parser.add_argument('--mode',choices=('review','local-approve-install','local-approve-select','execute-install','execute-select'),default='review')
    parser.add_argument('--decision-sha256')
    args=parser.parse_args(argv)
    if args.mode=='review':
        p=proposal(args.proposal,args.proposal_sha256);plan=prepared(p);original_state(p)
        return {'status':'SOURCE_AND_DEPENDENCY_PLAN_ONLY_NO_OPERATIONAL_MUTATION','source_commit':p['source_commit'],
                'files':len(plan['names']),'bytes':plan['total'],'financial_authority':False,
                'timing_policy':p['timing_policy']}
    kind=args.mode.rsplit('-',1)[1]
    if args.mode.startswith('local-approve'):return decide(args.proposal,args.proposal_sha256,kind)
    if not args.decision_sha256:raise ValueError('SUCCESSOR_LOCAL_DECISION_PIN_REQUIRED')
    return execute(args.proposal,args.proposal_sha256,kind,args.decision_sha256)


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
