"""Disposable canonical-commit adapter over the existing E135/E133 outbox.

No installed runtime, provider or Discord import. Sender must be simulation-only.
Local consent checkpoints are not independent operational rollback authority.
"""

import json
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime

from app.investment.quality_dips_candidate_evidence import verified
from app.services.discord_consent_coordinator import DiscordConsentCoordinator
from app.services.discord_lifecycle_outbox import (
    LIFECYCLE_EVENT_TYPES,
    LifecycleContractError,
    make_lifecycle_event,
)
from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import (
    body,
    digest,
    number,
    replay_verified_events,
    strict,
)
from app.services.paper_journal_identity import PaperJournalIdentityBatch
from app.services.paper_lifecycle_producer import IsolatedPaperLifecycleProducer

LANES = {"QUALITY_DIPS": "USD", "HYPERLIQUID": "USDC"}


class CommittedNotificationRecovery(IsolatedPaperLifecycleProducer):
    def __init__(self, root, *, source, authority, consent, scope, policy, clock):
        if (
            source is None
            or authority is None
            or type(consent) is not DiscordConsentCoordinator
            or clock is None
        ):
            raise LifecycleContractError(
                "explicit disposable committed source/consent required"
            )
        self.source, self.authority, self.consent, self.clock = (
            source,
            authority,
            consent,
            clock,
        )
        self.scope, self.policy = strict(body(scope)), strict(body(policy))
        if (
            set(self.scope) != set(LANES)
            or any(
                set(row) != {"account_id", "epoch", "currency"}
                or row["currency"] != LANES[k]
                or any(type(v) is not str or not v for v in row.values())
                for k, row in self.scope.items()
            )
            or len({r["account_id"] for r in self.scope.values()}) != 2
            or len({r["epoch"] for r in self.scope.values()}) != 2
        ):
            raise LifecycleContractError("separate USD/USDC account scope required")
        if (
            set(self.policy) != {"recipients", "max_per_minute", "max_age_seconds"}
            or type(self.policy["max_per_minute"]) is not int
            or not 1 <= self.policy["max_per_minute"] <= 60
            or type(self.policy["max_age_seconds"]) is not int
            or not 1 <= self.policy["max_age_seconds"] <= 120
            or type(self.policy["recipients"]) is not dict
            or len(self.policy["recipients"]) > 500
        ):
            raise LifecycleContractError(
                "bounded notification recipient/type/rate scope required"
            )
        for recipient, kinds in self.policy["recipients"].items():
            if (
                str(int(recipient)) != recipient
                or int(recipient) <= 0
                or int(recipient) >= 2**64
                or type(kinds) is not list
                or not kinds
                or len(set(kinds)) != len(kinds)
                or not set(kinds) <= LIFECYCLE_EVENT_TYPES
            ):
                raise LifecycleContractError(
                    "explicit recipient/category scope required"
                )
        self._ports = (
            source,
            authority,
            consent,
            clock,
            body(self.scope),
            body(self.policy),
        )
        super().__init__(root)
        self._verify_handoff()

    def _verify_ports(self):
        if (
            self.source,
            self.authority,
            self.consent,
            self.clock,
            body(self.scope),
            body(self.policy),
        ) != self._ports:
            raise LifecycleContractError("notification component/scope substitution")

    def _read_source(self):
        self._verify_ports()
        now = self.clock()
        cut = strict(body(self.source.read_committed()))
        if (
            type(now) is not int
            or set(cut)
            != {
                "schema",
                "execution_domain",
                "source_id",
                "observed_at",
                "manifests",
                "commits",
            }
            or cut["schema"] != "ATLAS_COMMITTED_LIFECYCLE_CUT_V1"
            or cut["execution_domain"] != "DISPOSABLE"
            or type(cut["source_id"]) is not str
            or not cut["source_id"]
            or type(cut["observed_at"]) is not int
            or not 0 <= now - cut["observed_at"] <= 5
            or set(cut["manifests"]) != set(LANES)
            or type(cut["commits"]) is not list
            or len(cut["commits"]) > 256
            or len(body(cut).encode()) > 2 * 1024 * 1024
        ):
            raise LifecycleContractError(
                "bounded current disposable committed cut required"
            )
        context = {"scope": self.scope, "cut": cut}
        frozen = body(context)
        proof = verified(
            self.authority.verify_committed(context, now=now),
            digest(context),
            "ATLAS_COMMITTED_EVENTS_VERIFIED_V1",
        )
        if proof.get("execution_domain") != "DISPOSABLE" or body(context) != frozen:
            raise LifecycleContractError("committed event source unverified")
        rows = {k: [] for k in LANES}
        events = []
        raw = b""
        sequences = Counter()
        ops = set()
        for lane, currency in LANES.items():
            m = cut["manifests"][lane]
            if (
                m["schema"]
                not in (
                    "PAPER_EPOCH_FIXTURE_V1",
                    "PAPER_EPOCH_AUTONOMOUS_QD_V1",
                    "PAPER_EPOCH_PERP_FIXTURE_V2",
                )
                or m["epoch"] != self.scope[lane]["epoch"]
                or m["currency"] != currency
            ):
                raise LifecycleContractError("foreign financial source scope")
        for item in cut["commits"]:
            if (
                type(item) is not dict
                or set(item) != {"lane", "record", "commit_ack"}
                or item["lane"] not in LANES
                or type(item["commit_ack"]) is not dict
                or not item["commit_ack"]
            ):
                raise LifecycleContractError(
                    "original committed financial ACK required"
                )
            lane = item["lane"]
            row = item["record"]
            m = cut["manifests"][lane]
            rows[lane].append(row)
            state, _, _ = replay_verified_events(m, rows[lane])
            audit_financial_events(m, rows[lane], state)
            command, receipt = strict(row["command"]), strict(row["receipt"])
            op = (lane, row["operation_id"])
            if op in ops:
                raise LifecycleContractError("duplicate committed operation")
            ops.add(op)
            position = receipt["position_id"]
            entity = digest([self.scope[lane], position])
            sequences[(lane, entity)] += 1
            kind = (
                "PAPER_ENTRY"
                if command["kind"] == "ENTRY"
                else "PAPER_CLOSE"
                if command["kind"] == "EXIT"
                and number(state["positions"][position]["remaining"]) == 0
                else "PAPER_MARK"
            )
            event = make_lifecycle_event(
                event_type=kind,
                source="atlas-paper."
                + digest([cut["source_id"], lane, self.scope[lane]]),
                entity_id=entity,
                source_event_id=digest([row["operation_id"], row["digest"]])
                + ":"
                + str(len(raw)),
                source_sequence=sequences[(lane, entity)],
                occurred_at=datetime.fromtimestamp(command["timestamp"], UTC),
                payload={
                    "execution_domain": "DISPOSABLE",
                    "execution": "SIMULATED",
                    "lane": lane,
                    "scope": self.scope[lane],
                    "operation_id": row["operation_id"],
                    "source_revision": row["revision"],
                    "record_digest": row["digest"],
                    "commit_ack": item["commit_ack"],
                    "receipt": receipt,
                    "kind": command["kind"],
                    "position_id": position,
                    "remaining": state["positions"][position]["remaining"],
                },
            )
            events.append(event)
            raw += (body(item) + "\n").encode()
        if (
            self.source.read_committed() != cut
            or type(self.clock()) is not int
            or not 0 <= self.clock() - now <= 1
        ):
            raise LifecycleContractError("committed cut changed during read")
        self._verify_ports()
        return (
            raw,
            PaperJournalIdentityBatch(tuple(events), True, 0, 0, False, digest(cut)),
            [
                "DISPOSABLE_COMMITTED_SOURCE",
                digest([cut["source_id"], self.scope, cut["manifests"]]),
            ],
        )

    def _consent(self):
        self._verify_ports()
        recipients = []
        evidence = {}
        for recipient, kinds in sorted(self.policy["recipients"].items()):
            state = self.consent._state(int(recipient))
            if (
                state is not None
                and state[1]
                and self.consent.authorized(int(recipient), state[0])
            ):
                recipients.append(int(recipient))
                evidence[recipient] = {
                    "generation": state[0],
                    "database_id": self.consent.consent.database_id,
                    "types": kinds,
                }
        return recipients, {
            "execution_domain": "DISPOSABLE",
            "policy": self.policy,
            "active": evidence,
        }

    def _event_consent(self, event, recipients, consent):
        return [
            r
            for r in recipients
            if event.event_type in self.policy["recipients"][str(r)]
        ], consent

    def _state(self, db):
        state = super()._state(db)
        if (
            state.get("committed_scope") != digest([self.scope, self.policy])
            or state.get("notification_stopped") is not False
        ):
            raise LifecycleContractError(
                "notification scope changed or durably stopped"
            )
        return state

    def activate_for_simulation(self, *, approval_reference):
        super().activate_for_simulation(approval_reference=approval_reference)
        with self._transaction() as db:
            state = super()._state(db)
            state.update(
                committed_scope=digest([self.scope, self.policy]),
                notification_stopped=False,
                notification_rate={},
            )
            self._save(db, state)

    def stop(self):
        super().stop()
        with self._transaction() as db:
            if db.execute("SELECT 1 FROM state").fetchone():
                state = super()._state(db)
                state["notification_stopped"] = True
                self._save(db, state)

    async def dispatch_simulated(self, *, sender, now=None):
        if getattr(sender, "simulation_only", None) is not True:
            raise LifecycleContractError("real notification transport disabled")
        owner = self

        class ScopedFake:
            simulation_only = True

            async def __call__(self, *, recipient_id, event):
                owner._verify_ports()
                stamp = owner.clock()
                occurred = datetime.fromisoformat(event.occurred_at).timestamp()
                if (
                    event.event_type
                    not in owner.policy["recipients"].get(str(recipient_id), [])
                    or not 0 <= stamp - occurred <= owner.policy["max_age_seconds"]
                ):
                    raise LifecycleContractError(
                        "stale or out-of-scope financial notification"
                    )
                with owner._transaction() as db:
                    state = owner._state(db)
                    history = state["notification_rate"].get(str(recipient_id), [])
                    if any(t > stamp for t in history):
                        raise LifecycleContractError("notification clock rollback")
                    history = [t for t in history if stamp - t < 60]
                    if len(history) >= owner.policy["max_per_minute"]:
                        raise LifecycleContractError("notification rate exhausted")
                    state["notification_rate"][str(recipient_id)] = history + [stamp]
                    owner._save(db, state)
                if owner._stopped.is_set():
                    raise LifecycleContractError("notification stopped")
                return await sender(recipient_id=recipient_id, event=event)

        return await super().dispatch_simulated(
            sender=ScopedFake(), now=now or datetime.fromtimestamp(self.clock(), UTC)
        )

    def status(self):
        """Read-only dashboard data; never deliveries, payloads or recipient IDs."""
        self._verify_ports()
        with closing(
            sqlite3.connect(self.state_path.resolve().as_uri() + "?mode=ro", uri=True)
        ) as db:
            row = db.execute("SELECT document FROM state WHERE id=1").fetchone()
            state = json.loads(row[0]) if row else {}
        with closing(
            sqlite3.connect(self.outbox_path.resolve().as_uri() + "?mode=ro", uri=True)
        ) as db:
            db.row_factory = sqlite3.Row
            self.outbox._validate_events(db)
            counts = dict(
                db.execute(
                    "SELECT status,COUNT(*) FROM lifecycle_deliveries GROUP BY status"
                )
            )
        return {
            "schema": "ATLAS_NOTIFICATION_STATUS_V1",
            "execution_domain": "DISPOSABLE",
            "stopped": state.get("notification_stopped", True),
            "delivery_states": counts,
            "real_discord_enabled": False,
            "startup_authorized": False,
            "exactly_once_external_delivery": False,
        }
