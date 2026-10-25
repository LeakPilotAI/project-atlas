"""Offline autonomous QD pipeline over the existing disposable canonical ledger.

No provider, native operational paths, startup hook, default grant or broker.
Research MANUAL_ONLY labels are research provenance, never forged trade approval.
"""

from datetime import datetime
from decimal import ROUND_FLOOR, Decimal, DecimalException, localcontext
from threading import Lock
from zoneinfo import ZoneInfo

from app.investment.quality_dips_candidate_evidence import verified
from app.investment.quality_dips_paper_exit_policy import evaluate_exit
from app.investment.quality_dips_v2_position_monitor import PositionMonitorInput, evaluate_position
from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import (
    body,
    digest,
    event_stream_record,
    number,
    strict,
    text,
)
from app.services.quality_dips_account_policy import verify_reached_level

SCHEMA = "PAPER_EPOCH_AUTONOMOUS_QD_V1"
POLICY = "QD_AUTO_RISK_PARTIAL_THESIS_V1"


class NoFill(ValueError):
    """Known refusal, without a financial effect."""


def validate_autonomous_manifest(m):
    from app.services.paper_financial_replay import validate_manifest

    base = dict(m)
    policy = base.pop("autonomous_policy", None)
    if (
        m.get("schema") != SCHEMA
        or m.get("strategy") != "QUALITY_DIPS"
        or m.get("opening_cash") != "1000"
        or (m.get("fees_bps"), m.get("slippage_bps")) != ("2", "2")
        or m.get("cost_policy") != "SIDE_NOTIONAL_FEE_SLIPPAGE_V1"
    ):
        raise ValueError("AUTO_MANIFEST_REQUIRED")
    base.update(schema="PAPER_EPOCH_FIXTURE_V1", cost_policy="FIXTURE_ENTRY_NOTIONAL_ROUNDTRIP_V1")
    validate_manifest(base)  # Structural arithmetic fields only, no trust conversion.
    if (
        type(policy) is not dict
        or set(policy)
        != {
            "schema",
            "quote_age_seconds",
            "max_spread_bps",
            "participation",
            "quantity_step",
            "partial_fraction",
            "max_session_seconds",
        }
        or policy["schema"] != POLICY
    ):
        raise ValueError("AUTO_EXPLICIT_POLICY_REQUIRED")
    if any(
        type(policy[k]) is not int or not 0 < policy[k] <= cap
        for k, cap in (("quote_age_seconds", 30), ("max_session_seconds", 86400))
    ):
        raise ValueError("AUTO_BOUNDED_POLICY_REQUIRED")
    if (
        not 0 < number(policy["participation"]) <= 1
        or not 0 < number(policy["quantity_step"]) <= 1
        or not 0 < number(policy["partial_fraction"]) < 1
        or not 0 < number(policy["max_spread_bps"]) <= 100
    ):
        raise ValueError("AUTO_POLICY_OUT_OF_RANGE")


def validate_grant(m, grant, now):
    if (
        type(grant) is not dict
        or set(grant)
        != {
            "schema",
            "session_id",
            "epoch",
            "issued_at",
            "expires_at",
            "capabilities",
            "feed_id",
            "calendar_id",
        }
        or grant["schema"] not in ("QD_AUTO_SESSION_FIXTURE_V1", "QD_AUTO_ENGINE_SESSION_V5")
        or grant["epoch"] != m["epoch"]
        or any(type(grant[k]) is not int for k in ("issued_at", "expires_at"))
        or type(now) is not int
        or not m["opened_at"]
        <= grant["issued_at"]
        <= now
        < grant["expires_at"]
        <= grant["issued_at"] + m["autonomous_policy"]["max_session_seconds"]
        or grant["capabilities"] != ["AUTO_ENTRY", "AUTO_EXIT"]
    ):
        raise NoFill("SESSION_REFUSED")
    for k in ("session_id", "feed_id", "calendar_id"):
        text(grant[k])


