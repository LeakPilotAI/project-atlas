import json
import math
from pathlib import Path

import pytest
from app.backtest.holdout_evidence_freeze import build, run


def summary():
    return {"status":"UNTOUCHED_HOLDOUT_EVALUATION_COMPLETE", "source_audit_green":True,
            "source_audit_id":"fixture-audit", "parameters_frozen":True,
            "threshold_retuning_allowed":False, "production_strategy_modified":False,
            "live_capital_allowed":False, "aggregate":{"trade_count":3,"total_r":-1.,"expectancy_r":-1./3},
            "runs":[{"symbol":s,"run_id":s,"metrics":{}} for s in ("BTC","ETH","SOL")]}


def source(tmp_path):
    p=tmp_path/"summary.json";p.write_text(json.dumps(summary()));return p


def test_payload_is_bound_to_same_input_bytes_as_digest(tmp_path, monkeypatch):
    p=source(tmp_path); altered=summary();altered["aggregate"]["total_r"]=99.
    original=Path.read_text
    monkeypatch.setattr(Path,"read_text", lambda self,*a,**kw: json.dumps(altered) if self==p else original(self,*a,**kw))
    result=run(summary_path=p,output=tmp_path/"out.json")
    assert result["aggregate"]["total_r"] == json.loads(p.read_bytes())["aggregate"]["total_r"]


def test_identical_replay_does_not_rewrite_existing_evidence(tmp_path, monkeypatch):
    p=source(tmp_path);output=tmp_path/"out.json";a=run(summary_path=p,output=output)
    original=Path.write_text
    def guarded(self,*args,**kwargs):
        if self==output: raise AssertionError("Existing evidence rewrite")
        return original(self,*args,**kwargs)
    monkeypatch.setattr(Path,"write_text",guarded)
    assert run(summary_path=p,output=output)==a


@pytest.mark.parametrize("field,value", [("trade_count",True),("trade_count",1.25),("trade_count",-1),("total_r",math.nan),("expectancy_r",math.inf)])
def test_invalid_measured_aggregate_refused(field,value):
    s=summary();s["aggregate"][field]=value
    with pytest.raises((ValueError,RuntimeError)): build(s)


def test_required_flush_failure_is_not_success(tmp_path, monkeypatch):
    from app.core import durable_io
    p=source(tmp_path)
    def fail(_): raise OSError("synthetic fsync failure")
    monkeypatch.setattr(durable_io.os,"fsync",fail)
    with pytest.raises(OSError,match="synthetic fsync"):
        run(summary_path=p,output=tmp_path/"out.json")



def test_conflicting_existing_artifact_never_overwritten(tmp_path):
    p=source(tmp_path);out=tmp_path/"out.json";out.write_bytes(b"preserved-original")
    with pytest.raises(RuntimeError):run(summary_path=p,output=out)
    assert out.read_bytes()==b"preserved-original"


def test_partial_publication_failure_is_preserved_and_not_acknowledged(tmp_path,monkeypatch):
    p=source(tmp_path);out=tmp_path/"out.json";original=Path.open
    class ShortWrite:
        def __init__(self,stream):self.stream=stream
        def __enter__(self):return self
        def __exit__(self,*args):self.stream.close()
        def write(self,value):return self.stream.write(value[:-1])
        def flush(self):return self.stream.flush()
        def fileno(self):return self.stream.fileno()
    def opened(self,*args,**kwargs):
        stream=original(self,*args,**kwargs)
        return ShortWrite(stream) if self==out and args and args[0]=="x" else stream
    monkeypatch.setattr(Path,"open",opened)
    with pytest.raises(OSError,match="Incomplete"):run(summary_path=p,output=out)
    partial=out.read_bytes();assert partial
    monkeypatch.setattr(Path,"open",original)
    with pytest.raises(RuntimeError):run(summary_path=p,output=out)
    assert out.read_bytes()==partial


def test_failed_fsync_can_only_reacknowledge_after_fresh_successful_sync(tmp_path,monkeypatch):
    from app.core import durable_io
    p=source(tmp_path);out=tmp_path/"out.json";original=durable_io.os.fsync
    def fail(_):raise OSError("synthetic fsync")
    monkeypatch.setattr(durable_io.os,"fsync",fail)
    with pytest.raises(OSError):run(summary_path=p,output=out)
    committed_bytes=out.read_bytes()
    with pytest.raises(OSError):run(summary_path=p,output=out)
    monkeypatch.setattr(durable_io.os,"fsync",original)
    assert run(summary_path=p,output=out)["status"]=="HOLDOUT_EVIDENCE_FROZEN"
    assert out.read_bytes()==committed_bytes


def test_parent_sync_failure_is_not_success(tmp_path,monkeypatch):
    from app.backtest import holdout_evidence_freeze as module
    p=source(tmp_path);out=tmp_path/"out.json"
    def fail(_):raise OSError("synthetic directory sync")
    monkeypatch.setattr(module,"sync_parent",fail)
    with pytest.raises(OSError,match="directory"):run(summary_path=p,output=out)
    assert out.exists()


def test_concurrent_publishers_never_truncate_each_other(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    p=source(tmp_path);out=tmp_path/"out.json"
    def attempt(_):
        try:return run(summary_path=p,output=out)
        except RuntimeError:return None
    with ThreadPoolExecutor(max_workers=2) as workers:results=list(workers.map(attempt,range(2)))
    assert any(r is not None for r in results)
    assert json.loads(out.read_bytes())["status"]=="HOLDOUT_EVIDENCE_FROZEN"


def test_source_bytes_not_clobbered_when_output_matches_input(tmp_path):
    p=source(tmp_path);old=p.read_bytes()
    with pytest.raises(RuntimeError):run(summary_path=p,output=p)
    assert p.read_bytes()==old



def test_legacy_windows_crlf_freeze_replays_without_rewrite(tmp_path):
    p=source(tmp_path);out=tmp_path/"out.json";expected=run(summary_path=p,output=out)
    legacy=out.read_bytes().replace(b"\n",b"\r\n");out.write_bytes(legacy)
    assert run(summary_path=p,output=out)==expected
    assert out.read_bytes()==legacy


def test_existing_numeric_serialization_keeps_float_return_contract():
    s=summary();s["aggregate"]={"trade_count":1,"total_r":1,"expectancy_r":1}
    result=build(s)
    assert type(result["aggregate"]["total_r"]) is float
    assert type(result["aggregate"]["expectancy_r"]) is float


def test_mixed_or_malformed_legacy_bytes_are_not_normalized_into_success(tmp_path):
    p=source(tmp_path);out=tmp_path/"out.json";run(summary_path=p,output=out)
    bad=out.read_bytes().replace(b"\n",b"\r\n",1);out.write_bytes(bad)
    with pytest.raises(RuntimeError):run(summary_path=p,output=out)
    assert out.read_bytes()==bad
