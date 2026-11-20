"""Create-only independent-NTP support SOURCE package for installed version-safe Atlas.

The existing V7/V8 support adapter and installed native support remain immutable.
This source-only ZIP is NOT authorized for native support installation or r12
selection: the historical adapter still defaults to Windows-clock for new apps.
"""
import copy
import hashlib
import json
import os
import zipfile
from pathlib import Path

from scripts.build_release_candidate import source_bytes
from scripts.release_selection import digest, encoded
from scripts import support_deployment as legacy

ROOT = Path(__file__).resolve().parents[1]
NEW = '2d4879878bf58bea5a3ed0a986b809791f638fec'
RECEIPT_SHA = 'acdae2f01fb5defdf0e302240dc589eca0f1c99e3fcc15ec319d98260125cbb6'
ARTIFACT = '20d96aa9b8349506eb4c3e725523a59c18eb8386684ddfefd2bffc472302b732'
V7_HEAD = '933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997'
V7 = 'af96bec0484a8e43f9965610e071a907a0d316bf'
SOURCE_SHA = '230a35d8b293be0d38ded533bb964d36bc5bf3c80d432a85656bc4c22650979c'
CLOCK_SHA = '4054239941084707ede0e5d434bb39bb4b572b6eb80bfcee7a94c00b2b2af1d3'
COMMISSION_SHA = '3820434a4f8a4a455a98f1e6a3986726b9d0f06c65c8befde43b62516cf04ad3'
OLD = ROOT/'logs/diagnostics/atlas-v8-ntp-support-offline-proposal-20261108-r11'
DEST = ROOT/'logs/diagnostics/atlas-version-safe-ntp-support-source-20261109-r12-review'
APP_RECEIPT = ROOT/'logs/diagnostics'/('qd-unselected-release-'+NEW+'.json')
APPLICATION_PATH = Path('D:/AtlasRuntime/releases')/NEW
PINS = {'scripts/observation_runtime/atlas_independent_ntp_clock.py':SOURCE_SHA,
        'scripts/observation_runtime/personal_version_safe_release_clock.py':CLOCK_SHA,
        'scripts/observation_runtime/personal_activation_commission.py':COMMISSION_SHA}
SIX = ('personal_local_authority.py','personal_source_install_authority.py',
       'personal_installation_technical.py','personal_paper_activation.py',
       'personal_activation_publisher.py','personal_activation_commission.py')
NTP = {'issuer':'ATLAS_INDEPENDENT_DUAL_NTP_V1_GOOGLE_CLOUDFLARE',
       'maximum_evidence_age_seconds':120,'maximum_uncertainty_ms':1000}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def verify_predecessor_and_app():
    from scripts.release_selection import digest
    sel=Path('D:/AtlasRuntime/selection')
    history=json.loads((sel/'r0011.json').read_bytes())['record']
    if (history.get('revision')!=11 or digest(history)!=V7_HEAD
            or history['selected']['release']!=V7
            or os.path.lexists(sel/'r0012.json') or os.path.lexists(sel/'r0012.pending')):
        raise ValueError('VERSION_SAFE_SUPPORT_SELECTED_V7_PREDECESSOR_REQUIRED')
    raw=source_bytes(APP_RECEIPT.parent,APP_RECEIPT.name,maximum_bytes=8*1024**2)
    if sha(raw)!=RECEIPT_SHA:
        raise ValueError('VERSION_SAFE_SUPPORT_INSTALLED_RECEIPT_PIN_REQUIRED')
    receipt=json.loads(raw)
    if (receipt.get('source_commit')!=NEW or receipt.get('release_path')!=str(APPLICATION_PATH)
            or receipt.get('artifact_digest')!=ARTIFACT
            or any(receipt.get(key) is not False for key in
                   ('selected','financial_effects','provider_connections','operational_acceptance'))
            or len(receipt.get('files',[]))!=10574):
        raise ValueError('VERSION_SAFE_SUPPORT_NONFINANCIAL_APP_REQUIRED')
    actual={r['path'].replace('\\','/'):r['sha256'] for r in receipt['files']}
    if any(actual.get(path)!=pin for path,pin in PINS.items()):
        raise ValueError('VERSION_SAFE_SUPPORT_INSTALLED_NTP_SOURCES_REQUIRED')
    if any('scripts/observation_runtime/'+name not in actual for name in SIX):
        raise ValueError('VERSION_SAFE_SUPPORT_SIX_FINANCIAL_ADAPTERS_REQUIRED')
    return receipt,actual


