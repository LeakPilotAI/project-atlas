"""Native synthetic Windows registry tests. No Docker or production databases."""
import ctypes as C
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes as W
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Native Windows required')
loader = importlib.util.spec_from_file_location('shared_fence', ROOT/'scripts/volume_inspector/shared_fence.py')
m = importlib.util.module_from_spec(loader)
if os.name == 'nt': loader.loader.exec_module(m)


def ident(pid=1100, created=900):
    return {'pid':pid,'created':created,'exe':'a'*64,'command':'b'*64}


def provision(tmp_path,mode='PERSIST'):
    return m.Registry.provision(str(tmp_path/'registry'),mode=mode)


def inspection(reg,op='inspection-one'):
    return reg.begin_inspection(op,{'observed':1000,'stopped':True,'no_pending':True},1000,approved=True)


def test_native_provision_and_restart(tmp_path):
    reg=provision(tmp_path);instance=reg.instance;root=reg.output.root
    assert reg.startup_allowed();assert reg.snapshot()['revision']==0
    assert reg.surface()['fence.sqlite3']=={'aces':2,'inherited':False,'restricted':True}
    reg.close()
    reopened=m.Registry(root,instance)
    try: assert reopened.startup_allowed()
    finally: reopened.close()
    with pytest.raises(OSError):m.Registry.provision(root)


@pytest.mark.parametrize('mode',['PERSIST','WAL'])
def test_native_complete_sidecar_surface(tmp_path,mode):
    reg=provision(tmp_path,mode)
    try:
        with reg.guard(),reg.database() as db:
            assert db.execute('PRAGMA synchronous').fetchone()==(2,)
            assert db.execute('PRAGMA temp_store').fetchone()==(2,)
            db.execute('BEGIN IMMEDIATE');db.execute('UPDATE state SET value=value')
            surface=reg.surface()
            suffixes=['-journal'] if mode=='PERSIST' else ['-wal','-shm']
            for suffix in suffixes:
                assert surface['fence.sqlite3'+suffix]['restricted']
                assert surface['fence.sqlite3'+suffix]['inherited']
            (tmp_path/'surface-evidence.json').write_text(json.dumps(surface,indent=2))
            db.rollback()
    finally:reg.close()


def test_native_concurrent_wal_connections(tmp_path):
    reg=provision(tmp_path,'WAL')
    try:
        with reg.guard(),reg.database() as first,reg.database() as second:
            first.execute('BEGIN IMMEDIATE');first.execute('UPDATE state SET value=value')
            assert second.execute('SELECT COUNT(*) FROM state').fetchone()==(1,)
            with pytest.raises(sqlite3.OperationalError):second.execute('BEGIN IMMEDIATE')
            assert set(reg.surface())>= {'fence.sqlite3','fence.sqlite3-wal','fence.sqlite3-shm'}
            first.rollback()
    finally:reg.close()


def test_native_startup_handoff(tmp_path):
    reg=provision(tmp_path)
    try:
        pending=reg.reserve_start('startup-one',ident(),1000)['startup'];assert not reg.startup_allowed()
        worker=ident(1200,1001)
        reg.bind_worker('startup-one',pending['nonce'],ident(),worker,1001)
        assert reg.admit_worker('startup-one',pending['nonce'],worker,1002)['startup']['phase']=='STARTING'
        with pytest.raises(m.Refused):reg.admit_worker('startup-one',pending['nonce'],worker,1003)
        with pytest.raises(m.Refused):inspection(reg)
    finally:reg.close()


