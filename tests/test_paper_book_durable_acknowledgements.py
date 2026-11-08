import json
from pathlib import Path

import pytest
from app.core import durable_io
from app.investment import paper_book


def book(tmp_path):
    return paper_book.PaperBook(cash=1000, state_path=tmp_path/'state.json', ledger_path=tmp_path/'ledger.jsonl')


@pytest.mark.parametrize('operation', ['save','ledger'])
def test_fsync_failure_is_not_success(tmp_path, monkeypatch, operation):
    instance=book(tmp_path)
    error=OSError('synthetic fsync failure')
    def fail(_descriptor):
        raise error
    monkeypatch.setattr(durable_io.os,'fsync',fail)
    with pytest.raises(OSError) as raised:
        instance.save() if operation=='save' else instance._ledger('fixture',{'value':1})
    assert raised.value is error
    with pytest.raises(paper_book.PaperBookStateUnavailable) as refused:
        instance.snapshot()
    assert refused.value.__cause__ is error


@pytest.mark.parametrize('operation', ['save','ledger'])
@pytest.mark.parametrize('fault', ['short','flush'])
def test_full_write_and_flush_are_required(tmp_path, monkeypatch, operation, fault):
    instance=book(tmp_path)
    original_open=Path.open
    class FaultStream:
        def __init__(self, stream):self.stream=stream
        def __enter__(self):return self
        def __exit__(self,*args):return self.stream.__exit__(*args)
        def write(self,text):return self.stream.write(text[:-1] if fault=='short' else text)
        def flush(self):
            if fault=='flush':raise OSError('synthetic flush failure')
            self.stream.flush()
        def fileno(self):return self.stream.fileno()
    def open_fault(path,mode='r',*args,**kwargs):
        stream=original_open(path,mode,*args,**kwargs)
        return FaultStream(stream) if path.parent==tmp_path and mode in ('a','x') else stream
    monkeypatch.setattr(Path,'open',open_fault)
    with pytest.raises(OSError):
        instance.save() if operation=='save' else instance._ledger('fixture',{'value':1})
    with pytest.raises(paper_book.PaperBookStateUnavailable):instance.save()


@pytest.mark.parametrize('stage',['replace','parent'])
def test_snapshot_publication_failure_preserves_evidence_and_refusal(tmp_path,monkeypatch,stage):
    instance=book(tmp_path);instance.save();prior=instance.state_path.read_bytes()
    instance.cash=900
    error=OSError('synthetic publication failure')
    def fail(*args):raise error
    if stage=='replace':monkeypatch.setattr(Path,'replace',fail)
    else:monkeypatch.setattr(paper_book,'sync_parent',fail)
    with pytest.raises(OSError) as raised:instance.save()
    assert raised.value is error
    if stage=='replace':
        assert instance.state_path.read_bytes()==prior
        assert list(tmp_path.glob('*.tmp'))
    else:assert json.loads(instance.state_path.read_bytes())['cash']==900
    for operation in (lambda:instance.save(),lambda:instance.research_buy('SPY',10,10),
                      lambda:instance.seed_benchmark(10),lambda:instance.submit_from_plan(None),
                      lambda:instance.cancel_open('SPY'),lambda:instance.try_fill('SPY',10,session='MARKET_OPEN'),
                      lambda:instance.mark({'SPY':10}),lambda:instance.snapshot(),lambda:instance.as_legacy_account()):
        with pytest.raises(paper_book.PaperBookStateUnavailable):operation()


def test_committed_ledger_then_failed_snapshot_is_not_a_transaction(tmp_path,monkeypatch):
    instance=book(tmp_path);instance.save();before=instance.state_path.read_bytes()
    real=durable_io.os.fsync;calls=0
    def fail_second(fd):
        nonlocal calls
        calls+=1
        if calls==2:raise OSError('synthetic snapshot fsync failure')
        return real(fd)
    monkeypatch.setattr(durable_io.os,'fsync',fail_second)
    with pytest.raises(OSError):instance.research_buy('SPY',100,100)
    rows=[json.loads(line) for line in instance.ledger_path.read_text().splitlines()]
    assert len(rows)==1 and rows[0]['kind']=='research_buy'
    assert instance.state_path.read_bytes()==before
    with pytest.raises(paper_book.PaperBookStateUnavailable):instance.research_buy('SPY',100,100)
    assert len(instance.ledger_path.read_text().splitlines())==1


def test_successful_publication_retains_legacy_json(tmp_path):
    instance=book(tmp_path)
    instance.research_buy('SPY',100,100)
    loaded=paper_book.PaperBook.load(instance.state_path,ledger_path=instance.ledger_path)
    assert loaded.cash==900
    assert loaded.positions['SPY'].shares==1
    assert len(loaded.fills)==1
    assert not list(tmp_path.glob('*.tmp'))
