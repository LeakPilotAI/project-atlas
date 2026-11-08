"""Source-only closure: ordinary disposable files and explicit native I/O doubles."""
import ctypes as C
import hashlib
import io
import json
import os
import time
import zipfile
from ctypes import wintypes
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import install_verified_release as adapter
from scripts import native_copy_test_scope as scope
from scripts import native_install_adapter_acceptance as acceptance
from scripts import native_install_candidate as copier


@pytest.fixture(autouse=True)
def close_exact_owned_negative_probe_aliases(tmp_path):
    yield
    # Only aliases created by this file in this test's fresh owned tmp_path.
    # Preserve original-session failures and source contents; no tree deletion.
    for relative in ('account/pytest/arbitrary_fixture_index77/outside-source.py','external-alias','foreign-to-account'):
        path=tmp_path/relative
        if os.path.lexists(path):
            if path.is_symlink() or path.is_junction():raise ValueError('UNEXPECTED_TEST_REPARSE')
            path.unlink()


@pytest.mark.parametrize('raw',[b'',b'ValueError: EXPECTED',b'header\n'+b'x'*10000+b'\nValueError: PERSONAL_RELEASE_PATH_OR_ARTIFACT',b'\xff'*6000+b'\nValueError: END'],ids=['empty','short','long-tail','invalid-utf8'])
def test_bounded_diagnostic_preserves_terminal_reason_and_raw_integrity(raw):
    row=adapter.bounded_child_diagnostic(raw)
    assert row['bytes']==len(raw) and row['sha256']==hashlib.sha256(raw).hexdigest()
    assert len(row['head'])<=2048 and len(row['tail'])<=2048
    assert (row['tail'] or row['head']).endswith(raw.decode(errors='replace')[-30:])
    assert row['truncated']==(len(raw.decode(errors='replace'))>4096)


@pytest.mark.parametrize('code,out',[(1,b''),(0,b'x'*65537)],ids=['failed-child','oversized-output'])
def test_actual_readback_error_branch_retains_reason_with_mocked_process(tmp_path,monkeypatch,code,out):
    from scripts.observation_runtime import disposable_host_owner as owners
    closed=[];root=tmp_path/'synthetic-image';raw=b'Traceback\n'+b'x'*2000+b'\nValueError: PERSONAL_RELEASE_PATH_OR_ARTIFACT'
    class Handle:
        def __int__(self):return 100
        def Close(self):closed.append(True)
    child=SimpleNamespace(pid=123,_handle=Handle(),returncode=code,communicate=lambda *a,**k:(out,raw))
    class Context:
        def __enter__(self):return child
        def __exit__(self,*a):pass
    monkeypatch.setattr(adapter.subprocess,'Popen',lambda *a,**k:Context())
    monkeypatch.setattr(owners,'observe_pid',lambda *a:{'pid':123,'created':99,'image':str(root/'python/python.exe').casefold()})
    monkeypatch.setattr(owners,'observe_handle',lambda *a:99)
    with pytest.raises(adapter.InstalledReadbackRefusal,match='PERSONAL_RELEASE_PATH_OR_ARTIFACT') as error:
        adapter.installed_readback(root,{},'a'*64,timeout=1)
    assert error.value.diagnostic['stdout_bytes']==len(out) and closed==[True]


