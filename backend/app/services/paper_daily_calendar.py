"""Explicit offline daily cash reconciliation; no implied market valuation."""
import hashlib
import json
import sqlite3
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo


def publish_daily_fixture(path, *, local_date, timezone, evidence):
    zone = ZoneInfo(timezone)
    day = date.fromisoformat(local_date)
    start = datetime.combine(day, time(), zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time(), zone).astimezone(UTC)
    # Evidence is explicit supplied fixture data, not independently authenticated cash.
    opening = Decimal(evidence["opening_cash"])
    totals = {key: Decimal(0) for key in ("cashflow", "realized_net")}
    if not opening.is_finite() or not evidence.get("currency"):
        raise ValueError("Missing cash evidence")
    seen = set()
    for item in evidence["events"]:
        if item["id"] in seen or item["currency"] != evidence["currency"]:
            raise ValueError("Duplicate or mixed-currency cash event")
        seen.add(item["id"])
        stamp = datetime.fromisoformat(item["timestamp"])
        if stamp.tzinfo is None:
            raise ValueError("Unqualified event timestamp")
        value = Decimal(item["amount"])
        if not value.is_finite() or item["kind"] not in totals:
            raise ValueError("Invalid cash event")
        if start <= stamp.astimezone(UTC) < end:
            totals[item["kind"]] += value
    report = {"date": local_date, "timezone": timezone, "start_utc": start.isoformat(),
              "end_utc": end.isoformat(), "opening_cash": str(opening),
              **{k: str(v) for k, v in totals.items()},
              "ending_cash": str(opening + sum(totals.values())), "total_equity": None,
              "equity_status": "UNAVAILABLE_NO_MARK_TO_MARKET_EVIDENCE",
              "unresolved": evidence["unresolved"],
              "shutdown": "INCOMPLETE" if evidence["unresolved"] else "CASH_RECONCILED_ONLY",
              "production_authorized": False}
    body = json.dumps(report, sort_keys=True)
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rw", uri=True) as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS daily_history(id INTEGER PRIMARY KEY,body TEXT,parent TEXT,digest TEXT)")
        parent = ""
        for old, prior, digest in db.execute("SELECT body,parent,digest FROM daily_history ORDER BY id"):
            if prior != parent or hashlib.sha256((prior + old).encode()).hexdigest() != digest:
                raise ValueError("Corrupt daily history")
            parent = digest
        db.execute("INSERT INTO daily_history(body,parent,digest) VALUES(?,?,?)",
                   (body, parent, hashlib.sha256((parent + body).encode()).hexdigest()))
    return report
