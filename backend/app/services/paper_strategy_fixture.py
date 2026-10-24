"""Explicit disposable strategy commands and native-projection acceptance seam.

No native singleton imports, production dispatch, provider calls or startup path.
Projection callbacks must refer only to disposable stores supplied by tests.
"""
from decimal import Decimal

from app.services.paper_epoch_fixture import body, digest, number, strict


def entry_command(store, *, operation_id, symbol, quantity, quote, timestamp, origin_ref,
                  manual, side="LONG", risk_price=None):
    return {"schema": "PAPER_COMMAND_FIXTURE_V1", "epoch": store.manifest["epoch"],
            "operation_id": operation_id, "kind": "ENTRY", "expected_source_revision": store.snapshot()["revision"],
            "timestamp": timestamp, "manual": manual, "quote": quote, "symbol": symbol, "side": side,
            "quantity": quantity, "risk_price": risk_price, "origin_ref": origin_ref}


def exit_command(store, *, operation_id, position_id, quantity, quote, timestamp, manual):
    state = store.snapshot()
    return {"schema": "PAPER_COMMAND_FIXTURE_V1", "epoch": store.manifest["epoch"],
            "operation_id": operation_id, "kind": "EXIT", "expected_source_revision": state["revision"],
            "timestamp": timestamp, "manual": manual, "quote": quote, "position_id": position_id,
            "quantity": quantity, "expected_position_revision": state["positions"][position_id]["revision"]}


def quality_entry(store, observation, *, level, notional, operation_id, timestamp, manual):
    if (store.manifest["strategy"] != "QUALITY_DIPS" or level not in ("L1", "L2", "L3", "L4")
            or observation.get("classification") not in ("ACCUMULATION", "DEEP_VALUE", "GENERATIONAL")
            or observation.get("strategy_version") != "QUALITY_DIPS_V3"
            or observation.get("policy_version") != "quality-dips-v3-mos-15-20-25-30-v1"
            or observation.get("evidence_class") != "FORWARD_COLLECTION"
            or type(observation.get("observation_id")) is not str or not observation["observation_id"]
            or type(observation.get("reached_levels")) is not list or level not in observation["reached_levels"]):
        raise ValueError("Frozen eligible Quality Dips fixture evidence required")
    amount = number(notional)
    price = number(observation["quote"]["price"])
    if min(amount, price) <= 0:
        raise ValueError("Explicit positive notional/price required")
    return entry_command(store, operation_id=operation_id, symbol=observation["symbol"],
                         quantity=str(amount / price), quote=observation["quote"], timestamp=timestamp,
                         origin_ref=observation["observation_id"] + ":" + level, manual=manual)


def quality_terminal_exit(store, *, position_id, operation_id, terminal_observation, quote, timestamp, manual):
    from app.investment.quality_dips_paper_exit_policy import evaluate_exit

    if store.manifest["strategy"] != "QUALITY_DIPS" or not evaluate_exit(terminal_observation)["terminal"]:
        raise ValueError("Price-only shutdown must not liquidate patient-capital lots")
    quantity = store.snapshot()["positions"][position_id]["remaining"]
    if Decimal(quantity) <= 0:
        raise ValueError("No remaining terminal position")
    return exit_command(store, operation_id=operation_id, position_id=position_id, quantity=quantity,
                        quote=quote, timestamp=timestamp, manual=manual)


class NativeProjectionFixture:
    """Atomically reserve projection intent with canonical commit; never replay UNKNOWN.

    Callbacks publish/observe disposable native projections. They confer no
    ownership, protected file identity or operational authority. Snapshot/report
    reads must use this bridge to verify currently retained native bytes.
    """
    def __init__(self, store, *, publish, observe):
        self.store, self.publish, self.observe = store, publish, observe

    def _observed_digest(self):
        observation = self.observe()
        if type(observation) is not dict or not observation or len(body(observation)) > 1048576:
            raise ValueError("Missing or oversized native fixture observation")
        return digest(observation)

    def snapshot(self):
        with self.store.connect() as db:
            db.execute("BEGIN")
            _, _, operations = self.store._load(db)
            latest = None
            for ident, raw in db.execute("SELECT id,receipt FROM projections"):
                if raw is None:
                    raise ValueError("UNKNOWN native projection")
                ack = strict(raw)
                revision = operations[ident][1]["source_revision"]
                if latest is None or revision > latest[0]:
                    latest = revision, ack
            if latest and self._observed_digest() != latest[1]["evidence"]["projection_digest"]:
                raise ValueError("Changed native projection")
        return self.store.snapshot()

    def daily_report(self, day):
        self.snapshot()
        return self.store.daily_report(day)

    def apply(self, command, *, fault=lambda phase: None):
        with self.store.connect() as db:
            self.store._load(db)
            prior = db.execute("SELECT body,receipt FROM projections WHERE id=?", (command["operation_id"],)).fetchone()
            if prior:
                if prior[0] != digest(command) or prior[1] is None:
                    raise ValueError("UNKNOWN/conflicting projection;no callback replay")
                ack = strict(prior[1])
                if ack["ack_digest"] != digest(ack["evidence"]):
                    raise ValueError("Corrupt projection acknowledgement")
                self.snapshot()
                return ack
        receipt = self.store.execute(command, projection_required=True, fault=fault)
        with self.store.connect() as db:
            completed = db.execute("SELECT receipt FROM projections WHERE id=?", (command["operation_id"],)).fetchone()
            if completed and completed[0] is not None:
                self.snapshot()
                return strict(completed[0])
        fault("before_projection")
        self.publish(self.store.snapshot(), receipt)
        fault("after_projection")
        evidence = {"canonical_receipt": receipt, "projection_digest": self._observed_digest(),
                    "production_authorized": False, "startup_authorized": False}
        ack = {"evidence": evidence, "ack_digest": digest(evidence)}
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.store._load(db)
            if db.execute("SELECT body,receipt FROM projections WHERE id=?", (command["operation_id"],)).fetchone() != (digest(command), None):
                raise ValueError("Changed projection intent")
            db.execute("UPDATE projections SET receipt=? WHERE id=?", (body(ack), command["operation_id"]))
            fault("before_projection_ack")
        fault("after_projection_ack")
        return ack
