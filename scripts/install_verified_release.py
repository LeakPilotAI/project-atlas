"""One explicitly approved unselected D: code copy; never promotion or enrollment.

Source-only until separately authorized. No selector, launcher, provider,
financial root, account, service, credential or recovery mutation exists here.
The existing native copier and installed release verifier supply physical facts.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from scripts.native_install_candidate import _copy_prepared_code
from scripts.native_install_plan import prepare_install_inputs


def write_new_json(path, value):
    raw=json.dumps(value,sort_keys=True,allow_nan=False).encode()
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_BINARY',0)
    descriptor=os.open(path,flags,0o600)
    with os.fdopen(descriptor,'wb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())


def installation_target(source_commit, receipt_path):
    if type(source_commit) is not str or not re.fullmatch('[0-9a-f]{40}',source_commit):
        raise ValueError('EXACT_SOURCE_COMMIT_REQUIRED')
    destination=Path('D:/AtlasRuntime/releases')/source_commit
    audit=Path(receipt_path).absolute()
    expected=Path(__file__).resolve().parents[1]/'logs/diagnostics'/('qd-unselected-release-'+source_commit+'.json')
    if audit!=expected or not audit.parent.is_dir():raise ValueError('EXACT_PRIVATE_INSTALL_RECEIPT_REQUIRED')
    for path in (destination,audit,audit.with_suffix('.pending.jsonl')):
        if os.path.lexists(path):raise ValueError('INSTALLATION_ALREADY_EXISTS_PRESERVE_NO_RETRY')
        for parent in path.parents:
            if parent.exists() and (not parent.is_dir() or parent.is_symlink() or parent.is_junction()):
                raise ValueError('INSTALLATION_ANCESTOR_REFUSED')
    if not destination.parent.is_dir():raise ValueError('ACCEPTED_RELEASE_PARENT_REQUIRED')
    return destination,audit


def validate_installed_readback(result,destination,receipt,artifact_digest,identity):
    if type(result) is not dict or set(result)!={'layout','native_proof','handles_after_close'}:
        raise ValueError('INSTALLED_NATIVE_PROOF_INCOMPLETE')
    proof=result['native_proof'];layout=result['layout']
    if (type(proof) is not dict or set(proof)!={'source_commit','artifact_digest','process','files','directories'}
            or type(layout) is not dict or set(layout)!={'executable','base','prefix','base_prefix','stdlib','bits','version'}):
        raise ValueError('INSTALLED_NATIVE_PROOF_INCOMPLETE')
    process=proof['process']
    if (type(process) is not dict or set(process)!={'pid','creation_filetime','image'}
            or type(result['handles_after_close']) is not int or result['handles_after_close']!=0
            or proof['source_commit']!=receipt['source_commit'] or proof['artifact_digest']!=artifact_digest
            or type(proof['files']) is not int or proof['files']!=len(receipt['files'])
            or type(proof['directories']) is not int or proof['directories']!=len(receipt['directories'])
            or type(process['pid']) is not int or process['pid']!=identity['pid']
            or type(process['creation_filetime']) is not int or process['creation_filetime']!=identity['created']
            or type(process['image']) is not str or process['image'].casefold()!=identity['image']
            or type(layout['bits']) is not int or layout['bits']!=64 or layout['version']!=[3,12]):
        raise ValueError('INSTALLED_NATIVE_PROOF_INCOMPLETE')
    for name in ('executable','base','prefix','base_prefix','stdlib'):
        if type(layout[name]) is not str or not Path(layout[name]).is_absolute() or not Path(layout[name]).is_relative_to(destination):
            raise ValueError('INSTALLED_LAYOUT_FOREIGN_PATH')
    if (Path(layout['executable'])!=destination/'python/python.exe' or Path(layout['base'])!=destination/'python/python.exe'
            or Path(layout['prefix'])!=destination/'python' or Path(layout['base_prefix'])!=destination/'python'
            or Path(layout['stdlib'])!=destination/'python/Lib'):
        raise ValueError('INSTALLED_LAYOUT_FOREIGN_PATH')
    return result


def installed_readback(destination, receipt, artifact_digest, *, timeout):
    """Exact retained child; installed verifier, not a workspace verification callback."""
    from scripts.observation_runtime.disposable_host_owner import (
        observe_handle,
        observe_pid,
    )

    code=r'''
import json,sys,struct,sysconfig
from pathlib import Path
request=json.loads(sys.stdin.read());root=Path(request['receipt']['release_path'])
sys.dont_write_bytecode=True;sys.path[:0]=[str(root/'backend'),str(root)]
layout=dict(executable=sys.executable,base=getattr(sys,'_base_executable',None),prefix=sys.prefix,
 base_prefix=sys.base_prefix,stdlib=sysconfig.get_path('stdlib'),bits=struct.calcsize('P')*8,version=list(sys.version_info[:2]))
if layout['version']!=[3,12] or layout['bits']!=64:raise ValueError('INSTALLED_LAYOUT_VERSION')
if any(not isinstance(layout[k],str) or not Path(layout[k]).resolve().is_relative_to(root) for k in ('executable','base','prefix','base_prefix','stdlib')):raise ValueError('INSTALLED_LAYOUT_FOREIGN_PATH')
if any(not Path(p).resolve().is_relative_to(root) for p in sys.path if p):raise ValueError('INSTALLED_EXTERNAL_IMPORT_PATH')
from scripts.observation_runtime.personal_release_identity import NativePersonalReleaseIdentity
owner=NativePersonalReleaseIdentity(receipt=request['receipt'],artifact_digest=request['digest'])
try:proof=owner.verify(release_digest=request['digest'])
finally:owner.close()
print(json.dumps({'layout':layout,'native_proof':proof,'handles_after_close':len(owner.handles)+len(owner.outputs)}))
'''
    env=dict(os.environ)
    for name in ('PYTHONPATH','PYTHONHOME'):env.pop(name,None)
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1')
    executable=destination/'python/python.exe'
    with subprocess.Popen([str(executable),'-I','-B','-c',code],cwd=destination,env=env,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW) as child:
        identity=observe_pid(child.pid)
        if identity['created']!=observe_handle(int(child._handle)) or identity['image']!=str(executable).casefold():
            child.stdin.close();child.wait(timeout=12);child._handle.Close()
            raise ValueError('INSTALLED_CHILD_OWNERSHIP_REFUSED')
        try:stdout,stderr=child.communicate(json.dumps({'receipt':receipt,'digest':artifact_digest}).encode(),timeout=timeout)
        except subprocess.TimeoutExpired:
            child.kill();child.communicate(timeout=5);child._handle.Close()
            raise ValueError('EXACT_OWNED_INSTALL_READBACK_TIMEOUT') from None
        if child.returncode or len(stdout)>65536:
            child._handle.Close()
            raise ValueError('INSTALLED_RUNTIME_READBACK_REFUSED:'+stderr.decode(errors='replace')[:250])
    child._handle.Close()
    result=json.loads(stdout.decode('utf-8-sig'))
    return validate_installed_readback(result,destination,receipt,artifact_digest,identity)


def install_unselected_release(*, approved_execution=False, archive=None, archive_sha256=None,
        source_commit=None, inventory_digest=None, dependency_receipt=None, dependency_digest=None,
        receipt_path=None, clock=None):
    if approved_execution is not True:raise ValueError('SEPARATE_CODE_INSTALL_AUTHORIZATION_REQUIRED')
    # This invocation flag is not financial/session authority. Never default a
    # clock or manufacture an issuer; the operator supplies a live native clock.
    from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock

    if type(clock) is not LocalWindowsClock:raise ValueError('GENUINE_INSTALL_CLOCK_REQUIRED')
    prepared=prepare_install_inputs(archive=archive,archive_sha256=archive_sha256,source_commit=source_commit,
        inventory_digest=inventory_digest,dependency_receipt=dependency_receipt,dependency_digest=dependency_digest,
        require_tracked=True)
    if inventory_digest is None:raise ValueError('EXACT_SELECTED_SOURCE_INVENTORY_REQUIRED')
    destination,audit=installation_target(source_commit,receipt_path)
    runtime='qd-unselected-code-install-'+source_commit

    def admission():
        clock.require_operational(runtime)
        if time.monotonic()-prepared['started']>600:raise ValueError('INSTALLATION_DEADLINE')
        return True

    admission()
    intent={'schema':'ATLAS_UNSELECTED_CODE_INSTALL_INTENT_V1','source_commit':source_commit,
        'archive_sha256':archive_sha256,'inventory_sha256':inventory_digest,'dependency_sha256':dependency_digest,
        'destination':str(destination),'selection_allowed':False,'financial_authority':False}
    journal=audit.with_suffix('.pending.jsonl')
    write_new_json(journal,intent)

    def record(value):
        raw=b'\n'+json.dumps(value,sort_keys=True,allow_nan=False).encode()
        with journal.open('ab') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())

    try:
        copied=_copy_prepared_code(destination=destination,archive_sha256=archive_sha256,source_commit=source_commit,
            prepared=prepared,observer=record,admission=admission)
        admission()
        receipt={'schema':'ATLAS_QD_D_RUNTIME_INSTALLATION_V1','stage':'D_RUNTIME_LAYOUT_VERIFIED',
            'release_path':str(destination),'source_commit':source_commit,'files':copied['files'],
            'directories':copied['directories'],'archive_sha256':archive_sha256,'inventory_sha256':inventory_digest,
            'selected':False,'financial_effects':False,'provider_connections':False,'operational_acceptance':False}
        pin=hashlib.sha256(json.dumps(receipt['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        result=installed_readback(destination,receipt,pin,timeout=min(180,max(1,600-(time.monotonic()-prepared['started'])-5)))
        admission();receipt.update(layout=result['layout'],artifact_digest=pin)
        write_new_json(audit,receipt)
        record({'stage':'UNSELECTED_CODE_INSTALL_VERIFIED','receipt_sha256':hashlib.sha256(audit.read_bytes()).hexdigest()})
        return receipt
    except (ValueError,OSError,RuntimeError,KeyError,TypeError):
        record({'stage':'FAILED_PRESERVE_PARTIAL_NO_RETRY_OR_SELECTION'})
        raise


def validate_proposal(proposal):
    fields={'schema','status','source_commit','archive','archive_sha256','inventory_sha256','dependency_receipt',
        'dependency_sha256','destination','receipt_path','selected','adapter_source_sha256','limits',
        'financial_enrollment','provider_activation','paper_startup','promotion'}
    if (type(proposal) is not dict or set(proposal)!=fields
            or proposal['schema']!='QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V1'
            or proposal['status']!='PROPOSAL_NOT_PERMISSION'
            or any(proposal[k] is not False for k in ('selected','financial_enrollment','provider_activation','paper_startup','promotion'))
            or type(proposal['source_commit']) is not str or not re.fullmatch('[0-9a-f]{40}',proposal['source_commit'])
            or any(type(proposal[k]) is not str for k in ('archive','destination','receipt_path','dependency_receipt'))
            or proposal['limits']!={'seconds':600,'entries':40000,'bytes':1024**3}):
        raise ValueError('UNSELECTED_CODE_SCOPE_REQUIRED')
    if Path(proposal['destination'])!=Path('D:/AtlasRuntime/releases')/proposal['source_commit']:
        raise ValueError('EXACT_INSTALL_DESTINATION_REQUIRED')
    repo=Path(__file__).resolve().parents[1]
    if (not Path(proposal['archive']).is_absolute() or Path(proposal['archive']).drive.upper()!='D:'
            or not Path(proposal['archive']).is_relative_to(repo/'logs/diagnostics')):
        raise ValueError('EXACT_LOCAL_SOURCE_ARCHIVE_REQUIRED')
    if Path(proposal['dependency_receipt'])!=repo/'logs/diagnostics/qd-d-runtime-coordination-installation-20261028.json':
        raise ValueError('EXACT_DEPENDENCY_RECEIPT_REQUIRED')
    for name in ('archive_sha256','inventory_sha256','dependency_sha256'):
        if type(proposal[name]) is not str or not re.fullmatch('[0-9a-f]{64}',proposal[name]):
            raise ValueError('EXACT_INSTALL_PIN_REQUIRED')
    return proposal


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if '--execute-approved-unselected' not in argv:
        raise SystemExit('REFUSED: source-only adapter; separately reviewed exact installation invocation required.')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-approved-unselected',action='store_true')
    parser.add_argument('--proposal',required=True)
    parser.add_argument('--proposal-sha256',required=True,help='Approved canonical UTF8/LF proposal hash')
    args=parser.parse_args(argv)
    from scripts.build_release_candidate import source_bytes
    from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock

    repo=Path(__file__).resolve().parents[1]
    expected=repo/'docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V1_2026-10-30.json'
    if Path(args.proposal).absolute()!=expected:raise ValueError('EXACT_INSTALL_PROPOSAL_REQUIRED')
    raw=source_bytes(repo,str(expected.relative_to(repo)).replace('\\','/'),maximum_bytes=65536)
    if hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()!=args.proposal_sha256:
        raise ValueError('APPROVED_INSTALL_PROPOSAL_HASH_MISMATCH')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('DUPLICATE_INSTALL_PROPOSAL_FIELD')
            result[key]=value
        return result
    proposal=validate_proposal(json.loads(raw,object_pairs_hook=unique))
    if set(proposal['adapter_source_sha256'])!={'scripts/install_verified_release.py','scripts/native_install_candidate.py','scripts/native_install_plan.py'}:
        raise ValueError('EXACT_INSTALL_ADAPTER_SOURCE_SET_REQUIRED')
    for name,pin in proposal['adapter_source_sha256'].items():
        actual=source_bytes(repo,name,maximum_bytes=65536).replace(b'\r\n',b'\n')
        if hashlib.sha256(actual).hexdigest()!=pin:raise ValueError('INSTALL_ADAPTER_SOURCE_CHANGED')
    clock=LocalWindowsClock(expected_source='time.windows.com,0x9',
        runtime_id='qd-unselected-code-install-'+proposal['source_commit'])
    try:
        dependency=json.loads(source_bytes(repo,str(Path(proposal['dependency_receipt']).relative_to(repo)).replace('\\','/'),
            maximum_bytes=16*1024**2),object_pairs_hook=unique)
        return install_unselected_release(approved_execution=True,archive=proposal['archive'],
            archive_sha256=proposal['archive_sha256'],source_commit=proposal['source_commit'],
            inventory_digest=proposal['inventory_sha256'],dependency_receipt=dependency,
            dependency_digest=proposal['dependency_sha256'],receipt_path=proposal['receipt_path'],clock=clock)
    finally:clock.revoke()


if __name__=='__main__':main()
