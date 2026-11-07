"""Only disposable pending journals and fake PAPER execution; never activates services."""
import asyncio
import json
import os
from pathlib import Path

import app.services.perp_setup_paper_mirror as mod
import pytest


def mirror(tmp_path):
    m=mod.PerpSetupPaperMirror(pending_path=tmp_path/'pending.jsonl');m._seeded=True
    m._pending={'synthetic':{'setup_instance_id':'synthetic','symbol':'BTC','side':'LONG','limit_price':99,'stop':95,'tp1':105,'tp2':110}}
    return m


@pytest.mark.parametrize('fault',['write','short','flush','fsync','close','disk-full'])
def test_append_failure_is_not_acknowledged_and_retry_refuses(tmp_path,monkeypatch,fault):
    m=mirror(tmp_path);original=Path.open;fsync=os.fsync;fds=set();error=OSError(28 if fault=='disk-full' else 5,'synthetic '+fault)
    class Stream:
        def __init__(self,h):self.h=h
        def __enter__(self):return self
        def __exit__(self,*args):
            result=self.h.__exit__(*args)
            if fault=='close' and args[0] is None:raise error
            return result
        def write(self,v):
            if fault in ('write','disk-full'):raise error
            return self.h.write(v[:len(v)//2] if fault=='short' else v)
        def flush(self):
            if fault=='flush':raise error
            self.h.flush()
        def fileno(self):
            fd=self.h.fileno();fds.add(fd);return fd
    def opened(p,*args,**kw):
        h=original(p,*args,**kw)
        return Stream(h) if p==m._pending_path and args and args[0]=='a' else h
    def synced(fd):
        if fault=='fsync' and fd in fds:raise error
        return fsync(fd)
    with monkeypatch.context() as patch:
        patch.setattr(Path,'open',opened);patch.setattr(os,'fsync',synced)
        with pytest.raises(OSError) as actual:m.cancel_all_pending(reason='OPERATOR_CANCEL')
    if fault!='short':assert actual.value is error
    assert 'synthetic' in m._pending and not m._terminal_pending_instances
    before=m._pending_path.read_bytes() if m._pending_path.exists() else b''
    with pytest.raises(OSError):m.cancel_all_pending(reason='OPERATOR_CANCEL')
    assert (m._pending_path.read_bytes() if m._pending_path.exists() else b'')==before
    with pytest.raises(OSError):mod.PerpSetupPaperMirror(pending_path=m._pending_path)._seed()


@pytest.mark.parametrize('marker',['append-intent','fill-intent'])
def test_restart_retains_uncertain_marker(tmp_path,marker):
    m=mirror(tmp_path);p=m._pending_path.with_name(m._pending_path.name+'.'+marker);p.write_text('synthetic interrupted operation',encoding='utf-8')
    with pytest.raises(OSError):m.cancel_all_pending(reason='OPERATOR_CANCEL')
    assert p.read_text()=='synthetic interrupted operation'
    with pytest.raises(OSError):mod.PerpSetupPaperMirror(pending_path=m._pending_path)._seed()


@pytest.mark.parametrize('raw',[b'{bad}\n',b'[]\n',b'{"event":"armed"}',b'{"event":"armed","event":"filled"}\n',b'{"value":NaN}\n',b'\xff\n'])
def test_invalid_history_is_not_a_safe_empty_state(tmp_path,raw,monkeypatch):
    m=mirror(tmp_path);m._seeded=False;m._pending_path.write_bytes(raw);source=tmp_path/'paper.jsonl';monkeypatch.setattr(mod,'JOURNAL_PATH',source)
    with pytest.raises((OSError,ValueError,UnicodeError)):m._seed()
    assert not m._seeded and m._pending_path.read_bytes()==raw


def configure_fill(m,monkeypatch,action):
    monkeypatch.setattr(m,'_fresh_mark_timestamp',lambda _:True)
    monkeypatch.setattr(mod,'utc_day_risk_snapshot',lambda:{'reliable':True,'net_r':0})
    monkeypatch.setattr(mod,'risk_snapshot_is_current',lambda _:True)
    monkeypatch.setattr(mod,'check_paper_risk',lambda **_:{'allowed':True})
    class Journal:
        def list_open(self):return []
        async def open_trade(self,**kwargs):return await action(kwargs)
    monkeypatch.setattr(mod,'paper_journal',Journal())


def test_fill_intent_precedes_open_and_survives_interruption(tmp_path,monkeypatch):
    m=mirror(tmp_path);calls=[]
    async def action(kwargs):
        calls.append(kwargs);assert m._pending_path.with_name(m._pending_path.name+'.fill-intent').exists()
        raise OSError('synthetic ambiguous PAPER acknowledgement')
    configure_fill(m,monkeypatch,action)
    with pytest.raises(OSError):asyncio.run(m._fill_pending('synthetic',mark=98.9,setup={}))
    with pytest.raises(OSError):asyncio.run(m._fill_pending('synthetic',mark=98.9,setup={}))
    assert len(calls)==1 and 'synthetic' in m._pending


def test_fill_terminal_failure_prevents_second_open_even_after_trade_closed(tmp_path,monkeypatch):
    m=mirror(tmp_path);calls=[]
    async def action(kwargs):calls.append(kwargs);return 'synthetic-trade'
    configure_fill(m,monkeypatch,action)
    def fail(_):raise OSError('synthetic terminal failure')
    monkeypatch.setattr(m,'_append_pending_event',fail)
    with pytest.raises(OSError):asyncio.run(m._fill_pending('synthetic',mark=98.9,setup={}))
    with pytest.raises(OSError):asyncio.run(m._fill_pending('synthetic',mark=98.9,setup={}))
    assert len(calls)==1
    assert m._pending_path.with_name(m._pending_path.name+'.fill-intent').exists()


def test_successful_fill_is_once_and_removes_only_own_intent(tmp_path,monkeypatch):
    m=mirror(tmp_path);calls=[]
    async def action(kwargs):calls.append(kwargs);return 'synthetic-trade'
    configure_fill(m,monkeypatch,action)
    assert asyncio.run(m._fill_pending('synthetic',mark=98.9,setup={}))
    assert not asyncio.run(m._fill_pending('synthetic',mark=98.9,setup={}))
    assert len(calls)==1 and not list(tmp_path.glob('*.fill-intent'))
    rows=[json.loads(x) for x in m._pending_path.read_text().splitlines()]
    assert rows[-1]['event']=='filled' and rows[-1]['trade_id']=='synthetic-trade'


@pytest.mark.parametrize('response',[None,'',False,{}])
def test_invalid_open_acknowledgement_retains_fill_fence(tmp_path,monkeypatch,response):
    m=mirror(tmp_path)
    async def action(_):return response
    configure_fill(m,monkeypatch,action)
    with pytest.raises(OSError):asyncio.run(m._fill_pending('synthetic',mark=98.9,setup={}))
    assert m._pending_path.with_name(m._pending_path.name+'.fill-intent').exists()
    assert 'synthetic' in m._pending


def test_cancelled_open_keeps_exact_exception_and_refuses_restart(tmp_path,monkeypatch):
    m=mirror(tmp_path);error=asyncio.CancelledError('synthetic cancelled open')
    async def action(_):raise error
    configure_fill(m,monkeypatch,action)
    with pytest.raises(asyncio.CancelledError) as caught:asyncio.run(m._fill_pending('synthetic',mark=98.9,setup={}))
    assert caught.value is error
    with pytest.raises(OSError):mod.PerpSetupPaperMirror(pending_path=m._pending_path)._seed()


def test_other_instance_refuses_during_inflight_open(tmp_path,monkeypatch):
    m=mirror(tmp_path);other=mod.PerpSetupPaperMirror(pending_path=m._pending_path);other._seeded=True
    async def action(_):
        with pytest.raises(OSError):other.cancel_all_pending(reason='OPERATOR_CANCEL')
        with pytest.raises(OSError):m.cancel_all_pending(reason='OPERATOR_CANCEL')
        return 'synthetic'
    configure_fill(m,monkeypatch,action)
    # A conflicting same-instance request conservatively latches uncertainty.
    with pytest.raises(OSError):asyncio.run(m._fill_pending('synthetic',mark=98.9,setup={}))
    assert m._pending_path.with_name(m._pending_path.name+'.fill-intent').exists()


@pytest.mark.parametrize('kind',['append-intent','fill-intent'])
def test_intent_replacement_is_preserved_not_removed(tmp_path,monkeypatch,kind):
    m=mirror(tmp_path);original=m._finish_intent
    def replaced(k,payload):
        if k==kind:m._intent_path(k).write_text('synthetic replacement',encoding='utf-8')
        return original(k,payload)
    monkeypatch.setattr(m,'_finish_intent',replaced)
    if kind=='append-intent':
        with pytest.raises(OSError):m.cancel_all_pending(reason='OPERATOR_CANCEL')
    else:
        async def action(_):return 'synthetic'
        configure_fill(m,monkeypatch,action)
        with pytest.raises(OSError):asyncio.run(m._fill_pending('synthetic',mark=98.9,setup={}))
    assert m._intent_path(kind).read_text()=='synthetic replacement'


def test_exponent_overflow_is_not_replayed_as_infinite_price(tmp_path,monkeypatch):
    m=mirror(tmp_path);m._seeded=False;m._pending_path.write_bytes(b'{"event":"armed","setup_instance_id":"a","limit_price":1e999}\n');monkeypatch.setattr(mod,'JOURNAL_PATH',tmp_path/'paper.jsonl')
    with pytest.raises(ValueError):m._seed()
    assert not m._seeded


def test_shutdown_report_receives_pending_persistence_failure(tmp_path,monkeypatch):
    from app.core.shutdown import ShutdownReport
    m=mirror(tmp_path);error=OSError('synthetic failed acknowledgement');m._persistence_error=error
    report=ShutdownReport(timeout=1,clock=lambda:0)
    async def run():
        with pytest.raises(OSError) as actual:await report.run('pending_limits',lambda:m.cancel_all_pending(reason='ATLAS_SHUTDOWN'))
        assert actual.value is error
    asyncio.run(run())
    assert report.errors == [('pending_limits',error)]
    report.sealed=True
    assert report.outcome=='INCOMPLETE'


@pytest.mark.parametrize('row',[{}, {'event':'armed'}, {'event':'armed','setup_instance_id':True}, {'event':'unknown','setup_instance_id':'a'}])
def test_missing_or_ambiguous_pending_identity_blocks_seed(tmp_path,monkeypatch,row):
    m=mirror(tmp_path);m._seeded=False;m._pending_path.write_text(json.dumps(row)+'\n',encoding='utf-8');monkeypatch.setattr(mod,'JOURNAL_PATH',tmp_path/'paper.jsonl')
    with pytest.raises(ValueError):m._seed()
    assert not m._seeded


def test_arm_after_terminal_is_not_resurrected_by_replay(tmp_path,monkeypatch):
    m=mirror(tmp_path);m._seeded=False;rows=[{'event':event,'setup_instance_id':'a'} for event in ['armed','cancelled','armed']]
    m._pending_path.write_text(''.join(json.dumps(x)+'\n' for x in rows),encoding='utf-8');monkeypatch.setattr(mod,'JOURNAL_PATH',tmp_path/'paper.jsonl')
    with pytest.raises(ValueError):m._seed()
    assert not m._seeded


def test_sync_does_not_report_fill_persistence_failure_as_skip(tmp_path,monkeypatch):
    from datetime import UTC, datetime
    m=mirror(tmp_path);m._pending['synthetic']['timestamp']=datetime.now(UTC).isoformat()
    async def action(_):return 'synthetic-trade'
    configure_fill(m,monkeypatch,action)
    monkeypatch.setattr(m,'_instance_id',lambda _:'synthetic')
    monkeypatch.setattr(m,'_instruction',lambda _:{})
    monkeypatch.setattr(m,'_arm',lambda *_,**kw:False)
    error=OSError('synthetic filled-event failure')
    def fail(_):raise error
    monkeypatch.setattr(m,'_append_pending_event',fail)
    with pytest.raises(OSError) as actual:asyncio.run(m.sync([{'symbol':'BTC','state':'PREPARE'}],{'BTC':98.9}))
    assert actual.value is error and m._persistence_error is error



def test_process_crash_during_open_leaves_restart_refusal(tmp_path):
    import shutil
    import subprocess
    import sys
    backend=tmp_path/'isolated-backend'
    shutil.copytree(Path(mod.__file__).resolve().parents[1],backend/'app',ignore=shutil.ignore_patterns('data','__pycache__','*.pyc','.env*'))
    path=tmp_path/'pending.jsonl'
    code="""
import sys,os,asyncio
from pathlib import Path
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root));os.chdir(root)
def guard(event,args):
 if event=='socket.connect' and sys._getframe(1).f_code.co_name!='_fallback_socketpair':raise PermissionError('synthetic crash fixture denies network')
 if event=='open' and isinstance(args[0],(str,bytes)):
  p=Path(os.fsdecode(args[0])).resolve()
  if ('data' in p.parts or p.name=='.env') and not p.is_relative_to(root):raise PermissionError('synthetic crash fixture denies external data')
sys.addaudithook(guard)
import app.services.perp_setup_paper_mirror as mod
m=mod.PerpSetupPaperMirror(pending_path=Path(sys.argv[2]));m._seeded=True
m._pending={'synthetic':{'symbol':'BTC','side':'LONG','limit_price':99,'stop':95,'tp1':105,'tp2':110}}
m._fresh_mark_timestamp=lambda _:True
mod.utc_day_risk_snapshot=lambda:{'net_r':0}
mod.risk_snapshot_is_current=lambda _:True
mod.check_paper_risk=lambda **_:{'allowed':True}
class Journal:
 def list_open(self):return []
 async def open_trade(self,**kwargs):os._exit(23)
mod.paper_journal=Journal()
asyncio.run(m._fill_pending('synthetic',mark=98.9,setup={}))
"""
    completed=subprocess.run([sys.executable,'-c',code,str(backend),str(path)],capture_output=True,text=True,timeout=15,check=False)
    assert completed.returncode==23,completed.stderr
    marker=path.with_name(path.name+'.fill-intent');raw=marker.read_bytes()
    assert json.loads(raw)['setup_instance_id']=='synthetic'
    with pytest.raises(OSError):mod.PerpSetupPaperMirror(pending_path=path)._seed()
    assert marker.read_bytes()==raw


def test_competing_local_append_refuses_before_writing(tmp_path,monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    a=mirror(tmp_path);b=mirror(tmp_path);original=a._begin_intent;entered=threading.Event();release=threading.Event()
    def held(kind,row):
        payload=original(kind,row);entered.set();assert release.wait(5);return payload
    monkeypatch.setattr(a,'_begin_intent',held)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(a.cancel_all_pending,reason='OPERATOR_CANCEL')
        try:
            assert entered.wait(5)
            with pytest.raises(OSError):b.cancel_all_pending(reason='OPERATOR_CANCEL')
        finally:release.set()
        assert future.result(timeout=5)==1
    rows=[json.loads(line) for line in a._pending_path.read_text().splitlines()]
    assert len(rows)==1 and rows[0]['event']=='cancelled'
