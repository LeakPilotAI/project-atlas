"""Confined native immutable read-cut tests, never operational enrollment."""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest
from app.services.personal_native_coordination import PersonalNativeCoordination
from test_personal_paper_inception_memory import system

from scripts.observation_runtime.disposable_host_owner import observe_handle, observe_pid
from scripts.observation_runtime.personal_coordination_store import NativePersonalCoordinationImages
from scripts.observation_runtime.personal_paper_inception import native_primitives


@pytest.fixture
def store(tmp_path):
    root=Path(os.environ['ATLAS_PERSONAL_READ_VIEW_ROOT'])
    assert root.parent==Path(__file__).resolve().parents[1]/'logs/diagnostics'
    assert root.name.startswith('qd-read-view-') and tmp_path.is_relative_to(root)
    assert not any(p.is_symlink() or p.is_junction() for p in (tmp_path,*tmp_path.parents))
    native=native_primitives()
    with native.w.WindowsOutput.create_root(str(tmp_path/'control')) as output:
        identity=native.native.file_identity(output.root_handle)
    manifest=system('QUALITY_DIPS').m
    images=NativePersonalCoordinationImages(root=str(tmp_path/'control'),native_root=identity,enrollment_digest=digest(manifest))
    @contextmanager
    def synthetic(request):yield SimpleNamespace(check=lambda value:value==request)
    try:
        images.initialize(PersonalNativeCoordination.initial_image(manifest),authorization=SimpleNamespace(lease=synthetic))
        ledger=PersonalNativeCoordination(manifest=manifest,images=images,path=tmp_path/'control/memory-only')
        yield SimpleNamespace(images=images,ledger=ledger,native=native)
    finally:
        images.close()
        assert not images._retained_reads


def test_nested_queries_reuse_cut_but_full_native_verification_brackets_it(store):
    s=store;calls=[];read=s.images._read
    def counted(*args,**kwargs):calls.append(args[0]);return read(*args,**kwargs)
    s.images._read=counted
    with s.ledger.read_view():
        initial=len(calls)
        assert initial>0
        for _ in range(5):
            with s.ledger.read_view(),s.ledger.connect(readonly=True) as db:
                assert db.execute('SELECT COUNT(*) FROM inception').fetchone()==(1,)
        assert len(calls)==initial
    assert len(calls)==2*initial and s.images._read_view is None


def test_read_view_refuses_sql_and_native_publication(store):
    s=store;before=s.images._load()
    with s.ledger.read_view():
        with pytest.raises(ValueError,match='NO_WRITE'),s.ledger.connect():pass
        with s.ledger.connect(readonly=True) as db,pytest.raises(sqlite3.OperationalError):
            db.execute('DELETE FROM inception')
        with pytest.raises(ValueError,match='NO_WRITE'):
            s.images._publish(before[0],before[0])
    assert s.images._load()==before


def test_other_thread_cannot_read_snapshot_or_publish(store):
    s=store
    def attempt(readonly):
        try:
            with s.ledger.connect(readonly=readonly):pass
        except ValueError:return 'REFUSED'
        return 'UNSAFE'
    with s.ledger.read_view(),ThreadPoolExecutor(max_workers=1) as pool:
        assert list(pool.map(attempt,[True,False]))==['REFUSED','REFUSED']


def test_unexpected_tail_refuses_before_nested_value_and_on_exit(store):
    s=store
    with pytest.raises(ValueError),s.ledger.read_view():
        s.images.output.write_bound('0002-intent.json',b'{}')
        with pytest.raises(ValueError),s.ledger.connect(readonly=True):pytest.fail('unexpected tail was accepted')
    assert s.images._read_view is None
    with pytest.raises(ValueError):s.images._load()


def test_retained_acl_is_reverified_before_value_can_leave_scope(store,monkeypatch):
    s=store;original=s.images.native.w.validate_acl;changed=[False]
    retained=set()
    def verify(handle,sid):
        if changed[0] and getattr(handle,'value',handle) in retained:raise ValueError('SYNTHETIC_ACL_CHANGE_REFUSAL')
        return original(handle,sid)
    monkeypatch.setattr(s.images.native.w,'validate_acl',verify)
    def read():
        with s.ledger.read_view():
            retained.update(getattr(row[0],'value',row[0]) for row in s.images._retained_reads.values())
            with s.ledger.connect(readonly=True) as db:value=db.execute('SELECT body FROM inception').fetchone()
            changed[0]=True
            return value
    with pytest.raises(ValueError,match='ACL_CHANGE'):read()
    assert s.images._read_view is None


