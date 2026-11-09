"""Independent-NTP native SUPPORT bootstrap for installed version-safe Atlas.

Source-only: real support installation is blocked by a separate absent approval.
No selector writer, account reader, provider access, financial action or startup.
Execute read-only inspection using the installed native Python 3.12 -I -B -S.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path

REPO = Path(r'D:\Work\Project Atlas')
NEW = '2d4879878bf58bea5a3ed0a986b809791f638fec'
V7 = 'af96bec0484a8e43f9965610e071a907a0d316bf'
APP = Path(r'D:\AtlasRuntime\releases') / NEW
SUPPORT = REPO / 'logs/diagnostics/atlas-version-safe-ntp-support-source-20261109-r12-review'
MANIFEST = SUPPORT / 'deployment.json'
ARCHIVE = SUPPORT / 'support-source.zip'
REVIEW = SUPPORT / 'review.json'
SOURCE = REPO / 'scripts/support_deployment.py'
APP_RECEIPT = REPO / 'logs/diagnostics' / ('qd-unselected-release-'+NEW+'.json')
SELECTOR = Path(r'D:\AtlasRuntime\selection')
HEAD = '933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997'
APP_SHA = 'acdae2f01fb5defdf0e302240dc589eca0f1c99e3fcc15ec319d98260125cbb6'
ARTIFACT = '20d96aa9b8349506eb4c3e725523a59c18eb8386684ddfefd2bffc472302b732'
MANIFEST_SHA = 'd61fd6c9fa18bd819f3328040e6c40581efc8faeef8eca8e6326eb110b919ad8'
ARCHIVE_SHA = '3bf7ff32eeda8235afaa5f6befe0abb66f09faac0096dc6fadb8e6cc7782a6b2'
SUPPORT_SHA = '6a22a5a7a75150a421cb769aee85e95a8e297b4c0a3457d503bc808c661ff674'
ADAPTER_SHA = '808a7994ec644f596aa7214c281c557862d10b1ad571a6632d3c0c67d426ede8'
NTP_SHA = '230a35d8b293be0d38ded533bb964d36bc5bf3c80d432a85656bc4c22650979c'
CLOCK_SHA = '4054239941084707ede0e5d434bb39bb4b572b6eb80bfcee7a94c00b2b2af1d3'
BASE_ID = [4004218753, 65536, 1113770]
PARENTS = {r'D:\AtlasRuntime\launchers':[4004218753, 327680, 1532783],
           r'D:\AtlasRuntime\support-installations':[4004218753, 327680, 1532784],
           r'D:\AtlasRuntime\selection':[4004218753, 65536, 1532785]}
NTP_ISSUER = 'ATLAS_INDEPENDENT_DUAL_NTP_V1_GOOGLE_CLOUDFLARE'
CONFIRM = 'NO_SELECTION_NO_FINANCIAL_ACCOUNTS_NO_ORDERS'
# Explicitly unset until a distinct source-reviewed, one-time operator decision.
APPROVAL_PIN = None
APPROVAL_FILE = REPO/'logs/diagnostics/atlas-version-safe-support-install-approval-20261109.json'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def normalized(raw):
    return raw.replace(b'\r\n', b'\n')


def read_pinned(path, expected, *, limit=16*1024**2):
    from pathlib import Path
    if type(expected) is not str or not re.fullmatch('[0-9a-f]{64}',expected):
        raise ValueError('SUPPORT_VSAFE_PIN_REQUIRED')
    path=Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size>limit:
        raise ValueError('SUPPORT_VSAFE_SOURCE_FILE_REQUIRED')
    content=path.read_bytes()
    require(sha(content)==expected, 'SUPPORT_VSAFE_PIN_CHANGED')
    return content


def require_installed_interpreter():
    require(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode
            and sys.dont_write_bytecode
            and Path(sys.executable)==APP/'python/python.exe'
            and Path(sys.base_prefix)==APP/'python',
            'SUPPORT_VSAFE_EXACT_INSTALLED_ISOLATED_PYTHON_REQUIRED')
    require(all(Path(s).is_absolute() and Path(s).resolve().is_relative_to(APP)
                for s in sys.path if s), 'SUPPORT_VSAFE_FOREIGN_IMPORT_PATH')
    sys.path[:0]=[str(APP/'backend'),str(APP),str(APP/'python/Lib/site-packages')]


def load_reviewed_support(manifest):
    """Only explicit noninstalled source exception: hash/ZIP checked adapter."""
    raw=normalized(SOURCE.read_bytes())
    require(sha(raw)==ADAPTER_SHA,'SUPPORT_VSAFE_WORKSPACE_ADAPTER_CHANGED')
    with zipfile.ZipFile(ARCHIVE) as z:
        require(sha(z.read('scripts/support_deployment.py'))==ADAPTER_SHA,
                'SUPPORT_VSAFE_ARCHIVED_ADAPTER_CHANGED')
    spec=importlib.util.spec_from_file_location('scripts.support_deployment',SOURCE)
    require(spec is not None and spec.loader is not None,
            'SUPPORT_VSAFE_ADAPTER_LOADER_REFUSED')
    module=importlib.util.module_from_spec(spec)
    sys.modules['scripts.support_deployment']=module
    spec.loader.exec_module(module)
    require(Path(module.__file__).resolve()==SOURCE,
            'SUPPORT_VSAFE_ADAPTER_ORIGIN_CHANGED')
    return module


def require_v7_native_parents(support):
    from scripts.volume_inspector import windows_output as win
    from scripts.release_selection import digest
    from scripts.release_selection_store import NativeSelectionStore
    with support.held(win.WindowsOutput(r'D:\AtlasRuntime')) as out:
        require(support.identity(win,out.root_handle)==BASE_ID,
                'SUPPORT_VSAFE_NATIVE_BASE_CHANGED')
    for p,identity in PARENTS.items():
        with support.held(win.WindowsOutput(p)) as out:
            require(support.identity(win,out.root_handle)==identity,
                    'SUPPORT_VSAFE_NATIVE_PARENT_CHANGED')
    store=NativeSelectionStore(root=str(SELECTOR),native_root=PARENTS[str(SELECTOR)])
    try:
        with store.locked():
            rows=store.records()
            require(len(rows)==11 and rows[-1]['revision']==11
                    and rows[-1]['selected']['release']==V7
                    and digest(rows[-1])==HEAD,
                    'SUPPORT_VSAFE_V7_NATIVE_HISTORY_CHANGED')
    finally:
        store.close()
    require(not os.path.lexists(SELECTOR/'r0012.json')
            and not os.path.lexists(SELECTOR/'r0012.pending'),
            'SUPPORT_VSAFE_R12_ALREADY_EXISTS')


def inspect():
    require_installed_interpreter()
    r=json.loads(read_pinned(APP_RECEIPT,APP_SHA,limit=8*1024**2))
    require(r.get('source_commit')==NEW and r.get('artifact_digest')==ARTIFACT
            and r.get('release_path')==str(APP)
            and all(r.get(k) is False for k in ('selected','financial_effects',
                         'provider_connections','operational_acceptance')),
            'SUPPORT_VSAFE_INSTALLED_APP_SCOPE_CHANGED')
    m=json.loads(read_pinned(MANIFEST,MANIFEST_SHA))
    read_pinned(ARCHIVE,ARCHIVE_SHA)
    review=json.loads(REVIEW.read_bytes())
    require(review.get('status')=='SOURCE_REVIEW_NOT_PERMISSION'
            and review.get('manifest_sha256')==MANIFEST_SHA
            and review.get('archive_sha256')==ARCHIVE_SHA
            and all(review.get(k) is False for k in ('native_install_authorized',
                'selection_authorized','financial_authority',
                'legacy_windows_clock_profile_accepted')),
            'SUPPORT_VSAFE_SOURCE_REVIEW_NOT_AUTHORITY')
    from scripts.release_selection import encoded
    require(sha(encoded(m))==MANIFEST_SHA,
            'SUPPORT_VSAFE_MANIFEST_CANONICAL_CHANGED')
    require(m['application']=={'release':NEW,'root':str(APP),
               'receipt':str(APP_RECEIPT),'receipt_sha256':APP_SHA,
               'artifact_digest':ARTIFACT},
            'SUPPORT_VSAFE_APPLICATION_BINDING_REQUIRED')
    require(m.get('accepted_parents')==PARENTS,
            'SUPPORT_VSAFE_NATIVE_PARENT_PLAN_CHANGED')
    require(m['support_manifest_sha256']==SUPPORT_SHA
            and m['archive_sha256']==ARCHIVE_SHA
            and m['runtime']['python']==str(APP/'python/python.exe')
            and m['runtime']['providers'] is False
            and m['runtime']['financial_writers'] is False
            and m['runtime']['workspace_fallback'] is False,
            'SUPPORT_VSAFE_NO_FINANCIAL_OR_WORKSPACE_FALLBACK')
    require(not os.path.lexists(m['destination'])
            and not os.path.lexists(m['control']),
            'SUPPORT_VSAFE_NATIVE_ALREADY_INSTALLED_OR_PARTIAL_NO_RETRY')
    support=load_reviewed_support(m)
    package,files=support.prepare(m,ARCHIVE,MANIFEST_SHA)
    require(package==m and sha(files['support-manifest.json'])==SUPPORT_SHA,
            'SUPPORT_VSAFE_PACKAGE_ARCHIVE_MISMATCH')
    p=support.strict(files['support-manifest.json'])
    require(p.get('application_release')==NEW
            and p.get('clock')=={'issuer':NTP_ISSUER,
                'maximum_evidence_age_seconds':120,'maximum_uncertainty_ms':1000}
            and all(p.get(k) is False for k in ('installation_authorized',
                 'promotion_authorized','financial_startup_authorized',
                 'providers_authorized')),
            'SUPPORT_VSAFE_INDEPENDENT_NTP_PROFILE_REQUIRED')
    rows={x['path']:x['sha256'] for x in p['required_installed_application_sources']}
    actual={x['path'].replace('\\','/'):x['sha256'] for x in r['files']}
    require(len(rows)==24 and all(actual.get(n)==v for n,v in rows.items())
            and rows.get('scripts/observation_runtime/atlas_independent_ntp_clock.py')==NTP_SHA
            and rows.get('scripts/observation_runtime/personal_version_safe_release_clock.py')==CLOCK_SHA,
            'SUPPORT_VSAFE_INSTALLED_NATIVE_DEPENDENCIES_CHANGED')
    require(support.support_clock_profile(m)=='WINDOWS_TIME_CODE_SELECTION_V1',
            'SUPPORT_VSAFE_HISTORICAL_ADAPTER_CHANGED')
    require_v7_native_parents(support)
    return support,m,p


def validate_operator_decision(value, *, sid, manifest):
    """Pure consent contract, NOT an independently authenticated approval."""
    fields={'schema','decision','scope','operator_sid','target_release',
            'application_receipt_sha256','artifact_digest','manifest_sha256',
            'archive_sha256','support_manifest_sha256','selected_v7_head',
            'destination','control','one_shot','selection_allowed',
            'provider_access','financial_authority','paper_accounts','orders'}
    if (type(value) is not dict or set(value)!=fields
            or type(sid) is not str or not sid.startswith('S-1-')
            or value.get('schema')!='ATLAS_VERSION_SAFE_SUPPORT_CODE_ONLY_APPROVAL_V1'
            or value.get('decision')!='APPROVE_ONE_NATIVE_SUPPORT_COPY_ONLY'
            or value.get('scope')!=CONFIRM or value.get('operator_sid')!=sid
            or value.get('target_release')!=NEW
            or value.get('application_receipt_sha256')!=APP_SHA
            or value.get('artifact_digest')!=ARTIFACT
            or value.get('manifest_sha256')!=MANIFEST_SHA
            or value.get('archive_sha256')!=ARCHIVE_SHA
            or value.get('support_manifest_sha256')!=SUPPORT_SHA
            or value.get('selected_v7_head')!=HEAD
            or value.get('destination')!=manifest['destination']
            or value.get('control')!=manifest['control']
            or value.get('one_shot') is not True
            or any(value.get(k) is not False for k in (
                'selection_allowed','provider_access','financial_authority',
                'paper_accounts','orders'))):
        raise ValueError('SUPPORT_VSAFE_EXACT_OPERATOR_DECISION_REQUIRED')
    return value


def require_install_approval(*, manifest=None):
    """Read-only exact one-shot native-SID consent; no minting or guessing."""
    if not APPROVAL_FILE.is_file():
        raise ValueError('SUPPORT_VSAFE_SEPARATE_INSTALL_APPROVAL_ABSENT')
    if type(APPROVAL_PIN) is not str or not re.fullmatch('[0-9a-f]{64}',APPROVAL_PIN):
        raise ValueError('SUPPORT_VSAFE_APPROVAL_NOT_INDEPENDENTLY_PINNED')
    if manifest is None:
        manifest=json.loads(read_pinned(MANIFEST,MANIFEST_SHA))
    raw=read_pinned(APPROVAL_FILE,APPROVAL_PIN,limit=4096)
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ValueError('SUPPORT_VSAFE_DUPLICATE_APPROVAL_KEY')
            result[k]=v
        return result
    decision=json.loads(raw,object_pairs_hook=unique)
    from scripts.volume_inspector.windows_output import current_sid
    return validate_operator_decision(decision,sid=current_sid(),manifest=manifest)


def qualify_independent_clock(clock, runtime_id):
    """Single genuine external NTP clock: 180s monotonic, >=37 checks."""
    from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock, SOURCE as NTP_SOURCE
    if type(clock) is not IndependentNtpClock:
        raise ValueError('SUPPORT_VSAFE_REAL_INDEPENDENT_CLOCK_REQUIRED')
    start=time.perf_counter();samples=0
    while True:
        clock.require_operational(runtime_id)
        evidence=clock.evidence
        if (evidence.get('source')!=NTP_SOURCE
                or evidence.get('domain')!='TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS'
                or evidence.get('financial_authority') is not False
                or type(evidence.get('bound_ms')) is not int
                or not 0<=evidence['bound_ms']<=1000):
            raise ValueError('SUPPORT_VSAFE_TWO_PEER_CLOCK_CONTINUITY_REFUSED')
        samples+=1
        elapsed=time.perf_counter()-start
        if elapsed>=180:break
        time.sleep(min(5,180-elapsed))
    if samples<37:
        raise ValueError('SUPPORT_VSAFE_180S_37_CLOCK_SAMPLES_REQUIRED')
    return {'samples':samples,'elapsed_seconds':elapsed,
            'uncertainty_ms':evidence['bound_ms']}


def install_code_only():
    """Future reviewed one-shot create-only support copy. CURRENTLY BLOCKED."""
    # Approval before any NTP UDP traffic or native mutation.
    require_install_approval()
    support,m,p=inspect()
    from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
    from scripts.release_selection import NativeInstalledReleaseVerifier
    runtime_id='qd-support-deployment-'+MANIFEST_SHA
    clock=IndependentNtpClock(runtime_id=runtime_id)
    try:
        lease=qualify_independent_clock(clock,runtime_id)
        require_install_approval(manifest=m)
        # Recheck all hash/parent/selector/create-only checks AFTER clock lease.
        support,m,p=inspect()
        reference={'schema':'QD_INSTALLED_RELEASE_REFERENCE_V1',
                   'domain':'WINDOWS_LOCAL',**m['application']}
        def admission():
            clock.require_operational(runtime_id)
            ev=clock.evidence
            from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE as NTP_SOURCE
            if (ev.get('source')!=NTP_SOURCE
                    or ev.get('domain')!='TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS'
                    or ev.get('financial_authority') is not False
                    or type(ev.get('bound_ms')) is not int
                    or not 0<=ev['bound_ms']<=1000):
                raise ValueError('SUPPORT_VSAFE_NTP_LOST_DURING_NATIVE_COPY')
            return True
        admission()
        with NativeInstalledReleaseVerifier().open(reference) as receipt:
            actual={x['path'].replace('\\','/'):x['sha256'] for x in receipt['files']}
            required=p['required_installed_application_sources']
            require(all(actual.get(x['path'])==x['sha256'] for x in required),
                    'SUPPORT_VSAFE_NATIVE_APPLICATION_SOURCE_CHANGED')
            # Unlike historical install_operational(), the explicitly reviewed
            # new NTP profile is admitted ONLY above. Never accept Windows Time.
            _,files=support.prepare(m,ARCHIVE,MANIFEST_SHA)
            result=support._install(m,files,parent_identity=BASE_ID,admission=admission)
        require(result['handles_after_close']==0
                and result['receipt']['selected'] is False
                and result['receipt']['financial_actions']==0,
                'SUPPORT_VSAFE_INSTALL_FINANCIAL_OR_HANDLE_REFUSED')
        require_v7_native_parents(support)
        return {'status':'VERSION_SAFE_NONFINANCIAL_SUPPORT_INSTALLED_UNSELECTED',
                'receipt_sha256':result['receipt_sha256'],
                'source_release':NEW,'ntp_preflight':lease,
                'selected':False,'financial_authority':False,'providers':False}
    finally:
        clock.revoke()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--inspect',action='store_true')
    actions.add_argument('--execute-reviewed-code-only',action='store_true')
    parser.add_argument('--confirm-scope',default=None)
    a=parser.parse_args(argv)
    if a.execute_reviewed_code_only:
        require(a.confirm_scope==CONFIRM,'SUPPORT_VSAFE_EXACT_NONFINANCIAL_SCOPE_REQUIRED')
        # No external sockets/clock, source/writer mutation or startup before consent.
        require_install_approval()
        install_code_only()
    require(a.confirm_scope is None,'SUPPORT_VSAFE_INSPECT_NO_EXECUTION_FLAG')
    _,m,p=inspect()
    return {'status':'VERSION_SAFE_NTP_SUPPORT_NATIVE_BOOTSTRAP_REVIEW_PASS',
            'source_release':NEW,'application_receipt_sha256':APP_SHA,
            'manifest_sha256':MANIFEST_SHA,
            'support_manifest_sha256':SUPPORT_SHA,
            'archive_sha256':ARCHIVE_SHA,
            'support_files':len(m['files']),
            'native_application_dependencies':len(p['required_installed_application_sources']),
            'native_support_installed':False,'selected':False,
            'financial_authority':False,'providers':False,
            'operator_approval_pinned':False}


if __name__=='__main__':
    print(json.dumps(main(),sort_keys=True))
