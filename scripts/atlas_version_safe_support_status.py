"""Read-only independently verified installed support/ACK status. NO selector/order action.

Run from the installed 2d487987 Python interpreter using -I -B -S. This tool
never invokes installers or release-selection writers, and stores no secrets.
"""
import hashlib
import json
import sys
from pathlib import Path

APP=Path(r'D:\AtlasRuntime\releases\2d4879878bf58bea5a3ed0a986b809791f638fec')
REPO=Path(r'D:\Work\Project Atlas')
MANIFEST=REPO/'logs/diagnostics/atlas-version-safe-ntp-support-source-20261109-r12-review/deployment.json'
RECEIPT_SHA='2d2631152aea9086d95f2b60d06f1fde1c61ac61778d9ea36098d6883ce7eaac'
MANIFEST_SHA='d61fd6c9fa18bd819f3328040e6c40581efc8faeef8eca8e6326eb110b919ad8'
SUPPORT_SOURCE_SHA='808a7994ec644f596aa7214c281c557862d10b1ad571a6632d3c0c67d426ede8'
APP_RECEIPT_SHA='acdae2f01fb5defdf0e302240dc589eca0f1c99e3fcc15ec319d98260125cbb6'
V7_HEAD='933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997'


def checked(path,pin,limit):
    if not path.is_file() or path.is_symlink() or path.stat().st_size>limit:
        raise ValueError('VERSION_SAFE_SUPPORT_STATUS_REQUIRED_FILE_ABSENT')
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=pin:
        raise ValueError('VERSION_SAFE_SUPPORT_STATUS_PIN_MISMATCH')
    return data


def inspect():
    if (not sys.flags.isolated or not sys.flags.no_site or not sys.flags.dont_write_bytecode
            or Path(sys.executable)!=APP/'python/python.exe'):
        raise ValueError('VERSION_SAFE_SUPPORT_STATUS_INSTALLED_PYTHON_REQUIRED')
    m=json.loads(checked(MANIFEST,MANIFEST_SHA,65536))
    assert m['application']['release']==APP.name
    assert m['application']['root']==str(APP)
    assert m['application']['receipt_sha256']==APP_RECEIPT_SHA
    app_receipt=Path(m['application']['receipt'])
    checked(app_receipt,APP_RECEIPT_SHA,8*1024**2)
    dest=Path(m['destination']);control=Path(m['control'])
    if not dest.is_dir() or not control.is_dir():
        raise ValueError('VERSION_SAFE_SUPPORT_STATUS_NATIVE_INSTALL_ABSENT_OR_PARTIAL')
    support_source=dest/'scripts/support_deployment.py'
    checked(support_source,SUPPORT_SOURCE_SHA,262144)
    raw=checked(control/'receipt.json',RECEIPT_SHA,65536)
    receipt=json.loads(raw)
    if (receipt.get('schema')!='QD_SUPPORT_INSTALL_RECEIPT_V1'
            or receipt.get('deployment')!=m
            or receipt.get('financial_actions')!=0
            or receipt.get('selected') is not False):
        raise ValueError('VERSION_SAFE_SUPPORT_STATUS_FINANCIAL_OR_RECEIPT_REFUSED')
    for name in ('ack.json','intent.json'):
        if not (control/name).is_file():
            raise ValueError('VERSION_SAFE_SUPPORT_STATUS_NATIVE_ACK_OR_INTENT_REQUIRED')
    sys.path[:0]=[str(dest),str(APP/'backend'),str(APP),str(APP/'python/Lib/site-packages')]
    from scripts import support_deployment
    if Path(support_deployment.__file__).resolve()!=support_source:
        raise ValueError('VERSION_SAFE_SUPPORT_STATUS_VERIFIER_ORIGIN_REFUSED')
    evidence=support_deployment.verify_deployment(m,expected_receipt_sha256=RECEIPT_SHA)
    if evidence['selected'] is not False or evidence['financial_actions']!=0:
        raise ValueError('VERSION_SAFE_SUPPORT_STATUS_NONFINANCIAL_REQUIRED')
    from scripts.release_selection import digest
    sel=Path('D:/AtlasRuntime/selection')
    row=json.loads((sel/'r0011.json').read_bytes())['record']
    if (row.get('revision')!=11 or digest(row)!=V7_HEAD
            or row['selected']['release']!='af96bec0484a8e43f9965610e071a907a0d316bf'
            or (sel/'r0012.json').exists() or (sel/'r0012.pending').exists()):
        raise ValueError('VERSION_SAFE_SUPPORT_STATUS_V7_PREDECESSOR_REQUIRED')
    return {'schema':'ATLAS_VERSION_SAFE_NATIVE_SUPPORT_READONLY_STATUS_V1',
            'status':'INSTALLED_SUPPORT_RECEIPT_AND_ACK_VERIFIED_UNSELECTED',
            'release':APP.name,'receipt_sha256':RECEIPT_SHA,
            'support_files':len(m['files']),
            'support_directories':len(m['directories']),
            'native_ack_verified':True,
            'selected_release':row['selected']['release'],
            'r12_absent':True,'financial_authority':False,
            'paper_accounts':False,'provider_connections':False,'orders':False}


if __name__=='__main__':
    print(json.dumps(inspect(),sort_keys=True),flush=True)
