"""Disposable canonical event/receipt prototype. No runtime entry point or trust authority.

SQLite transactions cover this one fixture file only. External projections are
separate commits and must use the pending/acknowledgement bridge. Local hashes,
file identity and declared capital do not establish protected operational storage,
independent opening cash, anti-rollback, trusted clock or startup permission.
"""
import hashlib
import json
import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo


def body(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(body(value).encode()).hexdigest()


def number(value):
    if type(value) is not str:
        raise ValueError("Explicit decimal string required")
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("Finite decimal required")
    return result


def text(value):
    if type(value) is not str or not value or len(value) > 256:
        raise ValueError("Bounded explicit identity required")
    return value


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate persisted field")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def validate_manifest(m):
    if (set(m) != {"schema", "epoch", "strategy", "currency", "opening_cash", "opened_at", "timezone",
                   "release", "provenance", "cost_policy", "fees_bps", "slippage_bps", "initial_net_r"}
            or m["schema"] != "PAPER_EPOCH_FIXTURE_V1"
            or m["strategy"] not in ("QUALITY_DIPS", "HYPERLIQUID_MANUAL") or m["currency"] != "USD"
            or m["cost_policy"] != "FIXTURE_ENTRY_NOTIONAL_ROUNDTRIP_V1"
            or type(m["opened_at"]) is not int or m["opened_at"] <= 0
            or number(m["opening_cash"]) <= 0
            or min(number(m["fees_bps"]), number(m["slippage_bps"])) < 0):
        raise ValueError("Exact explicit simulated inception required")
    for key in ("epoch", "release", "provenance"):
        text(m[key])
    ZoneInfo(m["timezone"])
    number(m["initial_net_r"])
    if m["strategy"] == "HYPERLIQUID_MANUAL" and (m["fees_bps"], m["slippage_bps"]) != ("2", "2"):
        raise ValueError("Preserve selected Hyperliquid cost assumptions")


def create_epoch_fixture(path, manifest):
    validate_manifest(manifest)
    path = Path(path)
    with path.open("xb"):
        pass
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("CREATE TABLE inception(body TEXT NOT NULL)")
        db.execute("CREATE TABLE events(revision INTEGER PRIMARY KEY,id TEXT UNIQUE,body TEXT,parent TEXT,digest TEXT,receipt TEXT)")
        db.execute("CREATE TABLE projections(id TEXT PRIMARY KEY,body TEXT,receipt TEXT)")
        db.execute("CREATE TABLE daily(day TEXT,revision INTEGER,body TEXT,parent TEXT,digest TEXT,PRIMARY KEY(day,revision))")
        db.execute("INSERT INTO inception VALUES(?)", (body(manifest),))
    return EpochFixture(path, expected_manifest=manifest)


class EpochFixture:
    def __init__(self, path, *, expected_manifest):
        validate_manifest(expected_manifest)
        self.path = Path(path).resolve()
        self.manifest = strict(body(expected_manifest))
        stat = self.path.stat()
        self.identity = (stat.st_dev, stat.st_ino)
        self.pin = digest(self.manifest)

    def connect(self):
        stat = self.path.stat()
        if (stat.st_dev, stat.st_ino) != self.identity or self.path.is_symlink():
            raise ValueError("Changed fixture resource")
        db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=2)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _initial(self):
        return {"positions": {}, "cash": self.manifest["opening_cash"], "gross": "0", "costs": "0",
                "net": "0", "net_r": self.manifest["initial_net_r"], "revision": 0, "last_clock": self.manifest["opened_at"]}

    def _apply(self, state, command):
        m = self.manifest
        common = {"schema", "epoch", "operation_id", "kind", "expected_source_revision", "timestamp", "manual", "quote"}
        extra = {"symbol", "side", "quantity", "risk_price", "origin_ref"} if command.get("kind") == "ENTRY" else {"position_id", "quantity", "expected_position_revision"}
        if (set(command) != common | extra or command["schema"] != "PAPER_COMMAND_FIXTURE_V1"
                or command["epoch"] != m["epoch"] or command["kind"] not in ("ENTRY", "EXIT")
                or command["manual"] is not True or type(command["expected_source_revision"]) is not int
                or command["expected_source_revision"] != state["revision"]
                or type(command["timestamp"]) is not int or command["timestamp"] < state["last_clock"]):
            raise ValueError("Unknown,stale or mismatched command")
        text(command["operation_id"])
        q = command["quote"]
        if (type(q) is not dict or set(q) != {"symbol", "price", "observed_at", "source_id"}
                or type(q["observed_at"]) is not int
                or not 0 <= command["timestamp"] - q["observed_at"] <= 30):
            raise ValueError("Fresh explicit fixture quote required")
        text(q["source_id"])
        price, qty = number(q["price"]), number(command["quantity"])
        if min(price, qty) <= 0:
            raise ValueError("Positive fill evidence required")
        if command["kind"] == "ENTRY":
            text(command["symbol"])
            text(command["origin_ref"])
            if any(p["origin_ref"] == command["origin_ref"] for p in state["positions"].values()):
                raise ValueError("Origin already associated")
            if command["symbol"] != q["symbol"] or command["side"] not in ("LONG", "SHORT"):
                raise ValueError("Instrument mismatch")
            risk = None if command["risk_price"] is None else number(command["risk_price"])
            if m["strategy"] == "HYPERLIQUID_MANUAL":
                if (command["symbol"] not in ("BTC", "ETH", "SOL") or risk is None or risk <= 0
                        or risk * qty > 1 or number(state["net_r"]) <= -3
                        or sum(number(p["remaining"]) > 0 for p in state["positions"].values()) >= 3):
                    raise ValueError("Selected risk/position/session restriction")
            elif command["side"] != "LONG" or risk is not None:
                raise ValueError("Quality Dips is long-only,not a fabricated stop model")
            ident = m["epoch"] + ":" + digest([m["epoch"], command["operation_id"]])
            notional = price * qty
            if m["strategy"] == "QUALITY_DIPS":
                if notional > number(state["cash"]):
                    raise ValueError("Insufficient simulated cash")
                state["cash"] = str(number(state["cash"]) - notional)
            state["positions"][ident] = {"symbol": command["symbol"], "side": command["side"], "entry": str(price),
                "quantity": str(qty), "remaining": str(qty), "risk_price": command["risk_price"],
                "revision": 1, "origin_ref": command["origin_ref"], "realized_net": "0"}
        else:
            ident = command["position_id"]
            p = state["positions"].get(ident)
            if (not p or type(command["expected_position_revision"]) is not int
                    or p["revision"] != command["expected_position_revision"] or q["symbol"] != p["symbol"]
                    or qty > number(p["remaining"])):
                raise ValueError("Position/revision/remaining quantity mismatch")
            entry = number(p["entry"])
            gross = (price - entry) * qty * (1 if p["side"] == "LONG" else -1)
            costs = 2 * entry * qty * (number(m["fees_bps"]) + number(m["slippage_bps"])) / 10000
            net = gross - costs
            p.update(remaining=str(number(p["remaining"]) - qty), revision=p["revision"] + 1,
                     realized_net=str(number(p["realized_net"]) + net))
            state.update(gross=str(number(state["gross"]) + gross), costs=str(number(state["costs"]) + costs),
                         net=str(number(state["net"]) + net),
                         cash=str(number(state["cash"]) + (price * qty - costs if m["strategy"] == "QUALITY_DIPS" else net)))
            if p["risk_price"] is not None:
                state["net_r"] = str(number(state["net_r"]) + net / (number(p["risk_price"]) * number(p["quantity"])))
        state.update(revision=state["revision"] + 1, last_clock=command["timestamp"])
        return {"schema": "PAPER_RECEIPT_FIXTURE_V1", "epoch": m["epoch"], "operation_id": command["operation_id"],
                "payload_digest": digest(command), "source_revision": state["revision"], "position_id": ident,
                "position_revision": state["positions"][ident]["revision"], "state_digest": digest(state),
                "production_authorized": False, "startup_authorized": False}

    def _load(self, db):
        if db.execute("SELECT body FROM inception").fetchall() != [(body(self.manifest),)]:
            raise ValueError("Substituted or incomplete inception")
        state, parent, operations = self._initial(), self.pin, {}
        for revision, ident, raw, prior, checksum, ack in db.execute("SELECT * FROM events ORDER BY revision"):
            command = strict(raw)
            receipt = self._apply(state, command)
            stored = strict(ack)
            if type(stored.get("projection_required")) is not bool:
                raise ValueError("Missing projection contract")
            receipt["projection_required"] = stored["projection_required"]
            if (revision != state["revision"] or ident != command["operation_id"] or ident in operations
                    or prior != parent or checksum != digest([parent, command, receipt]) or strict(ack) != receipt):
                raise ValueError("Corrupt canonical event/receipt lineage")
            operations[ident] = (command, receipt)
            parent = checksum
        projections = {}
        for ident, payload, ack in db.execute("SELECT * FROM projections"):
            if ident not in operations or payload != digest(operations[ident][0]) or not operations[ident][1]["projection_required"]:
                raise ValueError("Foreign projection intent")
            if ack is not None:
                parsed = strict(ack)
                if (parsed["ack_digest"] != digest(parsed["evidence"])
                        or parsed["evidence"]["canonical_receipt"] != operations[ident][1]):
                    raise ValueError("Corrupt projection acknowledgement")
            projections[ident] = ack
        if any(r["projection_required"] and ident not in projections for ident, (_, r) in operations.items()):
            raise ValueError("Missing projection intent")
        return state, parent, operations

    def execute(self, command, *, projection_required=False, fault=lambda phase: None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state, parent, operations = self._load(db)
            if db.execute("SELECT COUNT(*) FROM projections WHERE receipt IS NULL").fetchone()[0]:
                raise ValueError("UNKNOWN projection;no financial replay")
            previous = operations.get(command.get("operation_id"))
            if previous:
                if previous[0] != command:
                    raise ValueError("Conflicting operation replay")
                if projection_required and not db.execute("SELECT 1 FROM projections WHERE id=?", (command["operation_id"],)).fetchone():
                    raise ValueError("Existing operation lacks projection intent")
                return previous[1]
            receipt = self._apply(state, command)
            if type(projection_required) is not bool:
                raise ValueError("Explicit projection contract required")
            receipt["projection_required"] = projection_required
            fault("before_event")
            db.execute("INSERT INTO events VALUES(?,?,?,?,?,?)", (state["revision"], command["operation_id"],
                       body(command), parent, digest([parent, command, receipt]), body(receipt)))
            if projection_required:
                db.execute("INSERT INTO projections VALUES(?,?,NULL)", (command["operation_id"], digest(command)))
            fault("before_commit")
            db.commit()
            fault("after_commit")
            return receipt

    def snapshot(self):
        with self.connect() as db:
            db.execute("BEGIN")
            state, _, _ = self._load(db)
            pending = db.execute("SELECT COUNT(*) FROM projections WHERE receipt IS NULL").fetchone()[0]
            return {**state, "epoch": self.manifest["epoch"], "strategy": self.manifest["strategy"],
                    "report_state": "INCOMPLETE" if pending or any(number(p["remaining"]) > 0 for p in state["positions"].values()) else "RECONCILED_FIXTURE_ONLY",
                    "equity": None, "pending_projections": pending, "startup_authorized": False, "shutdown_authorized": False}

    def daily_report(self, day):
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError("Explicit ISO reporting date required")
        if day < datetime.fromtimestamp(self.manifest["opened_at"], UTC).astimezone(ZoneInfo(self.manifest["timezone"])).date().isoformat():
            raise ValueError("No account before inception")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state, head, _ = self._load(db)
            if db.execute("SELECT COUNT(*) FROM projections WHERE receipt IS NULL").fetchone()[0]:
                raise ValueError("UNKNOWN projection;no complete report")
            # Replay to each local date boundary; cash is not an equity valuation.
            opening, closing, gross, costs = number(self.manifest["opening_cash"]), number(self.manifest["opening_cash"]), Decimal(0), Decimal(0)
            replay = self._initial()
            closing_positions, closing_revision = {}, 0
            for raw, in db.execute("SELECT body FROM events ORDER BY revision"):
                c = strict(raw)
                local = datetime.fromtimestamp(c["timestamp"], UTC).astimezone(ZoneInfo(self.manifest["timezone"])).date().isoformat()
                before_gross, before_costs = number(replay["gross"]), number(replay["costs"])
                self._apply(replay, c)
                if local < day:
                    opening = number(replay["cash"])
                if local <= day:
                    closing = number(replay["cash"])
                    closing_positions = strict(body(replay["positions"]))
                    closing_revision = replay["revision"]
                if local == day:
                    gross += number(replay["gross"]) - before_gross
                    costs += number(replay["costs"]) - before_costs
            report = {"schema": "PAPER_DAILY_FIXTURE_V1", "epoch": self.manifest["epoch"], "day": day,
                      "timezone": self.manifest["timezone"], "source_revision": state["revision"], "source_head": head,
                      "closing_source_revision": closing_revision,
                      "opening_cash": str(opening), "closing_cash": str(closing), "realized_gross": str(gross),
                      "costs": str(costs), "realized_net": str(gross - costs), "equity": None,
                      "state": "INCOMPLETE" if any(number(p["remaining"]) > 0 for p in closing_positions.values()) else "RECONCILED_FIXTURE_ONLY",
                      "startup_authorized": False, "shutdown_authorized": False}
            parent, prior = self.pin, None
            revision = 0
            for n, raw, previous, checksum in db.execute("SELECT revision,body,parent,digest FROM daily WHERE day=? ORDER BY revision", (day,)):
                revision += 1
                if n != revision or previous != parent or checksum != digest([parent, strict(raw)]):
                    raise ValueError("Corrupt report history")
                parent, prior = checksum, strict(raw)
            if prior == report:
                return prior
            db.execute("INSERT INTO daily VALUES(?,?,?,?,?)", (day, revision + 1, body(report), parent, digest([parent, report])))
            return report
