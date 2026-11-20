import hashlib
import json

import pytest
from app.core import durable_io
from app.investment.paper_book import PaperBook
from app.investment.paper_book_audit import PaperBookAuditRefused, audit_fill_subset


def audit(state, ledger):
    return audit_fill_subset(state,ledger,expected_snapshot_sha256=hashlib.sha256(state).hexdigest(),
                             expected_ledger_sha256=hashlib.sha256(ledger).hexdigest())


def test_actual_successful_book_is_matched_subset_without_authority(tmp_path):
    state=tmp_path/'state.json';ledger=tmp_path/'ledger.jsonl'
    book=PaperBook(cash=1000,state_path=state,ledger_path=ledger)
    book.research_buy('SPY',100,100)
    before=(state.read_bytes(),ledger.read_bytes())
    result=audit(*before)
    assert result['status']=='MATCHED_RECORDED_FILL_SUBSET'
    assert result['snapshot_fill_n']==result['ledger_fill_n']==1
    assert all(result[k] is False for k in ('startup_authorized','recovery_authorized','paper_trading_authorized',
        'live_trading_authorized','repair_performed','full_book_consistency_established','source_ownership_established'))
    assert before==(state.read_bytes(),ledger.read_bytes())


def test_actual_partial_publication_exposes_retained_ledger_event(tmp_path,monkeypatch):
    state=tmp_path/'state.json';ledger=tmp_path/'ledger.jsonl'
    book=PaperBook(cash=1000,state_path=state,ledger_path=ledger);book.save()
    real=durable_io.os.fsync;calls=0
    def fail_second(fd):
        nonlocal calls
        calls+=1
        if calls==2:raise OSError('synthetic partial publication')
        return real(fd)
    monkeypatch.setattr(durable_io.os,'fsync',fail_second)
    with pytest.raises(OSError):book.research_buy('SPY',100,100)
    result=audit(state.read_bytes(),ledger.read_bytes())
    assert result['status']=='REQUIRES_RECONCILIATION'
    assert result['ledger_payloads_missing_from_snapshot']==1
    assert result['snapshot_fill_n']==0


@pytest.mark.parametrize('kind',['missing_ledger','repeated_ledger'])
def test_missing_and_repeated_payloads_are_not_repaired(tmp_path,kind):
    state=tmp_path/'state.json';ledger=tmp_path/'ledger.jsonl'
    book=PaperBook(cash=1000,state_path=state,ledger_path=ledger);book.research_buy('SPY',100,100)
    raw=ledger.read_bytes()
    result=audit(state.read_bytes(),b'' if kind=='missing_ledger' else raw+raw)
    assert result['status']=='REQUIRES_RECONCILIATION'
    assert result['snapshot_payloads_missing_from_ledger' if kind=='missing_ledger' else 'repeated_ledger_payload_n']==1


@pytest.mark.parametrize('raw',[b'\n',b'{',b'{"kind":"fill","kind":"order"}',b'{"kind":"fill","price":NaN}'])
def test_malformed_journal_refused(raw):
    with pytest.raises(PaperBookAuditRefused):audit(b'{"fills":[]}',raw)


def test_caller_pin_mismatch_refused_before_parse():
    with pytest.raises(PaperBookAuditRefused,match='commitment'):
        audit_fill_subset(b'{',b'',expected_snapshot_sha256='a'*64,expected_ledger_sha256='b'*64)


def test_empty_fills_and_unexamined_order_scope_are_insufficient():
    result=audit(b'{"fills":[]}',json.dumps({'kind':'order','order_id':'fixture'}).encode()+b'\n')
    assert result['status']=='INSUFFICIENT_EVIDENCE'
    assert result['unexamined_event_kinds']=={'order':1}
