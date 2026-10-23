"""Synthetic bootstrap and execution boundary; NO real lifecycle integrations."""
from __future__ import annotations

import copy
import math
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from .contracts import (
    Action,
    FixturePin,
    Refused,
    RuntimeContract,
    digest,
    require_capability,
)
from .history import SessionHistory


class Status(StrEnum):
    ADMITTED = "ADMITTED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


REQUIRED = frozenset({"ownership", "admission_state", "dependencies", "provider_rights",
                      "provider_budget", "storage", "development_isolation"})


def evidence_subject(manifest: dict, kind: str) -> str:
    """Bind fixture observations to the exact subject, not a generic green flag."""
    subjects = {
        "ownership": manifest["owner"],
        "admission_state": {"session_id": manifest["session_id"], "state": "CLEAN_SYNTHETIC"},
        "dependencies": manifest["dependency_ids"],
        "provider_rights": {"sources": manifest["data_sources"], "scope": "FIXTURE_ONLY"},
        "provider_budget": {"sources": manifest["data_sources"], "budget": "FIXTURE_ONLY"},
        "storage": {key: manifest[key] for key in ("state_root", "journal_root", "configuration_id")},
        "development_isolation": manifest["development"],
    }
    return digest(subjects[kind])


@dataclass(frozen=True)
class Evidence:
    kind: str
    status: Status
    observed_at: float
    manifest_id: str
    attempt_id: str
    subject_id: str
    scope: str = "SYNTHETIC_ONLY"


@dataclass(frozen=True)
class Decision:
    status: Status
    reasons: tuple[str, ...]
    manifest_id: str
    scope: str = field(default="SYNTHETIC_ONLY", init=False)
    production_start_authorized: bool = field(default=False, init=False)


class SyntheticWorld:
    """Inert dependency/transport stand-in. Cannot launch processes or send data."""
    def __init__(self, now: float):
        self.now = now
        self.evidence: list[Evidence] = []
        self.effects: list[tuple[str, str | None]] = []
        self.runtime_alive = False
        self.release_id: str | None = None

    def perform(self, action: Action, source: str | None) -> dict:
        self.effects.append((action.value, source))
        return {"synthetic": True, "action": action.value, "source": source, "release_id": self.release_id}


class ObservationBootstrap:
    def __init__(self, contract: RuntimeContract, history: SessionHistory, world: SyntheticWorld, attempt_id: str):
        if type(world) is not SyntheticWorld or type(history) is not SessionHistory or type(contract) is not RuntimeContract:
            raise Refused("Synthetic-only contract/history/world required")
        if history.contract.pin.manifest_id != contract.pin.manifest_id:
            raise Refused("History belongs to a different manifest")
        if str(uuid.UUID(attempt_id)) != attempt_id:
            raise Refused("Canonical attempt identity required")
        self.contract, self.history, self.world, self.attempt_id = contract, history, world, attempt_id
        self._runtime: SyntheticRuntime | None = None

    def evaluate(self, *, continuing: bool = False) -> Decision:
        identity = self.contract.pin.manifest_id
        try:
            self.contract.verify()
            self.history.admission(continuing=continuing)
            facts = tuple(self.world.evidence)
            if any(type(fact) is not Evidence for fact in facts):
                return Decision(Status.BLOCKED, ("Malformed evidence",), identity)
            if len({f.kind for f in facts}) != len(facts) or any(f.kind not in REQUIRED for f in facts):
                return Decision(Status.BLOCKED, ("Duplicate/unknown/contradictory evidence",), identity)
            reasons = []
            blocked = False
            by_kind = {fact.kind: fact for fact in facts}
            if type(self.world.now) not in (int, float) or not math.isfinite(self.world.now) or self.world.now < 0:
                return Decision(Status.UNKNOWN, ("Clock unavailable",), identity)
            if self.contract.manifest["owner"]["created"] > self.world.now:
                return Decision(Status.BLOCKED, ("Owner creation time is in the future",), identity)
            if type(self.world.runtime_alive) is not bool:
                return Decision(Status.UNKNOWN, ("Synthetic runtime ownership state ambiguous",), identity)
            if self.world.runtime_alive and not continuing:
                return Decision(Status.BLOCKED, ("Synthetic runtime already active",), identity)
            for kind in sorted(REQUIRED):
                fact = by_kind.get(kind)
                if fact is None:
                    reasons.append(kind + ": missing")
                    continue
                if (fact.scope != "SYNTHETIC_ONLY" or fact.manifest_id != identity
                        or fact.attempt_id != self.attempt_id or type(fact.status) is not Status
                        or fact.subject_id != evidence_subject(self.contract.manifest, kind)):
                    blocked = True
                    reasons.append(kind + ": identity/scope/status mismatch")
                elif type(fact.observed_at) not in (int, float) or not math.isfinite(fact.observed_at) or not 0 <= self.world.now - fact.observed_at <= 5:
                    reasons.append(kind + ": stale/future/invalid time")
                elif fact.status != Status.ADMITTED:
                    blocked |= fact.status == Status.BLOCKED
                    reasons.append(kind + ": " + fact.status.value)
            status = Status.BLOCKED if blocked else Status.UNKNOWN if reasons else Status.ADMITTED
            return Decision(status, tuple(reasons), identity)
        except (OSError, ValueError, TypeError, KeyError) as error:
            return Decision(Status.BLOCKED if isinstance(error, Refused) else Status.UNKNOWN,
                            (type(error).__name__ + ": required evidence unavailable",), identity)

    def start(self) -> SyntheticRuntime:
        decision = self.evaluate()
        if decision.status != Status.ADMITTED or self._runtime is not None or self.world.runtime_alive:
            raise Refused("Synthetic startup refused: " + decision.status.value)
        manifest = self.contract.manifest
        self.history.append("SESSION_START", {k: manifest[k] for k in ("release_id", "profile", "configuration_id")}, str(uuid.uuid4()), observed_at=self.world.now)
        if self.evaluate(continuing=True).status != Status.ADMITTED:
            raise Refused("Evidence changed during durable synthetic startup intent")
        self.world.release_id = manifest["release_id"]
        self.world.runtime_alive = True
        self._runtime = SyntheticRuntime(self)
        return self._runtime