@pytest.mark.parametrize('case',['pid','created','exe','command','nonce','operation','old-worker','delay','parent'])
def test_native_reject_replaced_or_stale_handoff(tmp_path,case):
    reg=provision(tmp_path)
    try:
        pending=reg.reserve_start('startup-one',ident(),1000)['startup'];worker=ident(1200,1001)
        reg.bind_worker('startup-one',pending['nonce'],ident(),worker,1001)
        changed=dict(worker);nonce=pending['nonce'];op='startup-one';now=1002
        if case=='pid':changed['pid']=1201
        elif case=='created':changed['created']=1002
        elif case=='exe':changed['exe']='c'*64
        elif case=='command':changed['command']='c'*64
        elif case=='nonce':nonce='c'*64
        elif case=='operation':op='startup-other'
        elif case=='old-worker':changed['created']=999
        elif case=='delay':now=1031
        elif case=='parent':
            with pytest.raises(m.Refused):reg.bind_worker('startup-one',nonce,ident(999),worker,1002)
        if case!='parent':
            with pytest.raises(m.Refused):reg.admit_worker(op,nonce,changed,now)
        assert not reg.startup_allowed()
    finally:reg.close()


def test_native_startup_inspection_race(tmp_path):
    reg=provision(tmp_path);barrier=threading.Barrier(2)
    def start():
        barrier.wait(5)
        try:reg.reserve_start('startup-race',ident(),1000);return True
        except m.Refused:return False
    def inspect():
        barrier.wait(5)
        try:inspection(reg);return True
        except m.Refused:return False
    try:
        with ThreadPoolExecutor(2) as pool:results=[pool.submit(start),pool.submit(inspect)];assert sum(f.result(timeout=5) for f in results)==1
        assert not reg.startup_allowed()
    finally:reg.close()


def test_native_recovery_authority(tmp_path):
    reg=provision(tmp_path);auth=m.FixtureRecoveryAuthority()
    try:
        inspection(reg);reg.bind_helper('inspection-one','a'*64)
        proof={'id':'a'*64,'operation':'inspection-one','state':'exited','pid':0,'observed':1000}
        state=reg.snapshot();grant=auth.issue(state,proof,approved=True)
        reg.recover_inspection(auth,grant,proof,1001)
        assert reg.startup_allowed()
        with pytest.raises(m.Refused):reg.recover_inspection(auth,grant,proof,1001)
        with pytest.raises(sqlite3.IntegrityError):inspection(reg)
        with reg.guard(),reg.database() as db:
            audit=json.loads(db.execute('SELECT value FROM audit ORDER BY revision DESC LIMIT 1').fetchone()[0])
            assert audit['event']['type']=='INSPECTION_FAILED_EXIT_PROVEN'
    finally:reg.close()


@pytest.mark.parametrize('case',['no-approval','forged','foreign-key','stale','future','replacement','running','pid-bool','no-identity','changed-revision'])
def test_native_recovery_never_assumes_exit(tmp_path,case):
    reg=provision(tmp_path);auth=m.FixtureRecoveryAuthority()
    try:
        inspection(reg)
        if case!='no-identity':reg.bind_helper('inspection-one','a'*64)
        proof={'id':'a'*64,'operation':'inspection-one','state':'exited','pid':0,'observed':1000}
        if case=='stale':proof['observed']=990
        elif case=='future':proof['observed']=1002
        elif case=='replacement':proof['id']='b'*64
        elif case=='running':proof['state']='running'
        elif case=='pid-bool':proof['pid']=False
        if case=='no-approval':
            with pytest.raises(m.Refused):auth.issue(reg.snapshot(),proof)
        else:
            grant=auth.issue(reg.snapshot(),proof,approved=True)
            if case=='forged':grant['mac']='0'*64
            if case=='foreign-key':auth=m.FixtureRecoveryAuthority()
            if case=='changed-revision':
                # Revision-bound grant cannot be replayed into another state.
                grant['payload']['revision']-=1
            with pytest.raises(m.Refused):reg.recover_inspection(auth,grant,proof,1001)
        assert not reg.startup_allowed()
    finally:reg.close()


def test_native_missing_partial_corrupt_storage(tmp_path):
    with pytest.raises(OSError):m.Registry(str(tmp_path/'missing'),'00000000-0000-0000-0000-000000000000')
    partial=tmp_path/'partial'
    with m.w.WindowsOutput.create_root(str(partial)):pass
    with pytest.raises(OSError):m.Registry(str(partial),'00000000-0000-0000-0000-000000000000')
    reg=provision(tmp_path);root=reg.output.root;instance=reg.instance
    reg.close();(Path(root)/'fence.sqlite3').write_bytes(b'SYNTHETIC_CORRUPTION')
    with pytest.raises(sqlite3.DatabaseError):m.Registry(root,instance)


