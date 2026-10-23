"""As-of fixture inventory reconstruction; not independent historical availability."""
import json
import sqlite3
from decimal import Decimal
from pathlib import Path


def historical_fixture_inventory(path, *, cutoff):
    if type(cutoff) is not int:
        raise ValueError("Explicit UTC epoch cutoff required")
    result = []
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("BEGIN")
        for ident, body in db.execute("SELECT id,body FROM positions ORDER BY id"):
            p = json.loads(body)
            opened = p.get("opened_at")
            if type(opened) is not int:
                raise ValueError("Historical opening timestamp unavailable")
            if opened >= cutoff:
                continue
            original = Decimal(str(p["quantity"]))
            if not original.is_finite() or original <= 0:
                raise ValueError("Invalid original quantity")
            remaining = original
            prior = opened
            for raw, in db.execute("SELECT body FROM partial_fills WHERE trade=? ORDER BY rowid", (ident,)):
                fill = json.loads(raw)
                clock = fill["timestamp"]
                amount = Decimal(str(fill["quantity"]))
                if type(clock) is not int or clock < prior or not amount.is_finite() or amount <= 0:
                    raise ValueError("Contradictory historical fill")
                prior = clock
                if clock < cutoff:
                    remaining -= amount
            if remaining < 0:
                raise ValueError("Historical overclose")
            closed = db.execute("SELECT body FROM exits WHERE id=?", (ident,)).fetchone()
            if closed:
                row = json.loads(closed[0])
                if type(row.get("exit_timestamp")) is not int or row["exit_timestamp"] < opened:
                    raise ValueError("Contradictory final exit clock")
                if row["exit_timestamp"] < cutoff:
                    remaining = Decimal(0)
            result.append({"trade_id": ident, "original_quantity": str(original),
                           "remaining_quantity": str(remaining), "opened_at": opened})
    return {"cutoff_exclusive": cutoff, "positions": result,
            "unresolved": [row["trade_id"] for row in result if Decimal(row["remaining_quantity"]) > 0],
            "historical_availability_authenticated": False}