def l1_price(m, packet, instrument, grant, now, kind):
    fields = {
        "schema",
        "provider_id",
        "feed_id",
        "entitlement_id",
        "feed_scope",
        "delay_status",
        "symbol",
        "instrument_id",
        "asset_class",
        "currency",
        "bid",
        "ask",
        "bid_size",
        "ask_size",
        "size_units",
        "source_timestamp",
        "received_timestamp",
        "sequence",
        "session",
        "calendar",
        "market_status",
        "connection_status",
        "clock_uncertainty_seconds",
    }
    if type(packet) is not dict or set(packet) != fields or packet["schema"] != "QD_AUTO_L1_V1":
        raise NoFill("L1_SCHEMA")
    for key in ("provider_id", "entitlement_id", "sequence"):
        text(packet[key])
    if (
        packet["feed_id"] != grant["feed_id"]
        or packet["delay_status"] != "REALTIME"
        or packet["feed_scope"] not in ("VENUE", "CONSOLIDATED")
        or packet["symbol"] != instrument["symbol"]
        or packet["instrument_id"] != instrument["instrument_id"]
        or packet["asset_class"] != instrument["asset_class"]
        or packet["asset_class"] not in ("STOCK", "ETF")
        or packet["currency"] != "USD"
        or packet["size_units"] != "SHARES"
        or packet["session"] != "REGULAR"
        or packet["market_status"] != "TRADING"
        or packet["connection_status"] != "CONNECTED"
    ):
        raise NoFill("L1_IDENTITY_ENTITLEMENT_OR_MARKET")
    if any(type(packet[k]) is not int for k in ("source_timestamp", "received_timestamp")):
        raise NoFill("L1_TIME")
    age = m["autonomous_policy"]["quote_age_seconds"]
    uncertainty = number(packet["clock_uncertainty_seconds"])
    if (
        not 0 <= uncertainty <= age
        or not packet["source_timestamp"] <= packet["received_timestamp"] <= now
        or not 0 <= now - packet["source_timestamp"] + uncertainty <= age
    ):
        raise NoFill("L1_STALE_OR_CLOCK_UNCERTAIN")
    cal = packet["calendar"]
    local = datetime.fromtimestamp(now, ZoneInfo("America/New_York"))
    if (
        type(cal) is not dict
        or set(cal) != {"id", "date", "open", "close", "is_open"}
        or cal["id"] != grant["calendar_id"]
        or cal["date"] != local.date().isoformat()
        or cal["is_open"] is not True
        or any(type(cal[k]) is not int for k in ("open", "close"))
        or not cal["open"] <= now < cal["close"]
        or local.weekday() >= 5
        or not (9, 30) <= (local.hour, local.minute) < (16, 0)
    ):
        raise NoFill("MARKET_CLOSED_OR_CALENDAR_UNVERIFIED")
    bid, ask = number(packet["bid"]), number(packet["ask"])
    if not 0 < bid <= ask or (ask - bid) * 10000 / ask > number(
        m["autonomous_policy"]["max_spread_bps"]
    ):
        raise NoFill("L1_SPREAD")
    size = number(packet["ask_size" if kind == "ENTRY" else "bid_size"])
    if size <= 0:
        raise NoFill("L1_LIQUIDITY_UNAVAILABLE")
    return (ask if kind == "ENTRY" else bid), size


def liquidity_key(packet, kind):
    return digest(
        [
            packet["provider_id"],
            packet["feed_id"],
            packet["instrument_id"],
            packet["sequence"],
            kind,
        ]
    )


def available_liquidity(m, state, packet, kind, size):
    prior = state["l1_consumption"].get(
        liquidity_key(packet, kind), {"quantity": "0", "packet_digest": digest(packet)}
    )
    if prior["packet_digest"] != digest(packet):
        raise NoFill("L1_SEQUENCE_CONFLICT")
    return max(
        Decimal(0),
        size * number(m["autonomous_policy"]["participation"]) - number(prior["quantity"]),
    )