def evaluate_candidate(manifest: dict, pin: FixturePin, history: SessionHistory,
                       world: SyntheticWorld, attempt_id: str) -> Decision:
    """Report invalid/missing candidate inputs without starting or initializing anything."""
    try:
        contract = RuntimeContract(manifest, pin)
        return ObservationBootstrap(contract, history, world, attempt_id).evaluate()
    except (OSError, ValueError, TypeError, KeyError) as error:
        identity = pin.manifest_id if type(pin) is FixturePin else "UNVERIFIED"
        return Decision(Status.BLOCKED if isinstance(error, Refused) else Status.UNKNOWN,
                        (type(error).__name__ + ": candidate evidence unavailable",), identity)


class SyntheticRuntime:
    def __init__(self, bootstrap: ObservationBootstrap):
        self.bootstrap = bootstrap
        self._release_id = bootstrap.contract.manifest["release_id"]
        self._session_managed = False
        self._session_dispatch_permit = False

    @property
    def release_id(self) -> str:
        return self._release_id

    def execute(self, action: Action | str, *, source: str | None = None) -> dict:
        """Execution guard precedes transport/handler/history effects, including API callers."""
        manifest = self.bootstrap.contract.manifest
        parsed = require_capability(action, tuple(manifest["allowed_capabilities"]))
        if parsed == Action.OBSERVE and self._session_managed:
            if not self._session_dispatch_permit:
                raise Refused("Session-managed observation requires budgeted ingestion")
            self._session_dispatch_permit = False
        if not self.bootstrap.world.runtime_alive or self.bootstrap.evaluate(continuing=True).status != Status.ADMITTED:
            raise Refused("Fresh continuing admission unavailable")
        if parsed == Action.OBSERVE and source not in manifest["data_sources"]:
            raise Refused("Source not in explicit observation scope")
        if parsed == Action.HISTORY:
            raise Refused("History writes require the typed session methods")
        result = self.bootstrap.world.perform(parsed, source)
        if self.bootstrap.evaluate(continuing=True).status != Status.ADMITTED:
            raise Refused("Evidence changed during synthetic handler; result not acknowledged")
        if parsed == Action.OBSERVE:
            self.bootstrap.history.append("DATA_SOURCE", {"source_id": source}, str(uuid.uuid4()), observed_at=self.bootstrap.world.now)
        return result

    def api_request(self, action: Action | str, *, source: str | None = None) -> dict:
        """Synthetic API dispatch, not an installed FastAPI route."""
        return self.execute(action, source=source)

    def background_step(self, action: Action | str, *, source: str | None = None) -> dict:
        return self.execute(action, source=source)

    def asset(self, relative: str) -> bytes:
        self.execute(Action.RESEARCH)
        return self.bootstrap.contract.read_release(relative)

    def health(self, state: str) -> dict:
        require_capability(Action.HISTORY, tuple(self.bootstrap.contract.manifest["allowed_capabilities"]))
        if not self.bootstrap.world.runtime_alive or self.bootstrap.evaluate(continuing=True).status != Status.ADMITTED:
            raise Refused("Health publication requires fresh continuing admission")
        return self.bootstrap.history.append("HEALTH", {"state": state}, str(uuid.uuid4()), observed_at=self.bootstrap.world.now)

    def stop(self) -> None:
        # Cleanup of an inert world never depends on continued provider permission.
        decision = self.bootstrap.evaluate(continuing=True)
        self.bootstrap.world.runtime_alive = False
        if decision.status != Status.ADMITTED:
            self.bootstrap.history.append("INTERRUPTED", {"reason": "EVIDENCE_EXPIRED"}, str(uuid.uuid4()), observed_at=self.bootstrap.world.now)
            self.bootstrap.history.append("RECOVERY_REQUIRED", {"reason": "UNKNOWN_EXIT"}, str(uuid.uuid4()), observed_at=self.bootstrap.world.now)
            raise Refused("Synthetic shutdown remains recovery-required")
        self.bootstrap.history.append("GRACEFUL_SHUTDOWN", {"outcome": "COMPLETE"}, str(uuid.uuid4()), observed_at=self.bootstrap.world.now)


class NextStartupSelection:
    """In-memory prototype selection only. No install, deploy, restart or migration."""
    def __init__(self):
        self.next_manifest: dict | None = None

    def select(self, contract: RuntimeContract, world: SyntheticWorld, *, accepted: bool, approved: bool) -> None:
        if type(world) is not SyntheticWorld or world.runtime_alive or accepted is not True or approved is not True:
            raise Refused("Selection requires accepted/approved candidate and stopped synthetic runtime")
        contract.verify()
        self.next_manifest = copy.deepcopy(contract.manifest)