def validate_new_profile(manifest, package, actual):
    """STRICT new NTP review; legacy operational Windows fallback is forbidden."""
    m=legacy.validate_manifest(manifest)
    if (m['schema']!='QD_SUPPORT_DEPLOYMENT_V2' or m['domain']!='WINDOWS_LOCAL'
            or m['status']!='REVIEW_INVENTORY_NOT_PERMISSION'
            or m['application']!={'release':NEW,'root':str(APPLICATION_PATH),
                 'receipt':str(APP_RECEIPT),'receipt_sha256':RECEIPT_SHA,
                 'artifact_digest':ARTIFACT}
            or m['runtime']['providers'] is not False
            or m['runtime']['financial_writers'] is not False
            or m['runtime']['workspace_fallback'] is not False):
        raise ValueError('VERSION_SAFE_SUPPORT_EXACT_APP_SCOPE_REQUIRED')
    if (type(package) is not dict or package.get('schema')!='QD_NONFINANCIAL_LAUNCHER_SUPPORT_V2'
            or package.get('application_release')!=NEW
            or package.get('clock')!=NTP
            or any(package.get(k) is not False for k in (
                'installation_authorized','promotion_authorized',
                'providers_authorized','financial_startup_authorized'))):
        raise ValueError('VERSION_SAFE_SUPPORT_EXACT_NTP_PACKAGE_REQUIRED')
    required={x['path']:x['sha256'] for x in package['required_installed_application_sources']}
    for name in SIX:
        path='scripts/observation_runtime/'+name
        if required.get(path)!=actual.get(path):
            raise ValueError('VERSION_SAFE_SUPPORT_FINANCIAL_INTERFACE_PIN_REQUIRED')
    if any(required.get(name)!=pin for name,pin in PINS.items()):
        raise ValueError('VERSION_SAFE_SUPPORT_CLOCK_PIN_REQUIRED')
    if legacy.support_clock_profile(m)!= 'WINDOWS_TIME_CODE_SELECTION_V1':
        raise ValueError('VERSION_SAFE_SUPPORT_HISTORIC_ADAPTER_CHANGED')
    return m


