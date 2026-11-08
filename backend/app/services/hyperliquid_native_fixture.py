"""Dependency-injected N1 prototype. No singleton, dispatch, entry or recovery path.

Native V1 journal bytes remain immutable. Only the supplied disposable manual
snapshot receives additive fixture projections. Unknown cross-store commits
require external reconciliation; this prototype never repairs them automatically.
"""
import hashlib
from decimal import Decimal

from app.services.hyperliquid_partial_fixture import (
    _body,
    _connect,
    _digest,
    _load,
    append_partial_exit_fixture,
    partial_fixture_view,
    publish_partial_daily_fixture,
)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _native_positions(journal, positions):
    observed = journal.list_open()
    expected = {p["trade_id"]: p for p in positions}
    if len(observed) != len(expected) or {p["trade_id"] for p in observed} != set(expected):
        raise ValueError("Changed native position inventory")
    for row in observed:
        p = expected[row["trade_id"]]
        if (row["symbol"] != p["symbol"] or row["side"] != p["side"]
                or any(Decimal(str(row[native])) != Decimal(p[normalized]) for native, normalized in
                       (("actual_entry_price", "actual_entry_price"), ("risk_price", "risk_price"),
                        ("position_size", "quantity"), ("fees_bps", "fees_bps"), ("slippage_bps", "slippage_bps")))):
            raise ValueError("Changed native financial identity")


def _projection(state, view):
    plans = []
    for plan in state["plans"]:
        matching = [p for p in view["positions"] if p["native_trade_id"] == plan.get("fixture_journal_trade_id")]
        if len(matching) != 1:
            raise ValueError("Exact disposable native association required")
        p = matching[0]
        plans.append({**plan, "fixture_v2": {"schema": "HYPERLIQUID_NATIVE_PROJECTION_V2",
                      "position_id": p["position_id"], "source_revision": view["revision"],
                      "position_revision": p["accounting"]["unique_fill_n"],
                      "applied_position_revision": p["accounting"]["unique_fill_n"],
                      "applied_source_revision": view["revision"], "source_digest": view["digest"],
                      "lifecycle_status": p["status"], "accounting": p["accounting"]}})
    return {"plans": plans, "setup_history": state["setup_history"]}


def create_native_fixture(path, ledger, *, baseline, journal, journal_path, manual_store, fault=lambda phase: None):
    """Persist association before projection; partial initialization refuses restart."""
    view = partial_fixture_view(path, ledger, expected_baseline=baseline)
    state = manual_store.load()
    if view["revision"] != 0 or any("fixture_v2" in p for p in state["plans"]):
        raise ValueError("Fresh disposable facade baseline required")
    pairs = [(p.get("fixture_journal_trade_id"), p.get("setup_key")) for p in state["plans"]]
    if (len(pairs) != len(view["positions"]) or len({a for a, _ in pairs}) != len(pairs)
            or len({b for _, b in pairs}) != len(pairs)
            or any(type(a) is not str or not a or type(b) is not str or not b for a, b in pairs)):
        raise ValueError("Unique native trade/setup associations required")
    with _connect(path) as db:
        source = _load(db.execute("SELECT body FROM baseline").fetchone()[0])
    _native_positions(journal, source["positions"].values())
    if (_sha(journal_path.read_bytes()) != source["journal_sha256"]
            or _sha(manual_store.path.read_bytes()) != source["manual_sha256"]
            or {p["trade_id"] for p in journal.list_open()} != {a for a, _ in pairs}):
        raise ValueError("Changed native baseline")
    association = {"schema": "HYPERLIQUID_NATIVE_ASSOCIATION_V2", "baseline": baseline,
                   "journal_sha256": source["journal_sha256"],
                   "original_manual_sha256": source["manual_sha256"],
                   "links": {p["position_id"]: {"trade_id": p["native_trade_id"],
                            "setup_key": dict(pairs)[p["native_trade_id"]]} for p in view["positions"]}}
    pin = _digest(association)
    head = {"association": association, "phase": "INITIALIZING", "source_revision": 0,
            "position_revisions": {p["position_id"]: 0 for p in view["positions"]},
            "applied_source_revision": 0, "manual_sha256": source["manual_sha256"]}
    with _connect(path) as db:
        db.execute("CREATE TABLE native_head(body TEXT NOT NULL,digest TEXT NOT NULL)")
        db.execute("CREATE TABLE native_operations(id TEXT PRIMARY KEY,body TEXT NOT NULL,receipt TEXT)")
        db.execute("INSERT INTO native_head VALUES(?,?)", (_body(head), _digest(head)))
    fault("after_association")
    manual_store.save(**_projection(state, view))
    fault("after_initial_projection")
    head.update(phase="READY", manual_sha256=_sha(manual_store.path.read_bytes()))
    with _connect(path) as db:
        db.execute("UPDATE native_head SET body=?,digest=?", (_body(head), _digest(head)))
    return pin


