"""Source-only enrollment intent/readback. No publisher, issuer, loader or startup.

Only independently accepted injected authorities can authenticate scope/witness.
JSON plans and test doubles confer no authority. No path is created or repaired.
"""

import ntpath
from contextlib import contextmanager

from app.investment.quality_dips_operational_contract import (
    exact,
    hashed,
    positive,
    validate_enrollment,
)
from app.services.paper_financial_replay import body, digest, number, strict, text


class EnrollmentRefused(ValueError):
    """Incomplete/uncertain evidence; never permission to replay publication."""


class EnrollmentBootstrap:
    """Publication authority must durably preserve operation state across crashes.

    issuer.lease(scope,now).check authenticates B1/C1/D1 account/policy/release,
    actual resources, principal and read-service scope. publication.lease exposes
    an independently authenticated durable witness and monotonic high-water.
    No implementation of either authority or publisher is provided.
    """

    def __init__(self, *, enrollment, release, issuer, publication, clock, composition):
        if any(
            value is None
            for value in (enrollment, release, issuer, publication, clock, composition)
        ):
            raise EnrollmentRefused("ENROLLMENT_ACCEPTED_DEPENDENCIES_REQUIRED")
        self.enrollment, self.release = strict(body(enrollment)), strict(body(release))
        validate_enrollment(self.enrollment)
        exact(self.release, "QD_OP_ENROLLMENT_RELEASE_V1", {"sha256", "executable"})
        hashed(self.release["sha256"])
        executable = self.release["executable"]
        if (
            type(executable) is not str
            or not ntpath.isabs(executable)
            or len(executable) > 512
            or len(ntpath.splitdrive(executable)[0]) != 2
            or not executable.lower().endswith(".exe")
            or "%" in executable
            or "\x00" in executable
            or ":" in executable[2:]
            or ".." in executable.replace("/", "\\").split("\\")
        ):
            raise EnrollmentRefused("ACCEPTED_LOCAL_EXECUTABLE_REQUIRED")
        if getattr(composition, "operational", None) is not True or body(
            composition.enrollment
        ) != body(self.enrollment):
            raise EnrollmentRefused("ACCEPTED_OPERATIONAL_COMPOSITION_REQUIRED")
        self.issuer, self.publication, self.clock, self.composition = (
            issuer,
            publication,
            clock,
            composition,
        )

    def _scope(self):
        e = self.enrollment
        scope = {
            "schema": "QD_OP_ENROLLMENT_INTENT_V1",
            "account_id": e["account"]["account_id"],
            "epoch": e["account"]["epoch"],
            "enrollment_digest": digest(e),
            "policy_digest": digest(e["policy"]),
            "resources_digest": digest(e["resources"]),
            "release_digest": self.release["sha256"],
            "executable": self.release["executable"],
            "capabilities": ["READ_ONLY"],
        }
        # Once per account/epoch, not once per process, resource substitution or
        # release upgrade. Custody must reject a changed payload under this ID.
        scope["operation_id"] = "qd-enrollment:" + digest(
            [scope["account_id"], scope["epoch"]]
        )
        return scope

    @contextmanager
    def _admitted(self):
        scope = self._scope()
        now = self.clock()
        positive(now)
        with self.issuer.lease(strict(body(scope)), now) as approval:
            if approval.check(strict(body(scope)), now) is not True:
                raise EnrollmentRefused("INDEPENDENT_ENROLLMENT_ISSUER_REQUIRED")
            with self.publication.lease(strict(body(scope)), now) as lease:
                witness = strict(body(lease.snapshot))
                if lease.check(strict(body(witness)), now) is not True:
                    raise EnrollmentRefused("DURABLE_PUBLICATION_AUTHORITY_REQUIRED")
                exact(
                    witness,
                    "QD_OP_PUBLICATION_WITNESS_V1",
                    {
                        "intent_digest",
                        "operation_id",
                        "state",
                        "ack_id",
                        "current_digest",
                        "resources_digest",
                        "acknowledged_at",
                    },
                )
                if (
                    witness["intent_digest"] != digest(scope)
                    or witness["operation_id"] != scope["operation_id"]
                    or witness["resources_digest"] != scope["resources_digest"]
                    or witness["state"]
                    not in (
                        "UNPUBLISHED",
                        "PENDING",
                        "UNKNOWN",
                        "FAILED",
                        "ACKNOWLEDGED",
                    )
                ):
                    raise EnrollmentRefused("PUBLICATION_SCOPE_OR_STATE_REFUSED")
                if witness["state"] == "ACKNOWLEDGED":
                    text(witness["ack_id"])
                    hashed(witness["current_digest"])
                    positive(witness["acknowledged_at"])
                    if witness["acknowledged_at"] > now:
                        raise EnrollmentRefused("FUTURE_PUBLICATION_ACK")
                elif witness["state"] == "UNPUBLISHED" and any(
                    witness[k] is not None
                    for k in ("ack_id", "current_digest", "acknowledged_at")
                ):
                    raise EnrollmentRefused("CONTRADICTORY_UNPUBLISHED_STATE")
                yield scope, witness, now
                end = self.clock()
                if (
                    type(end) is not int
                    or not now <= end <= now + 30
                    or approval.check(strict(body(scope)), end) is not True
                    or lease.check(strict(body(witness)), end) is not True
                ):
                    raise EnrollmentRefused("ENROLLMENT_AUTHORITY_CONTINUITY_LOST")
                checked = self.clock()
                if type(checked) is not int or not end <= checked <= now + 30:
                    raise EnrollmentRefused("ENROLLMENT_CLOCK_CHANGED")

    def prepare(self):
        """Pure deterministic publication request, never a write or grant."""
        with self._admitted() as (scope, witness, _):
            if witness["state"] != "UNPUBLISHED":
                raise EnrollmentRefused("ENROLLMENT_NOT_NEW_NO_PUBLICATION_REPLAY")
            self.composition.admitted(lambda: None)  # Auth only, no store read.
            return strict(body(scope))

    def _readback(self, scope, witness):
        if witness["state"] != "ACKNOWLEDGED":
            raise EnrollmentRefused("ENROLLMENT_PUBLICATION_INCOMPLETE_OR_UNKNOWN")
        value = self.composition.preflight()
        state = value["state"]
        if (
            value["account_id"] != scope["account_id"]
            or value["epoch"] != scope["epoch"]
            or value["policy_digest"] != scope["policy_digest"]
            or type(value["source_revision"]) is not int
            or value["source_revision"] != 0
            or type(value["projection_revision"]) is not int
            or value["projection_revision"] != 0
            or value["status"] != "ACKNOWLEDGED"
            or value["source_identity"]["pin_digest"] != witness["current_digest"]
            or state["positions"] != {}
            or number(state["cash"]) != 1000
            or any(number(state[key]) != 0 for key in ("gross", "costs", "net"))
        ):
            raise EnrollmentRefused("GENESIS_READBACK_OR_CURRENT_PIN_MISMATCH")
        return {
            "schema": "QD_OP_ENROLLED_READ_READY_V1",
            "operation_id": scope["operation_id"],
            "enrollment_digest": scope["enrollment_digest"],
            "publication_digest": digest(witness),
            "current_digest": witness["current_digest"],
            "source_revision": 0,
            "report_status": value["report_status"],
            "commands_enabled": False,
            "operational_startup_authorized": False,
        }

    def verify_publication(self):
        """Idempotent authenticated genesis read; never adopts an active account."""
        with self._admitted() as (scope, witness, _):
            return self._readback(scope, witness)

    def launch_plan(self):
        """Claims for a separately authenticated launcher, not a bearer token."""
        with self._admitted() as (scope, witness, now):
            ready = self._readback(scope, witness)
            return {
                "schema": "QD_OP_ENROLLED_LAUNCH_PLAN_V1",
                **{
                    k: scope[k]
                    for k in (
                        "operation_id",
                        "account_id",
                        "epoch",
                        "enrollment_digest",
                        "policy_digest",
                        "release_digest",
                        "executable",
                    )
                },
                "publication_digest": ready["publication_digest"],
                "issued_at": now,
                "expires_at": now + 30,
                "capabilities": ["READ_ONLY"],
            }


if __name__ == "__main__":
    raise SystemExit(
        "REFUSED: explicit independently accepted dependencies required; no default enrollment or launcher"
    )
