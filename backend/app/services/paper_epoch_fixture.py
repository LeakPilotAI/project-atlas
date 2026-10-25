"""Disposable canonical event/receipt prototype. No runtime entry point or trust authority.

SQLite transactions cover this one fixture file only. External projections are
separate commits and must use the pending/acknowledgement bridge. Local hashes,
file identity and declared capital do not establish protected operational storage,
independent opening cash, anti-rollback, trusted clock or startup permission.
"""
import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from app.services.paper_financial_replay import (
    apply_event,
    body,
    digest,
    event_stream_record,
    initial_state,
    number,
    replay_verified_events,
    strict,
    text,
    validate_manifest,
)

__all__ = ["EpochFixture", "body", "create_epoch_fixture", "digest", "number", "strict", "text", "validate_manifest"]


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
        if manifest["schema"] == "PAPER_EPOCH_AUTONOMOUS_QD_V1":
            db.execute("CREATE TABLE autonomous_control(revision INTEGER PRIMARY KEY,body TEXT,parent TEXT,digest TEXT)")
    return EpochFixture(path, expected_manifest=manifest)


class EpochFixture:
    def __init__(self, path, *, expected_manifest):
        validate_manifest(expected_manifest)
        self.path = Path(path).resolve()
        self.manifest = strict(body(expected_manifest))
        stat = self.path.stat()
        self.identity = (stat.st_dev, stat.st_ino)
        self.pin = digest(self.manifest)

    def connect(self, *, readonly=False):
        stat = self.path.stat()
        if (stat.st_dev, stat.st_ino) != self.identity or self.path.is_symlink():
            raise ValueError("Changed fixture resource")
        db = sqlite3.connect(self.path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"), uri=True, timeout=2)
        if not readonly:
            db.execute("PRAGMA synchronous=FULL")
        return db

    def _initial(self):
        return initial_state(self.manifest)

    def _apply(self, state, command):
        candidate, receipt = apply_event(self.manifest, state, command)
        state.clear()
        state.update(candidate)
        return receipt

    def _load(self, db):
        if db.execute("SELECT body FROM inception").fetchall() != [(body(self.manifest),)]:
            raise ValueError("Substituted or incomplete inception")
        records = (event_stream_record(*row) for row in db.execute("SELECT * FROM events ORDER BY revision"))
        state, parent, operations = replay_verified_events(self.manifest, records)
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
            if callable(command):
                if self.manifest["schema"] != "PAPER_EPOCH_AUTONOMOUS_QD_V1":
                    raise ValueError("Autonomous callback requires explicit contract")
                command = command(db, state, operations)
            elif self.manifest["schema"] == "PAPER_EPOCH_AUTONOMOUS_QD_V1":
                raise ValueError("Autonomous admission callback required")
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
        with self.connect(readonly=True) as db:
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
