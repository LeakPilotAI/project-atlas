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
