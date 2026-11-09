"""Explicit one-shot R12 native CODE-ONLY selector, fail-closed until consent.

This separate publisher supports the newly installed independent two-peer NTP
release without modifying the historical V7-only ReleaseSelector.change rule.
It MUST NOT grant PAPER accounts, providers, trading, startup or live orders.

Read-only:  installed python -I -B -S <this file> --inspect
Mutating path: separately pinned one-shot native-SID decision REQUIRED; absent.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import weakref
from pathlib import Path

REPO=Path(r'D:\Work\Project Atlas')
RELEASE='2d4879878bf58bea5a3ed0a986b809791f638fec'
APP=Path('D:/AtlasRuntime/releases')/RELEASE
SELECTOR=Path(r'D:\AtlasRuntime\selection')
PROPOSAL=REPO/'scripts/atlas_version_safe_r12_selection_proposal.py'
PROPOSAL_SHA='9ad0a7f0bcc34b17da1c942fc29ddaa5eb84147210ac15c2aa86ac6d3c60b38f'
REVIEW=REPO/'docs/ATLAS_VERSION_SAFE_R12_NONFINANCIAL_SELECTION_REVIEW_R1_2026-11-09.json'
REVIEW_SHA='6bf4567c4a196b801f0effa3fc74d3292e96ea2a94094cafc19f006e5ed73588'
V7_HEAD='933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997'
V7_RELEASE='af96bec0484a8e43f9965610e071a907a0d316bf'
R12_HEAD='f4cf83bb1e98ecb7cfa3be37fe27e80a79b339dc26f73358a1702349b47958fd'
OPERATION='08ca065b488c6e1748976aeb251939c3'
APP_RECEIPT_SHA='acdae2f01fb5defdf0e302240dc589eca0f1c99e3fcc15ec319d98260125cbb6'
APP_DIGEST='20d96aa9b8349506eb4c3e725523a59c18eb8386684ddfefd2bffc472302b732'
SUPPORT_RECEIPT_SHA='2d2631152aea9086d95f2b60d06f1fde1c61ac61778d9ea36098d6883ce7eaac'
SUPPORT_MANIFEST_SHA='d61fd6c9fa18bd819f3328040e6c40581efc8faeef8eca8e6326eb110b919ad8'
NATIVE_ID=[4004218753,65536,1532785]
CLOCK_PROFILE='INDEPENDENT_TWO_PEER_NTP_VERSION_SAFE_R12_V1'
SCOPE='SELECT_ONE_PINNED_R12_CODE_RELEASE_ONLY_NO_PAPER_START'
DECISION='APPROVE_EXACT_NONFINANCIAL_R12_CODE_SELECTION'
APPROVAL=REPO/'logs/diagnostics/atlas-version-safe-r12-code-selection-approval-20261109.json'
# A proposal and permission to continue development are not selector approval.
# A separately reviewed native-SID decision and independent local SHA pin are
# needed before any public NTP sockets or append-only r12 publication.
APPROVAL_PIN=None
# Fresh in-process NTP qualification, bound to a specific clock object and
# consumed on the ONE publication attempt. A forged dict is not a lease.
_qualifications=weakref.WeakKeyDictionary()


def refuse_if(condition,reason):
    if condition:raise ValueError(reason)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def checked(path,pin,limit=65536):
    refuse_if(not path.is_file() or path.is_symlink() or path.stat().st_size>limit,
              'ATLAS_R12_PUBLISHER_REVIEWED_BYTES_REQUIRED')
    data=path.read_bytes()
    refuse_if(sha(data)!=pin,'ATLAS_R12_PUBLISHER_PIN_CHANGED')
    return data


def strictly_json(raw):
    def unique(pairs):
        result={}
        for key,val in pairs:
            if key in result:raise ValueError('ATLAS_R12_PUBLISHER_DUPLICATE_JSON_KEY')
            result[key]=val
        return result
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda k:(_ for _ in ()).throw(
        ValueError('ATLAS_R12_PUBLISHER_NONFINITE_JSON')))


def installed_python():
    refuse_if(not(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode
                  and sys.dont_write_bytecode and Path(sys.executable)==APP/'python/python.exe'
                  and Path(sys.base_prefix)==APP/'python'),
              'ATLAS_R12_PUBLISHER_INSTALLED_ISOLATED_PYTHON_REQUIRED')
    if str(APP) not in sys.path:
        sys.path[:0]=[str(APP/'backend'),str(APP),str(APP/'python/Lib/site-packages')]


def load_reviewed_plan():
    installed_python()
    review=strictly_json(checked(REVIEW,REVIEW_SHA,limit=8192))
    refuse_if(review.get('schema')!='ATLAS_VERSION_SAFE_R12_NONFINANCIAL_SELECTION_REVIEW_V1'
              or review.get('status')!='READY_FOR_SEPARATE_OPERATOR_REVIEW_NOT_AUTHORIZED'
              or review.get('proposed_revision')!=12
              or review.get('predecessor_head')!=V7_HEAD
              or review.get('predecessor_selected_release')!=V7_RELEASE
              or review.get('proposed_head')!=R12_HEAD
              or review.get('support_receipt_sha256')!=SUPPORT_RECEIPT_SHA
              or review.get('support_manifest_sha256')!=SUPPORT_MANIFEST_SHA
              or review.get('clock_profile')!=CLOCK_PROFILE
              or review.get('installed_clock_source_match') is not True
              or review.get('predecessor_records_verified')!=11
              or review.get('row',{}).get('operation')!=OPERATION
              or review.get('row',{}).get('revision')!=12
              or review.get('row',{}).get('previous')!=V7_HEAD
              or review.get('row',{}).get('action')!='SELECT'
              or review.get('row',{}).get('selected',{}).get('release')!=RELEASE
              or review.get('row',{}).get('selected',{}).get('receipt_sha256')!=APP_RECEIPT_SHA
              or review.get('row',{}).get('selected',{}).get('artifact_digest')!=APP_DIGEST
              or review.get('r12_published') is not False
              or any(review.get(key) is not False for key in (
                  'operator_approval_record_present','code_selection_authorized',
                  'financial_accounts_authorized','providers_authorized',
                  'paper_start_authorized','simulated_orders_authorized',
                  'live_trading_authorized')),
              'ATLAS_R12_PUBLISHER_EXACT_NONFINANCIAL_REVIEW_REQUIRED')
    checked(PROPOSAL,PROPOSAL_SHA,limit=32768)
    spec=importlib.util.spec_from_file_location('atlas_r12_frozen_readonly_proposal',PROPOSAL)
    refuse_if(spec is None or spec.loader is None,'ATLAS_R12_PUBLISHER_SOURCE_LOADER_REFUSED')
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    refuse_if(Path(mod.__file__)!=PROPOSAL
              or mod.R11_HEAD!=V7_HEAD or mod.RELEASE!=RELEASE
              or mod.R11_ENVELOPE_SHA!='3804a749f88cbf6da1873f71b917ef440ca801e31f4a93f73759df4382898c4d'
              or mod.APP_SHA!=APP_RECEIPT_SHA
              or mod.ARTIFACT!=APP_DIGEST
              or mod.SUPPORT_RECEIPT_SHA!=SUPPORT_RECEIPT_SHA
              or mod.SUPPORT_MANIFEST_SHA!=SUPPORT_MANIFEST_SHA,
              'ATLAS_R12_PUBLISHER_REVIEWED_SOURCE_CHANGED')
    from scripts.release_selection import digest
    refuse_if(digest(review['row'])!=R12_HEAD,'ATLAS_R12_PUBLISHER_ROW_DIGEST_CHANGED')
    return mod,review


def validate_operator_decision(data,*,sid,review):
    """Strict one-shot nonfinancial selector permission, no self-minting."""
    required={'schema','decision','scope','operator_sid','one_shot','source_release',
              'review_sha256','predecessor_head','operation','proposed_head',
              'application_receipt_sha256','application_artifact_digest',
              'support_receipt_sha256','support_manifest_sha256','native_selection_root',
              'clock_profile','selection_allowed','financial_authority',
              'paper_accounts','providers','simulated_orders','live_orders',
              'automatic_startup'}
    refuse_if(type(data) is not dict or set(data)!=required
              or type(sid) is not str or not sid.startswith('S-1-')
              or data.get('schema')!='ATLAS_VERSION_SAFE_R12_CODE_ONLY_OPERATOR_DECISION_V1'
              or data.get('decision')!=DECISION or data.get('scope')!=SCOPE
              or data.get('operator_sid')!=sid or data.get('one_shot') is not True
              or data.get('source_release')!=RELEASE
              or data.get('review_sha256')!=REVIEW_SHA
              or data.get('predecessor_head')!=V7_HEAD
              or data.get('operation')!=OPERATION
              or data.get('proposed_head')!=R12_HEAD
              or data.get('application_receipt_sha256')!=APP_RECEIPT_SHA
              or data.get('application_artifact_digest')!=APP_DIGEST
              or data.get('support_receipt_sha256')!=SUPPORT_RECEIPT_SHA
              or data.get('support_manifest_sha256')!=SUPPORT_MANIFEST_SHA
              or data.get('native_selection_root')!=str(SELECTOR)
              or data.get('clock_profile')!=CLOCK_PROFILE
              or data.get('selection_allowed') is not True
              or any(data.get(key) is not False for key in (
                  'financial_authority','paper_accounts','providers',
                  'simulated_orders','live_orders','automatic_startup'))
              or review.get('row',{}).get('operation')!=OPERATION,
              'ATLAS_R12_PUBLISHER_EXACT_ONE_SHOT_OPERATOR_SCOPE_REQUIRED')
    return data


def require_approved_operator(*,review):
    if not APPROVAL.is_file():
        raise ValueError('ATLAS_R12_PUBLISHER_SEPARATE_APPROVAL_ABSENT')
    if type(APPROVAL_PIN) is not str or not re.fullmatch('[0-9a-f]{64}',APPROVAL_PIN):
        raise ValueError('ATLAS_R12_PUBLISHER_APPROVAL_NOT_SEPARATELY_PINNED')
    decision=strictly_json(checked(APPROVAL,APPROVAL_PIN,limit=4096))
    from scripts.volume_inspector.windows_output import current_sid
    return validate_operator_decision(decision,sid=current_sid(),review=review)


def validate_clock(clock,runtime_id):
    from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock,SOURCE
    refuse_if(type(clock) is not IndependentNtpClock,
              'ATLAS_R12_PUBLISHER_GENUINE_TWO_PEER_CLOCK_REQUIRED')
    clock.require_operational(runtime_id)
    evidence=clock.evidence
    refuse_if(type(evidence) is not dict
              or evidence.get('source')!=SOURCE
              or evidence.get('domain')!='TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS'
              or evidence.get('financial_authority') is not False
              or evidence.get('os_windows_time_service_required') is not False
              or type(evidence.get('bound_ms')) is not int
              or not 0<=evidence['bound_ms']<=1000,
              'ATLAS_R12_PUBLISHER_CLOCK_SOURCE_OR_UNCERTAINTY_REFUSED')
    return evidence


def qualify_clock(clock,runtime_id):
    """180 real monotonic seconds, >=37 samples, same owned two-peer object."""
    start=time.perf_counter();samples=0
    while True:
        value=validate_clock(clock,runtime_id)
        samples+=1
        elapsed=time.perf_counter()-start
        if elapsed>=180:break
        time.sleep(min(5,180-elapsed))
    refuse_if(samples<37,'ATLAS_R12_PUBLISHER_37_NTP_SAMPLES_REQUIRED')
    proof={'elapsed_seconds':elapsed,'samples':samples,
           'last_bound_ms':value['bound_ms']}
    _qualifications[clock]={'runtime_id':runtime_id,
        'completed_at_perf':time.perf_counter(),'proof':proof.copy()}
    return proof


def preview():
    mod,review=load_reviewed_plan()
    value=mod.native_plan()
    refuse_if(value!=review,'ATLAS_R12_PUBLISHER_NATIVE_PLAN_DIVERGED')
    from scripts.release_selection import digest
    refuse_if(digest(value['row'])!=R12_HEAD,'ATLAS_R12_PUBLISHER_PROPOSED_HEAD_CHANGED')
    return {'schema':'ATLAS_VERSION_SAFE_R12_SELECTION_PUBLISHER_PREVIEW_V1',
            'status':'READY_FOR_SEPARATE_OPERATOR_SELECTION_APPROVAL',
            'selected_release':V7_RELEASE,'proposed_release':RELEASE,
            'previous_head':V7_HEAD,'proposed_head':R12_HEAD,
            'operation':OPERATION,'support_receipt_sha256':SUPPORT_RECEIPT_SHA,
            'clock_profile':CLOCK_PROFILE,'revision':12,
            'operator_approval_pinned':type(APPROVAL_PIN) is str,
            'r12_published':False,'financial_authority':False,'paper_start':False,
            'provider_access':False,'orders':False}


def publish_with_native_lock(*,clock,runtime_id,preflight,mod,review):
    """Guarded native append-only primitive, unreachable without consent."""
    require_approved_operator(review=review)
    # Consume the exact qualification from this clock/process; caller-supplied
    # proof dictionaries cannot bypass a real 180-second NTP observation.
    try:
        qualification=_qualifications.pop(clock,None)
    except TypeError:  # a non-weakrefable forged clock is never qualified
        qualification=None
    refuse_if(type(preflight) is not dict
              or type(qualification) is not dict
              or qualification.get('runtime_id')!=runtime_id
              or qualification.get('proof')!=preflight
              or type(preflight.get('elapsed_seconds')) not in (float,int)
              or preflight['elapsed_seconds']<180
              or type(preflight.get('samples')) is not int
              or preflight['samples']<37
              or type(qualification.get('completed_at_perf')) not in (float,int)
              or not 0<=time.perf_counter()-qualification['completed_at_perf']<=120,
              'ATLAS_R12_PUBLISHER_FRESH_180S_CLOCK_PROOF_REQUIRED')
    validate_clock(clock,runtime_id)
    from scripts.release_selection import digest,NativeInstalledReleaseVerifier,validate_spec
    from scripts.release_selection_store import NativeSelectionStore
    from scripts.observation_runtime.personal_version_safe_release_clock import admit_version_safe_clock_source
    # Under a single native selection lock, recheck support and all prior
    # native selection records; no re-entrance into the selector's V7-only
    # historical change() method and no broad financial authority.
    store=NativeSelectionStore(root=str(SELECTOR),native_root=list(NATIVE_ID))
    try:
        with store.locked():
            require_approved_operator(review=review)
            validate_clock(clock,runtime_id)
            mod.check_external_support()  # full installed support receipt/ACK before publish
            records=store.records()
            used=mod.validated_chain(records,digest,validate_spec)
            refuse_if(OPERATION in used or len(records)!=11,
                      'ATLAS_R12_PUBLISHER_HEAD_OR_OPERATION_CHANGED')
            refuse_if(mod.sha((SELECTOR/'r0011.json').read_bytes())!=mod.R11_ENVELOPE_SHA
                      or os.path.lexists(SELECTOR/'r0012.json')
                      or os.path.lexists(SELECTOR/'r0012.pending'),
                      'ATLAS_R12_PUBLISHER_NATIVE_TAIL_CHANGED')
            target=validate_spec(review['row']['selected'],'WINDOWS_LOCAL')
            refuse_if(target['release']!=RELEASE or target['receipt_sha256']!=APP_RECEIPT_SHA
                      or target['artifact_digest']!=APP_DIGEST,
                      'ATLAS_R12_PUBLISHER_WRONG_APPLICATION_RECEIPT')
            with NativeInstalledReleaseVerifier().open(target) as installed:
                refuse_if(installed.get('source_commit')!=RELEASE
                          or installed.get('artifact_digest')!=APP_DIGEST
                          or any(installed.get(k) is not False for k in (
                              'selected','financial_effects','provider_connections',
                              'operational_acceptance')),
                          'ATLAS_R12_PUBLISHER_NONFINANCIAL_INSTALLED_APP_REQUIRED')
                row=review['row']
                source=APP/'scripts/observation_runtime/personal_version_safe_release_clock.py'
                proposed_head,spec=admit_version_safe_clock_source(
                    source_file=source,records=[*records,row])
                refuse_if(spec!=target or proposed_head!=R12_HEAD or digest(row)!=R12_HEAD,
                          'ATLAS_R12_PUBLISHER_SELECTED_CLOCK_BINDING_CHANGED')
                # LAST gates directly before the irreversible native NTFS
                # hardlink publication. Failed or partial tails are preserved;
                # no automatic retry or adoption is implemented.
                require_approved_operator(review=review)
                validate_clock(clock,runtime_id)
                store.publish(row)
            current=store.records()
            refuse_if(len(current)!=12 or current[-1]!=review['row']
                      or digest(current[-1])!=R12_HEAD
                      or mod.validated_chain(current[:11],digest,validate_spec)!=used,
                      'ATLAS_R12_PUBLISHER_POST_PUBLICATION_UNKNOWN')
            return {'schema':'ATLAS_VERSION_SAFE_R12_CODE_ONLY_NATIVE_PUBLICATION_V1',
                    'status':'R12_NONFINANCIAL_CODE_SELECTED',
                    'selected_release':RELEASE,'previous_head':V7_HEAD,
                    'new_head':R12_HEAD,'operation':OPERATION,'revision':12,
                    'application_receipt_sha256':APP_RECEIPT_SHA,
                    'support_receipt_sha256':SUPPORT_RECEIPT_SHA,
                    'clock_samples':preflight['samples'],
                    'clock_elapsed_seconds':preflight['elapsed_seconds'],
                    'financial_authority':False,'paper_accounts':False,
                    'provider_access':False,'orders':False}
    finally:
        store.close()


def execute():
    # Need separate explicit user/operator decision. Checking it BEFORE any
    # external NTP sockets prevents a mere code-review artifact from granting
    # write authority. R12 absence is rechecked before and after preflight.
    mod,review=load_reviewed_plan()
    require_approved_operator(review=review)
    preview()
    runtime_id='atlas-r12-code-only-'+OPERATION
    from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
    clock=IndependentNtpClock(runtime_id=runtime_id)
    try:
        proof=qualify_clock(clock,runtime_id)
        require_approved_operator(review=review)
        preview()
        return publish_with_native_lock(clock=clock,runtime_id=runtime_id,
                                        preflight=proof,mod=mod,review=review)
    finally:
        clock.revoke()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--inspect',action='store_true',help='Read-only native proposal/receipt verification')
    group.add_argument('--execute-one-shot-code-selection',action='store_true',
                       help='Requires separately reviewed native-SID code-only selection approval')
    parser.add_argument('--confirm-scope',default=None)
    a=parser.parse_args(argv)
    if a.inspect:
        refuse_if(a.confirm_scope is not None,'ATLAS_R12_PUBLISHER_INSPECT_SCOPE_MIXED')
        return preview()
    refuse_if(a.confirm_scope!=SCOPE,'ATLAS_R12_PUBLISHER_EXACT_NONFINANCIAL_CLI_SCOPE_REQUIRED')
    return execute()


if __name__=='__main__':
    print(json.dumps(main(),sort_keys=True),flush=True)
