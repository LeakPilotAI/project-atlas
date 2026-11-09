"""Read-only native R12 version-safe NTP code-selection proposal; NOT permission.

Bind complete native V7-r11 predecessor, installed app and support receipt+ACK,
and the selected release's own version-safe clock handoff. This module cannot
publish a selection record, create a clock, access providers or start PAPER.
Run using the frozen installed app Python 3.12 with -I -B -S.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

REPO=Path(r'D:\Work\Project Atlas')
RELEASE='2d4879878bf58bea5a3ed0a986b809791f638fec'
APP=Path('D:/AtlasRuntime/releases')/RELEASE
SEL=Path(r'D:\AtlasRuntime\selection')
V7='af96bec0484a8e43f9965610e071a907a0d316bf'
R11_HEAD='933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997'
R11_ENVELOPE_SHA='3804a749f88cbf6da1873f71b917ef440ca801e31f4a93f73759df4382898c4d'
SEL_NATIVE=[4004218753,65536,1532785]
APP_RECEIPT=REPO/'logs/diagnostics'/('qd-unselected-release-'+RELEASE+'.json')
APP_SHA='acdae2f01fb5defdf0e302240dc589eca0f1c99e3fcc15ec319d98260125cbb6'
ARTIFACT='20d96aa9b8349506eb4c3e725523a59c18eb8386684ddfefd2bffc472302b732'
SUPPORT_MANIFEST_SHA='d61fd6c9fa18bd819f3328040e6c40581efc8faeef8eca8e6326eb110b919ad8'
SUPPORT_RECEIPT_SHA='2d2631152aea9086d95f2b60d06f1fde1c61ac61778d9ea36098d6883ce7eaac'
SUPPORT_ROOT=Path('D:/AtlasRuntime/support-installations/6a22a5a7a75150a421cb769aee85e95a8e297b4c0a3457d503bc808c661ff674')
SUPPORT_LAUNCHER=Path('D:/AtlasRuntime/launchers/6a22a5a7a75150a421cb769aee85e95a8e297b4c0a3457d503bc808c661ff674')
SUPPORT_STATUS_SCRIPT=REPO/'scripts/atlas_version_safe_support_status.py'
# This is the exact support-status source reviewed in this source milestone.
SUPPORT_STATUS_PIN='2748992dcc9a491433585dce2ca2a233d4d41f77ca9bcb01e8dd9d171f4b2e56'
REVIEW=REPO/'docs/ATLAS_VERSION_SAFE_R12_NONFINANCIAL_SELECTION_REVIEW_R1_2026-11-09.json'
PROFILE='INDEPENDENT_TWO_PEER_NTP_VERSION_SAFE_R12_V1'


def fail(test,message):
    if not test:raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def installed_context():
    fail(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode
         and Path(sys.executable)==APP/'python/python.exe'
         and Path(sys.base_prefix)==APP/'python',
         'ATLAS_R12_INSTALLED_ISOLATED_PYTHON_REQUIRED')
    if not str(APP) in sys.path:sys.path[:0]=[str(APP/'backend'),str(APP),str(APP/'python/Lib/site-packages')]


def validated_chain(rows, digest, validate_spec):
    """Pure replay of all native linked records. No selection writer."""
    fail(type(rows) is list and len(rows)==11,'ATLAS_R12_EXACT_11_PREDECESSORS_REQUIRED')
    prior=None; operations=set();known={}
    for index,row in enumerate(rows,1):
        fail(type(row) is dict and set(row)=={'schema','domain','revision','action',
             'operation','previous','selected','restores'}
             and row['schema']=='QD_RELEASE_SELECTION_RECEIPT_V1'
             and row['domain']=='WINDOWS_LOCAL'
             and type(row['revision']) is int and row['revision']==index
             and row['action'] in ('SELECT','ROLLBACK')
             and type(row['operation']) is str
             and re.fullmatch('[0-9a-f]{32}',row['operation'])
             and row['operation'] not in operations and row['previous']==prior,
             'ATLAS_R12_HISTORICAL_NATIVE_CHAIN_INVALID')
        if row['selected'] is not None:validate_spec(row['selected'],'WINDOWS_LOCAL')
        if row['action']=='SELECT':
            fail(row['selected'] is not None and row['restores'] is None,
                'ATLAS_R12_HISTORICAL_SELECT_INVALID')
        else:
            ref=row['restores']
            if ref=='BASELINE':
                fail(index==2 and row['selected'] is None,
                     'ATLAS_R12_HISTORICAL_BASELINE_INVALID')
            else:
                fail(ref in known and row['selected']==known[ref]['selected'],
                     'ATLAS_R12_HISTORICAL_RESTORE_INVALID')
        operations.add(row['operation']);prior=digest(row);known[prior]=row
    fail(prior==R11_HEAD and rows[-1]['revision']==11
         and rows[-1]['action']=='SELECT' and rows[-1]['selected']['release']==V7,
         'ATLAS_R12_V7_PREDECESSOR_CHANGED')
    return operations


def check_external_support():
    """Run hash-pinned read-only native support receipt+ACK verifier."""
    fail(type(SUPPORT_STATUS_PIN) is str and re.fullmatch('[0-9a-f]{64}',SUPPORT_STATUS_PIN),
         'ATLAS_R12_SUPPORT_STATUS_PIN_NOT_REVIEWED')
    fail(SUPPORT_STATUS_SCRIPT.is_file() and not SUPPORT_STATUS_SCRIPT.is_symlink()
         and sha(SUPPORT_STATUS_SCRIPT.read_bytes().replace(b'\r\n',b'\n'))==SUPPORT_STATUS_PIN,
         'ATLAS_R12_SUPPORT_STATUS_SOURCE_CHANGED')
    spec=importlib.util.spec_from_file_location('atlas_r12_support_status_reviewed',SUPPORT_STATUS_SCRIPT)
    fail(spec is not None and spec.loader is not None,'ATLAS_R12_SUPPORT_STATUS_LOADER_REFUSED')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    result=mod.inspect()
    fail(result.get('status')=='INSTALLED_SUPPORT_RECEIPT_AND_ACK_VERIFIED_UNSELECTED'
         and result.get('receipt_sha256')==SUPPORT_RECEIPT_SHA
         and result.get('r12_absent') is True
         and result.get('selected_release')==V7
         and result.get('support_files')==10 and result.get('support_directories')==3
         and all(result.get(k) is False for k in ('financial_authority','paper_accounts',
                      'provider_connections','orders')),
         'ATLAS_R12_NATIVE_SUPPORT_PROOF_NOT_ACCEPTED')
    return result


def native_plan():
    installed_context()
    from scripts.release_selection import digest,encoded,validate_spec,NativeInstalledReleaseVerifier
    from scripts.release_selection_store import NativeSelectionStore
    target=validate_spec({'schema':'QD_INSTALLED_RELEASE_REFERENCE_V1',
          'domain':'WINDOWS_LOCAL','release':RELEASE,'root':str(APP),
          'receipt':str(APP_RECEIPT),'receipt_sha256':APP_SHA,
          'artifact_digest':ARTIFACT},'WINDOWS_LOCAL')
    # Reopen exact support source/ACK first, then lock and replay the native
    # historical selector; r12 cannot appear between native reads.
    check_external_support()
    store=NativeSelectionStore(root=str(SEL),native_root=list(SEL_NATIVE))
    try:
        with store.locked():
            rows=store.records()
            used=validated_chain(rows,digest,validate_spec)
            fail(sha((SEL/'r0011.json').read_bytes())==R11_ENVELOPE_SHA,
                 'ATLAS_R12_LAST_NATIVE_ENVELOPE_CHANGED')
            fail(not os.path.lexists(SEL/'r0012.json')
                 and not os.path.lexists(SEL/'r0012.pending'),
                 'ATLAS_R12_ALREADY_PUBLISHED_OR_PARTIAL')
            operation=sha(encoded({'scope':'ATLAS_R12_EXACT_VERSION_SAFE_NONFINANCIAL_CODE_SELECT',
                'r11':R11_HEAD,'new_app_receipt':APP_SHA,
                'new_support_receipt':SUPPORT_RECEIPT_SHA,
                'new_support_manifest':SUPPORT_MANIFEST_SHA}))[:32]
            fail(operation not in used,'ATLAS_R12_OPERATION_REUSED')
            with NativeInstalledReleaseVerifier().open(target) as receipt:
                fail(receipt.get('source_commit')==RELEASE
                     and receipt.get('artifact_digest')==ARTIFACT
                     and all(receipt.get(k) is False for k in (
                         'selected','financial_effects','provider_connections',
                         'operational_acceptance')),
                     'ATLAS_R12_APP_NATIVE_VERIFIER_REFUSED')
            row={'schema':'QD_RELEASE_SELECTION_RECEIPT_V1',
                 'domain':'WINDOWS_LOCAL','revision':12,'action':'SELECT',
                 'operation':operation,'previous':R11_HEAD,
                 'selected':target,'restores':None}
            from scripts.observation_runtime.personal_version_safe_release_clock import admit_version_safe_clock_source
            source=APP/'scripts/observation_runtime/personal_version_safe_release_clock.py'
            synthetic_head,source_spec=admit_version_safe_clock_source(
                source_file=source,records=[*rows,row])
            fail(synthetic_head==digest(row) and source_spec==target,
                 'ATLAS_R12_INSTALLED_CLOCK_SOURCE_ADMISSION_FAILED')
    finally:
        store.close()
    return {'schema':'ATLAS_VERSION_SAFE_R12_NONFINANCIAL_SELECTION_REVIEW_V1',
        'status':'READY_FOR_SEPARATE_OPERATOR_REVIEW_NOT_AUTHORIZED',
        'predecessor_head':R11_HEAD,'predecessor_selected_release':V7,
        'proposed_revision':12,'row':row,'proposed_head':digest(row),
        'support_receipt_sha256':SUPPORT_RECEIPT_SHA,
        'support_manifest_sha256':SUPPORT_MANIFEST_SHA,
        'support_control':str(SUPPORT_ROOT),
        'support_launcher':str(SUPPORT_LAUNCHER),
        'clock_profile':PROFILE,'installed_clock_source_match':True,
        'predecessor_records_verified':11,
        'operator_approval_record_present':False,
        'r12_published':False,'code_selection_authorized':False,
        'financial_accounts_authorized':False,'providers_authorized':False,
        'paper_start_authorized':False,'simulated_orders_authorized':False,
        'live_trading_authorized':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    flags=parser.add_mutually_exclusive_group(required=True)
    flags.add_argument('--inspect',action='store_true')
    flags.add_argument('--write-review-once',action='store_true')
    a=parser.parse_args(argv)
    value=native_plan()
    from scripts.release_selection import encoded
    if a.write_review_once:
        if REVIEW.exists():raise ValueError('ATLAS_R12_PROPOSAL_ALREADY_RECORDED_NO_OVERWRITE')
        with REVIEW.open('xb') as f:f.write(encoded(value))
    return {'status':value['status'],'revision':12,
            'proposed_head':value['proposed_head'],
            'operation':value['row']['operation'],
            'predecessor_records_verified':11,
            'support_receipt_verified':True,'installed_clock_source_match':True,
            'review_recorded':REVIEW.exists(),'r12_published':False,
            'code_selection_authorized':False,'financial_authority':False}


if __name__=='__main__':
    print(json.dumps(main(),sort_keys=True),flush=True)