def validate_autonomous_command(m, state, c):
    if c.get("schema") != "QD_AUTO_COMMAND_V1" or c.get("manual") is not False:
        raise ValueError("AUTO_DISPATCH_NOT_MANUAL")
    e = c["evidence"]
    grant = e["session"]
    validate_grant(m, grant, c["timestamp"])
    if (
        e["source_binding"] != digest(e["request"])
        or e["request_digest"] != digest(e["request"])
        or e["l1"] not in e["request"]["quotes"]
    ):
        raise ValueError("AUTO_SOURCE_BINDING")
    if c["session_id"] != grant["session_id"] or c["operation_id"] != m[
        "epoch"
    ] + ":decision:" + digest(e["decision_id"]):
        raise ValueError("AUTO_DECISION_IDENTITY")
    instrument = e["instrument"]
    price, size = l1_price(m, e["l1"], instrument, grant, c["timestamp"], c["kind"])
    if c["quote"] != {
        "symbol": instrument["symbol"],
        "price": str(price),
        "observed_at": e["l1"]["source_timestamp"],
        "source_id": e["l1"]["provider_id"],
    }:
        raise ValueError("AUTO_PRICE_BINDING")
    qty = number(c["quantity"])
    step = number(m["autonomous_policy"]["quantity_step"])
    if (
        qty <= 0
        or qty % step != 0
        or qty > available_liquidity(m, state, e["l1"], c["kind"], size)
        or (instrument["fractional"] is not True and qty != qty.to_integral_value())
    ):
        raise ValueError("AUTO_QUANTITY_OR_LIQUIDITY")
    if (
        instrument.get("currency") != "USD"
        or instrument.get("units") != "SHARES"
        or instrument.get("long_supported") is not True
    ):
        raise ValueError("AUTO_INSTRUMENT")
    verified(e["source_proof"], e["source_binding"], "QD_AUTO_SOURCE_PROOF_V1")
    verified(e["session_proof"], digest(grant), "QD_AUTO_SESSION_PROOF_V1")
    if c["kind"] == "ENTRY":
        candidate = e["candidate"]
        if candidate["source_bundle"] not in e["request"]["bundles"]:
            raise ValueError("AUTO_RANKING_SOURCE_BINDING")
        verified(
            candidate["ranking_proof"], digest(candidate["source_bundle"]), "QD_RANKING_VERIFIED_V1"
        )
        verify_reached_level(
            candidate["source_bundle"]["observation"]["prediction"]["entry_ladder"],
            candidate["ranking"]["level"],
            str(price),
        )
        if (
            candidate["execution"]["instrument"] != instrument
            or candidate["ranking"]["symbol"] != instrument["symbol"]
            or c["timestamp"] >= candidate["expires_at"]
        ):
            raise ValueError("AUTO_CANDIDATE_BINDING")
    else:
        position = state["positions"][c["position_id"]]
        if instrument != position["instrument"]:
            raise ValueError("AUTO_EXIT_INSTRUMENT")
        observation = e["request"]["observation"]
        if e["exit_reason"] == "SHUTDOWN_FLATTEN":
            if (e["request"].get("shutdown_mode") != "SHUTDOWN_FLATTEN"
                    or e["request"]["bundles"] != [] or qty != number(position["remaining"])
                    or observation.get("symbol") != position["symbol"]
                    or type(observation.get("observed_at")) is not int
                    or not 0 <= c["timestamp"] - observation["observed_at"] <= 30):
                raise ValueError("AUTO_SHUTDOWN_FULL_EXIT_REQUIRED")
            return
        monitor = evaluate_position(
            PositionMonitorInput(
                position["symbol"],
                float(position["entry"]),
                float(price),
                position["entry_snapshot"],
                observation["current"],
            )
        )
        terminal = evaluate_exit(
            {"classification": monitor["state"], "prediction": observation["current"]}
        )
        if (e["exit_reason"] == "THESIS_TERMINAL" and not terminal["terminal"]) or (
            e["exit_reason"] == "EXIT_REVIEW_PARTIAL" and monitor["state"] != "EXIT_REVIEW"
        ):
            raise ValueError("AUTO_EXIT_REASON_UNSUPPORTED")
        if e["exit_reason"] == "EXIT_REVIEW_PARTIAL" and qty > max(
            Decimal(0),
            number(position["quantity"]) * number(m["autonomous_policy"]["partial_fraction"])
            - (number(position["quantity"]) - number(position["remaining"])),
        ):
            raise ValueError("AUTO_PARTIAL_TARGET_EXCEEDED")
        if e["exit_reason"] not in ("EXIT_REVIEW_PARTIAL", "THESIS_TERMINAL"):
            raise ValueError("AUTO_EXIT_POLICY")


