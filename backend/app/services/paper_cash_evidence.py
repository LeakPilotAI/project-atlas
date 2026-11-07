"""Append-preserved fixture cash evidence. No banking/provider authenticity claim."""
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path


def derive_fixture_realizations(path):
    """Read one ledger snapshot; each partial counted once, final leg is residual."""
    from app.services.daily_paper_liquidation import _partial_position
    from app.services.paper_partial_accounting import replay_partial_fills

    events = []
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("BEGIN")
        if db.execute("SELECT COUNT(*) FROM partial_fills WHERE trade NOT IN (SELECT id FROM positions)").fetchone()[0] or db.execute("SELECT COUNT(*) FROM exits WHERE id NOT IN (SELECT id FROM positions)").fetchone()[0]:
            raise ValueError("Orphan committed accounting evidence")
        for ident, body in db.execute("SELECT id,body FROM positions ORDER BY id"):
            position = json.loads(body)
            fills, prior = [], Decimal(0)
            for raw, in db.execute("SELECT body FROM partial_fills WHERE trade=? ORDER BY rowid", (ident,)):
                fill = json.loads(raw)
                fills.append(fill)
                state = replay_partial_fills(_partial_position(position), fills)
                total = Decimal(state["net_currency"])
                events.append({"id": "fill:" + fill["fill_id"], "kind": "REALIZED_NET",
                               "currency": state["currency"], "amount": str(total - prior),
                               "timestamp": datetime.fromtimestamp(fill["timestamp"], UTC).isoformat(),
                               "source_digest": hashlib.sha256(raw.encode()).hexdigest()})
                prior = total
            closed = db.execute("SELECT body FROM exits WHERE id=?", (ident,)).fetchone()
            if closed:
                exit_row = json.loads(closed[0])
                if exit_row.get("reason") == "RECORDED_PARTIAL_FILLS_COMPLETE":
                    if not fills or not state["complete"] or Decimal(exit_row["net_pnl_r"]) != Decimal(state["net_r_original_risk"]):
                        raise ValueError("Finalization quantity/P&L mismatch")
                    continue
                money = exit_row.get("currency_accounting")
                if not money:
                    raise ValueError("Missing currency evidence; daily accounting incomplete")
                events.append({"id": "exit:" + ident, "kind": "REALIZED_NET", "currency": money["currency"],
                               "amount": str(Decimal(money["net"]) - prior),
                               "timestamp": datetime.fromtimestamp(exit_row["exit_timestamp"], UTC).isoformat(),
                               "source_digest": hashlib.sha256(closed[0].encode()).hexdigest()})
    return events


def append_cash_fixture(path, event):
    required = {"id", "kind", "currency", "amount", "timestamp", "source_digest"}
    if set(event) != required or event["kind"] not in ("OPENING", "DEPOSIT", "WITHDRAWAL", "REALIZED_NET"):
        raise ValueError("Exact cash evidence required")
    for key in ("id", "currency", "source_digest"):
        if type(event[key]) is not str or not event[key]:
            raise ValueError("Missing cash provenance")
    stamp = datetime.fromisoformat(event["timestamp"])
    value = Decimal(event["amount"])
    if stamp.tzinfo is None or not value.is_finite():
        raise ValueError("Invalid cash clock/amount")
    if event["kind"] in ("DEPOSIT", "WITHDRAWAL") and value <= 0:
        raise ValueError("Positive cashflow magnitude required")
    body = json.dumps(event, sort_keys=True)
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rw", uri=True) as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS cash_evidence(id TEXT PRIMARY KEY,body TEXT,parent TEXT,digest TEXT)")
        previous = ""
        duplicate = False
        for ident, old, parent, digest in db.execute("SELECT id,body,parent,digest FROM cash_evidence ORDER BY rowid"):
            if parent != previous or hashlib.sha256((parent + old).encode()).hexdigest() != digest:
                raise ValueError("Corrupt cash evidence")
            previous = digest
            if ident == event["id"]:
                if old != body:
                    raise ValueError("Conflicting cash identity")
                duplicate = True
        if duplicate:
            return
        db.execute("INSERT INTO cash_evidence VALUES(?,?,?,?)",
                   (event["id"], body, previous, hashlib.sha256((previous + body).encode()).hexdigest()))
