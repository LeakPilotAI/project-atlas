"""Native Windows/NTFS tests in disposable synthetic directories only."""
import ctypes as C
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes as W
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Native Windows required')
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('native_output',ROOT/'scripts/volume_inspector/windows_output.py')
m = importlib.util.module_from_spec(SPEC)
if os.name == 'nt': SPEC.loader.exec_module(m)


def value(size=54):
    return {'schema': 1,'service': 'postgres','status': 'METADATA_COMPLETE_COVERAGE_UNPROVEN','files': 1,'directories': 0,'logical_file_bytes': size,'effective_configuration': 'NOT_ESTABLISHED','payloads_read': False}


def set_acl(path, sddl, flags=0x80000004):
    sd = C.c_void_p()
    m.check(m.sddl_sd(sddl,1,C.byref(sd),None))
    fn = m.bind(m.A,'SetFileSecurityW',[W.LPCWSTR,W.DWORD,C.c_void_p])
    try: m.check(fn(str(path),flags,sd))
    finally: m.local_free(sd)


def test_native_acl_publish_integrity_restart(tmp_path):
    path=str(tmp_path/'private')
    with m.WindowsOutput.create_root(path) as out:
        m.validate_acl(out.root_handle,out.sid)
        digest=out.publish('test.json',value())
        assert out.read('test.json')==value()
        assert hashlib.sha256((Path(path)/'test.json.pending/metadata.json').read_bytes()).hexdigest()==digest
        assert {p.name for p in Path(path).iterdir()}=={'test.json.pending','test.json.commit'}
    with m.WindowsOutput(path) as restarted: assert restarted.read('test.json')==value()


def test_native_inherited_acl_rejected(tmp_path):
    path=tmp_path/'inherited';path.mkdir()
    with pytest.raises(PermissionError):m.WindowsOutput(str(path))


def test_native_broad_protected_acl_rejected(tmp_path):
    path=tmp_path/'broad'
    with m.WindowsOutput.create_root(str(path)):pass
    sid=m.current_sid();set_acl(path,f'O:{sid}D:P(A;OICI;FA;;;{sid})(A;OICI;FA;;;SY)(A;OICI;FA;;;WD)')
    with pytest.raises(PermissionError):m.WindowsOutput(str(path))


def test_native_acl_drift_rejected(tmp_path):
    path=tmp_path/'drift'
    with m.WindowsOutput.create_root(str(path)) as out:
        sid=m.current_sid();set_acl(path,f'O:{sid}D:P(A;OICI;FA;;;{sid})(A;OICI;FA;;;SY)(A;OICI;FR;;;WD)')
        with pytest.raises(PermissionError):out.publish('test.json',value())
        assert not (path/'test.json.pending').exists()


def test_native_denied_restricted_token(tmp_path):
    path=tmp_path/'deny'
    with m.WindowsOutput.create_root(str(path)) as out:
        out.publish('test.json',value())
        normal, restricted = W.HANDLE(), W.HANDLE()
        everyone=C.c_void_p()
        convert=m.bind(m.A,'ConvertStringSidToSidW',[W.LPCWSTR,C.POINTER(C.c_void_p)])
        restrict=m.bind(m.A,'CreateRestrictedToken',[W.HANDLE,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,C.c_void_p,W.DWORD,C.POINTER(m.SidAttr),C.POINTER(W.HANDLE)])
        impersonate=m.bind(m.A,'ImpersonateLoggedOnUser',[W.HANDLE]);revert=m.bind(m.A,'RevertToSelf',[])
        m.check(m.open_token(m.process(),0xE,C.byref(normal)));m.check(convert('S-1-1-0',C.byref(everyone)))
        try:
            sa=m.SidAttr(everyone,0)
            m.check(restrict(normal,1,0,None,0,None,1,C.byref(sa),C.byref(restricted)))
            m.check(impersonate(restricted))
            try:
                h=m.create_file(str(path/'test.json.pending/metadata.json'),m.WRITE,1,None,3,0x00200000,None)
                error=C.get_last_error()
                if h!=m.INVALID:m.close_handle(h)
                assert h==m.INVALID and error==5
            finally:m.check(revert())
        finally:
            if restricted:m.close_handle(restricted)
            m.close_handle(normal);m.local_free(everyone)
        assert out.read('test.json')==value()


@pytest.mark.parametrize('position',['root','ancestor'])
def test_native_junction_escape_rejected(tmp_path,position):
    outside=tmp_path/'outside';outside.mkdir()
    with m.WindowsOutput.create_root(str(outside/'private')):pass
    link=tmp_path/'junction'
    p=subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(link),str(outside)],capture_output=True,check=False,timeout=10)
    assert p.returncode==0,p.stderr
    target=link if position=='root' else link/'private'
    with pytest.raises(PermissionError):m.WindowsOutput(str(target))
    with pytest.raises(PermissionError):m.WindowsOutput.create_root(str(link/'new'))
    assert not (outside/'new').exists()


