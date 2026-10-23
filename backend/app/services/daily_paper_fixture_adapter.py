"""Fixture-row adapter only: never opens a legacy journal or writes production."""
import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path


def _entry_clock(row):
    if "entry_timestamp" not in row:
        return None  # Legacy import remains possible; historical reporting refuses missing evidence.
    try:
        value = datetime.fromisoformat(row["entry_timestamp"])
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Unqualified entry timestamp")
        return value
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid supplied legacy entry timestamp") from error


def validate_close(row):
    if row.get("status") != "closed" or row.get("result") in (None, "INTERRUPTED", "SESSION_ROLL"):
        raise ValueError("Incomplete or interrupted close is not liquidation")
    if type(row.get("exit_reason")) is not str or not row["exit_reason"]:
        raise ValueError("Missing close reason")
    stamp = datetime.fromisoformat(row["exit_timestamp"])
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Unqualified close timestamp")
    for key in ("actual_exit_price", "gross_pnl_r", "net_pnl_r"):
        value = Decimal(str(row[key]))
        if not value.is_finite() or key == "actual_exit_price" and value <= 0:
            raise ValueError("Invalid recorded close accounting")


def adapt_legacy_rows(rows, *, currency):
    if type(currency) is not str or not currency:
        raise ValueError("Explicit reviewed settlement currency required")
    opened, closed = {}, {}
    for row in rows:
        ident, event = row.get("trade_id"), row.get("event")
        if type(ident) is not str or not ident:
            raise ValueError("Missing trade identity")
        if event not in ("open", "close", "mark"):
            raise ValueError("Unsupported legacy event; partial fills require separate policy")
        if any(key in row for key in ("remaining_quantity", "partial_close", "filled_quantity")):
            raise ValueError("Ambiguous partial-close accounting")
        if event == "open":
            if row.get("trade_type") != "PAPER" or row.get("status") != "open":
                raise ValueError("Only explicit open PAPER source records supported")
            _entry_clock(row)
            if ident in closed:
                raise ValueError("Reopened closed identity")
            if ident in opened and opened[ident] != row:
                raise ValueError("Conflicting open records")
            opened[ident] = dict(row)
        else:
            if ident not in opened:
                raise ValueError("Orphan legacy record")
            if event == "close":
                validate_close(row)
                original = opened[ident]
                opened_at = _entry_clock(original)
                if opened_at is not None and (
                    row.get("entry_timestamp") != original["entry_timestamp"]
                    or datetime.fromisoformat(row["exit_timestamp"]) < opened_at
                ):
                    raise ValueError("Close/source entry chronology mismatch")
                for key in ("symbol", "side", "trade_type"):
                    if key not in original or row.get(key) != original[key]:
                        raise ValueError("Close/source position identity mismatch")
                for key in ("position_size", "actual_entry_price", "risk_price", "fees_bps", "slippage_bps"):
                    try:
                        if isinstance(row.get(key), bool) or isinstance(original.get(key), bool):
                            raise TypeError("Boolean accounting evidence")
                        source, closed_value = Decimal(str(original[key])), Decimal(str(row[key]))
                        if not source.is_finite() or not closed_value.is_finite() or source != closed_value:
                            raise ValueError("Close/source accounting mismatch")
                    except (KeyError, TypeError, ArithmeticError) as error:
                        raise ValueError("Missing or invalid close/source accounting evidence") from error
                if ident in closed and closed[ident] != row:
                    raise ValueError("Conflicting close records")
                closed[ident] = dict(row)
    result = []
    for ident, row in sorted(opened.items()):
        if ident in closed:
            continue
        if row.get("trade_type") != "PAPER" or row.get("status") != "open":
            raise ValueError("Only explicit open PAPER records supported")
        result.append({key: row[key] for key in ("trade_id", "symbol", "side", "actual_entry_price",
                                                "risk_price", "fees_bps", "slippage_bps")}
                      | {"quantity": row["position_size"], "currency": currency})
        stamp = _entry_clock(row)
        if stamp is not None:
            # Existing fixture inventory uses whole-second UTC cutoffs. Preserve the
            # exact supplied clock too; this conversion does not authenticate it.
            result[-1].update(opened_at=(stamp.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC))
                             // timedelta(seconds=1), source_entry_timestamp=row["entry_timestamp"])
    # Return independent plain data; do not mutate original evidence.
    return json.loads(json.dumps(result))


def migrate_fixture_rows(path, rows, *, currency, fault=lambda phase: None):
    """Atomic import into an explicitly provisioned EMPTY disposable fixture ledger."""
    positions = adapt_legacy_rows(rows, currency=currency)
    body = json.dumps({"rows": rows, "currency": currency}, sort_keys=True, allow_nan=False)
    digest = hashlib.sha256(body.encode()).hexdigest()
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rw", uri=True, timeout=1) as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS migration(digest TEXT PRIMARY KEY, body TEXT NOT NULL)")
        previous = db.execute("SELECT digest,body FROM migration").fetchall()
        if previous:
            if previous != [(digest, body)]:
                raise ValueError("Conflicting migration snapshot")
            return digest
        if db.execute("SELECT COUNT(*) FROM positions").fetchone()[0] or db.execute("SELECT COUNT(*) FROM exits").fetchone()[0]:
            raise ValueError("Migration target not empty")
        fault("before_import")
        db.executemany("INSERT INTO positions VALUES(?,?)", [(p["trade_id"], json.dumps(p, sort_keys=True)) for p in positions])
        db.execute("INSERT INTO migration VALUES(?,?)", (digest, body))
        fault("before_commit")
        db.commit()
        fault("after_commit")
    return digest


def isolated_shutdown(ledger, session, quotes, *, now, max_age, quiesce, drain, stop_owned):
    """Dependency-injected integration contract, not a Windows service hook."""
    from app.services.daily_paper_liquidation import liquidate

    if quiesce() is not True or drain() is not True:
        return {"outcome": "INCOMPLETE", "reason": "WRITERS_NOT_QUIESCENT", "services_stopped": False}
    report = liquidate(ledger, session, quotes, now=now, max_age=max_age)
    if not report["complete"]:
        return {"outcome": "INCOMPLETE", "report": report, "services_stopped": False}
    stopped = stop_owned() is True
    return {"outcome": "COMPLETE" if stopped else "INCOMPLETE", "report": report, "services_stopped": stopped}
