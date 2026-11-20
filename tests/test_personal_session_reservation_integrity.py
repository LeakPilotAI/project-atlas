"""Personal session correctness;in-memory coordination only,no financial store."""
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from app.services.quality_dips_personal_dependencies import PersonalSessionReservations


class Memory:
    def __init__(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE personal_sessions(id TEXT PRIMARY KEY,body TEXT,state TEXT)')
    @contextmanager
    def connect(self,readonly=False):
        with self.db:yield self.db


@pytest.mark.parametrize('failure',['revoked-pending','changed-body','removed-pending','changed-state','revoked-ack','changed-ack'])
def test_no_success_receipt_from_incomplete_or_changed_reservation(failure):
    ledger=Memory();allowed=[True];request={'grant':{'session_id':'synthetic-personal'}}
    def fault(phase):
        if phase=='after_pending':
            if failure=='revoked-pending':allowed[0]=False
            elif failure=='changed-body':ledger.db.execute("UPDATE personal_sessions SET body='foreign'");ledger.db.commit()
            elif failure=='removed-pending':ledger.db.execute('DELETE FROM personal_sessions');ledger.db.commit()
            elif failure=='changed-state':ledger.db.execute("UPDATE personal_sessions SET state='UNKNOWN'");ledger.db.commit()
        elif phase=='after_ack':
            if failure=='revoked-ack':allowed[0]=False
            elif failure=='changed-ack':ledger.db.execute("UPDATE personal_sessions SET state='UNKNOWN'");ledger.db.commit()
    port=PersonalSessionReservations(ledger=ledger,authorization=SimpleNamespace(verify=lambda _:allowed[0]),fault=fault)
    try:
        with pytest.raises(ValueError):port.reserve(request)
    finally:ledger.db.close()


def test_acknowledged_request_is_stable_and_single_use():
    ledger=Memory();request={'grant':{'session_id':'synthetic-personal'}}
    def fault(phase):
        if phase=='after_pending':request['grant']['session_id']='caller-mutated'
    port=PersonalSessionReservations(ledger=ledger,authorization=SimpleNamespace(verify=lambda _:True),fault=fault)
    original={'grant':{'session_id':'synthetic-personal'}}
    try:
        receipt=port.reserve(request);assert port.verify(original,receipt)
        assert not port.verify(request,receipt)
        with pytest.raises(ValueError,match='REPLAY_OR_UNCERTAIN'):port.reserve(original)
    finally:ledger.db.close()