def test_native_held_root_cannot_be_replaced(tmp_path):
    path=tmp_path/'pinned'
    with m.WindowsOutput.create_root(str(path)) as out:
        with pytest.raises(OSError):os.rename(path,tmp_path/'moved')
        out.publish('test.json',value())
        assert out.read('test.json')==value()


def test_native_concurrent_publication(tmp_path):
    path=tmp_path/'concurrent'
    with m.WindowsOutput.create_root(str(path)):pass
    barrier=threading.Barrier(2)
    def publish(_):
        with m.WindowsOutput(str(path)) as out:
            barrier.wait(timeout=5)
            try:out.publish('same.json',value());return True
            except OSError:return False
    with ThreadPoolExecutor(2) as pool:assert sum(pool.map(publish,range(2)))==1
    with m.WindowsOutput(str(path)) as out:assert out.read('same.json')==value()


def test_native_collision_retains_original(tmp_path):
    with m.WindowsOutput.create_root(str(tmp_path/'collision')) as out:
        original=out.publish('same.json',value())
        with pytest.raises(OSError):out.publish('same.json',value(99))
        assert out.read('same.json')==value()
        assert (Path(out.root)/'same.json.pending').is_dir()
        assert hashlib.sha256((Path(out.root)/'same.json.pending/metadata.json').read_bytes()).hexdigest()==original


@pytest.mark.parametrize('partial',[False,True])
def test_native_process_interruption_retains_unpublished(tmp_path,partial):
    path=tmp_path/'interrupted'
    with m.WindowsOutput.create_root(str(path)):pass
    code='''import importlib.util,sys,os,json
s=importlib.util.spec_from_file_location('w',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
o=m.WindowsOutput(sys.argv[2]);original=o._write
partial=sys.argv[3]=='True'
def interrupt(directory,name,data):
 original(directory,name,data[:10] if partial else data);os._exit(23)
o._write=interrupt;o.publish('crash.json',json.loads(sys.argv[4]))
'''
    p=subprocess.run([sys.executable,'-I','-B','-c',code,str(ROOT/'scripts/volume_inspector/windows_output.py'),str(path),str(partial),json.dumps(value())],capture_output=True,check=False,timeout=10)
    assert p.returncode==23,p.stderr
    assert (path/'crash.json.pending/metadata.json').is_file()
    assert not (path/'crash.json.commit').exists()
    if partial:assert (path/'crash.json.pending/metadata.json').stat().st_size==10
    with m.WindowsOutput(str(path)) as out:
        with pytest.raises(OSError):out.read('crash.json')
        with pytest.raises(OSError):out.publish('crash.json',value())


def test_native_atomic_visibility(tmp_path):
    path=tmp_path/'atomic';ready=threading.Event();release=threading.Event()
    with m.WindowsOutput.create_root(str(path)):pass
    def writer():
        with m.WindowsOutput(str(path)) as out:
            original=out._write
            def pause(directory,name,data):
                original(directory,name,data)
                if name=='commit.json':ready.set();assert release.wait(5)
            out._write=pause
            out.publish('test.json',value())
    with ThreadPoolExecutor(1) as pool:
        task=pool.submit(writer)
        assert ready.wait(5)
        with m.WindowsOutput(str(path)) as reader:
            assert not (path/'test.json.commit').exists()
            with pytest.raises(OSError):reader.read('test.json')
            release.set();task.result(timeout=5)
            assert reader.read('test.json')==value()


def test_native_tamper_integrity_refused(tmp_path):
    path=tmp_path/'tamper'
    with m.WindowsOutput.create_root(str(path)) as out:
        out.publish('test.json',value())
        (path/'test.json.pending/metadata.json').write_bytes(b'{}')
        with pytest.raises(ValueError):out.read('test.json')


def test_native_file_acl_failure_refused(tmp_path):
    path=tmp_path/'file-acl'
    with m.WindowsOutput.create_root(str(path)) as out:
        out.publish('test.json',value())
        sid=m.current_sid();set_acl(path/'test.json.pending/metadata.json',f'O:{sid}D:P(A;;FA;;;{sid})(A;;FA;;;SY)(A;;FR;;;WD)')
        with pytest.raises(PermissionError):out.read('test.json')


@pytest.mark.parametrize('bad',['../secret.json','private:name.json','secret.json/child','CAPS.json'])
def test_native_invalid_publication_names(tmp_path,bad):
    with m.WindowsOutput.create_root(str(tmp_path/'names')) as out:
        with pytest.raises(ValueError):out.publish(bad,value())
        assert list(Path(out.root).iterdir())==[]


@pytest.mark.parametrize('bad',[{'password':'SECRET'}, {'schema':1}, {'status':'INCOMPLETE'}])
def test_native_forbidden_output_never_written(tmp_path,bad):
    with m.WindowsOutput.create_root(str(tmp_path/'redaction')) as out:
        with pytest.raises(ValueError):out.publish('test.json',bad)
        assert list(Path(out.root).iterdir())==[]


