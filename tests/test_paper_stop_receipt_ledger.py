import pytest
from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger, StopReceiptConflict

def test_stop_intent_survives_reopen_and_cannot_change_mode(tmp_path):
    path = tmp_path / "stop.sqlite"
    ledger = PaperStopReceiptLedger(path)
    assert ledger.reserve("session-1", "SHUTDOWN_FLATTEN")["state"] == "PENDING"
    reopened = PaperStopReceiptLedger(path)
    assert reopened.reserve("session-1", "SHUTDOWN_FLATTEN")["state"] == "PENDING"
    with pytest.raises(StopReceiptConflict):
        reopened.reserve("session-1", "EMERGENCY")

def test_stop_receipt_survives_reopen_and_refuses_duplicate_finish(tmp_path):
    path = tmp_path / "stop.sqlite"
    ledger = PaperStopReceiptLedger(path)
    ledger.reserve("session-1", "SHUTDOWN_FLATTEN")
    receipt = {"phase":"FINISHED","outcome":{"mode":"SHUTDOWN_FLATTEN","status":"SHUTDOWN_INCOMPLETE"}}
    ledger.finish("session-1", "SHUTDOWN_FLATTEN", receipt)
    assert PaperStopReceiptLedger(path).reserve("session-1", "SHUTDOWN_FLATTEN")["receipt"] == receipt
    with pytest.raises(StopReceiptConflict):
        ledger.finish("session-1", "SHUTDOWN_FLATTEN", receipt)

def test_stop_receipt_requires_reserved_intent_and_matching_mode(tmp_path):
    ledger = PaperStopReceiptLedger(tmp_path / "stop.sqlite")
    receipt = {"phase":"FINISHED","outcome":{"mode":"SHUTDOWN_FLATTEN","status":"SHUTDOWN_INCOMPLETE"}}
    with pytest.raises(StopReceiptConflict):
        ledger.finish("missing", "SHUTDOWN_FLATTEN", receipt)
    ledger.reserve("s", "EMERGENCY")
    with pytest.raises(ValueError):
        ledger.finish("s", "EMERGENCY", receipt)
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import pytest
from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger, StopReceiptConflict

def test_simultaneous_reservations_one_intent(tmp_path):
    path = tmp_path / "stop.sqlite"
    def reserve(_):
        return PaperStopReceiptLedger(path).reserve("same", "SHUTDOWN_FLATTEN")
    PaperStopReceiptLedger(path)
    with ThreadPoolExecutor(max_workers=12) as pool:
        rows = list(pool.map(reserve, range(24)))
    assert all(row == {"state":"PENDING","mode":"SHUTDOWN_FLATTEN","receipt":None} for row in rows)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM stop_receipts").fetchone()[0] == 1

def test_interrupted_stop_remains_pending_not_flat(tmp_path):
    path = tmp_path / "stop.sqlite"
    PaperStopReceiptLedger(path).reserve("interrupted", "SHUTDOWN_FLATTEN")
    recovered = PaperStopReceiptLedger(path).reserve("interrupted", "SHUTDOWN_FLATTEN")
    assert recovered["state"] == "PENDING"
    assert recovered["receipt"] is None

def test_concurrent_finishes_only_one_wins(tmp_path):
    path = tmp_path / "stop.sqlite"
    PaperStopReceiptLedger(path).reserve("same", "SHUTDOWN_FLATTEN")
    receipt = {"phase":"FINISHED","outcome":{"mode":"SHUTDOWN_FLATTEN","status":"SHUTDOWN_INCOMPLETE"}}
    def finish(_):
        try:
            PaperStopReceiptLedger(path).finish("same", "SHUTDOWN_FLATTEN", receipt)
            return "FINISHED"
        except StopReceiptConflict:
            return "CONFLICT"
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(finish, range(12)))
    assert results.count("FINISHED") == 1
    assert results.count("CONFLICT") == 11

def test_corrupted_receipt_never_treated_as_complete(tmp_path):
    path = tmp_path / "stop.sqlite"
    ledger = PaperStopReceiptLedger(path)
    ledger.reserve("same", "SHUTDOWN_FLATTEN")
    with sqlite3.connect(path) as db:
        db.execute("UPDATE stop_receipts SET state='FINISHED',receipt='invalid-json' WHERE session='same'")
    with pytest.raises(ValueError):
        ledger.reserve("same", "SHUTDOWN_FLATTEN")
def test_read_only_recovery_does_not_create_missing_intent(tmp_path):
    ledger = PaperStopReceiptLedger(tmp_path / "stop.sqlite")
    with pytest.raises(StopReceiptConflict):
        ledger.recover("missing", "SHUTDOWN_FLATTEN")
    ledger.reserve("s", "SHUTDOWN_FLATTEN")
    assert ledger.recover("s", "SHUTDOWN_FLATTEN") == {
        "state":"SHUTDOWN_UNVERIFIED","mode":"SHUTDOWN_FLATTEN","receipt":None}
    receipt = {"phase":"FINISHED","outcome":{"mode":"SHUTDOWN_FLATTEN","status":"SHUTDOWN_INCOMPLETE"}}
    ledger.finish("s", "SHUTDOWN_FLATTEN", receipt)
    assert PaperStopReceiptLedger(ledger.path).recover("s", "SHUTDOWN_FLATTEN") == {
        "state":"RECEIPT_RECORDED","mode":"SHUTDOWN_FLATTEN","receipt":receipt}