class AutonomousPaper:
    """Injected disposable ledger, research adapter and authorities. Never starts itself."""

    def __init__(self, *, ledger, candidates, session_authority, source_authority, clock, publication=None):
        if any(x is None for x in (ledger, candidates, session_authority, source_authority, clock)):
            raise ValueError("AUTO_DEPENDENCIES_REQUIRED")
        validate_autonomous_manifest(ledger.manifest)
        self.ledger, self.candidates, self.session_authority, self.source_authority, self.clock = (
            ledger,
            candidates,
            session_authority,
            source_authority,
            clock,
        )
        self._decision_lock = Lock()
        self.publication = publication  # Explicit disposable native bridge, never a default authority.
        self.grant = None  # Reconstructed instances never resume automatically.
        self.entry_admission_closed = True
        self.dispatch_closed = True

    def _control(self, db):
        parent = digest(self.ledger.manifest)
        last = {"mode": "STOPPED", "session": None, "clock": self.ledger.manifest["opened_at"]}
        revision = 0
        for n, raw, previous, checksum in db.execute(
            "SELECT * FROM autonomous_control ORDER BY revision"
        ):
            value = strict(raw)
            revision += 1
            if (
                n != revision
                or type(value) is not dict
                or set(value) != {"mode", "session", "clock"}
                or previous != parent
                or checksum != digest([parent, value])
                or value["mode"]
                not in ("RUNNING", "PAUSED", "STOPPING", "STOPPED", "STOP_INCOMPLETE")
                or type(value["clock"]) is not int
                or value["clock"] < last["clock"]
                or (
                    value["mode"] in ("RUNNING", "PAUSED")
                    and (type(value["session"]) is not str or len(value["session"]) != 64)
                )
                or (value["mode"] == "STOPPED" and value["session"] is not None)
            ):
                raise ValueError("AUTO_CONTROL_CORRUPT")
            last = value
            parent = checksum
        return last, parent, revision

    def _append(self, db, mode, grant):
        last, parent, n = self._control(db)
        now = self.clock()
        if type(now) is not int or now < last["clock"]:
            raise ValueError("AUTO_CLOCK_ROLLBACK")
        value = {"mode": mode, "session": None if grant is None else digest(grant), "clock": now}
        db.execute(
            "INSERT INTO autonomous_control VALUES(?,?,?,?)",
            (n + 1, body(value), parent, digest([parent, value])),
        )
        return value

    def _grant(self, now):
        validate_grant(self.ledger.manifest, self.grant, now)
        return verified(
            self.session_authority.verify(self.grant, now=now),
            digest(self.grant),
            "QD_AUTO_SESSION_PROOF_V1",
        )

    def start(self, grant):
        grant = strict(body(grant))
        validate_grant(self.ledger.manifest, grant, self.clock())
        verified(
            self.session_authority.verify(grant, now=self.clock()),
            digest(grant),
            "QD_AUTO_SESSION_PROOF_V1",
        )
        with self.ledger.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            control, _, _ = self._control(db)
            if (
                control["mode"] not in ("STOPPED",)
                or db.execute("SELECT 1 FROM projections WHERE receipt IS NULL").fetchone()
            ):
                raise ValueError("AUTO_START_REFUSED")
            if any(
                strict(row[0])["session"] == digest(grant)
                for row in db.execute("SELECT body FROM autonomous_control")
            ):
                raise ValueError("AUTO_SESSION_GRANT_REUSE")
            self.ledger._load(db)
            self._append(db, "RUNNING", grant)
        self.grant = grant
        self.entry_admission_closed = False
        self.dispatch_closed = False
        return "RUNNING"

    def pause(self):
        self.entry_admission_closed = True
        self._grant(self.clock())
        with self.ledger.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            c, _, _ = self._control(db)
            if c["mode"] != "RUNNING" or c["session"] != digest(self.grant):
                raise ValueError("AUTO_PAUSE_REFUSED")
            self._append(db, "PAUSED", self.grant)
        return "PAUSED"

    def stop(self):
        self.entry_admission_closed = True
        self.dispatch_closed = True
        # Close shared admission before drain. The same database write lock
        # serializes closure against financial intent creation in execute().
        with self.ledger.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._append(db, "STOPPING", self.grant)
        try:
            self.reconcile()
            with self.ledger.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                if db.execute("SELECT 1 FROM projections WHERE receipt IS NULL").fetchone():
                    raise ValueError("UNKNOWN")
                self._append(db, "STOPPED", None)
            self.grant = None
            return "STOPPED"
        except (ValueError, OSError, KeyError, TypeError, DecimalException):
            with self.ledger.connect() as db:
                self._append(db, "STOP_INCOMPLETE", self.grant)
            self.grant = None
            return "STOP_INCOMPLETE"

    def status(self):
        with self.ledger.connect(readonly=True) as db:
            mode = self._control(db)[0]["mode"]
            return (
                "STOP_INCOMPLETE" if (self.grant is None or self.dispatch_closed) and mode in ("RUNNING", "PAUSED") else mode
            )

    def reconcile(self):
        with self.ledger.connect(readonly=True) as db:
            db.execute("BEGIN")
            state, _, _ = self.ledger._load(db)
            if db.execute("SELECT 1 FROM projections WHERE receipt IS NULL").fetchone():
                raise ValueError("AUTO_UNKNOWN_ACK")
            records = [
                event_stream_record(*row)
                for row in db.execute("SELECT * FROM events ORDER BY revision")
            ]
            audit = audit_financial_events(self.ledger.manifest, records, state)
            if self.publication is not None:
                self.publication.verify(records, state)
            return audit

    def step(self, decision_id, *, bundles, quotes, observation=None, fault=lambda phase: None, shutdown_mode=None):
        # Serialize the same live coordinator through native ACK. This grants no
        # cross-process recovery authority; an orphaned pending ACK still refuses.
        if not self._decision_lock.acquire(timeout=2):
            return {"execution": "SIMULATED", "filled": False, "reason": "DECISION_IN_PROGRESS"}
        try:
            return self._step(decision_id, bundles=bundles, quotes=quotes, observation=observation, fault=fault, shutdown_mode=shutdown_mode)
        finally:
            self._decision_lock.release()

    def _step(self, decision_id, *, bundles, quotes, observation=None, fault=lambda phase: None, shutdown_mode=None):
        text(decision_id)
        request = strict(body({"bundles": bundles, "quotes": quotes, "observation": observation}))
        if shutdown_mode is not None:
            if shutdown_mode != "SHUTDOWN_FLATTEN" or bundles:
                raise NoFill("SHUTDOWN_CANDIDATES_REFUSED")
            request["shutdown_mode"] = shutdown_mode
        if (
            type(request["bundles"]) is not list
            or type(request["quotes"]) is not list
            or len(request["bundles"]) > 100
            or len(request["quotes"]) > 100
            or len(body(request).encode()) > 131072
        ):
            raise NoFill("REQUEST_CAPACITY_OR_SCHEMA")
        binding = digest(request)
        operation = self.ledger.manifest["epoch"] + ":decision:" + digest(decision_id)

        def prepare(db, state, operations):
            if self.publication is not None and not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='autonomous_activity'").fetchone():
                raise NoFill("NATIVE_COORDINATION_VERSION_REQUIRED")
            if self.dispatch_closed:
                raise NoFill("DISPATCH_CLOSED")
            now = self.clock()
            proof = self._grant(now)
            control, _, _ = self._control(db)
            if (
                control["mode"] not in ("RUNNING", "PAUSED")
                or control["session"] != digest(self.grant)
                or now < max(state["last_clock"], control["clock"])
            ):
                raise NoFill("SESSION_STOPPED_OR_CHANGED")
            prior = operations.get(operation)
            if prior:
                if prior[0]["evidence"]["request_digest"] != binding:
                    raise NoFill("CONFLICTING_DECISION")
                return prior[0]
            source = verified(
                self.source_authority.verify(request, now=now), binding, "QD_AUTO_SOURCE_PROOF_V1"
            )
            try:
                with localcontext() as context:
                    context.prec = 28
                    return self._decide(
                        state, decision_id, request, proof, source, control["mode"], now
                    )
            except (ValueError, KeyError, TypeError, DecimalException) as error:
                raise NoFill(str(error)) from error

        try:
            receipt = self.ledger.execute(prepare, projection_required=True, fault=fault)
            fault("before_ack")
            with self.ledger.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                state, _, operations = self.ledger._load(db)
                evidence = {"canonical_receipt": receipt, "execution": "SIMULATED"}
                if self.publication is not None:
                    # Reserve locally first. Native failure leaves the durable local ACK NULL.
                    # No distributed atomicity or blind cross-store repair is claimed.
                    evidence["native"] = self.publication.publish(operations[operation][0], receipt, state)
                    fault("after_native_ack")
                ack = body({"ack_digest": digest(evidence), "evidence": evidence})
                db.execute(
                    "UPDATE projections SET receipt=? WHERE id=? AND receipt IS NULL",
                    (ack, operation),
                )
            fault("after_ack")
            audit = self.reconcile()
            self._record_activity(decision_id, "ACKNOWLEDGED", None)
            return {"execution": "SIMULATED", "filled": True, "receipt": receipt, "audit": audit}
        except NoFill as error:
            self._record_activity(decision_id, "REFUSED", str(error))
            return {"execution": "SIMULATED", "filled": False, "reason": str(error)}
        except (ValueError, OSError, KeyError, TypeError, DecimalException) as error:
            # Acknowledgement loss is never an invitation to replay a callback.
            with self.ledger.connect() as db:
                self._append(db, "STOP_INCOMPLETE", self.grant)
            self.grant = None
            self._record_activity(decision_id, "UNKNOWN", "UNKNOWN_OR_CORRUPT")
            return {
                "execution": "SIMULATED",
                "filled": False,
                "reason": "UNKNOWN_OR_CORRUPT",
                "detail": type(error).__name__,
            }

    def _record_activity(self, decision_id, status, reason):
        # Diagnostic decision evidence only; it never clears a pending financial ACK.
        with self.ledger.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='autonomous_activity'").fetchone():
                return  # Retained V1 coordinator: no implicit migration or new authority.
            parent, n = digest(self.ledger.manifest), 0
            for n, raw, prior, checksum in db.execute("SELECT * FROM autonomous_activity ORDER BY revision"):
                if prior != parent or checksum != digest([parent, strict(raw)]):
                    raise ValueError("AUTO_ACTIVITY_CORRUPT")
                parent = checksum
            if n >= 256:
                raise ValueError("AUTO_ACTIVITY_CAPACITY")
            value = {"decision_id": decision_id, "status": status, "reason": reason, "observed_at": self.clock(),
                     "source_revision": db.execute("SELECT COUNT(*) FROM events").fetchone()[0]}
            db.execute("INSERT INTO autonomous_activity VALUES(?,?,?,?)", (n + 1, body(value), parent, digest([parent, value])))

    def _decide(self, state, decision_id, request, session_proof, source_proof, mode, now):
        if len({(q["instrument_id"], q["feed_id"]) for q in request["quotes"]}) != len(
            request["quotes"]
        ):
            raise NoFill("AMBIGUOUS_L1_SNAPSHOT")
        m = self.ledger.manifest
        policy = m["autonomous_policy"]
        active = [(i, p) for i, p in state["positions"].items() if number(p["remaining"]) > 0]
        candidate = None
        exit_reason = None
        if active:
            ident, position = active[0]
            observation = request["observation"]
            if (
                type(observation) is not dict
                or observation.get("symbol") != position["symbol"]
                or type(observation.get("observed_at")) is not int
                or not 0 <= now - observation["observed_at"] <= 30
            ):
                raise NoFill("MONITOR_EVIDENCE_UNAVAILABLE")
            instrument = observation["instrument"]
            quote = next(
                (q for q in request["quotes"] if q["instrument_id"] == instrument["instrument_id"]),
                None,
            )
            price, size = l1_price(m, quote, instrument, self.grant, now, "EXIT")
            monitor = evaluate_position(
                PositionMonitorInput(
                    position["symbol"],
                    float(position["entry"]),
                    float(price),
                    position["entry_snapshot"],
                    observation["current"],
                )
            )
            terminal = evaluate_exit(
                {"classification": monitor["state"], "prediction": observation["current"]}
            )
            if request.get("shutdown_mode") == "SHUTDOWN_FLATTEN":
                quantity = number(position["remaining"])
                exit_reason = "SHUTDOWN_FLATTEN"
            elif terminal["terminal"]:
                quantity = number(position["remaining"])
                exit_reason = "THESIS_TERMINAL"
            elif monitor["state"] == "EXIT_REVIEW":
                quantity = max(
                    Decimal(0),
                    number(position["quantity"]) * number(policy["partial_fraction"])
                    - (number(position["quantity"]) - number(position["remaining"])),
                )
                exit_reason = "EXIT_REVIEW_PARTIAL"
            else:
                raise NoFill("HOLD_EXISTING_POSITION")
            kind = "EXIT"
            entry_snapshot = {}
        else:
            if mode == "PAUSED" or self.entry_admission_closed:
                raise NoFill("PAUSED_ENTRIES_CLOSED")
            candidates = [
                strict(self.candidates.candidate(b, level="L1", now=now))
                for b in request["bundles"]
            ]
            if not candidates:
                raise NoFill("NO_ELIGIBLE_CANDIDATE")
            if (
                len({(c["cohort_id"], c["source_revision"], c["generation"]) for c in candidates})
                != 1
            ):
                raise NoFill("CROSS_COHORT_RANKING")
            candidate = min(
                candidates,
                key=lambda c: (
                    c["ranking"]["rank"],
                    -number(str(c["score"])),
                    c["ranking"]["instrument_id"],
                ),
            )
            instrument = candidate["execution"]["instrument"]
            quote = next(
                (q for q in request["quotes"] if q["instrument_id"] == instrument["instrument_id"]),
                None,
            )
            price, size = l1_price(m, quote, instrument, self.grant, now, "ENTRY")
            verify_reached_level(
                candidate["source_bundle"]["observation"]["prediction"]["entry_ladder"],
                "L1",
                str(price),
            )
            quantity = min(
                Decimal(100) / price, number(state["cash"]) / (price * Decimal("1.0004"))
            )
            entry_snapshot = candidate["source_bundle"]["observation"]["prediction"]
            kind = "ENTRY"
        step = number(policy["quantity_step"]) if instrument["fractional"] is True else Decimal(1)
        quantity = (
            min(quantity, available_liquidity(m, state, quote, kind, size)) / step
        ).to_integral_value(rounding=ROUND_FLOOR) * step
        if quantity <= 0:
            raise NoFill("NO_SUPPORTED_FILL_QUANTITY")
        if request.get("shutdown_mode") == "SHUTDOWN_FLATTEN" and quantity != number(position["remaining"]):
            raise NoFill("SHUTDOWN_INSUFFICIENT_LIQUIDITY")
        evidence = {
            "decision_id": decision_id,
            "request_digest": digest(request),
            "request": request,
            "session": self.grant,
            "session_proof": session_proof,
            "source_binding": digest(request),
            "source_proof": source_proof,
            "instrument": instrument,
            "l1": quote,
            "candidate": candidate,
            "entry_snapshot": entry_snapshot,
            "exit_reason": exit_reason,
        }
        command = {
            "schema": "QD_AUTO_COMMAND_V1",
            "epoch": m["epoch"],
            "operation_id": m["epoch"] + ":decision:" + digest(decision_id),
            "kind": kind,
            "expected_source_revision": state["revision"],
            "timestamp": now,
            "manual": False,
            "session_id": self.grant["session_id"],
            "evidence": evidence,
            "quote": {
                "symbol": instrument["symbol"],
                "price": str(price),
                "observed_at": quote["source_timestamp"],
                "source_id": quote["provider_id"],
            },
            "quantity": str(quantity),
        }
        if kind == "ENTRY":
            command.update(
                symbol=instrument["symbol"],
                side="LONG",
                risk_price=None,
                origin_ref=candidate["ranking"]["observation_id"],
            )
        else:
            command.update(position_id=ident, expected_position_revision=position["revision"])
        return command