def build():
    if DEST.exists():
        raise ValueError('VERSION_SAFE_SUPPORT_CREATE_ONLY_CANDIDATE_EXISTS')
    receipt,actual=verify_predecessor_and_app()
    old=json.loads((OLD/'deployment.json').read_bytes())
    if old['application']['release']!=legacy.V8_NTP_APP or old['schema']!='QD_SUPPORT_DEPLOYMENT_V2':
        raise ValueError('VERSION_SAFE_SUPPORT_HISTORICAL_TEMPLATE_REQUIRED')
    with zipfile.ZipFile(OLD/'support-source.zip') as z:
        package=json.loads(z.read('support-manifest.json'))
    payload={name:source_bytes(ROOT,name,maximum_bytes=262144).replace(b'\r\n',b'\n')
             for name in sorted(legacy.SOURCES)}
    wanted={r['path'] for r in package['required_installed_application_sources']}
    wanted.update(PINS)
    wanted.update('scripts/observation_runtime/'+name for name in SIX)
    if not wanted.issubset(actual):
        raise ValueError('VERSION_SAFE_SUPPORT_MISSING_INSTALLED_APPLICATION_DEPENDENCY')
    package.update(application_release=NEW,
        application_archive_sha256=receipt['archive_sha256'],
        required_installed_application_sources=[{'path':p,'sha256':actual[p]} for p in sorted(wanted)],
        support_sources=[{'path':p,'bytes':len(v),'sha256':sha(v)} for p,v in sorted(payload.items())],
        missing_from_frozen_application=sorted(p for p,data in payload.items() if actual.get(p)!=sha(data)),
        clock=NTP)
    payload['support-manifest.json']=encoded(package)
    h=sha(payload['support-manifest.json'])
    m=copy.deepcopy(old)
    m.update(support_manifest_sha256=h,
        application={'release':NEW,'root':str(APPLICATION_PATH),
            'receipt':str(APP_RECEIPT),'receipt_sha256':RECEIPT_SHA,'artifact_digest':ARTIFACT},
        destination=str(Path('D:/AtlasRuntime/launchers')/h),
        control=str(Path('D:/AtlasRuntime/support-installations')/h),
        runtime={'python':str(APPLICATION_PATH/'python/python.exe'),
            'version':[3,12],'bits':64,'app_receipt_inventory':True,
            'providers':False,'financial_writers':False,'workspace_fallback':False},
        files=[{'path':p,'bytes':len(v),'sha256':sha(v)} for p,v in sorted(payload.items())],
        directories=sorted({'.'}|{x.as_posix() for p in payload for x in Path(p).parents}))
    validate_new_profile(m,package,actual)
    # Before writing anything, verify that the native support namespace is unused.
    if os.path.lexists(m['destination']) or os.path.lexists(m['control']):
        raise ValueError('VERSION_SAFE_SUPPORT_EXISTING_TARGET_NO_OVERWRITE')
    DEST.mkdir()
    archive=DEST/'support-source.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(payload.items()):
            item=zipfile.ZipInfo(name,date_time=(2026,11,9,0,0,0))
            item.compress_type=zipfile.ZIP_DEFLATED
            item.external_attr=0o100600 << 16
            z.writestr(item,data)
    m['archive_sha256']=sha(archive.read_bytes())
    validate_new_profile(m,package,actual)
    with (DEST/'deployment.json').open('xb') as out:out.write(encoded(m))
    with (DEST/'review.json').open('xb') as out:out.write(encoded({
        'schema':'ATLAS_VERSION_SAFE_NTP_SUPPORT_SOURCE_REVIEW_V1',
        'status':'SOURCE_REVIEW_NOT_PERMISSION',
        'new_app_receipt_sha256':RECEIPT_SHA,'app_artifact_digest':ARTIFACT,
        'manifest_sha256':sha(encoded(m)), 'support_manifest_sha256':h,
        'archive_sha256':m['archive_sha256'],
        'installed_app_requirements':len(package['required_installed_application_sources']),
        'native_install_authorized':False,'selection_authorized':False,
        'financial_authority':False,'legacy_windows_clock_profile_accepted':False,
        'real_ntp_required_for_future_support_install':True}))
    return m


def verify():
    receipt,actual=verify_predecessor_and_app()
    m=json.loads((DEST/'deployment.json').read_bytes())
    archive=DEST/'support-source.zip'
    if sha(archive.read_bytes())!=m['archive_sha256']:
        raise ValueError('VERSION_SAFE_SUPPORT_ARCHIVE_CHANGED')
    with zipfile.ZipFile(archive) as z:
        package=json.loads(z.read('support-manifest.json'))
    validate_new_profile(m,package,actual)
    checked,files=legacy.prepare(m,archive,sha(encoded(m)))
    if checked!=m or sha(files['support-manifest.json'])!=m['support_manifest_sha256']:
        raise ValueError('VERSION_SAFE_SUPPORT_ARCHIVE_ADAPTER_BINDING_CHANGED')
    review=json.loads((DEST/'review.json').read_bytes())
    if (review['manifest_sha256']!=sha(encoded(m))
            or review['archive_sha256']!=m['archive_sha256']
            or review['installed_app_requirements']!=len(package['required_installed_application_sources'])
            or any(review.get(key) is not False for key in (
                'native_install_authorized','selection_authorized','financial_authority',
                'legacy_windows_clock_profile_accepted'))):
        raise ValueError('VERSION_SAFE_SUPPORT_SOURCE_REVIEW_CHANGED')
    if os.path.lexists(m['destination']) or os.path.lexists(m['control']):
        raise ValueError('VERSION_SAFE_SUPPORT_TARGET_ALREADY_EXISTS')
    return {'status':'NONFINANCIAL_SUPPORT_SOURCE_ONLY_VERIFIED',
            'manifest_sha256':sha(encoded(m)),'support_manifest_sha256':m['support_manifest_sha256'],
            'archive_sha256':m['archive_sha256'],'required_installed_app_files':len(package['required_installed_application_sources']),
            'files':len(m['files']),'native_install':False,'selection':False,'financial':False}


if __name__=='__main__':
    print(json.dumps(verify() if DEST.exists() else (build() and verify()),sort_keys=True))
