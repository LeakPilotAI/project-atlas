"""Disposable offline closure only. No native copy, account or provider entry."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'backend'),str(REPO),str(REPO/'tests')]

from scripts.native_copy_test_scope import (
    account,
    confined_environment,
    inside,
    install_write_audit,
)


def snapshot(paths):
    result={}
    for root in paths:
        if not root.exists():continue
        for path in root.rglob('*'):
            if path.is_symlink() or path.is_junction():raise ValueError('SNAPSHOT_REPARSE')
            if path.is_file():
                st=path.stat();result[str(path)]={'bytes':st.st_size,'mtime':st.st_mtime_ns,
                    'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    return result


def candidate_metadata(root):
    rows={}
    for parent,dirs,files in os.walk(root,followlinks=False):
        for name in dirs+files:
            path=Path(parent)/name;st=path.lstat()
            if getattr(st,'st_file_attributes',0)&0x400:raise ValueError('RETAINED_CANDIDATE_REPARSE')
            rows[path.relative_to(root).as_posix()]=[name in dirs,st.st_ino,st.st_size,st.st_mtime_ns,st.st_nlink]
    return rows


def child(root):
    import pytest
    audit=install_write_audit(root)
    denied=root.parent/('qd-closure-forbidden-write-'+root.name)
    assert not os.path.lexists(denied)
    try:denied.write_bytes(b'MUST_NOT_EXIST')
    except PermissionError:pass
    else:raise AssertionError('Scope guard did not refuse outside write')
    assert not os.path.lexists(denied)
    names=['test_native_install_plan','test_unselected_release_adapter','test_native_install_candidate',
        'test_candidate_verifier','test_candidate_selected_inventory','test_candidate_source_identity',
        'test_candidate_windows_namespace','test_personal_release_module_binding','test_nonfinancial_resource_host',
        'test_windows_clock_probe_boundary','test_native_install_adapter_acceptance','test_native_copy_closure']
    result=pytest.main(['-q','-p','no:cacheprovider','-p','pytest_asyncio.plugin','-p','native_copy_scope_plugin',
        '--basetemp',str(root/'pytest'),*[str(REPO/'tests'/(n+'.py')) for n in names]])
    summary=dict(audit,expected_denial_only=len(audit['denied'])==1 and not os.path.lexists(denied),
        outside_control_created=False,financial_actions=0,provider_connections=0,full_native_copy_executed=False)
    with (root/'python-write-audit.json').open('x') as stream:json.dump(summary,stream,indent=2)
    if not summary['expected_denial_only']:raise ValueError('UNEXPECTED_PYTHON_WRITE_DENIAL')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-offline-fixtures',action='store_true')
    parser.add_argument('--audited-child')
    args=parser.parse_args()
    if args.audited_child:
        root=Path(args.audited_child).absolute()
        if root.parent!=REPO/'logs/diagnostics' or not root.name.startswith('qd-native-copy-closure-v1-') or root!=Path.cwd():
            raise ValueError('EXACT_OFFLINE_FIXTURE_REQUIRED')
        inside(root,root)
        return child(root)
    if not args.execute_offline_fixtures:raise SystemExit('Explicit offline test invocation required')
    started=time.monotonic()
    root=REPO/'logs/diagnostics'/('qd-native-copy-closure-v1-'+uuid.uuid4().hex[:12])
    inside(root,root)
    if os.path.lexists(root):raise ValueError('NO_FIXTURE_ADOPTION')
    # Snapshot only repository cache files and old native-test evidence; no
    # financial journal, account, credential or Genesis path is enumerated.
    caches=[REPO/'.ruff_cache',REPO/'.pytest_cache']
    before=snapshot(caches)
    old_root=REPO/'logs/diagnostics/qd-native-install-adapter-v1'
    preserved={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in old_root.iterdir() if p.is_file()}
    retained_metadata=candidate_metadata(old_root/'candidate')
    root.mkdir();(root/'probe-registry').mkdir()
    with (root/'retained-candidate-before.json').open('x') as stream:json.dump(retained_metadata,stream)
    env=confined_environment(root)
    env.update(ATLAS_NEGATIVE_PROBE_ROOT=str(root),ATLAS_RETAINED_CODE_FIXTURE=str(old_root/'candidate'),GIT_CONFIG_NOSYSTEM='1',
        GIT_CONFIG_GLOBAL=str(root/'unused-git-config'),PYTHONPATH='')
    output=subprocess.run([sys.executable,'-I','-B',str(Path(__file__).resolve()),'--audited-child',str(root)],
        cwd=root,env=env,capture_output=True,timeout=150,check=False,creationflags=subprocess.CREATE_NO_WINDOW)
    (root/'regressions.txt').write_bytes(output.stdout+output.stderr)
    files=['scripts/install_verified_release.py','scripts/native_install_adapter_acceptance.py',
        'scripts/native_copy_test_scope.py','tests/native_copy_scope_plugin.py','tests/test_native_copy_closure.py',
        'tests/test_native_install_adapter_acceptance.py','tests/test_unselected_release_adapter.py','tests/run_native_copy_closure.py']
    lint=subprocess.run([str(REPO/'backend/.venv/Scripts/ruff.exe'),'check','--no-cache',
        '--config','lint.isort.known-third-party=["pytest"]',
        '--config','lint.isort.known-first-party=["app","scripts"]',*[str(REPO/p) for p in files]],
        cwd=root,env=env,capture_output=True,timeout=30,check=False,creationflags=subprocess.CREATE_NO_WINDOW)
    (root/'lint.txt').write_bytes(lint.stdout+lint.stderr)
    assert snapshot(caches)==before,'Existing repository cache was modified'
    assert {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in old_root.iterdir() if p.is_file()}==preserved
    after_metadata=candidate_metadata(old_root/'candidate')
    with (root/'retained-candidate-after.json').open('x') as stream:json.dump(after_metadata,stream)
    differences=[{'path':name,'before':retained_metadata.get(name),'after':after_metadata.get(name)}
        for name in sorted(retained_metadata.keys()|after_metadata.keys()) if retained_metadata.get(name)!=after_metadata.get(name)]
    with (root/'retained-candidate-differences.json').open('x') as stream:json.dump(differences,stream,indent=2)
    assert not differences,'Retained metadata changed; exact differences preserved'
    audit=json.loads((root/'python-write-audit.json').read_bytes())
    counts=account(root)
    summary={'status':'PASS' if output.returncode==lint.returncode==0 else 'FAIL_PRESERVED',
        'scope':'OFFLINE_FIXTURES_ONLY_NO_FULL_NATIVE_COPY','seconds':round(time.monotonic()-started,3),
        'tests_summary':re.findall(r'\d+ passed[^\r\n]*',output.stdout.decode(errors='replace'))[-1:],
        'pytest_exit':output.returncode,'lint_exit':lint.returncode,'resource_before_result':counts,
        'existing_cache_snapshot_unchanged':True,'old_native_evidence_unchanged':True,'retained_candidate_metadata_unchanged':True,
        'expected_write_denials':len(audit['denied']),'full_native_copy_executed':False,
        'financial_actions':0,'provider_connections':0,'ports_opened':0,'children_exited':True}
    final=dict(counts,entries=counts['entries']+1,files=counts['files']+1)
    summary['resource_final']=final
    # Include the result file itself, without an uncounted trailing audit file.
    for _ in range(10):
        raw=json.dumps(summary,indent=2).encode()
        size=counts['logical_bytes']+len(raw)
        if final['logical_bytes']==size:break
        final.update(logical_bytes=size,allocation_upper_bound_bytes=size+final['entries']*4096)
    else:raise ValueError('FINAL_ACCOUNTING_DID_NOT_CONVERGE')
    if time.monotonic()-started>=300 or final['entries']>=8192 or final['allocation_upper_bound_bytes']>=128*1024**2:
        raise ValueError('OFFLINE_CLOSURE_RESOURCE_LIMIT')
    with (root/'result.json').open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    assert account(root)==final,'Exact final filesystem accounting mismatch'
    print(json.dumps({'root':str(root),**summary},indent=2))
    return output.returncode or lint.returncode


if __name__=='__main__':raise SystemExit(main())