def test_native_receipt_gap_preserves_failure(tmp_path):
    reg=provision(tmp_path);original=reg.output._write
    def fail(directory,name,data):
        if name=='revision-00000001.json':raise OSError('Synthetic receipt storage failure')
        return original(directory,name,data)
    try:
        reg.output._write=fail
        with pytest.raises(OSError):reg.reserve_start('receipt-start',ident(),1000)
        assert not reg.startup_allowed()
        assert (Path(reg.output.root)/'revision-00000000.json').is_file()
        assert not (Path(reg.output.root)/'revision-00000001.json').exists()
    finally:reg.close()


def test_native_database_rollback_detected(tmp_path):
    reg=provision(tmp_path)
    try:
        main=Path(reg.output.root)/'fence.sqlite3';initial=main.read_bytes()
        reg.reserve_start('rollback-start',ident(),1000)
        main.write_bytes(initial) # Synthetic rollback injection; no real backup/restore.
        assert not reg.startup_allowed()
    finally:reg.close()


def test_native_partial_state_json_rejected(tmp_path):
    reg=provision(tmp_path)
    try:
        with reg.guard(),reg.database() as db:db.execute("UPDATE state SET value='{' WHERE id=1");db.commit()
        assert not reg.startup_allowed()
    finally:reg.close()

def set_acl(path,sddl):
    sd=C.c_void_p();m.w.check(m.w.sddl_sd(sddl,1,C.byref(sd),None))
    f=m.w.bind(m.w.A,'SetFileSecurityW',[W.LPCWSTR,W.DWORD,C.c_void_p])
    try:m.w.check(f(str(path),0x80000004,sd))
    finally:m.w.local_free(sd)


@pytest.mark.parametrize('mode',['PERSIST','WAL'])
def test_native_restricted_token_denies_main_and_all_sidecars(tmp_path,mode):
    reg=provision(tmp_path,mode)
    normal,restricted=W.HANDLE(),W.HANDLE();everyone=C.c_void_p()
    convert=m.w.bind(m.w.A,'ConvertStringSidToSidW',[W.LPCWSTR,C.POINTER(C.c_void_p)])
    restrict=m.w.bind(m.w.A,'CreateRestrictedToken',[W.HANDLE,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,C.c_void_p,W.DWORD,C.POINTER(m.w.SidAttr),C.POINTER(W.HANDLE)])
    impersonate=m.w.bind(m.w.A,'ImpersonateLoggedOnUser',[W.HANDLE]);revert=m.w.bind(m.w.A,'RevertToSelf',[])
    try:
        with reg.guard(),reg.database() as db:
            db.execute('BEGIN IMMEDIATE');db.execute('UPDATE state SET value=value');surface=reg.surface()
            m.w.check(m.w.open_token(m.w.process(),0xE,C.byref(normal)));m.w.check(convert('S-1-1-0',C.byref(everyone)))
            entry=m.w.SidAttr(everyone,0);m.w.check(restrict(normal,1,0,None,0,None,1,C.byref(entry),C.byref(restricted)))
            m.w.check(impersonate(restricted))
            try:
                for file in surface:
                    for access in (m.w.READ, m.w.WRITE):
                        h=m.w.create_file(str(Path(reg.output.root)/file),access,7,None,3,0x00200000,None);error=C.get_last_error()
                        if h!=m.w.INVALID:m.w.close_handle(h)
                        assert h==m.w.INVALID and error==5
                open_mutex=m.w.bind(m.w.K,'OpenMutexW',[W.DWORD,W.BOOL,W.LPCWSTR],W.HANDLE)
                h=open_mutex(0x100001,False,reg.mutex_name);error=C.get_last_error()
                if h:m.w.close_handle(h)
                assert not h and error==5
            finally:m.w.check(revert())
            db.rollback()
    finally:
        if restricted:m.w.close_handle(restricted)
        if normal:m.w.close_handle(normal)
        if everyone:m.w.local_free(everyone)
        reg.close()