class NativeFixtureFacade:
    def __init__(self, path, ledger, *, baseline, association, journal, journal_path, manual_store):
        self.path, self.ledger = path, ledger
        self.baseline, self.association = baseline, association
        self.journal, self.journal_path, self.manual_store = journal, journal_path, manual_store

    def _ready(self, db):
        rows = db.execute("SELECT body,digest FROM native_head").fetchall()
        if len(rows) != 1:
            raise ValueError("Missing or duplicate facade head")
        head = _load(rows[0][0])
        if (_digest(head) != rows[0][1] or _digest(head["association"]) != self.association
                or head["association"]["baseline"] != self.baseline or head["phase"] != "READY"
                or any(type(head.get(k)) is not int or head[k] < 0 for k in ("source_revision", "applied_source_revision"))
                or type(head.get("position_revisions")) is not dict
                or any(type(v) is not int or v < 0 for v in head["position_revisions"].values())):
            raise ValueError("Corrupt,substituted or initializing facade")
        if db.execute("SELECT COUNT(*) FROM native_operations WHERE receipt IS NULL").fetchone()[0]:
            raise ValueError("Unacknowledged native projection; no replay or complete report")
        state = self.manual_store.load()
        expected_links = {p["trade_id"]: p["setup_key"] for p in head["association"]["links"].values()}
        actual_links = [(p.get("fixture_journal_trade_id"), p.get("setup_key")) for p in state["plans"]]
        if len(actual_links) != len(expected_links) or dict(actual_links) != expected_links:
            raise ValueError("Missing or changed native shared association")
        source = _load(db.execute("SELECT body FROM baseline").fetchone()[0])
        _native_positions(self.journal, source["positions"].values())
        if (_sha(self.journal_path.read_bytes()) != head["association"]["journal_sha256"]
                or _sha(self.manual_store.path.read_bytes()) != head["manual_sha256"]
                or {p["trade_id"] for p in self.journal.list_open()} !=
                {p["trade_id"] for p in head["association"]["links"].values()}):
            raise ValueError("Changed native source/projection")
        view = partial_fixture_view(self.path, self.ledger, expected_baseline=self.baseline)
        revisions = {p["position_id"]: p["accounting"]["unique_fill_n"] for p in view["positions"]}
        if (head["source_revision"] != view["revision"] or head["position_revisions"] != revisions
                or head["applied_source_revision"] != view["revision"]
                or state["plans"] != _projection(state, view)["plans"]):
            raise ValueError("Source,position or applied projection revision mismatch")
        operations = db.execute("SELECT id,body,receipt FROM native_operations ORDER BY rowid").fetchall()
        if len(operations) != view["revision"]:
            raise ValueError("Untracked canonical facade operation")
        seen = {p: 0 for p in revisions}
        for revision, (ident, body, raw) in enumerate(operations, 1):
            request, receipt = _load(body), _load(raw)
            if type(receipt) is not dict or any(type(receipt.get(k)) is not int for k in
                    ("source_revision", "position_revision", "applied_source_revision", "applied_position_revision")):
                raise ValueError("Strict durable facade revision required")
            event_row = db.execute("SELECT event FROM operations WHERE id=?", (ident,)).fetchone()
            event = _load(event_row[0]) if event_row else None
            p = request["position_id"]
            if p not in seen:
                raise ValueError("Unknown facade position")
            seen[p] += 1
            if (receipt != {"schema": "HYPERLIQUID_NATIVE_ACK_V2", "operation_id": ident,
                           "source_revision": revision, "position_id": p, "position_revision": seen[p],
                           "applied_source_revision": revision, "applied_position_revision": seen[p],
                           "event_digest": event["digest"] if event else None,
                           "production_authorized": False}
                    or request["expected_position_revision"] != seen[p] - 1
                    or event is None or event["request"] != self._v2_request(request, revision - 1)):
                raise ValueError("Corrupt facade receipt or revision lineage")
        return head, state, view

    @staticmethod
    def _v2_request(request, revision):
        keys = {"schema", "position_id", "operation_id", "expected_position_revision", "quantity", "quote", "timestamp", "session_id"}
        if (type(request) is not dict or set(request) != keys or request["schema"] != "HYPERLIQUID_NATIVE_EXIT_V2"
                or type(request["expected_position_revision"]) is not int or request["expected_position_revision"] < 0):
            raise ValueError("Strict native fixture request required")
        return {"schema": "HYPERLIQUID_PARTIAL_REQUEST_V2", "position_id": request["position_id"],
                "fill_id": request["operation_id"], "expected_revision": revision,
                **{k: request[k] for k in ("quantity", "quote", "timestamp", "session_id")}}

    def snapshot(self):
        with _connect(self.path) as db:
            head, _, view = self._ready(db)
        return {"schema": "HYPERLIQUID_NATIVE_VIEW_V2", "association": self.association,
                "source_revision": head["source_revision"], "position_revisions": head["position_revisions"],
                "applied_source_revision": head["applied_source_revision"], "view": view,
                "startup_authorized": False, "shutdown_authorized": False, "production_authorized": False}

    def record_exit(self, request, *, now, fault=lambda phase: None):
        # Freeze caller values before persistence/callback boundaries.
        request = _load(_body(request))
        self._v2_request(request, 0)
        ident, body = request["operation_id"], _body(request)
        with _connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            head, state, _ = self._ready(db)
            old = db.execute("SELECT body,receipt FROM native_operations WHERE id=?", (ident,)).fetchone()
            if old:
                if old[0] != body:
                    raise ValueError("Conflicting duplicate facade request")
                return _load(old[1])
            p = request["position_id"]
            if p not in head["position_revisions"] or request["expected_position_revision"] != head["position_revisions"][p]:
                raise ValueError("Unknown position or stale position revision")
            v2 = self._v2_request(request, head["source_revision"])
            fault("before_intent")
            db.execute("INSERT INTO native_operations VALUES(?,?,NULL)", (ident, body))
        fault("after_intent")
        event = append_partial_exit_fixture(self.path, self.ledger, v2, expected_baseline=self.baseline,
                                            now=now, fault=lambda phase: fault("canonical_" + phase))
        fault("after_canonical")
        view = partial_fixture_view(self.path, self.ledger, expected_baseline=self.baseline)
        projected = _projection(state, view)
        self.manual_store.save(**projected)
        fault("after_projection")
        if self.manual_store.load()["plans"] != projected["plans"]:
            raise ValueError("Unverified native projection publication")
        receipt = {"schema": "HYPERLIQUID_NATIVE_ACK_V2", "operation_id": ident,
                   "source_revision": event["revision"], "position_id": p,
                   "position_revision": head["position_revisions"][p] + 1,
                   "applied_source_revision": event["revision"],
                   "applied_position_revision": head["position_revisions"][p] + 1,
                   "event_digest": event["digest"], "production_authorized": False}
        head["position_revisions"][p] += 1
        head.update(source_revision=event["revision"], applied_source_revision=event["revision"],
                    manual_sha256=_sha(self.manual_store.path.read_bytes()))
        with _connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT body,receipt FROM native_operations WHERE id=?", (ident,)).fetchall() != [(body, None)]:
                raise ValueError("Changed facade intent")
            db.execute("UPDATE native_head SET body=?,digest=?", (_body(head), _digest(head)))
            db.execute("UPDATE native_operations SET receipt=? WHERE id=?", (_body(receipt), ident))
            self._ready(db)
            fault("before_ack_commit")
        fault("after_ack")
        return receipt

    def daily_report(self, *, day, timezone, currency):
        # Serialize cooperating facade admission through publication. This does
        # not exclude independent ledger/native clients or grant quiescence.
        with _connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            head, _, _ = self._ready(db)
            report = publish_partial_daily_fixture(self.path, self.ledger, expected_baseline=self.baseline,
                                                   day=day, timezone=timezone, currency=currency)
            return {**report, "native_association": self.association,
                    "native_applied_source_revision": head["applied_source_revision"]}
