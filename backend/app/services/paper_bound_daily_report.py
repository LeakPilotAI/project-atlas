"""Fixture-only daily reports bound to cash and position ledger snapshots."""
import hashlib
import json
import sqlite3
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from app.services.paper_cash_evidence import derive_fixture_realizations
from app.services.paper_exit_audit import audit_fixture_exits
from app.services.paper_historical_inventory import historical_fixture_inventory


def publish_bound_daily(path, *, day, timezone, currency, fault=lambda phase: None, inventory=None):
    zone = ZoneInfo(timezone)
    local = date.fromisoformat(day)
    start = datetime.combine(local, time(), zone).astimezone(UTC)
    end = datetime.combine(local + timedelta(days=1), time(), zone).astimezone(UTC)
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rw", uri=True, timeout=1) as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")  # Freeze cooperative writers across source reads/publication.
        audit_fixture_exits(path)  # Refuse contradictory exits before publishing reports.
        cash, parent = [], ""
        for body, previous, digest in db.execute("SELECT body,parent,digest FROM cash_evidence ORDER BY rowid"):
            if previous != parent or hashlib.sha256((previous + body).encode()).hexdigest() != digest:
                raise ValueError("Corrupt cash evidence")
            parent = digest
            event = json.loads(body)
            if (set(event) != {"id", "kind", "currency", "amount", "timestamp", "source_digest"}
                    or event["kind"] not in ("OPENING", "DEPOSIT", "WITHDRAWAL", "REALIZED_NET")
                    or any(type(event[key]) is not str or not event[key] for key in ("id", "currency", "source_digest"))
                    or datetime.fromisoformat(event["timestamp"]).tzinfo is None
                    or not Decimal(event["amount"]).is_finite()
                    or event["kind"] in ("DEPOSIT", "WITHDRAWAL") and Decimal(event["amount"]) <= 0):
                raise ValueError("Malformed historical cash evidence")
            cash.append(event)
        openings = [e for e in cash if e["currency"] == currency and e["kind"] == "OPENING"
                    and datetime.fromisoformat(e["timestamp"]).astimezone(UTC) == start]
        if len(openings) != 1:
            raise ValueError("Exactly one boundary-bound opening balance required")
        realized = derive_fixture_realizations(path)
        # Imported REALIZED_NET claims must match exact derived events, never added twice.
        derived = {e["id"]: e for e in realized}
        for event in cash:
            if event["kind"] == "REALIZED_NET" and derived.get(event["id"]) != event:
                raise ValueError("Unsupported realized cash claim")
        movement = Decimal(0)
        profit = Decimal(0)
        for event in [*cash, *realized]:
            if event["currency"] != currency:
                continue
            stamp = datetime.fromisoformat(event["timestamp"]).astimezone(UTC)
            if not start <= stamp < end:
                continue
            value = Decimal(event["amount"])
            if event["kind"] == "DEPOSIT":
                movement += value
            elif event["kind"] == "WITHDRAWAL":
                movement -= value
        for event in realized:
            if event["currency"] == currency and start <= datetime.fromisoformat(event["timestamp"]).astimezone(UTC) < end:
                profit += Decimal(event["amount"])
        historical = historical_fixture_inventory(path, cutoff=int(end.timestamp()))
        unresolved = historical["unresolved"]
        source = {table: db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
                  for table in ("positions", "partial_fills", "exits", "cash_evidence")}
        if inventory is not None:
            if (type(inventory) is not dict or set(inventory) != {"identity", "version", "sources"}
                    or type(inventory["identity"]) is not str or not inventory["identity"]
                    or type(inventory["version"]) is not int or inventory["version"] < 1):
                raise ValueError("Malformed fixture source inventory")
            actual = {key: hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
                      for key, value in source.items()}
            if actual != inventory["sources"]:
                raise ValueError("Incomplete or changed source inventory")
        report = {"schema": "PAPER_BOUND_DAILY_HISTORICAL_V3", "date": day, "timezone": timezone, "currency": currency,
                  "opening_cash": openings[0]["amount"], "cashflow": str(movement), "realized_net": str(profit),
                  "closing_cash": str(Decimal(openings[0]["amount"]) + movement + profit),
                  "source_sha256": hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest(),
                  "total_equity": None, "unresolved": unresolved,
                  "historical_inventory": historical,
                  "status": "INCOMPLETE" if unresolved else "CASH_RECONCILED_NOT_OPERATIONAL_ACCEPTANCE"}
        if inventory is not None:
            report.update(schema="PAPER_BOUND_DAILY_FIXTURE_HISTORICAL_V3", source_inventory=inventory,
                          independently_authenticated=False, production_authorized=False)
        body = json.dumps(report, sort_keys=True)
        db.execute("CREATE TABLE IF NOT EXISTS bound_daily(id INTEGER PRIMARY KEY,body TEXT,parent TEXT,digest TEXT)")
        previous = ""
        latest = None
        for old, prior, digest in db.execute("SELECT body,parent,digest FROM bound_daily ORDER BY id"):
            if prior != previous or hashlib.sha256((prior + old).encode()).hexdigest() != digest:
                raise ValueError("Corrupt bound report history")
            previous, latest = digest, old
            old_inventory = json.loads(old).get("source_inventory")
            if (inventory is not None and old_inventory and old_inventory["identity"] == inventory["identity"]
                and (inventory["version"] < old_inventory["version"] or (
                    inventory["version"] == old_inventory["version"] and inventory != old_inventory
                ))):
                raise ValueError("Stale or conflicting inventory revision")
        if latest != body:
            fault("before_report")
            db.execute("INSERT INTO bound_daily(body,parent,digest) VALUES(?,?,?)",
                       (body, previous, hashlib.sha256((previous + body).encode()).hexdigest()))
        fault("before_commit")
        db.commit()
        fault("after_commit")
        return report


def publish_inventory_bound_fixture(path, *, day, timezone, currency, inventory,
                                    expected_identity=None, expected_version=None):
    """Explicit V2 fixture path. A supplied commitment is not independent authority."""
    if inventory is None:
        raise ValueError("Externally retained fixture inventory required")
    if ((expected_identity is not None or expected_version is not None)
        and (type(expected_identity) is not str or not expected_identity
                or type(expected_version) is not int or expected_version < 1
                or inventory.get("identity") != expected_identity or inventory.get("version") != expected_version)):
        raise ValueError("Fixture authority identity/version mismatch")
    return publish_bound_daily(path, day=day, timezone=timezone, currency=currency, inventory=inventory)