@pytest.mark.skipif('ATLAS_RETAINED_CODE_FIXTURE' not in os.environ,reason='Explicit retained disposable interpreter fixture required')
def test_genuine_retained_disposable_interpreter_refuses_fixture_receipt_read_only():
    root=Path(os.environ['ATLAS_RETAINED_CODE_FIXTURE'])
    expected=Path(__file__).resolve().parents[1]/'logs/diagnostics/qd-native-install-adapter-v1/candidate'
    assert root==expected
    # Keep the original disposable schema. Do not relabel it operational merely
    # to exercise the diagnostic path. Schema refusal occurs before native roots.
    receipt=json.loads((root.parent/'installation-receipt.json').read_bytes())
    assert receipt['schema']=='ATLAS_DISPOSABLE_NATIVE_INSTALLATION_V1'
    pin=hashlib.sha256(json.dumps(receipt['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    with pytest.raises(adapter.InstalledReadbackRefusal,match='PERSONAL_RELEASE_VERIFIED_INVENTORY_REQUIRED') as error:
        adapter.installed_readback(root,receipt,pin,timeout=30)
    assert error.value.diagnostic['returncode']!=0


def probe(tmp_path):
    root=tmp_path/'account';fixture=root/'pytest/arbitrary_fixture_index77'
    fixture.mkdir(parents=True);(root/'probe-registry').mkdir()
    scope.declare_probe(root,fixture)
    source=fixture/'source/backend/app/example.py';source.parent.mkdir(parents=True)
    source.write_bytes(b'SYNTHETIC')
    alias=fixture/'outside-source.py';os.link(source,alias)
    return root,fixture,source,alias


def test_dynamic_declared_aliases_are_counted_without_relaxing_candidate_reader(tmp_path):
    from scripts.build_release_candidate import source_bytes
    root,fixture,source,alias=probe(tmp_path);counts=scope.account(root)
    assert counts['declared_materialized_groups']==1
    paths=[root,*root.rglob('*')]
    assert counts['entries']==len(paths)
    assert counts['logical_bytes']==sum(p.stat().st_size for p in paths if p.is_file())
    assert counts['allocation_upper_bound_bytes']==counts['logical_bytes']+counts['entries']*4096
    with pytest.raises(ValueError,match='Unsafe source identity'):
        source_bytes(fixture/'source','backend/app/example.py')
    assert source.stat().st_ino==alias.stat().st_ino


@pytest.mark.parametrize('fault',['unregistered','external','different-identities','parent','owner','candidate-path','duplicate-key','late-registration'])
def test_probe_declarations_do_not_hide_genuine_scope_failures(tmp_path,fault):
    root,fixture,source,alias=probe(tmp_path);record=next((root/'probe-registry').glob('*.json'))
    if fault=='unregistered':record.unlink()
    elif fault=='external':os.link(source,tmp_path/'external-alias')
    elif fault=='different-identities':
        alias.unlink();alias.write_bytes(b'OTHER');os.link(alias,tmp_path/'foreign-to-account')
    elif fault=='late-registration':
        with pytest.raises(ValueError,match='BEFORE_CREATION'):scope.declare_probe(root,fixture)
        return
    elif fault=='duplicate-key':record.write_bytes(b'{"schema":1,"schema":2}')
    else:
        row=json.loads(record.read_bytes())
        if fault=='parent':row['parent_identity'][1]+=1
        elif fault=='owner':row['owner']='UNKNOWN'
        elif fault=='candidate-path':row['paths'][0]='candidate/backend/app/example.py'
        record.write_text(json.dumps(row))
    with pytest.raises(ValueError):scope.account(root)


@pytest.mark.parametrize('name',['candidate','interrupted','report','source'])
def test_no_probe_declaration_can_admit_links_in_non_test_namespace(tmp_path,name):
    (tmp_path/name).mkdir();(tmp_path/'probe-registry').mkdir()
    with pytest.raises(ValueError,match='EXACT_NEGATIVE'):scope.declare_probe(tmp_path,tmp_path/name)


def test_cache_and_temporary_environment_is_confined(tmp_path):
    env=scope.confined_environment(tmp_path,{'PYTEST_ADDOPTS':'--cache-clear','PYTHONHOME':'FOREIGN'})
    assert env['RUFF_NO_CACHE']==env['PYTHONDONTWRITEBYTECODE']=='1'
    assert 'PYTEST_ADDOPTS' not in env and 'PYTHONHOME' not in env
    for key in ('TEMP','TMP','PYTHONPYCACHEPREFIX','RUFF_CACHE_DIR','XDG_CACHE_HOME'):
        assert Path(env[key]).is_relative_to(tmp_path)


def test_accounting_failure_never_hides_primary_error(tmp_path,monkeypatch):
    def refuse(*a,**k):raise ValueError('SYNTHETIC_ACCOUNTING_FAILURE')
    monkeypatch.setattr(scope,'account',refuse)
    original={'status':'PASS','primary_error':'ORIGINAL_COPY_REFUSAL'}
    row=scope.preserve_terminal_accounting(original,tmp_path,0,now=1,limit=5)
    assert row['primary_error']=='ORIGINAL_COPY_REFUSAL' and row['status']=='REFUSED_PRESERVE_PARTIAL'
    assert 'SYNTHETIC_ACCOUNTING_FAILURE' in row['accounting_error'] and original['status']=='PASS'


def test_consumed_authorization_cannot_run_any_native_child(tmp_path,monkeypatch):
    monkeypatch.setattr(acceptance,'ROOT',tmp_path)
    (tmp_path/'final-scope-accounting.json').write_bytes(b'CONSUMED')
    monkeypatch.setattr(acceptance,'worker',lambda *a:pytest.fail('No native worker'))
    with pytest.raises(ValueError,match='AUTHORIZATION_CONSUMED'):
        acceptance.main(['--grant',acceptance.GRANT,'--worker-start','123'])


@pytest.mark.parametrize('fault',[None,'input-hash','readback','interrupted','close'])
def test_shared_copy_algorithm_with_explicit_fake_windows_ports(tmp_path,monkeypatch,fault):
    from scripts.volume_inspector import windows_output as w
    handles={};counter=iter(range(1,1000));snapshots=[];closes=[]
    def allocate(path,directory,stream=None):
        h=next(counter);handles[h]=(path,directory,stream);return h
    class Output:
        sid='SYNTHETIC_NOT_WINDOWS_ACL_EVIDENCE'
        def __init__(self,path):
            self.path=Path(path);self.root_handle=allocate(self.path,True);self.handles=[self.root_handle]
        def _verify(self):assert self.handles
        @classmethod
        def create(cls,path):Path(path).mkdir();return cls(path)
    def info(h):
        p,_directory,stream=handles[h]
        if stream:stream.flush()
        st=p.stat();return SimpleNamespace(volume=1,index_hi=st.st_ino>>32,index_lo=st.st_ino&0xffffffff,
            links=st.st_nlink,size_hi=st.st_size>>32,size_lo=st.st_size&0xffffffff)
    def relative(h,name,sid,directory,*,create=False,access=None):
        p=handles[h][0]/name;return allocate(p,directory,p.open('xb+' if create else 'rb'))
    def close(h):
        _,_,stream=handles.pop(h)
        if stream:stream.close()
        closes.append(h);return fault!='close'
    def write(h,raw,length,count,*a):
        n=handles[h][2].write(raw[:length]);C.cast(count,C.POINTER(wintypes.DWORD))[0]=n;return True
    def read(h,buf,length,count,*a):
        data=handles[h][2].read(length)
        if data and fault=='readback':data=b'X'+data[1:]
        C.memmove(buf,data,len(data));C.cast(count,C.POINTER(wintypes.DWORD))[0]=len(data);return True
    monkeypatch.setattr(w.WindowsOutput,'create_root',Output.create)
    monkeypatch.setattr(w,'info',info);monkeypatch.setattr(w,'relative_open',relative)
    monkeypatch.setattr(w,'close_handle',close);monkeypatch.setattr(w,'validate_acl',lambda *a:None)
    monkeypatch.setattr(w,'write_file',write);monkeypatch.setattr(w,'read_file',read)
    monkeypatch.setattr(w,'flush',lambda h:handles[h][2].flush() or True)
    data={'data/a.txt':b'ALPHA','data/b.txt':b'BETA'};raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w') as z:
        for n,b in data.items():z.writestr(n,b)
    rows={n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in data.items()}
    if fault=='input-hash':rows['data/a.txt']['sha256']='0'*64
    prepared={'source':tmp_path,'dependencies':{},'runtime':rows,'names':sorted(rows),'directories':['data'],
        'old_dirs':{},'verified':{'synthetic':True},'raw':raw.getvalue(),'started':time.monotonic()}
    call=lambda:copier._copy_prepared_code(destination=tmp_path/'copy',archive_sha256='a'*64,
        source_commit='b'*40,prepared=prepared,observer=snapshots.append,interrupt_after=1 if fault=='interrupted' else None)
    if fault:
        with pytest.raises((ValueError,OSError)):call()
        assert snapshots[-1]['status']=='REFUSED_PRESERVE_PARTIAL'
    else:
        result=call();assert result['charged_bytes']==9 and result['retained_handles_after_close']==0
        assert all((tmp_path/'copy'/n).read_bytes()==b for n,b in data.items())
    assert not handles and closes
    if fault=='close':assert snapshots[-1]['retained_handles_after_close']>0


def test_durable_receipt_and_ack_preserve_bytes_and_reject_duplicate(tmp_path,monkeypatch):
    monkeypatch.setattr(acceptance,'ROOT',tmp_path)
    receipt={'schema':'SYNTHETIC_CODE_ONLY','files':[],'selected':False}
    pin=acceptance.save('receipt.json',receipt)
    acceptance.save('ack.json',{'receipt_sha256':pin,'financial_authority':False})
    assert hashlib.sha256((tmp_path/'receipt.json').read_bytes()).hexdigest()==json.loads((tmp_path/'ack.json').read_bytes())['receipt_sha256']
    with pytest.raises(FileExistsError):acceptance.save('receipt.json',{'overwrite':True})
    assert json.loads((tmp_path/'receipt.json').read_bytes())==receipt
