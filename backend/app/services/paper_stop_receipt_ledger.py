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
    def reconcile_restart_observation(self, session, *, lane_positions):
        """Compare durable Stop evidence to independently supplied read-only lane cuts.

        Caller-provided cuts are observations, not authenticated custody or an
        authorization to restart. Unknown/malformed cuts fail closed.
        """
        if type(lane_positions) is not dict or set(lane_positions) != {'QUALITY_DIPS', 'HYPERLIQUID'}:
            raise ValueError('STOP_RESTART_LANE_CUTS_REQUIRED')
        row = self.inspect_session(session)
        if row is None:
            raise StopReceiptConflict('STOP_RESTART_INTENT_MISSING')
        positions = {}
        for lane, cut in lane_positions.items():
            if type(cut) is not dict or set(cut) != {'open_positions', 'unsettled_orders'}:
                raise ValueError('STOP_RESTART_LANE_CUT_INVALID')
            if any(type(cut[k]) is not int or cut[k] < 0 for k in ('open_positions', 'unsettled_orders')):
                raise ValueError('STOP_RESTART_LANE_CUT_INVALID')
            positions[lane] = {'open_positions': cut['open_positions'],
                               'unsettled_orders': cut['unsettled_orders']}
        outstanding = any(x['open_positions'] or x['unsettled_orders'] for x in positions.values())
        return {'schema': 'ATLAS_PAPER_STOP_RESTART_OBSERVATION_V1',
                'stop_record_state': row['state'],
                'exposure_observed': bool(outstanding),
                'reconciliation_required': True,
                'startup_authorized': False, 'financial_authorized': False}
    def observe_native_account_restart(self, session, *, custody, grant):
        """Read existing custody-verified account cuts, never grant restart.

        Does not call verify_restart (which mutates the session journal).
        Missing resting-order evidence cannot be interpreted as zero orders.
        """
        from app.services.unified_portfolio_custody import UnifiedPortfolioCustody
        if type(custody) is not UnifiedPortfolioCustody:
            raise ValueError('STOP_RESTART_NATIVE_CUSTODY_REQUIRED')
        if type(grant) is not dict or grant.get('session_id') != session:
            raise ValueError('STOP_RESTART_SESSION_BINDING_REQUIRED')
        row = self.inspect_session(session)
        if row is None:
            raise StopReceiptConflict('STOP_RESTART_INTENT_MISSING')
        try:
            snapshot = custody.read_accounts(grant)
        except Exception as exc:
            raise StopReceiptConflict('STOP_RESTART_NATIVE_CUT_UNVERIFIED') from exc
        if (type(snapshot) is not dict or snapshot.get('state') != 'ACKNOWLEDGED'
                or type(snapshot.get('accounts')) is not dict
                or set(snapshot['accounts']) != {'QUALITY_DIPS', 'HYPERLIQUID'}):
            raise StopReceiptConflict('STOP_RESTART_NATIVE_CUT_UNVERIFIED')
        counts = {}
        for lane, account in snapshot['accounts'].items():
            if (type(account) is not dict or type(account.get('positions')) is not dict
                    or type(account.get('resting_orders')) is not dict
                    or not isinstance(account.get('source_head'), str)
                    or not account['source_head']):
                raise StopReceiptConflict('STOP_RESTART_NATIVE_CUT_UNVERIFIED')
            counts[lane] = {'open_positions': len(account['positions']),
                            'unsettled_orders': len(account['resting_orders'])}
        # Refuse a Stop intent/receipt that changed while native custody was read.
        if self.inspect_session(session) != row:
            raise StopReceiptConflict('STOP_RESTART_RECORD_CHANGED')
        return self.reconcile_restart_observation(session, lane_positions=counts)
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




