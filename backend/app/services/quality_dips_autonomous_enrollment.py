"""V4 enrollment admission seam, not an issuer, installer or startup entry.

Accepted dependencies authenticate evidence; JSON validity grants no authority.
Leases must surround each runtime action, never become reusable bearer tokens.
No fixture/manual schema translation and no filesystem publication occur here.
"""

import ntpath
from contextlib import contextmanager
from threading import RLock

from app.investment.quality_dips_operational_contract import (
    exact,
    hashed,
    native_id,
    positive,
    process,
)
from app.services.paper_financial_replay import body, digest, strict, text

PROFILE = "AUTONOMOUS_PAPER_ONLY_V1"
ROLES = ("source", "projection", "report", "control", "coordination", "custody")
WRITERS = ("decision", "source", "projection", "report", "coordination")


def publication_intent(enrollment):
    """Autonomous inception binding, not a manual bootstrap plan or write grant.

    The existing publisher's reserve/commit/ack protocol is retained. An accepted
    autonomous publication port must authenticate this distinct intent; strict
    QD_OP publisher inputs must never be translated or silently reinterpreted.
    """
    e = validate_enrollment(enrollment)
    return {
        "schema": "QD_AUTO_NATIVE_INCEPTION_INTENT_V4",
        "operation_id": "qd-auto-inception:" + digest([e["account_id"], e["epoch"]]),
        "enrollment_digest": digest(e),
        "inception_digest": e["inception_digest"],
        "opening_cash": "1000",
        "initial_positions": 0,
        "initial_obligations": 0,
    }


def validate_enrollment(value):
    """Pure structure only. B1/C1/D1/E1 remain external acceptance decisions."""
    e = strict(body(value))
    exact(
        e,
        "QD_AUTO_NATIVE_ENROLLMENT_V4",
        {
            "profile",
            "account_id",
            "epoch",
            "policy_digest",
            "inception_digest",
            "release_digest",
            "resources",
            "writers",
            "clock_source",
            "acceptance_id",
        },
    )
    if e["profile"] != PROFILE:
        raise ValueError("AUTO_ENROLLMENT_PROFILE_REQUIRED")
    for key in ("account_id", "epoch", "clock_source", "acceptance_id"):
        text(e[key])
    for key in ("policy_digest", "inception_digest", "release_digest"):
        hashed(e[key])
    if type(e["resources"]) is not dict or set(e["resources"]) != set(ROLES):
        raise ValueError("AUTO_ENROLLMENT_RESOURCE_ROSTER")
    paths, ids = [], []
    for resource in e["resources"].values():
        exact(resource, "QD_AUTO_NATIVE_ROOT_V4", {"path", "native_id"})
        native_id(resource["native_id"])
        path = resource["path"]
        if (
            type(path) is not str
            or not path.startswith("D:\\")
            or len(path) > 1024
            or any(c in path[2:] for c in (":", "%", "\x00", "/"))
            or any(p in ("", ".", "..") for p in path[3:].split("\\"))
        ):
            raise ValueError("AUTO_ENROLLMENT_D_ONLY_PATH")
        paths.append(ntpath.normcase(path))
        ids.append(body(resource["native_id"]))
    if (
        len(set(paths)) != len(ROLES)
        or len(set(ids)) != len(ROLES)
        or any(a != b and b.startswith(a + "\\") for a in paths for b in paths)
    ):
        raise ValueError("AUTO_ENROLLMENT_RESOURCE_ALIAS")
    if type(e["writers"]) is not dict or set(e["writers"]) != set(WRITERS):
        raise ValueError("AUTO_ENROLLMENT_WRITER_ROSTER")
    for identity in e["writers"].values():
        process(identity)  # Lifetime observation alone does not prove ownership.
        if not identity["image"].startswith("D:\\"):
            raise ValueError("AUTO_ENROLLMENT_D_ONLY_EXECUTABLE")
    return e


