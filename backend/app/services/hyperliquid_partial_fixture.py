"""Disposable V2 overlay; never writes native journals or manual snapshots.

The native V1 bytes are immutable inputs. SQLite intent and ledger commits are
separate: an unacknowledged operation ALWAYS blocks further mutation/projection.
No recovery authority or production path discovery exists in this module.
"""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from app.services.daily_paper_liquidation import append_partial_fixture
from app.services.hyperliquid_paper_handoff import fixture_scope
from app.services.paper_bound_daily_report import publish_bound_daily
from app.services.paper_exit_audit import audit_fixture_exits
from app.services.paper_partial_accounting import replay_partial_fills


def _body(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_body(value).encode()).hexdigest()


@contextmanager
def _connect(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rw", uri=True, timeout=2)
    try:
        db.execute("PRAGMA synchronous=FULL")
        with db:
            yield db
    finally:
        db.close()


def _identity(namespace, position):
    immutable = {k: position[k] for k in ("trade_id", "symbol", "side", "actual_entry_price", "risk_price",
                                          "quantity", "fees_bps", "slippage_bps", "opened_at", "currency")}
    return "hl-fixture-v2:" + _digest({"namespace": namespace, "position": immutable})


def create_partial_fixture(path, *, namespace, journal, consistency):
    """Exclusive disposable initialization from independently supplied fixture pins.

    Caller must already have used actual ManualPerpStateStore.load and verified
    pinned journal/manual bytes. These receipts are consistency, not authority.
    """
    if (type(namespace) is not str or not namespace or len(namespace) > 100
            or journal.get("schema") != "HYPERLIQUID_JOURNAL_HANDOFF_V1"
            or consistency.get("schema") != "HYPERLIQUID_NATIVE_FIXTURE_CONSISTENCY_V1"
            or consistency.get("journal_sha256") != journal.get("source_sha256")
            or consistency.get("journal_record_revision") != journal.get("record_revision")
            or consistency.get("production_authorized") is not False
            or journal.get("production_authorized") is not False):
        raise ValueError("Exact fixture baseline receipts required")
    positions = journal["open_positions"]
    if (not 1 <= len(positions) <= 3 or len({p["trade_id"] for p in positions}) != len(positions)
            or sorted(consistency["entered_ids"]) != sorted(p["trade_id"] for p in positions)):
        raise ValueError("Exact native open inventory required")
    baseline = {"schema": "HYPERLIQUID_PARTIAL_BASELINE_V2", "namespace": namespace,
                "journal_sha256": journal["source_sha256"], "manual_sha256": consistency["manual_sha256"],
                "journal_revision": journal["record_revision"],
                "positions": {_identity(namespace, p): p for p in positions}}
    with Path(path).open("xb"):
        pass
    with _connect(path) as db:
        db.execute("CREATE TABLE baseline(body TEXT NOT NULL, digest TEXT NOT NULL)")
        db.execute("CREATE TABLE operations(id TEXT PRIMARY KEY, body TEXT NOT NULL, event TEXT)")
        db.execute("INSERT INTO baseline VALUES(?,?)", (_body(baseline), _digest(baseline)))
    return _digest(baseline)


def _baseline(db, pin):
    rows = db.execute("SELECT body,digest FROM baseline").fetchall()
    if len(rows) != 1:
        raise ValueError("Missing or duplicate baseline")
    baseline = json.loads(rows[0][0])
    if _digest(baseline) != pin or rows[0][1] != pin:
        raise ValueError("Changed or corrupt baseline")
    return baseline


def _position(p):
    return {**p, "schema": "PAPER_PARTIAL_POSITION_V1", "entry": p["actual_entry_price"]}


def _price_evidence(p, quote, now):
    """Validate an exit's fixture scope and price, never fabricate entry controls."""
    risk = Decimal(p["risk_price"]) * Decimal(p["quantity"])
    scope = fixture_scope()
    if (p["symbol"] not in scope["symbols"] or not risk.is_finite() or not 0 < risk <= Decimal(scope["max_risk_usd"])
            or type(quote) is not dict or quote.get("verified") is not True
            or quote.get("symbol") != p["symbol"] or type(quote.get("observed_at")) is not int
            or not 0 <= now - quote["observed_at"] <= 30
            or type(quote.get("source_id")) is not str or not quote["source_id"]):
        raise ValueError("Out-of-scope or stale exit evidence")


def _verify(db, ledger, pin):
    baseline = _baseline(db, pin)
    rows = db.execute("SELECT id,body,event FROM operations ORDER BY rowid").fetchall()
    previous, fills, events = pin, {}, []
    for number, (ident, body, raw) in enumerate(rows, 1):
        request = json.loads(body)
        if raw is None:
            raise ValueError("Unacknowledged cross-store operation; preserve evidence, no replay")
        event = json.loads(raw)
        unsigned = {k: v for k, v in event.items() if k != "digest"}
        if (event.get("schema") != "HYPERLIQUID_PARTIAL_EVENT_V2" or event.get("revision") != number
                or event.get("previous") != previous or event.get("digest") != _digest(unsigned)
                or event.get("request") != request or request.get("fill_id") != ident
                or request.get("position_id") not in baseline["positions"]):
            raise ValueError("Corrupt event/intent lineage")
        p = baseline["positions"][request["position_id"]]
        fill = event["fill"]
        expected = {"schema": "PAPER_PARTIAL_FILL_V1", "fill_id": ident, "trade_id": p["trade_id"],
                    "quantity": request["quantity"], "price": request["quote"]["price"],
                    "timestamp": request["timestamp"], "session_id": request["session_id"]}
        if fill != expected or request["expected_revision"] != number - 1:
            raise ValueError("Conflicting fill identity or revision")
        fills.setdefault(p["trade_id"], []).append(fill)
        if replay_partial_fills(_position(p), fills[p["trade_id"]]) != event["accounting"]:
            raise ValueError("Contradictory partial accounting")
        previous = event["digest"]
        events.append(event)
    with _connect(ledger) as source:
        actual = source.execute("SELECT id,body FROM positions").fetchall()
        expected = {p["trade_id"]: p for p in baseline["positions"].values()}
        if len(actual) != len(expected) or {i: json.loads(b) for i, b in actual} != expected:
            raise ValueError("Ledger/native baseline inventory mismatch")
        actual_fills = source.execute("SELECT id,trade,body FROM partial_fills ORDER BY rowid").fetchall()
        expected_fills = {f["fill_id"]: f for group in fills.values() for f in group}
        if (len(actual_fills) != len(expected_fills)
                or {i: json.loads(b) for i, _, b in actual_fills} != expected_fills
                or any(t != json.loads(b)["trade_id"] for _, t, b in actual_fills)):
            raise ValueError("Untracked,missing or conflicting ledger fill")
    audit = audit_fixture_exits(ledger)
    unresolved = sorted(p["trade_id"] for p in baseline["positions"].values()
                        if not replay_partial_fills(_position(p), fills.get(p["trade_id"], []))["complete"])
    if audit["unresolved"] != unresolved:
        raise ValueError("Independent ledger finalization mismatch")
    return baseline, events, fills, previous


def partial_fixture_view(path, ledger, *, expected_baseline):
    """Derived V2 display only; original native states remain unchanged."""
    with _connect(path) as db:
        baseline, events, fills, previous = _verify(db, ledger, expected_baseline)
    positions = []
    for ident, p in baseline["positions"].items():
        accounting = replay_partial_fills(_position(p), fills.get(p["trade_id"], []))
        allocated = Decimal(p["actual_entry_price"]) * Decimal(accounting["closed_quantity"]) / 10000
        costs = {"entry_fee": str(allocated * Decimal(p["fees_bps"])),
                 "exit_fee": str(allocated * Decimal(p["fees_bps"])),
                 "entry_slippage": str(allocated * Decimal(p["slippage_bps"])),
                 "exit_slippage": str(allocated * Decimal(p["slippage_bps"]))}
        positions.append({"position_id": ident, "native_trade_id": p["trade_id"],
                          "symbol": p["symbol"], "side": p["side"], "cost_basis_per_unit": p["actual_entry_price"],
                          "remaining_entry_notional": str(Decimal(accounting["remaining_quantity"]) * Decimal(p["actual_entry_price"])),
                          "cost_components": costs, "accounting": accounting,
                          "status": "CLOSED_FIXTURE_LEDGER_ONLY" if accounting["complete"] else
                          ("PARTIALLY_CLOSED" if accounting["unique_fill_n"] else "OPEN"),
                          "native_journal_status": "OPEN", "native_manual_status": "ENTERED"})
    return {"schema": "HYPERLIQUID_PARTIAL_VIEW_V2", "baseline": expected_baseline,
            "revision": len(events), "digest": previous, "positions": positions,
            "native_positions_flat": False, "production_authorized": False,
            "shutdown_authorized": False, "recovery_authorized": False,
            "startup_authorized": False, "paper_trading_authorized": False}


def publish_partial_daily_fixture(path, ledger, *, expected_baseline, day, timezone, currency):
    """Report only a fully acknowledged fixture ledger, never operational shutdown.

    Independent clients remain outside this cooperative adapter; no cross-store
    snapshot/exclusion is claimed. Do not attach this to operational callers.
    """
    view = partial_fixture_view(path, ledger, expected_baseline=expected_baseline)
    if any(not p["accounting"]["complete"] for p in view["positions"]):
        raise ValueError("Remaining fixture quantity prevents complete daily report")
    report = publish_bound_daily(ledger, day=day, timezone=timezone, currency=currency)
    return {"schema": "HYPERLIQUID_PARTIAL_REPORT_RECEIPT_V2", "event_digest": view["digest"],
            "revision": view["revision"], "baseline": expected_baseline, "report": report,
            "production_authorized": False, "shutdown_authorized": False}


def append_partial_exit_fixture(path, ledger, request, *, expected_baseline, now, fault=lambda phase: None):
    """Versioned fill acknowledgement; never retry an unresolved callback.

    fault hooks are for disposable crash tests. This method cannot update native
    sources, grant startup, or recover a pending operation.
    """
    keys = {"schema", "position_id", "fill_id", "quantity", "quote", "timestamp", "session_id", "expected_revision"}
    if (type(request) is not dict or set(request) != keys or request["schema"] != "HYPERLIQUID_PARTIAL_REQUEST_V2"
            or any(type(request[k]) is not str or not request[k] or len(request[k]) > 200
                   for k in ("position_id", "fill_id", "session_id", "quantity"))
            or type(request["expected_revision"]) is not int or request["expected_revision"] < 0
            or type(now) is not int or type(request["timestamp"]) is not int):
        raise ValueError("Strict V2 fill request required")
    body = _body(request)
    if len(body) > 4096:
        raise ValueError("Bounded request required")
    with _connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        baseline, events, fills, previous = _verify(db, ledger, expected_baseline)
        prior = db.execute("SELECT body,event FROM operations WHERE id=?", (request["fill_id"],)).fetchone()
        if prior:
            if prior[0] != body:
                raise ValueError("Conflicting duplicate callback")
            return json.loads(prior[1])
        if request["expected_revision"] != len(events) or request["timestamp"] != now:
            raise ValueError("Stale revision or execution clock")
        p = baseline["positions"].get(request["position_id"])
        if p is None:
            raise ValueError("Unknown position identity")
        _price_evidence(p, request["quote"], now)
        # This is an exit adapter, not an entry path; no risk-control state is invented.
        fill = {"schema": "PAPER_PARTIAL_FILL_V1", "fill_id": request["fill_id"], "trade_id": p["trade_id"],
                "quantity": request["quantity"], "price": request["quote"]["price"],
                "timestamp": request["timestamp"], "session_id": request["session_id"]}
        accounting = replay_partial_fills(_position(p), [*fills.get(p["trade_id"], []), fill])
        event = {"schema": "HYPERLIQUID_PARTIAL_EVENT_V2", "revision": len(events) + 1,
                 "previous": previous, "request": request, "fill": fill, "accounting": accounting}
        event["digest"] = _digest(event)
        fault("before_intent")
        db.execute("INSERT INTO operations VALUES(?,?,NULL)", (request["fill_id"], body))
        db.commit()
    fault("after_intent")
    append_partial_fixture(ledger, p["trade_id"], fill, fault=lambda phase: fault("ledger_" + phase))
    fault("before_ack")
    with _connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT body,event FROM operations WHERE id=?", (request["fill_id"],)).fetchall() != [(body, None)]:
            raise ValueError("Changed operation before acknowledgement")
        _baseline(db, expected_baseline)
        db.execute("UPDATE operations SET event=? WHERE id=?", (_body(event), request["fill_id"]))
        # Verify both committed stores before publishing the acknowledgement.
        _verify(db, ledger, expected_baseline)
        fault("before_ack_commit")
        db.commit()
    fault("after_ack")
    return event