def test_stale_generation_refuses_snapshot_reuse(store):
    s=store
    with pytest.raises(ValueError,match='VIEW_CHANGED|ROLLBACK'),s.ledger.read_view():
        s.images.known['head']='foreign'
        with s.ledger.connect(readonly=True):pytest.fail('stale generation was accepted')


def test_original_handle_blocks_write_and_delete_during_read_view(store):
    s=store
    with s.ledger.read_view():
        leaf=Path(s.images.root)/'0001-ack.json'
        with pytest.raises(OSError),leaf.open('r+b'):pytest.fail('write admitted')
        with pytest.raises(OSError):leaf.unlink()


def test_separate_owned_process_writer_is_excluded_then_can_publish_after_release(store):
    s=store;repo=Path(__file__).resolve().parents[1]
    def attempt():
        with subprocess.Popen([sys.executable,'-B',str(repo/'tests/personal_read_view_writer_child.py')],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                creationflags=subprocess.CREATE_NO_WINDOW) as child:
            identity=observe_pid(child.pid)
            assert observe_handle(int(child._handle))==identity['created']
            data={'root':s.images.root,'native_root':s.images.root_id,'enrollment':s.images.enrollment}
            stdout,stderr=child.communicate(json.dumps(data),timeout=12)
            assert child.returncode==0,stderr
            return json.loads(stdout)
    with s.ledger.read_view():
        names=s.images._inventory()
        assert attempt()=={'published':False,'reason':'WRITER_BUSY'}
        assert s.images._inventory()==names
    assert attempt()=={'published':True,'revision':2}
    assert s.images._load()[1]['revision']==2


def test_native_v2_reuses_bound_pages_and_fresh_reader_reconstructs_exact_cut(store):
    s=store
    before=s.images._load()[0]
    original={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(s.images.root).iterdir()}
    after=before+b'x'*98304
    with s.images.transaction(readonly=False) as tx:tx.publish(before,after)
    later=after[:-1]+b'y'
    with s.images.transaction(readonly=False) as tx:tx.publish(after,later)
    commit=json.loads((Path(s.images.root)/'0003-commit.json').read_bytes())
    assert commit['schema']=='PERSONAL_NATIVE_COORDINATION_COMMIT_V2'
    assert sum(p['name'].startswith('0003-') for p in commit['pages'])==1
    assert all(hashlib.sha256((Path(s.images.root)/n).read_bytes()).hexdigest()==h for n,h in original.items())
    fresh=NativePersonalCoordinationImages(root=s.images.root,native_root=s.images.root_id,enrollment_digest=s.images.enrollment)
    try:
        assert fresh._load()[0]==later
        with fresh.read_view():assert fresh._load()[0]==later
    finally:fresh.close()


@pytest.mark.parametrize('phase',['intent','page','commit','ack'])
def test_actual_partial_native_v2_write_refuses_current_and_restart_without_repair(store,phase):
    s=store;before=s.images._load()[0];write=s.images.output.write_bound
    def interrupted(name,raw):
        result=write(name,raw)
        if name=={'intent':'0002-intent.json','page':'0002-page-0001.bin',
                  'commit':'0002-commit.json','ack':'0002-ack.json'}[phase]:
            raise OSError('INJECTED_NATIVE_PUBLICATION_INTERRUPT')
        return result
    s.images.output.write_bound=interrupted
    with pytest.raises(OSError,match='INTERRUPT'),s.images.transaction(readonly=False) as tx:
        tx.publish(before,b'changed'+before[7:])
    assert s.images.poisoned
    fresh=NativePersonalCoordinationImages(root=s.images.root,native_root=s.images.root_id,enrollment_digest=s.images.enrollment)
    try:
        with pytest.raises(ValueError,match='NAMESPACE'):fresh._load()
    finally:fresh.close()


def test_abrupt_commit_before_ack_leaves_unknown_native_tail_and_no_replay(store):
    s=store;repo=Path(__file__).resolve().parents[1]
    with subprocess.Popen([sys.executable,'-B',str(repo/'tests/personal_read_view_writer_child.py')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
            creationflags=subprocess.CREATE_NO_WINDOW) as child:
        identity=observe_pid(child.pid)
        assert observe_handle(int(child._handle))==identity['created']
        data={'root':s.images.root,'native_root':s.images.root_id,'enrollment':s.images.enrollment,
              'abrupt_after_commit':True}
        _stdout,stderr=child.communicate(json.dumps(data),timeout=12)
        assert child.returncode==73,stderr
    assert (Path(s.images.root)/'0002-commit.json').is_file()
    assert not (Path(s.images.root)/'0002-ack.json').exists()
    with pytest.raises(ValueError,match='INCOMPLETE_UNKNOWN'):s.images._load()
    with pytest.raises(ValueError),s.images.transaction(readonly=False):pytest.fail('abrupt outcome replayed')