class AutonomousNativeEnrollment:
    """Injected authorities retain custody, revocation, single-use session state.

    acceptance.lease authenticates the complete profile-scoped gate disposition.
    custody.lease pins complete acknowledged financial/publication evidence.
    ownership.lease authenticates all writers and native.verify independently
    verifies existing root identities/ACLs and financial replay/report consistency.
    sessions.reserve must durably reject reused IDs, including after a crash.
    None of these trust implementations is installed or synthesized by this class.
    """

    acceptance_schema = "QD_AUTO_NATIVE_ACCEPTANCE_V4"
    acceptance_profile = PROFILE
    gate_names = ("B1", "C1", "D1", "E1")
    gate_status = "ACCEPTED"

    def __init__(
        self,
        *,
        enrollment=None,
        acceptance=None,
        custody=None,
        clock=None,
        ownership=None,
        native=None,
        sessions=None,
        scope="LOCAL_ENROLLED",
    ):
        if any(
            x is None for x in (enrollment, acceptance, custody, clock, ownership, native, sessions)
        ):
            raise ValueError("AUTO_ENROLLMENT_ACCEPTED_DEPENDENCIES_REQUIRED")
        if scope not in ("LOCAL_ENROLLED", "DISPOSABLE_TEST"):
            raise ValueError("AUTO_ENROLLMENT_SCOPE_REQUIRED")
        self._enrollment = body(validate_enrollment(enrollment))
        self.acceptance, self.custody, self.clock = acceptance, custody, clock
        self.ownership, self.native, self.sessions = ownership, native, sessions
        self.scope, self.last_clock, self.high_water = scope, None, None
        self.lock = RLock()

    @property
    def enrollment(self):
        return strict(self._enrollment)

    def _clock(self):
        s = strict(body(self.clock.sample()))
        exact(s, "QD_AUTO_NATIVE_CLOCK_V4", {"utc", "monotonic_ns", "uncertainty_ms", "source"})
        positive(s["utc"])
        positive(s["monotonic_ns"], zero=True)
        if (
            s["source"] != self.enrollment["clock_source"]
            or type(s["uncertainty_ms"]) is not int
            or not 0 <= s["uncertainty_ms"] <= 1000
            or self.clock.verify(strict(body(s))) is not True
        ):
            raise ValueError("AUTO_ENROLLMENT_CLOCK_UNVERIFIED")
        old = self.last_clock
        if old and (
            s["utc"] < old["utc"]
            or s["monotonic_ns"] < old["monotonic_ns"]
            or abs((s["utc"] - old["utc"]) - (s["monotonic_ns"] - old["monotonic_ns"]) / 1e9) > 2
        ):
            raise ValueError("AUTO_ENROLLMENT_CLOCK_DISCONTINUITY")
        self.last_clock = s
        return s["utc"]

    @staticmethod
    def _checked(lease, now):
        snapshot = strict(body(lease.snapshot))
        if lease.check(strict(body(snapshot)), now) is not True:
            raise ValueError("AUTO_ENROLLMENT_AUTHORITY_UNVERIFIED_OR_REVOKED")
        return snapshot

    @contextmanager
    def admitted(self, grant):
        """Recheck acceptance/revocation and custody before AND after each action."""
        with self.lock:
            e = self.enrollment
            g = strict(body(grant))
            exact(
                g,
                "QD_AUTO_NATIVE_SESSION_V4",
                {
                    "session_id",
                    "enrollment_digest",
                    "issued_at",
                    "expires_at",
                    "capabilities",
                },
            )
            text(g["session_id"])
            now = self._clock()
            for key in ("issued_at", "expires_at"):
                positive(g[key])
            if (
                g["enrollment_digest"] != digest(e)
                or g["capabilities"] != ["AUTO_PAPER"]
                or not g["issued_at"] <= now < g["expires_at"] <= g["issued_at"] + 28800
            ):
                raise ValueError("AUTO_ENROLLMENT_SESSION_BINDING_OR_EXPIRY")
            request = {"scope": self.scope, "enrollment": e, "grant": g}
            with self.acceptance.lease(strict(body(request)), now) as accepted:
                a = self._checked(accepted, now)
                exact(
                    a,
                    self.acceptance_schema,
                    {
                        "request_digest",
                        "scope",
                        "acceptance_id",
                        "profile",
                        "gates",
                        "revoked",
                        "issued_at",
                        "expires_at",
                    },
                )
                if (
                    a["request_digest"] != digest(request)
                    or a["scope"] != self.scope
                    or a["acceptance_id"] != e["acceptance_id"]
                    or a["profile"] != self.acceptance_profile
                    or a["gates"] != dict.fromkeys(self.gate_names, self.gate_status)
                    or a["revoked"] is not False
                ):
                    raise ValueError("AUTO_ENROLLMENT_PROFILE_NOT_ACCEPTED")
                for key in ("issued_at", "expires_at"):
                    positive(a[key])
                if not a["issued_at"] <= now <= a["expires_at"] <= a["issued_at"] + 30:
                    raise ValueError("AUTO_ENROLLMENT_ACCEPTANCE_STALE")
                with self.ownership.lease(strict(body(request)), now) as owned:
                    o = self._checked(owned, now)
                    exact(
                        o,
                        "QD_AUTO_NATIVE_OWNERSHIP_V4",
                        {"request_digest", "writers", "resources", "unknown_writers"},
                    )
                    if (
                        o["request_digest"] != digest(request)
                        or body(o["writers"]) != body(e["writers"])
                        or body(o["resources"]) != body(e["resources"])
                        or o["unknown_writers"] != []
                    ):
                        raise ValueError("AUTO_ENROLLMENT_OWNERSHIP_MISMATCH")
                    with self.custody.lease(strict(body(request)), now) as current:
                        c = self._checked(current, now)
                        exact(
                            c,
                            "QD_AUTO_NATIVE_CURRENT_V4",
                            {
                                "request_digest",
                                "scope",
                                "revision",
                                "acknowledged_revision",
                                "high_water",
                                "generation",
                                "financial_digest",
                                "publication_ack",
                                "publication",
                                "status",
                                "observed_at",
                                "expires_at",
                            },
                        )
                        for key in (
                            "revision",
                            "acknowledged_revision",
                            "high_water",
                            "generation",
                        ):
                            positive(c[key], zero=True)
                        hashed(c["financial_digest"])
                        text(c["publication_ack"])
                        p = c["publication"]
                        exact(
                            p,
                            "QD_AUTO_NATIVE_PUBLICATION_V4",
                            {"intent_digest", "operation_id", "status", "ack_id"},
                        )
                        intent = publication_intent(e)
                        if (
                            p["intent_digest"] != digest(intent)
                            or p["operation_id"] != intent["operation_id"]
                            or p["status"] != "ACKNOWLEDGED"
                            or p["ack_id"] != c["publication_ack"]
                        ):
                            raise ValueError(
                                "AUTO_ENROLLMENT_PUBLICATION_UNACKNOWLEDGED_OR_FOREIGN"
                            )
                        positive(c["observed_at"])
                        positive(c["expires_at"])
                        if not c["observed_at"] <= now <= c["expires_at"] <= c["observed_at"] + 5:
                            raise ValueError("AUTO_ENROLLMENT_CURRENT_STALE")
                        if (
                            c["request_digest"] != digest(request)
                            or c["scope"] != self.scope
                            or c["status"] != "ACKNOWLEDGED"
                            or c["revision"] != c["acknowledged_revision"]
                            or c["revision"] != c["high_water"]
                        ):
                            raise ValueError("AUTO_ENROLLMENT_UNKNOWN_OR_HIGH_WATER")
                        previous = self.high_water
                        if previous and (
                            c["revision"] < previous[0]
                            or c["generation"] < previous[1]
                            or c["generation"] == previous[1]
                            and c["financial_digest"] != previous[2]
                            or c["revision"] > previous[0]
                            and c["generation"] <= previous[1]
                        ):
                            raise ValueError("AUTO_ENROLLMENT_ROLLBACK_OR_CONFLICT")
                        # This port must use existing-only native handles and the
                        # existing replay/auditor. A caller-supplied digest is not proof.
                        if (
                            self.native.verify(e, strict(body(c)), now, scope=self.scope)
                            is not True
                        ):
                            raise ValueError("AUTO_ENROLLMENT_NATIVE_EVIDENCE_REFUSED")
                        self.high_water = (c["revision"], c["generation"], c["financial_digest"])
                        yield strict(body(request))
                        end = self._clock()
                        if (
                            not now
                            <= end
                            < min(
                                g["expires_at"], a["expires_at"] + 1, c["expires_at"] + 1, now + 31
                            )
                        ):
                            raise ValueError("AUTO_ENROLLMENT_LEASE_EXPIRED")
                        for lease, original in ((accepted, a), (owned, o), (current, c)):
                            if body(self._checked(lease, end)) != body(original):
                                raise ValueError("AUTO_ENROLLMENT_EVIDENCE_CHANGED")
                        if (
                            self.native.verify(e, strict(body(c)), end, scope=self.scope)
                            is not True
                        ):
                            raise ValueError("AUTO_ENROLLMENT_NATIVE_CONTINUITY_LOST")

    def reserve_session(self, grant):
        """Explicit durable single-use reservation; construction never resumes it.

        An exception/ambiguous reservation is not retried or repaired here.
        Runtime actions still require admitted(); reservation alone grants nothing.
        """
        with self.admitted(grant) as request:
            receipt = self.sessions.reserve(strict(body(request)))
            exact(receipt, "QD_AUTO_NATIVE_SESSION_RESERVATION_V4", {"request_digest", "status"})
            if receipt["request_digest"] != digest(request) or receipt["status"] != "ACKNOWLEDGED":
                raise ValueError("AUTO_ENROLLMENT_SESSION_RESERVATION_UNKNOWN")
            if self.sessions.verify(strict(body(request)), strict(body(receipt))) is not True:
                raise ValueError("AUTO_ENROLLMENT_DURABLE_RESERVATION_UNVERIFIED")
            return strict(body(receipt))