def test_native_root_creation_no_overwrite(tmp_path):
    path=tmp_path/'already'
    with m.WindowsOutput.create_root(str(path)):pass
    with pytest.raises(OSError):m.WindowsOutput.create_root(str(path))

def test_native_actual_write_permission_denial(tmp_path):
    path=tmp_path/'permission'
    with m.WindowsOutput.create_root(str(path)):pass
    sid=m.current_sid();set_acl(path,f'O:{sid}D:P(A;OICI;FA;;;SY)')
    with pytest.raises(OSError):m.WindowsOutput(str(path))


def test_native_root_closed_refuses_publication(tmp_path):
    out=m.WindowsOutput.create_root(str(tmp_path/'closed'));out.close()
    with pytest.raises(PermissionError):out.publish('test.json',value())


def test_native_missing_root_not_created(tmp_path):
    path=tmp_path/'missing'
    with pytest.raises(OSError):m.WindowsOutput(str(path))
    assert not path.exists()


def test_native_adapter_mock_transport_real_publication(tmp_path):
    loader=importlib.util.spec_from_file_location('adapter_fixture',ROOT/'tests/test_r7e47b_isolated_adapter.py')
    fixture=importlib.util.module_from_spec(loader);loader.loader.exec_module(fixture)
    test=fixture.setup(tmp_path)
    with m.WindowsOutput.create_root(str(tmp_path/'adapter-output')) as out:
        test[0].output=out
        expected=json.loads(test[4]['output'])
        assert fixture.run(test)==expected
        assert out.read('test-operation.json')==expected
        assert test[0].fence.read()['state']=='COMPLETE'


@pytest.mark.parametrize('extra',[{'password':'SECRET'}, {'schema':1}])
def test_native_reader_revalidates_metadata_after_trusted_owner_tamper(tmp_path,extra):
    path=tmp_path/'reader'
    with m.WindowsOutput.create_root(str(path)) as out:
        out.publish('test.json',value())
        stage=path/'test.json.pending'
        data=json.dumps(extra).encode();digest=hashlib.sha256(data).hexdigest()
        audit=json.dumps({'schema':1,'event':'METADATA_STAGED','bytes':len(data),'sha256':digest}).encode()
        (stage/'metadata.json').write_bytes(data);(stage/'audit.json').write_bytes(audit)
        # Both aliases refer to the same actual native commit file.
        (stage/'commit.json').write_bytes(json.dumps({'schema':1,'metadata_sha256':digest,'audit_sha256':hashlib.sha256(audit).hexdigest()}).encode())
        with pytest.raises(ValueError):out.read('test.json')

def test_native_symbolic_link_escape_refused(tmp_path):
    target=tmp_path/'target'
    with m.WindowsOutput.create_root(str(target)):pass
    link=tmp_path/'symbolic'
    create=m.bind(m.K,'CreateSymbolicLinkW',[W.LPCWSTR,W.LPCWSTR,W.DWORD],C.c_ubyte)
    if not create(str(link),str(target),3):
        error=C.get_last_error()
        if error==1314:pytest.skip('Native symlink creation privilege unavailable; junction acceptance does not waive this case')
        m.check(False)
    with pytest.raises(PermissionError):m.WindowsOutput(str(link))

def test_native_output_uses_pinned_handles_not_mutable_path(tmp_path):
    original=tmp_path/'original';outside=tmp_path/'outside';outside.mkdir()
    with m.WindowsOutput.create_root(str(original)) as out:
        out.root=str(outside)  # Later string/path changes cannot redirect native I/O.
        out.publish('test.json',value())
        assert out.read('test.json')==value()
        assert list(outside.iterdir())==[]
        assert (original/'test.json.commit').is_file()


def test_native_stage_junction_rejected_on_read(tmp_path):
    path=tmp_path/'stage-junction';outside=tmp_path/'untrusted';outside.mkdir()
    (outside/'metadata.json').write_bytes(b'SYNTHETIC_NOT_METADATA')
    with m.WindowsOutput.create_root(str(path)) as out:
        out.publish('test.json',value())
        os.rename(path/'test.json.pending',path/'retained-original')
        p=subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(path/'test.json.pending'),str(outside)],capture_output=True,check=False,timeout=10)
        assert p.returncode==0,p.stderr
        with pytest.raises(OSError):out.read('test.json')
        assert (outside/'metadata.json').read_bytes()==b'SYNTHETIC_NOT_METADATA'


def test_native_independent_integrity_commitment(tmp_path):
    with m.WindowsOutput.create_root(str(tmp_path/'commitment')) as out:
        digest=out.publish('test.json',value())
        assert out.read('test.json',expected_digest=digest)==value()
        with pytest.raises(ValueError):out.read('test.json',expected_digest='0'*64)
