"""Offline-only durable PAPER stop intent/receipt ledger; grants no runtime authority."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

class StopReceiptConflict(ValueError):
    pass

class PaperStopReceiptLedger:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.is_symlink():
            raise ValueError("STOP_LEDGER_SYMLINK_FORBIDDEN")
        if not self.path.parent.is_dir():
            raise ValueError("STOP_LEDGER_PARENT_REQUIRED")
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS stop_receipts (session TEXT PRIMARY KEY, mode TEXT NOT NULL, state TEXT NOT NULL, receipt TEXT)")
    @contextmanager
    def _connect(self):
        """Close each SQLite handle even on errors; preserve transaction rollback."""
        db = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA busy_timeout=5000")
            with db:
                yield db
        finally:
            db.close()
    def reserve(self, session, mode):
        if not isinstance(session, str) or not session or len(session) > 256 or mode not in ("SHUTDOWN_FLATTEN", "EMERGENCY"):
            raise ValueError("STOP_INTENT_INVALID")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT mode,state,receipt FROM stop_receipts WHERE session=?", (session,)).fetchone()
            if row is None:
                db.execute("INSERT INTO stop_receipts VALUES (?,?,?,NULL)", (session,mode,"PENDING"))
                db.execute("COMMIT")
                return {"state":"PENDING","mode":mode,"receipt":None}
            if row[0] != mode:
                db.execute("ROLLBACK")
                raise StopReceiptConflict("STOP_MODE_CHANGED")
            db.execute("COMMIT")
            if row[1] == "PENDING" and row[2] is None:
                return {"state": "PENDING", "mode": mode, "receipt": None}
            if row[1] != "FINISHED" or row[2] is None:
                raise StopReceiptConflict("STOP_LEDGER_CORRUPT")
            try:
                receipt = json.loads(row[2])
            except (ValueError, TypeError) as exc:
                raise StopReceiptConflict("STOP_LEDGER_CORRUPT") from exc
            if (not isinstance(receipt, dict) or receipt.get("phase") != "FINISHED"
                    or not isinstance(receipt.get("outcome"), dict)
                    or receipt["outcome"].get("mode") != mode):
                raise StopReceiptConflict("STOP_LEDGER_CORRUPT")
            return {"state": "FINISHED", "mode": mode, "receipt": receipt}
    def reserve_fresh(self, session, mode):
        """Only a newly inserted intent grants this caller the stop attempt.

        Existing pending intents (including crash leftovers) cannot be replayed.
        """
        if not isinstance(session, str) or not session or len(session) > 256 or mode not in ("SHUTDOWN_FLATTEN", "EMERGENCY"):
            raise ValueError("STOP_INTENT_INVALID")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT mode,state FROM stop_receipts WHERE session=?", (session,)).fetchone()
            if existing is not None:
                db.execute("ROLLBACK")
                raise StopReceiptConflict("STOP_INTENT_ALREADY_EXISTS")
            db.execute("INSERT INTO stop_receipts VALUES (?,?,?,NULL)", (session, mode, "PENDING"))
            db.execute("COMMIT")
        return {"state": "PENDING", "mode": mode, "receipt": None}

    def inspect_session(self, session):
        """One-snapshot read-only cross-mode inspection; never claims a stop."""
        if not isinstance(session, str) or not session or len(session) > 256:
            raise ValueError("STOP_INTENT_INVALID")
        with self._connect() as db:
            row = db.execute("SELECT mode,state,receipt FROM stop_receipts WHERE session=?", (session,)).fetchone()
        if row is None:
            return None
        mode, state, serialized = row
        if mode not in ("SHUTDOWN_FLATTEN", "EMERGENCY"):
            raise StopReceiptConflict("STOP_LEDGER_CORRUPT")
        if state == "PENDING" and serialized is None:
            return {"state": "PENDING", "mode": mode, "receipt": None}
        if state != "FINISHED" or serialized is None:
            raise StopReceiptConflict("STOP_LEDGER_CORRUPT")
        try:
            receipt = json.loads(serialized)
        except (ValueError, TypeError) as exc:
            raise StopReceiptConflict("STOP_LEDGER_CORRUPT") from exc
        if (not isinstance(receipt, dict) or receipt.get("phase") != "FINISHED"
                or not isinstance(receipt.get("outcome"), dict)
                or receipt["outcome"].get("mode") != mode):
            raise StopReceiptConflict("STOP_LEDGER_CORRUPT")
        return {"state": "FINISHED", "mode": mode, "receipt": receipt}

    def summarize_recovery(self):
        """Read-only all-session recovery inventory; never certifies positions flat."""
        with self._connect() as db:
            rows = db.execute("SELECT mode,state,receipt FROM stop_receipts").fetchall()
        pending = finished = incomplete = 0
        for mode, state, serialized in rows:
            if mode not in ("SHUTDOWN_FLATTEN", "EMERGENCY"):
                raise StopReceiptConflict("STOP_LEDGER_CORRUPT")
            if state == "PENDING" and serialized is None:
                pending += 1
                continue
            if state != "FINISHED" or serialized is None:
                raise StopReceiptConflict("STOP_LEDGER_CORRUPT")
            try:
                receipt = json.loads(serialized)
            except (ValueError, TypeError) as exc:
                raise StopReceiptConflict("STOP_LEDGER_CORRUPT") from exc
            if (not isinstance(receipt, dict) or receipt.get("phase") != "FINISHED"
                    or not isinstance(receipt.get("outcome"), dict)
                    or receipt["outcome"].get("mode") != mode):
                raise StopReceiptConflict("STOP_LEDGER_CORRUPT")
            status = receipt["outcome"].get("status")
            if not isinstance(status, str) or not status:
                raise StopReceiptConflict("STOP_LEDGER_CORRUPT")
            if status != "FLATTENED":
                incomplete += 1
            finished += 1
        return {"schema": "ATLAS_PAPER_STOP_RECOVERY_INVENTORY_V1",
                "pending_unverified": pending, "receipts_recorded_not_flat_verified": finished,
                "receipts_without_flatten_claim": incomplete,
                "requires_independent_position_reconciliation": bool(pending or finished),
                "financial_authorized": False, "startup_authorized": False}
    def recover(self, session, mode):
        """Read-only restart inspection: pending is NEVER proof of flat positions."""
        row = self.reserve_existing(session, mode)
        if row["state"] == "PENDING":
            return {"state": "SHUTDOWN_UNVERIFIED", "mode": mode, "receipt": None}
        return {"state": "RECEIPT_RECORDED", "mode": mode, "receipt": row["receipt"]}

    def reserve_existing(self, session, mode):
        if not isinstance(session, str) or not session or len(session) > 256 or mode not in ("SHUTDOWN_FLATTEN", "EMERGENCY"):
            raise ValueError("STOP_INTENT_INVALID")
        with self._connect() as db:
            row = db.execute("SELECT mode,state,receipt FROM stop_receipts WHERE session=?", (session,)).fetchone()
        if row is None or row[0] != mode:
            raise StopReceiptConflict("STOP_INTENT_UNVERIFIED")
        if row[1] == "PENDING" and row[2] is None:
            return {"state": "PENDING", "mode": mode, "receipt": None}
        if row[1] != "FINISHED" or row[2] is None:
            raise StopReceiptConflict("STOP_LEDGER_CORRUPT")
        try:
            receipt = json.loads(row[2])
        except (ValueError, TypeError) as exc:
            raise StopReceiptConflict("STOP_LEDGER_CORRUPT") from exc
        if (not isinstance(receipt, dict) or receipt.get("phase") != "FINISHED"
                or not isinstance(receipt.get("outcome"), dict)
                or receipt["outcome"].get("mode") != mode):
            raise StopReceiptConflict("STOP_LEDGER_CORRUPT")
        return {"state": "FINISHED", "mode": mode, "receipt": receipt}

    def finish(self, session, mode, receipt):
        if not isinstance(receipt, dict) or receipt.get("phase") != "FINISHED" or not isinstance(receipt.get("outcome"), dict) or receipt["outcome"].get("mode") != mode:
            raise ValueError("STOP_RECEIPT_INVALID")
        serialized = json.dumps(receipt, sort_keys=True, separators=(",",":"), allow_nan=False)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT mode,state,receipt FROM stop_receipts WHERE session=?", (session,)).fetchone()
            if row is None or row[0] != mode or row[1] != "PENDING":
                db.execute("ROLLBACK")
                raise StopReceiptConflict("STOP_INTENT_NOT_PENDING")
            db.execute("UPDATE stop_receipts SET state='FINISHED', receipt=? WHERE session=?", (serialized,session))
            db.execute("COMMIT")
        return json.loads(serialized)




