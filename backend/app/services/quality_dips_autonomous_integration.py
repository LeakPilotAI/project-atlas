"""Explicit disposable autonomous native publication and read presentation.

No path defaults, enrollment issuer, operational pin, provider or route registration.
SQL decisions and FS2 native publication are separate commits. Uncertain tails
refuse; this module never repairs them or grants startup permission.
"""
import sqlite3

from app.investment.quality_dips_read_capability import (
    CurrentReadEvidenceUnverified,
    SelectedReadCapability,
)
from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import body, digest, event_stream_record, number, strict
from app.services.quality_dips_autonomous_paper import SCHEMA, validate_autonomous_manifest


def validate_activity(value, *, now):
    if (type(value) is not dict or value.get("schema") != "QD_AUTO_ACTIVITY_V1"
            or value.get("execution") != "SIMULATED"
            or value.get("session_state") not in ("RUNNING", "PAUSED", "STOPPING", "STOPPED", "STOP_INCOMPLETE")
            or value.get("controls") != "DISABLED_NOT_OPERATIONALLY_ACCEPTED"
            or type(value.get("observed_at")) is not int or not 0 <= now - value["observed_at"] <= 30
            or value.get("l1_state") not in ("FRESH", "STALE", "UNAVAILABLE")):
        raise ValueError("AUTO_ACTIVITY_INVALID")
    packet = value.get("l1")
    if packet is not None and (type(packet) is not dict or packet.get("schema") != "QD_AUTO_L1_V1"
                              or number(packet["bid"]) <= 0 or number(packet["ask"]) < number(packet["bid"])):
        raise ValueError("AUTO_L1_PRESENTATION_INVALID")


class AutonomousCoordinationRead:
    """Existing-only SQL coordination inspection; no native mutex/write surface."""
    def __init__(self, engine):
        self.engine = engine

    def read_status(self):
        try:
            return self._read_status()
        except sqlite3.Error as error:
            raise CurrentReadEvidenceUnverified("AUTO_COORDINATION_MISSING_OR_CORRUPT") from error

    def _read_status(self):
        engine = self.engine
        with engine.ledger.connect(readonly=True) as db:
            db.execute("BEGIN")
            state, head, _ = engine.ledger._load(db)
            if db.execute("SELECT 1 FROM projections WHERE receipt IS NULL").fetchone():
                raise CurrentReadEvidenceUnverified("AUTO_NATIVE_PUBLICATION_UNKNOWN")
            control = engine._control(db)[0]
            records = [event_stream_record(*row) for row in db.execute("SELECT * FROM events ORDER BY revision")]
            audit_financial_events(engine.ledger.manifest, records, state)
            for raw, in db.execute("SELECT receipt FROM projections"):
                ack = strict(raw)["evidence"]
                native = ack.get("native")
                if (type(native) is not dict or native.get("schema") != "QD_AUTO_NATIVE_ACK_V1"
                        or native.get("receipt_digest") != digest(ack["canonical_receipt"])):
                    raise ValueError("AUTO_NATIVE_ACK_REQUIRED")
            latest, parent = None, digest(engine.ledger.manifest)
            for count, (revision, raw, previous, checksum) in enumerate(db.execute("SELECT * FROM autonomous_activity ORDER BY revision"), 1):
                value = strict(raw)
                if (revision != count or previous != parent or checksum != digest([parent, value])
                        or set(value) != {"decision_id", "status", "reason", "observed_at", "source_revision"}
                        or value["status"] not in ("ACKNOWLEDGED", "REFUSED", "UNKNOWN")
                        or type(value["source_revision"]) is not int or not 0 <= value["source_revision"] <= state["revision"]
                        or type(value["observed_at"]) is not int or value["observed_at"] < engine.ledger.manifest["opened_at"]):
                    raise ValueError("AUTO_ACTIVITY_CORRUPT")
                latest, parent = value, checksum
            now = engine.clock()
            if type(now) is not int or now < max(control["clock"], state["last_clock"]):
                raise ValueError("AUTO_READ_CLOCK_ROLLBACK")
            mode = control["mode"]
            if (engine.grant is None or engine.dispatch_closed) and mode in ("RUNNING", "PAUSED"):
                mode = "STOP_INCOMPLETE"
            if engine.grant is not None and now >= engine.grant["expires_at"] and mode in ("RUNNING", "PAUSED"):
                mode = "STOP_INCOMPLETE"
            command = strict(records[-1]["command"]) if records else None
            entry = next((strict(row["command"]) for row in reversed(records)
                          if strict(row["command"])["kind"] == "ENTRY"), None)
            packet = command["evidence"]["l1"] if command else None
            shutdown = None
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='autonomous_shutdown'").fetchone():
                for raw, checksum in db.execute("SELECT body,digest FROM autonomous_shutdown ORDER BY rowid"):
                    shutdown = strict(raw)
                    if (checksum != digest(shutdown) or shutdown.get("schema") != "QD_AUTO_SHUTDOWN_V1"
                            or shutdown.get("status") not in ("FLATTENED", "SHUTDOWN_INCOMPLETE")
                            or shutdown.get("position_state") not in ("FLAT", "POSITION_OPEN", "UNKNOWN")):
                        raise ValueError("AUTO_SHUTDOWN_OUTCOME_CORRUPT")
            age = now - packet["source_timestamp"] if packet else None
            fresh = packet is not None and 0 <= age <= engine.ledger.manifest["autonomous_policy"]["quote_age_seconds"]
            return {"source_revision": state["revision"], "state_digest": digest(state), "head": head,
                    "activity": {"schema": "QD_AUTO_ACTIVITY_V1", "session_state": mode,
                        "observed_at": now, "execution": "SIMULATED", "controls": "DISABLED_NOT_OPERATIONALLY_ACCEPTED",
                        "candidate": entry["evidence"]["candidate"]["ranking"] if entry and fresh else None,
                        "decision": {"id": command["evidence"]["decision_id"], "kind": command["kind"],
                                     "reason": command["evidence"]["exit_reason"], "quantity": command["quantity"],
                                     "timestamp": command["timestamp"]} if command else None,
                        "l1": packet, "l1_state": "FRESH" if fresh else "STALE" if packet else "UNAVAILABLE",
                        "pending_exits": None, "latest_refusal": latest if latest and latest["status"] != "ACKNOWLEDGED" else None,
                        **({"shutdown_outcome": shutdown} if shutdown is not None else {}),
                        "limitations": ["LAST_COMMITTED_MARKET_EVIDENCE_ONLY",
                                        "PENDING_EXIT_INTENT_UNAVAILABLE", "NO_OPERATIONAL_AUTHORITY"]}}