@pytest.mark.parametrize('target',['root','main','journal','wal','shm'])
def test_native_acl_bypass_rejected(tmp_path,target):
    reg=provision(tmp_path,'WAL' if target in {'wal','shm'} else 'PERSIST')
    sid=m.w.current_sid()
    try:
        with pytest.raises(PermissionError),reg.guard(),reg.database() as db:
            db.execute('BEGIN IMMEDIATE');db.execute('UPDATE state SET value=value')
            file={'root':'','main':'fence.sqlite3','journal':'fence.sqlite3-journal','wal':'fence.sqlite3-wal','shm':'fence.sqlite3-shm'}[target]
            set_acl(Path(reg.output.root)/file,f'O:{sid}D:P(A;OICI;FA;;;{sid})(A;OICI;FA;;;SY)(A;OICI;FA;;;WD)')
            reg.surface()
        assert not reg.startup_allowed()
    finally:reg.close()


def test_native_bound_storage_and_sidecar_junction(tmp_path):
    reg=provision(tmp_path);outside=tmp_path/'outside';outside.mkdir();(outside/'sentinel').write_bytes(b'SYNTHETIC')
    try:
        journal=Path(reg.output.root)/'fence.sqlite3-journal'
        os.rename(journal,journal.with_name('retained-journal'))
        p=subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(journal),str(outside)],capture_output=True,check=False,timeout=10)
        assert p.returncode==0,p.stderr
        assert not reg.startup_allowed()
        assert (outside/'sentinel').read_bytes()==b'SYNTHETIC'
    finally:reg.close()


def test_native_database_file_replacement(tmp_path):
    reg=provision(tmp_path)
    try:
        main=Path(reg.output.root)/'fence.sqlite3';data=main.read_bytes();os.rename(main,main.with_name('retained-db'));main.write_bytes(data)
        assert not reg.startup_allowed()
    finally:reg.close()


def test_native_fixed_instance_rejects_substitution(tmp_path):
    reg=provision(tmp_path);root=reg.output.root;expected=reg.instance;reg.close()
    os.rename(root,str(tmp_path/'retained-registry'))
    other=m.Registry.provision(root);other.close()
    with pytest.raises(m.Refused):m.Registry(root,expected)


def test_native_bounded_coordination_and_no_raw_connection(tmp_path):
    reg=provision(tmp_path)
    try:
        with pytest.raises(m.Refused), reg.database():pass
        with ThreadPoolExecutor(1) as pool,reg.guard():
            def wait():
                with pytest.raises(m.Refused):reg.snapshot()
            pool.submit(wait).result(timeout=3)
    finally:reg.close()


CHILD='''import importlib.util,sys,os,time
s=importlib.util.spec_from_file_location('f',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
r=m.Registry(sys.argv[2],sys.argv[3])
if sys.argv[4]=='parent':
 owner=m.current_process_identity();assert owner['pid']==os.getpid();r.reserve_start('crashed-parent',owner,time.time());r.output._write(r.output.root_handle,'owned-child.json',m.encoded(owner));os._exit(23)
if sys.argv[4]=='transaction':
 with r.guard(),r.database() as db:
  db.execute('PRAGMA cache_size=1');db.execute('BEGIN IMMEDIATE');db.execute('UPDATE state SET value=?',('SYNTHETIC_UNCOMMITTED'*3000,));os._exit(24)
if sys.argv[4]=='start':
 try:r.reserve_start('race-'+str(os.getpid()),m.current_process_identity(),time.time());r.close();sys.exit(0)
 except m.Refused:r.close();sys.exit(17)
'''


def child_args(reg,action):
    return [sys.executable,'-I','-B','-c',CHILD,str(ROOT/'scripts/volume_inspector/shared_fence.py'),reg.output.root,reg.instance,action]


