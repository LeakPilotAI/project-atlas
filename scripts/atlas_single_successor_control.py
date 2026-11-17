"""One pinned successor's Windows-local CODE-ONLY decisions/execution.

Operator support, excluded from the application payload. No default proposal,
approval PIN, install, selection, launcher, financial or provider action.
Each execution consumes its own create-new local decision/attempt record.
"""
import argparse
import ctypes
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

from scripts.build_release_candidate import source_bytes
from scripts.install_verified_release import installation_target, installed_readback, write_new_json
from scripts.native_install_plan import prepare_install_inputs
from scripts import release_selection as releases

ROOT=Path('D:/Work/Project Atlas')
INSTALL_SCOPE='APPROVE_ONE_ATLAS_WRITER_RECOVERY_CODE_ONLY_INSTALL_NO_FINANCIAL_START'
SELECT_SCOPE='APPROVE_ONE_ATLAS_WRITER_RECOVERY_CODE_ONLY_SELECTION_NO_FINANCIAL_START'
R23_SOURCE='96c6b85f76368a69bfd035cbcf3eb05776c21525'
R23_ARTIFACT='fcf87dd612b66e5fbbd645462104c968473db218eaa844a18efa682cefdbbae0'
R23_HEAD='bca5b25734967c61385c03fa218aafcc6a192613ef85e8d1ea8497b5c2eeb57a'


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
    if (p.get('schema')!='ATLAS_SINGLE_SUCCESSOR_CODE_ONLY_PROPOSAL_V1'
            or type(source) is not str or re.fullmatch('[0-9a-f]{40}',source) is None
            or p.get('destination')!=str(Path('D:/AtlasRuntime/releases')/source)
            or p.get('receipt')!=str(ROOT/'logs/diagnostics'/('qd-unselected-release-'+source+'.json'))
            or p.get('control_source_sha256')!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            or p.get('previous_head')!=R23_HEAD
            or p.get('previous_spec',{}).get('release')!=R23_SOURCE
            or p.get('previous_spec',{}).get('artifact_digest')!=R23_ARTIFACT
            or p.get('limits')!={'seconds':600,'entries':40000,'bytes':1024**3,'processors':2}
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
    from scripts.release_selection_store import NativeSelectionStore
    from scripts.observation_runtime.personal_version_safe_release_clock import SELECTOR_NATIVE
    from scripts.observation_runtime.personal_existing_native_resource_evidence import inspect_two_lane_native_roots
    store=NativeSelectionStore(root=r'D:\AtlasRuntime\selection',native_root=list(SELECTOR_NATIVE))
    try:
        with store.locked():rows=store.records()
        if len(rows)!=21 or releases.digest(rows[-1])!=p['previous_head'] or rows[-1]['selected']!=p['previous_spec']:
            raise ValueError('SUCCESSOR_ORIGINAL_R23_REVISION21_REQUIRED')
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
    p=proposal(path,pin);plan=prepared(p);original_state(p)
    decision=verify_decision(path,pin,p,kind,decision_pin)
    if kind=='install':installation_target(p['source_commit'],p['receipt'])
    attempt=Path(path).parent/('local-'+kind+'-attempt.json')
    write_new_json(attempt,{'decision_sha256':decision_pin,'kind':kind,'status':'SINGLE_USE_CONSUMED'})
    from scripts.observation_runtime.atlas_r17_cpu_budget import NativeR17CpuBudget
    from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
    from scripts.install_version_safe_candidate import _qualify_native_clock_180s
    from scripts.observation_runtime.native_install_host_admission import require_code_install_host_ready
    from scripts.atlas_r13_low_impact_installer import LowImpactEnvelope
    identity='successor-code-'+kind+'-'+p['source_commit']
    started=time.monotonic()
    with NativeR17CpuBudget() as cpu, LowImpactEnvelope(max_seconds=600) as envelope:
        # Keep predecessor native files pinned throughout the attempt; repeated
        # admissions use native selector/root/approval checks, no repeated deep scans.
        with releases.NativeInstalledReleaseVerifier().open(p['previous_spec']):
            clock=IndependentNtpClock(runtime_id=identity)
            try:
                _qualify_native_clock_180s(clock,identity)
                last=None
                def admission(force=False):
                    nonlocal last
                    cpu.pulse();envelope.tick()
                    now=time.monotonic()
                    if now-started>600:raise ValueError('SUCCESSOR_BOUNDED_EXECUTION_EXPIRED')
                    if force or last is None or now-last>=30:
                        clock.require_operational(identity)
                        if clock.evidence.get('bound_ms',1001)>1000:raise ValueError('SUCCESSOR_CLOCK_UNACCEPTED')
                        original_state(p);verify_decision(path,pin,p,kind,decision_pin)
                        require_code_install_host_ready(Path(p['destination']).parent)
                        last=now
                    return True
                admission(force=True)
                if kind=='select':
                    spec=decision['target']
                    with releases.NativeInstalledReleaseVerifier().open(spec):
                        admission(force=True)
                        row={'schema':'QD_RELEASE_SELECTION_RECEIPT_V1','domain':'WINDOWS_LOCAL','revision':22,
                             'action':'SELECT','operation':hashlib.sha256((pin+decision_pin).encode()).hexdigest()[:32],
                             'previous':p['previous_head'],'selected':spec,'restores':None}
                        from scripts.release_selection_store import NativeSelectionStore
                        from scripts.observation_runtime.personal_version_safe_release_clock import SELECTOR_NATIVE
                        store=NativeSelectionStore(root=r'D:\AtlasRuntime\selection',native_root=list(SELECTOR_NATIVE))
                        try:
                            with store.locked():
                                rows=store.records()
                                if len(rows)!=21 or releases.digest(rows[-1])!=p['previous_head']:
                                    raise ValueError('SUCCESSOR_SELECTION_STALE_PREDECESSOR')
                                clock.require_operational(identity)
                                store.publish(row)
                                if store.records()[-1]!=row:raise ValueError('SUCCESSOR_SELECTION_ACK_UNKNOWN')
                        finally:store.close()
                        return {'status':'SUCCESSOR_SELECTED_CODE_ONLY','receipt':row,'financial_authority':False}
                from scripts.native_install_candidate import _copy_prepared_code
                journal=Path(p['receipt']).with_suffix('.pending.jsonl')
                write_new_json(journal,{'schema':'ATLAS_SUCCESSOR_UNSELECTED_CODE_INSTALL_INTENT_V1',
                    'source_commit':p['source_commit'],'archive_sha256':p['archive_sha256'],
                    'target':p['destination'],'financial_authority':False,'selection_allowed':False,'paper_start_authorized':False})
                def event(value):
                    with journal.open('ab') as stream:
                        stream.write(b'\n'+json.dumps(value,sort_keys=True,allow_nan=False).encode());stream.flush();os.fsync(stream.fileno())
                try:
                    plan['started']=started
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
                    artifact=releases.digest(receipt['files']);remaining=600-(time.monotonic()-started)
                    if remaining<40:raise ValueError('SUCCESSOR_INDEPENDENT_READBACK_TIME_UNAVAILABLE')
                    readback=installed_readback(Path(p['destination']),receipt,artifact,timeout=min(180,remaining-10))
                    receipt.update(layout=readback['layout'],artifact_digest=artifact)
                    admission(force=True)
                    raw=json.dumps(receipt,sort_keys=True,allow_nan=False).encode()
                    event({'stage':'UNSELECTED_CODE_INSTALL_VERIFIED','receipt_sha256':hashlib.sha256(raw).hexdigest()})
                    write_new_json(Path(p['receipt']),receipt)
                    return {'status':'SUCCESSOR_INSTALLED_UNSELECTED_CODE_ONLY','artifact_digest':artifact,
                            'receipt_sha256':hashlib.sha256(raw).hexdigest(),'financial_authority':False}
                except BaseException:
                    event({'stage':'REFUSED_PRESERVE_PARTIAL_NO_RETRY'});raise
            finally:clock.revoke()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proposal',required=True);parser.add_argument('--proposal-sha256',required=True)
    parser.add_argument('--mode',choices=('review','local-approve-install','local-approve-select','execute-install','execute-select'),default='review')
    parser.add_argument('--decision-sha256')
    args=parser.parse_args(argv)
    if args.mode=='review':
        p=proposal(args.proposal,args.proposal_sha256);plan=prepared(p)
        return {'status':'SOURCE_AND_DEPENDENCY_PLAN_ONLY_NO_OPERATIONAL_MUTATION','source_commit':p['source_commit'],
                'files':len(plan['names']),'bytes':plan['total'],'financial_authority':False}
    kind=args.mode.rsplit('-',1)[1]
    if args.mode.startswith('local-approve'):return decide(args.proposal,args.proposal_sha256,kind)
    if not args.decision_sha256:raise ValueError('SUCCESSOR_LOCAL_DECISION_PIN_REQUIRED')
    return execute(args.proposal,args.proposal_sha256,kind,args.decision_sha256)


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