class AutonomousNativePublication:
    """FS2/FS3 are the acknowledged financial authority, not a second engine."""

    def __init__(self, *, store, manifest):
        validate_autonomous_manifest(manifest)
        self.store, self.manifest = store, strict(body(manifest))
        with store.guard():
            if body(store._load()[1]) != body(manifest):
                raise ValueError("AUTO_NATIVE_MANIFEST_MISMATCH")

    def publish(self, command, receipt, state):
        if command.get("schema") != "QD_AUTO_COMMAND_V1" or command.get("manual") is not False:
            raise ValueError("AUTO_NATIVE_CONTRACT_REQUIRED")
        cut = self.store.verified_cut()
        prior = cut['acknowledged_operations'].get(command['operation_id'])
        if prior is not None:
            if prior != digest(command):
                raise ValueError('AUTO_NATIVE_OPERATION_CONFLICT')
            # Read an existing, independently replayed ACK. Never reserve or
            # replay a financial callback merely to recover an old receipt.
            native = self.store.operation_receipt(command['operation_id'], prior)
        else:
            native = self.store.execute(command, projection_required=True)
        if body(native) != body(receipt):
            raise ValueError("AUTO_NATIVE_ACK_UNKNOWN")
        snapshot = self.store.snapshot()
        if body(snapshot["state"]) != body(state):
            raise ValueError("AUTO_NATIVE_STATE_CONFLICT")
        return {"schema": "QD_AUTO_NATIVE_ACK_V1", "receipt_digest": digest(native),
                "state_digest": digest(state), "head": snapshot["head"],
                "root": self.store.trust.current()["root"]}

    def verify(self, records, state):
        with self.store.guard():
            _, manifest, rows, native_state, _, _, _ = self.store._load()
            if (body(manifest) != body(self.manifest) or body(rows) != body(records)
                    or body(native_state) != body(state)):
                raise ValueError("AUTO_NATIVE_SOURCE_INCOMPLETE")


