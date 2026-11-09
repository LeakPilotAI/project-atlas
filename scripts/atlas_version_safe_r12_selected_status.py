"""Read-only native r12 selected-code and installed-support status; no PAPER startup.

Use ONLY the installed release's isolated Python 3.12 with -I -B -S.
Rechecks current native r12 record pair and pinned independent installation
proof. --deep additionally rereads all installed application file hashes.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(r'D:\Work\Project Atlas')
APP=Path('D:/AtlasRuntime/releases/2d4879878bf58bea5a3ed0a986b809791f638fec')
SEL=Path('D:/AtlasRuntime/selection')
PROOF=ROOT/'logs/diagnostics/atlas-r12-independent-native-post-selection-proof-20261109.json'
PROOF_SHA='229ec543ec9c43f7904bbf42bd12b8367d005f822c513f515975acd3c7f42e94'
R12_RECORD_SHA='f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7'
R11_RECORD_SHA='3804a749f88cbf6da1873f71b917ef440ca801e31f4a93f73759df4382898c4d'
R11_HEAD='933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997'
R12_HEAD='f4cf83bb1e98ecb7cfa3be37fe27e80a79b339dc26f73358a1702349b47958fd'
RELEASE=APP.name
APP_RECEIPT=ROOT/'logs/diagnostics/qd-unselected-release-2d4879878bf58bea5a3ed0a986b809791f638fec.json'
APP_SHA='acdae2f01fb5defdf0e302240dc589eca0f1c99e3fcc15ec319d98260125cbb6'
SUPPORT=Path('D:/AtlasRuntime/support-installations/6a22a5a7a75150a421cb769aee85e95a8e297b4c0a3457d503bc808c661ff674/receipt.json')
SUPPORT_SHA='2d2631152aea9086d95f2b60d06f1fde1c61ac61778d9ea36098d6883ce7eaac'


def pinned(path,digest,limit=8*1024**2):
    if not path.is_file() or path.is_symlink() or path.stat().st_size>limit:
        raise ValueError('ATLAS_R12_SELECTED_STATUS_REQUIRED_NATIVE_EVIDENCE_ABSENT')
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=digest:
        raise ValueError('ATLAS_R12_SELECTED_STATUS_NATIVE_HASH_CHANGED')
    return data


def inspect(*,deep=False):
    if not (sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode
            and Path(sys.executable)==APP/'python/python.exe'
            and Path(sys.base_prefix)==APP/'python'):
        raise ValueError('ATLAS_R12_SELECTED_STATUS_INSTALLED_PYTHON_REQUIRED')
    sys.path[:0]=[str(APP/'backend'),str(APP),str(APP/'python/Lib/site-packages')]
    from scripts.release_selection import digest,NativeInstalledReleaseVerifier
    from scripts.release_selection_store import NativeSelectionStore
    from scripts.observation_runtime.personal_version_safe_release_clock import admit_version_safe_clock_source
    proof=json.loads(pinned(PROOF,PROOF_SHA,limit=4096))
    if (proof.get('status')!='R12_NATIVE_SELECTED_APP_SUPPORT_CLOCK_VERIFIED'
            or proof.get('revision')!=12
            or proof.get('selected_release')!=RELEASE
            or proof.get('r12_head')!=R12_HEAD
            or proof.get('support_receipt_sha256')!=SUPPORT_SHA
            or proof.get('application_receipt_sha256')!=APP_SHA
            or proof.get('own_clock_source_admitted') is not True
            or any(proof.get(k) is not False for k in (
                'financial_authority','paper_accounts_created',
                'providers_connected','orders_submitted','paper_start_authorized'))):
        raise ValueError('ATLAS_R12_SELECTED_STATUS_INDEPENDENT_PROOF_CHANGED')
    pinned(SEL/'r0011.json',R11_RECORD_SHA,limit=2048)
    pinned(SEL/'r0012.json',R12_RECORD_SHA,limit=2048)
    pinned(SEL/'r0012.pending',R12_RECORD_SHA,limit=2048)
    pinned(APP_RECEIPT,APP_SHA)
    pinned(SUPPORT,SUPPORT_SHA,limit=65536)
    store=NativeSelectionStore(root=str(SEL),native_root=[4004218753,65536,1532785])
    try:
        with store.locked():
            records=store.records()
            if (len(records)!=12 or digest(records[-2])!=R11_HEAD
                    or digest(records[-1])!=R12_HEAD
                    or records[-1]['revision']!=12
                    or records[-1]['previous']!=R11_HEAD
                    or records[-1]['action']!='SELECT'
                    or records[-1]['selected']['release']!=RELEASE
                    or records[-1]['selected']['receipt_sha256']!=APP_SHA):
                raise ValueError('ATLAS_R12_SELECTED_STATUS_NATIVE_CHAIN_CHANGED')
            from scripts.observation_runtime.personal_version_safe_release_clock import admit_version_safe_clock_source
            head,selected=admit_version_safe_clock_source(
                source_file=APP/'scripts/observation_runtime/personal_version_safe_release_clock.py',
                records=records)
            if head!=R12_HEAD or selected!=records[-1]['selected']:
                raise ValueError('ATLAS_R12_SELECTED_STATUS_INSTALLED_CLOCK_SOURCE_CHANGED')
            if deep:
                with NativeInstalledReleaseVerifier().open(selected) as installed:
                    if (installed.get('source_commit')!=RELEASE
                            or len(installed['files'])!=10574
                            or len(installed['directories'])!=914
                            or installed.get('financial_effects') is not False
                            or installed.get('provider_connections') is not False):
                        raise ValueError('ATLAS_R12_SELECTED_STATUS_INSTALLED_APP_CHANGED')
    finally:
        store.close()
    return {'schema':'ATLAS_R12_SELECTED_CODE_READONLY_STATUS_V1',
            'status':'NATIVE_R12_CODE_SELECTED_NOT_FINANCIAL_PAPER',
            'revision':12,'selected_release':RELEASE,'r12_head':R12_HEAD,
            'native_record_pair_verified':True,'support_receipt_verified':True,
            'independent_proof_verified':True,'selected_clock_source_verified':True,
            'deep_application_verified':deep,
            'financial_authority':False,'paper_accounts_authorized':False,
            'providers_authorized':False,'orders_authorized':False,
            'paper_start_authorized':False,'live_trading_authorized':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deep',action='store_true',help='Reverify all installed app files')
    args=parser.parse_args(argv)
    return inspect(deep=args.deep)


if __name__=='__main__':
    print(json.dumps(main(),sort_keys=True),flush=True)
