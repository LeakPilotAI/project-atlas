"""Shared canonical SQL event/replay operations; no paths or startup authority.

The fixture and personal native coordination adapters share these operations.
FS1 applies every financial transition; this mixin adds no financial semantics.
"""
from app.services.paper_financial_replay import (
    apply_event,
    body,
    digest,
    event_stream_record,
    initial_state,
    replay_verified_events,
    strict,
)


class CanonicalCoordinationSQL:
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