class AutonomousSelectedRead(SelectedReadCapability):
    """Existing read-only native port and FS3 auditor; separate test schema.

coordination.read_status() must be a read-only accepted lease participant; it
cannot grant financial authority. A stopped/restarted coordinator never resumes.
The authority lease must exclude all participating writers throughout both reads.
"""
    enrollment_schema = "QD_AUTO_READ_ENROLLMENT_V1"

    def __init__(self, *, coordination, **dependencies):
        super().__init__(**dependencies)
        if coordination is None:
            raise ValueError("AUTO_COORDINATION_READ_REQUIRED")
        self.coordination = coordination

    def _source_identity_extensions(self, manifest, rows, pin=None):
        # Report publication can advance without a new financial effect. Keep
        # financial identity stable; the complete report pin is still verified.
        return {"head": rows[-1]["digest"] if rows else digest(manifest),
                "pin_digest": digest({"source": pin["source"], "projection_root": self.enrollment["projection_root"]}),
                "generation": len(rows)}

    def _manifest_scope(self, manifest, enrollment, account_id):
        validate_autonomous_manifest(manifest)
        return (manifest["schema"] == SCHEMA and account_id == manifest["epoch"]
                and digest(manifest["autonomous_policy"]) == enrollment["policy_digest"])

    def read_committed(self, account_id, epoch):
        # Both calls must belong to the injected read lease. Revalidate local
        # source completeness against native evidence before exposing activity.
        before = strict(body(self.coordination.read_status()))
        payload = super().read_committed(account_id, epoch)
        after = strict(body(self.coordination.read_status()))
        before_time = before["activity"]["observed_at"]
        after_time = after["activity"]["observed_at"]
        after["activity"]["observed_at"] = before_time
        if (type(before_time) is not int or type(after_time) is not int
                or not 0 <= after_time - before_time <= 30
                or before != after or after["source_revision"] != payload["source_revision"]
                or after["state_digest"] != digest(payload["state"])
                or after["head"] != payload["source_identity"]["head"]):
            raise ValueError("AUTO_COORDINATION_CHANGED_OR_UNKNOWN")
        after["activity"]["observed_at"] = payload["observed_at"]
        payload["autonomous"] = after["activity"]
        # A remembered decision quote is not a fresh quote at HTTP read time.
        packet = payload['autonomous'].get('l1')
        if packet is not None and (type(packet.get('source_timestamp')) is not int
                or not 0 <= payload['observed_at'] - packet['source_timestamp'] <= 5):
            payload['autonomous']['l1_state'] = 'STALE'
        report = payload["report"]
        # A historical day's breakdown is not a cumulative account breakdown.
        # Derive cumulative fee/slip only when all committed entry/exit evidence
        # has been independently audited and the side-cost contract is explicit.
        payload["cost_breakdown"] = {
            "fees": str(number(payload["state"]["costs"]) / 2),
            "slippage": str(number(payload["state"]["costs"]) / 2),
            "basis": "REALIZED_COSTS_EQUAL_2BPS_PER_SIDE",
        }
        deferred = sum((number(p["remaining_entry_costs"]) for p in payload["state"]["positions"].values()), number("0"))
        paid = number(payload["state"]["costs"]) + deferred
        payload["cash_cost_evidence"] = {"schema": "QD_AUTO_CASH_COSTS_V1", "fees": str(paid / 2),
                                        "slippage": str(paid / 2), "unallocated_entry_costs": str(deferred)}
        if report["cost_allocation"] != "QD_AUTO_SIDE_COST_ALLOCATION_V1":
            raise ValueError("AUTO_REPORT_COST_VERSION_REQUIRED")
        return payload

    def verify(self, payload, *, account_id, epoch, now):
        expected = self.read_committed(account_id, epoch)
        trusted = self.clock()
        observed = payload.get("observed_at")
        activity_observed = payload.get("autonomous", {}).get("observed_at")
        expected["observed_at"] = observed
        expected["autonomous"]["observed_at"] = activity_observed
        valid = (type(now) is int and type(trusted) is int and type(observed) is int
                 and type(activity_observed) is int and activity_observed == observed
                 and 0 <= trusted - now <= 30 and 0 <= trusted - observed <= 30 and observed <= now
                 and body(expected) == body(payload))
        return {"verified": valid, "binding": digest(expected)}