def test_native_parent_process_crash_retains_durable_intent(tmp_path):
    reg=provision(tmp_path)
    try:
        p=subprocess.Popen(child_args(reg,'parent'),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        _,err=p.communicate(timeout=10);assert p.returncode==23,err
        state=reg.snapshot();proof=reg._read_json('owned-child.json');assert state['startup']['parent']==proof;assert proof['pid']!=os.getpid();assert not reg.startup_allowed()
        with pytest.raises(m.Refused):inspection(reg)
    finally:reg.close()


@pytest.mark.parametrize('mode',['PERSIST','WAL'])
def test_native_interrupted_transaction_recovery_remains_fenced(tmp_path,mode):
    reg=provision(tmp_path,mode)
    try:
        p=subprocess.run(child_args(reg,'transaction'),capture_output=True,check=False,timeout=10);assert p.returncode==24,p.stderr
        # Keep parent mutex handle alive so Windows reports actual abandonment.
        with pytest.raises(m.Refused):reg.snapshot()
        assert (Path(reg.output.root)/'recovery-required.json').is_file()
        assert not reg.startup_allowed()
        # Independent fixture-only SQLite recovery check, NOT fence authorization.
        db=sqlite3.connect((Path(reg.output.root)/'fence.sqlite3').as_uri()+'?mode=rw',uri=True)
        try:assert json.loads(db.execute('SELECT value FROM state').fetchone()[0])['revision']==0
        finally:db.close()
        assert not reg.startup_allowed()
    finally:reg.close()


def test_native_cross_process_startup_race(tmp_path):
    reg=provision(tmp_path)
    try:
        children=[subprocess.Popen(child_args(reg,'start'),stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
        for p in children:
            _,err=p.communicate(timeout=10);assert p.returncode in (0,17),err
        assert sorted(p.returncode for p in children)==[0,17]
        assert not reg.startup_allowed()
    finally:reg.close()


def test_native_exclusive_cross_process_initialization(tmp_path):
    root=str(tmp_path/'initialize')
    code='''import importlib.util,sys
s=importlib.util.spec_from_file_location('f',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
try:
 r=m.Registry.provision(sys.argv[2]);print(r.instance);r.close()
except FileExistsError:sys.exit(17)
'''
    args=[sys.executable,'-I','-B','-c',code,str(ROOT/'scripts/volume_inspector/shared_fence.py'),root]
    children=[subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)];results=[]
    for p in children:
        out,err=p.communicate(timeout=10);assert p.returncode in (0,17),err;results.append((p.returncode,out))
    assert sorted(p[0] for p in results)==[0,17]
    instance=next(out.decode().strip() for code,out in results if code==0)
    reg=m.Registry(root,instance)
    try:assert reg.startup_allowed()
    finally:reg.close()

def test_native_sidecar_violation_latch_survives_sqlite_cleanup_and_restart(tmp_path):
    reg=provision(tmp_path,'WAL');root=reg.output.root;instance=reg.instance;sid=m.w.current_sid()
    try:
        with pytest.raises(PermissionError),reg.guard(),reg.database() as db:
            db.execute('BEGIN IMMEDIATE');db.execute('UPDATE state SET value=value')
            set_acl(Path(root)/'fence.sqlite3-wal',f'O:{sid}D:P(A;OICI;FA;;;{sid})(A;OICI;FA;;;SY)(A;OICI;FA;;;WD)')
            reg.surface()
        assert (Path(root)/'recovery-required.json').is_file()
        assert not reg.startup_allowed()
    finally:reg.close()
    with pytest.raises(m.Refused):m.Registry(root,instance)


def test_native_reject_precreated_broad_mutex(tmp_path):
    reg=provision(tmp_path);root=reg.output.root;instance=reg.instance;name=reg.mutex_name;reg.close()
    sd=C.c_void_p();sid=m.w.current_sid();m.w.check(m.w.sddl_sd(f'O:{sid}D:P(A;;GA;;;{sid})(A;;GA;;;SY)(A;;GA;;;WD)',1,C.byref(sd),None))
    create=m.w.bind(m.w.K,'CreateMutexW',[C.POINTER(m.w.SA),W.BOOL,W.LPCWSTR],W.HANDLE)
    handle=create(C.byref(m.w.SA(C.sizeof(m.w.SA),sd,False)),False,name);m.w.check(handle)
    try:
        with pytest.raises(PermissionError):m.Registry(root,instance)
    finally:m.w.close_handle(handle);m.w.local_free(sd)


@pytest.mark.parametrize('case',['inspection-phase','startup-phase','schema-bool','audit-tail'])
def test_native_unknown_state_never_admits_startup(tmp_path,case):
    reg=provision(tmp_path)
    try:
        if case=='inspection-phase':inspection(reg)
        if case=='startup-phase':reg.reserve_start('malformed-start',ident(),1000)
        with reg.guard(),reg.database() as db:
            state=json.loads(db.execute('SELECT value FROM state').fetchone()[0])
            if case=='inspection-phase':state['inspection']['phase']='UNKNOWN'
            if case=='startup-phase':state['startup']['phase']='UNKNOWN'
            if case=='schema-bool':state['schema']=True
            if case=='audit-tail':db.execute('DELETE FROM audit')
            else:db.execute('UPDATE state SET value=?',(json.dumps(state),))
            db.commit()
        assert not reg.startup_allowed()
        assert (Path(reg.output.root)/'recovery-required.json').is_file()
    finally:reg.close()


@pytest.mark.parametrize('case',['parent-future','worker-before-intent','worker-rebind','replayed-operation'])
def test_native_additional_handoff_rejections(tmp_path,case):
    reg=provision(tmp_path)
    try:
        if case=='parent-future':
            with pytest.raises(m.Refused):reg.reserve_start('future-parent',ident(created=2000),1000)
        else:
            pending=reg.reserve_start('startup-one',ident(),1000)['startup']
            if case=='worker-before-intent':
                with pytest.raises(m.Refused):reg.bind_worker('startup-one',pending['nonce'],ident(),ident(1200,999),1001)
            elif case=='worker-rebind':
                reg.bind_worker('startup-one',pending['nonce'],ident(),ident(1200,1001),1001)
                with pytest.raises(m.Refused):reg.bind_worker('startup-one',pending['nonce'],ident(),ident(1201,1001),1001)
            else:
                with pytest.raises(m.Refused):reg.reserve_start('startup-one',ident(),1001)
            assert not reg.startup_allowed()
    finally:reg.close()


def test_native_sql_profile_uses_memory_temps_and_rejects_attach(tmp_path):
    reg=provision(tmp_path)
    try:
        with reg.guard(),reg.database() as db:
            assert db.getlimit(sqlite3.SQLITE_LIMIT_ATTACHED)==0
            assert db.execute('PRAGMA temp_store').fetchone()==(2,)
            with pytest.raises(sqlite3.DatabaseError):db.execute("ATTACH ':memory:' AS extra")
    finally:reg.close()

@pytest.mark.parametrize('sql',["PRAGMA journal_mode=OFF","PRAGMA synchronous=OFF","PRAGMA temp_store=FILE","CREATE TEMP TABLE unsafe(x)"])
def test_native_sql_profile_rejects_policy_drift(tmp_path,sql):
    reg=provision(tmp_path)
    try:
        with reg.guard(),reg.database() as db:
            with pytest.raises(sqlite3.DatabaseError):db.execute(sql)
            assert db.execute('PRAGMA synchronous').fetchone()==(2,)
            assert db.execute('PRAGMA temp_store').fetchone()==(2,)
    finally:reg.close()

def test_native_self_identity_uses_actual_process_image():
    import hashlib
    import time
    record=m.current_process_identity()
    image=C.create_unicode_buffer(32768)
    length=m.w.bind(m.w.K,'GetModuleFileNameW',[W.HMODULE,W.LPWSTR,W.DWORD],W.DWORD)(None,image,len(image));assert length>0
    assert record['pid']==os.getpid() and 0<record['created']<=time.time()
    assert record['exe']==hashlib.sha256(Path(image.value).read_bytes()).hexdigest()
