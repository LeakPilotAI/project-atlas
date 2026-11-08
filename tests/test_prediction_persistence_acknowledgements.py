"""Temporary prediction journals only; no provider, runtime or order activation."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from app.prediction.paper_engine import PredictionPaperError, PredictionPaperJournal


def journal(tmp_path):
    return PredictionPaperJournal(journal_path=tmp_path/'paper.jsonl',candidate_path=tmp_path/'candidates.jsonl')


def evaluation():
    return {'eligible':True,'ticker':'SYNTHETIC','side':'YES','quantity_contracts':'10','occurrence_datetime':'2026-10-20T20:00:00+00:00','flat_deadline':'2026-10-20T19:45:00+00:00','strategy':'SYNTHETIC_ONLY','entry_fill':{'fillable':True,'vwap_dollars':'0.42','notional_dollars':'4.20','estimated_taker_fee_dollars':'0.17','levels':[{'price_dollars':'0.42','quantity_contracts':'10'}]}}


@pytest.mark.parametrize('fault',['write','disk-full','short','flush','fsync','close'])
def test_ambiguous_append_failure_is_not_acknowledged_or_retried(tmp_path,monkeypatch,fault):
    j=journal(tmp_path);error=OSError(28 if fault=='disk-full' else 5,'synthetic '+fault)
    original_open=Path.open;original_fsync=os.fsync;data_fds=set()
    class Stream:
        def __init__(self,h):self.h=h
        def __enter__(self):return self
        def __exit__(self,*args):
            result=self.h.__exit__(*args)
            if fault=='close' and args[0] is None:raise error
            return result
        def write(self,value):
            if fault in ('write','disk-full'):raise error
            if fault=='short':return self.h.write(value[:len(value)//2])
            return self.h.write(value)
        def flush(self):
            if fault=='flush':raise error
            self.h.flush()
        def fileno(self):
            fd=self.h.fileno();data_fds.add(fd);return fd
    def opened(path,*args,**kwargs):
        h=original_open(path,*args,**kwargs)
        return Stream(h) if path==j.journal_path and args and args[0]=='a' else h
    def fsync(fd):
        if fault=='fsync' and fd in data_fds:raise error
        original_fsync(fd)
    with monkeypatch.context() as m:
        m.setattr(Path,'open',opened);m.setattr(os,'fsync',fsync)
        with pytest.raises(OSError) as actual:j.log_event({'event':'synthetic_event'})
    if fault!='short':assert actual.value is error
    marker=j.journal_path.with_name(j.journal_path.name+'.append-intent')
    assert marker.exists()
    before=j.journal_path.read_bytes() if j.journal_path.exists() else b''
    with pytest.raises((OSError,PredictionPaperError)):j.log_event({'event':'synthetic_retry'})
    with pytest.raises((OSError,PredictionPaperError)):journal(tmp_path).open_trade()
    assert (j.journal_path.read_bytes() if j.journal_path.exists() else b'')==before
    assert marker.exists()


@pytest.mark.parametrize('raw',[b'{bad}\n',b'[]\n',b'{"event":"open"}',b'{"event":"open","event":"close"}\n',b'{"n":NaN}\n',b'\xff\n'])
def test_corrupt_or_incomplete_journal_is_not_an_empty_safe_state(tmp_path,raw):
    j=journal(tmp_path);j.journal_path.write_bytes(raw)
    with pytest.raises((OSError,ValueError,PredictionPaperError)):j.open_from_evaluation(evaluation())
    assert j.journal_path.read_bytes()==raw


@pytest.mark.parametrize('method',['_rows','_tail_rows'])
def test_read_failure_propagates_instead_of_looking_empty(tmp_path,monkeypatch,method):
    j=journal(tmp_path);j.journal_path.write_text('{}\n',encoding='utf-8');original=Path.open;error=PermissionError('synthetic denied')
    def opened(path,*args,**kwargs):
        if path==j.journal_path:raise error
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',opened)
    with pytest.raises(PermissionError) as actual:getattr(j,method)(j.journal_path,*([3] if method=='_tail_rows' else []))
    assert actual.value is error


def test_unknown_intent_survives_fresh_process_and_does_not_authorize_open(tmp_path):
    j=journal(tmp_path);marker=j.journal_path.with_name(j.journal_path.name+'.append-intent');marker.write_bytes(b'{"unknown":"interrupted"}\n')
    code="import sys;from pathlib import Path;from app.prediction.paper_engine import PredictionPaperJournal,PredictionPaperError;j=PredictionPaperJournal(journal_path=Path(sys.argv[1]),candidate_path=Path(sys.argv[2]));\ntry:j.open_trade()\nexcept (OSError,PredictionPaperError):print('REFUSED');sys.exit(0)\nsys.exit(3)"
    r=subprocess.run([sys.executable,'-c',code,str(j.journal_path),str(j.candidate_path)],capture_output=True,text=True,timeout=15,env=os.environ.copy(),check=False)
    assert r.returncode==0 and r.stdout.strip()=='REFUSED' and marker.exists()


def test_legacy_complete_records_and_successful_restart_preserve_bytes(tmp_path):
    j=journal(tmp_path);legacy=b'{"event":"legacy_observation"}\n';j.journal_path.write_bytes(legacy)
    opened=j.open_from_evaluation(evaluation(),now=datetime(2026,10,20,12,tzinfo=timezone.utc));raw=j.journal_path.read_bytes()
    assert raw.startswith(legacy) and journal(tmp_path).open_trade()['trade_id']==opened['trade_id']
    with pytest.raises(PredictionPaperError):journal(tmp_path).open_from_evaluation(evaluation())
    assert j.journal_path.read_bytes()==raw
    assert not j.journal_path.with_name(j.journal_path.name+'.append-intent').exists()


@pytest.mark.parametrize('failure',['intent-write','intent-sync','intent-unlink','delete-sync','replacement','interrupted'])
def test_intent_and_cleanup_failures_retain_refusal(tmp_path,monkeypatch,failure):
    import app.prediction.paper_engine as module
    j=journal(tmp_path);intent=j.journal_path.with_name(j.journal_path.name+'.append-intent');error=OSError('synthetic '+failure)
    original_write=module.write_flushed;original_sync=module.sync_parent;original_unlink=Path.unlink;calls=0
    def write(handle,value):
        if Path(handle.name)==intent and failure=='intent-write':raise error
        original_write(handle,value)
        if Path(handle.name)==j.journal_path:
            if failure=='replacement':intent.write_bytes(b'{"replacement":true}\n')
            if failure=='interrupted':raise KeyboardInterrupt('synthetic interruption')
    def sync(path):
        nonlocal calls
        if path==intent:
            calls+=1
            if (failure=='intent-sync' and calls==1) or (failure=='delete-sync' and calls==2):raise error
        original_sync(path)
    def unlink(path,*args,**kwargs):
        if path==intent and failure=='intent-unlink':raise error
        return original_unlink(path,*args,**kwargs)
    with monkeypatch.context() as m:
        m.setattr(module,'write_flushed',write);m.setattr(module,'sync_parent',sync);m.setattr(Path,'unlink',unlink)
        with pytest.raises((OSError,PredictionPaperError,KeyboardInterrupt)) as observed:j.log_event({'event':'synthetic_event'})
    if failure not in ('replacement','interrupted'):assert observed.value is error
    assert intent.exists()
    with pytest.raises((OSError,PredictionPaperError,KeyboardInterrupt)):journal(tmp_path).open_trade()
    if failure=='replacement':assert intent.read_bytes()==b'{"replacement":true}\n'


@pytest.mark.parametrize('rows',[
 [{'event':'open'}],
 [{'event':'close','trade_id':'missing'}],
 [{'event':'open','trade_id':'a'},{'event':'open','trade_id':'a'}],
 [{'event':'open','trade_id':'a'},{'event':'open','trade_id':'b'}],
 [{'event':'open','trade_id':'a'},{'event':'close','trade_id':'a'},{'event':'expired_unclosed','trade_id':'a'}],
])
def test_contradictory_trade_replay_cannot_grant_new_open(tmp_path,rows):
    j=journal(tmp_path);raw=''.join(json.dumps(r)+'\n' for r in rows).encode();j.journal_path.write_bytes(raw)
    with pytest.raises(PredictionPaperError):j.snapshot()
    with pytest.raises(PredictionPaperError):j.open_from_evaluation(evaluation())
    assert j.journal_path.read_bytes()==raw


def test_exponent_overflow_is_not_finite_evidence(tmp_path):
    j=journal(tmp_path);j.journal_path.write_bytes(b'{"number":1e999}\n')
    with pytest.raises(PredictionPaperError):j.open_trade()


def test_process_exit_between_write_and_sync_leaves_durable_refusal(tmp_path):
    j=journal(tmp_path)
    code="import os,sys;from pathlib import Path;import app.prediction.paper_engine as m;j=m.PredictionPaperJournal(journal_path=Path(sys.argv[1]),candidate_path=Path(sys.argv[2]));original=m.write_flushed;\ndef interrupted(h,v):\n if Path(h.name)==Path(sys.argv[1]):h.write(v);h.flush();os._exit(47)\n original(h,v)\nm.write_flushed=interrupted;j.log_event({'event':'synthetic_interrupted'})"
    r=subprocess.run([sys.executable,'-c',code,str(j.journal_path),str(j.candidate_path)],capture_output=True,text=True,timeout=15,env=os.environ.copy(),check=False)
    assert r.returncode==47
    assert j.journal_path.with_name(j.journal_path.name+'.append-intent').exists()
    with pytest.raises(PredictionPaperError):j.open_trade()


def test_two_local_journal_instances_cannot_admit_simultaneous_positions(tmp_path,monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    a=journal(tmp_path);b=journal(tmp_path);entered=threading.Event();release=threading.Event();original=a._append
    def gap(path,row):
        entered.set();assert release.wait(5);return original(path,row)
    monkeypatch.setattr(a,'_append',gap)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(a.open_from_evaluation,evaluation(),now=datetime(2026,10,20,12,tzinfo=timezone.utc));assert entered.wait(5)
        second=pool.submit(b.open_from_evaluation,evaluation(),now=datetime(2026,10,20,12,tzinfo=timezone.utc))
        try:
            try:second.result(timeout=.1)
            except TimeoutError:pass
        finally:release.set()
        opened=[];refused=[]
        for future in [first,second]:
            try:opened.append(future.result(timeout=5))
            except PredictionPaperError as error:refused.append(error)
    assert len(opened)==len(refused)==1 and a.snapshot()['summary']['open_positions']==1
    assert len([r for r in a._rows(a.journal_path) if r.get('event')=='open'])==1


def test_expiry_source_and_generic_events_cannot_fabricate_lifecycle(tmp_path):
    j=journal(tmp_path)
    with pytest.raises(PredictionPaperError):j.expire_unclosed(opened={'trade_id':'not-recorded'})
    with pytest.raises(PredictionPaperError):j.log_event({'event':'open','trade_id':'not-recorded'})
    assert not j.journal_path.exists()


@pytest.mark.parametrize('raw',[b'[]\n',b'{bad}\n',b'{}',b'{"n":1e999}\n'])
def test_selected_candidate_tail_is_not_silently_cleaned(tmp_path,raw):
    j=journal(tmp_path);j.candidate_path.write_bytes(raw)
    with pytest.raises(PredictionPaperError):j.candidate_snapshot(1)
    assert j.candidate_path.read_bytes()==raw


def test_tail_and_record_limits_refuse_without_truncating_source(tmp_path,monkeypatch):
    j=journal(tmp_path);raw=b'{"event":"synthetic","payload":"'+b'x'*200+b'"}\n';j.candidate_path.write_bytes(raw)
    monkeypatch.setattr(PredictionPaperJournal,'_max_tail_bytes',64)
    with pytest.raises(PredictionPaperError):j.candidate_snapshot(1)
    monkeypatch.setattr(PredictionPaperJournal,'_max_line_bytes',64)
    with pytest.raises(PredictionPaperError):j.log_event({'event':'synthetic','payload':'x'*200})
    assert j.candidate_path.read_bytes()==raw and not j.journal_path.exists()


def test_intent_access_failure_retains_original_read_refusal(tmp_path,monkeypatch):
    j=journal(tmp_path);intent=j.journal_path.with_name(j.journal_path.name+'.append-intent');original=Path.exists;error=PermissionError('synthetic intent access denied')
    def exists(path):
        if path==intent:raise error
        return original(path)
    with monkeypatch.context() as m:
        m.setattr(Path,'exists',exists)
        with pytest.raises(PermissionError) as observed:j.open_trade()
    assert observed.value is error and j.persistence_failure() is error
    assert j.is_persistence_failure(error)
    with pytest.raises(PermissionError) as repeated:j.log_event({'event':'synthetic'})
    assert repeated.value is error and not j.journal_path.exists()
