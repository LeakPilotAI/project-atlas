"""Parent-observed end-to-end native Stop/exit/readback with synthetic authority."""
import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager, nullcontext
from pathlib import Path

import pytest

from scripts.observation_runtime.disposable_host_owner import (
    observe_handle,
    observe_pid,
)


def hashes(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


@contextmanager
def prepared_reader(enabled,repo):
    if not enabled:
        yield None
        return
    with subprocess.Popen([sys.executable,'-B',str(repo/'tests/personal_readonly_restart_child.py'),'--ready-before-input'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
            creationflags=subprocess.CREATE_NO_WINDOW) as child:
        try:
            observed=observe_pid(child.pid)
            ready=json.loads(child.stdout.readline())
            assert ready=={'reader_ready':True,'process':{'pid':child.pid,'creation_filetime':observed['created'],
                'image':str(Path(sys.executable))}}
            assert observe_handle(int(child._handle))==observed['created']
            yield child
        finally:
            if child.poll() is None:
                child.stdin.close()
                child.wait(timeout=30)  # Exact owned EOF/self-exit only.


@pytest.mark.parametrize('sample',[1,2,3])
def test_three_owned_native_shutdowns_include_exit_and_post_exit_readback(sample):
    parent=os.environ.get('ATLAS_OWNED_STOP_TIMING_PARENT')
    if parent is None:pytest.skip('NOT EXECUTED: explicit synthetic timing scope required')
    repo=Path(__file__).resolve().parents[1]
    from personal_fixture_sources import fixture_source_root
    source_repo=fixture_source_root(repo)
    parent=Path(parent)
    assert parent.parent==repo/'logs/diagnostics' and parent.name.startswith('qd-owned-stop-timing-')
    assert not any(p.is_symlink() or p.is_junction() for p in (parent,*parent.parents))
    nonce=uuid.uuid4().hex
    root=repo/'logs/diagnostics'/('qd-personal-pipeline-owned-'+nonce)
    assert not root.exists()
    env={**os.environ,'ATLAS_PERSONAL_PIPELINE_TEST_ROOT':str(root),
         'ATLAS_PERSONAL_STOP_PROFILE':'COMPLETE_FINANCIAL_STOP','ATLAS_SYNTHETIC_STOP_NONCE':nonce}
    mode=os.environ.get('ATLAS_OWNED_STOP_READER_MODE','COLD')
    assert mode in ('COLD','RETAINED')
    with prepared_reader(mode=='RETAINED',repo) as prepared:
        lines=queue.Queue();all_lines=[]
        with subprocess.Popen([sys.executable,'-B',str(repo/'tests/personal_owned_stop_child.py')],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,
                creationflags=subprocess.CREATE_NO_WINDOW) as child:
            def read():
                for line in child.stdout:all_lines.append(line);lines.put(line)
            reader=threading.Thread(target=read,daemon=True);reader.start()
            deadline=time.monotonic()+40;ready=None
            while ready is None:
                line=lines.get(timeout=max(.01,deadline-time.monotonic()))
                value=json.loads(line)
                if value.get('timing_channel')==nonce and value['phase']=='READY':ready=value
            identity=observe_pid(child.pid)
            expected={'pid':identity['pid'],'creation_filetime':identity['created'],'image':str(Path(sys.executable))}
            assert ready['identity']==expected
            assert observe_handle(int(child._handle))==identity['created']
            started=time.perf_counter()
            child.stdin.write(json.dumps({'action':'STOP','nonce':nonce,'identity':expected})+'\n');child.stdin.flush()
            child.wait(timeout=25);reader.join(timeout=2)
            exited=time.perf_counter()
            stderr=child.stderr.read()
            assert child.returncode==0,stderr
            assert observe_handle(int(child._handle))==identity['created']
        packets=[json.loads(line) for line in all_lines]
        result=next(p['value'] for p in packets if p.get('timing_channel')==nonce and p.get('phase')=='READBACK')
        assert result['source_root']==str(source_repo)
        before=hashes(root)
        with (nullcontext(prepared) if prepared is not None else subprocess.Popen(
                [sys.executable,'-B',str(repo/'tests/personal_readonly_restart_child.py')],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                creationflags=subprocess.CREATE_NO_WINDOW)) as reader_child:
            observed=observe_pid(reader_child.pid)
            assert observe_handle(int(reader_child._handle))==observed['created']
            data={k:result[k] for k in ('root','personal_enrollment','now')}
            stdout,stderr=reader_child.communicate(json.dumps(data),timeout=30)
            assert reader_child.returncode==0,stderr
            verified=json.loads(stdout)
            assert verified['source_root']==str(source_repo)
            assert verified['state_digest']==result['state_digest'] and verified['read_only_restart']
            assert verified['writer_rebind_refused']
        assert hashes(root)==before
        complete=time.perf_counter()-started
        evidence={'sample':sample,'synthetic_authority':True,'reader_mode':mode,'reader_ready_before_stop':prepared is not None,'root':str(root),'owned_process_exit_verified':True,
            'financial_bytes_unchanged':True,'coordinator_seconds':result['timings']['complete_native_financial_stop'],
            'stop_to_exit_seconds':exited-started,'stop_exit_and_post_exit_readback_seconds':complete,
            'eight_second_passed':complete<=8,'operational_installation_accepted':False}
        evidence['installed_candidate_source']=str(source_repo) if source_repo!=repo else None
        evidence['profile_inclusive']=next(p['synthetic_stop_profile_inclusive'] for p in packets
                                           if 'synthetic_stop_profile_inclusive' in p)
        parent.mkdir(exist_ok=True)
        (parent/f'sample-{sample}.json').write_text(json.dumps(evidence,indent=2))
        if source_repo!=repo:
            # Retain the exact acknowledged writer cut for subsequent read-only
            # installed HTTP acceptance; never reconstruct or rebind its writer.
            with (parent/f'native-readback-{sample}.json').open('x') as stream:
                json.dump({k:result[k] for k in ('root','personal_enrollment','now')},stream)
        print(json.dumps(evidence))
        assert complete<=8, evidence
