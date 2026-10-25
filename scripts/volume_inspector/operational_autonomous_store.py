"""Uninstalled operational autonomous record codec over the existing FS2 engine.

No provisioning, migration, issuer, credentials, route or startup implementation.
Existing immutable operational inception and independently accepted dependencies
are mandatory. Test records/pins are never imported, renamed or adopted.
"""

import importlib.util
from contextlib import contextmanager
from pathlib import Path
from typing import ClassVar

from app.investment.quality_dips_operational_contract import exact
from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_autonomous_enrollment import validate_enrollment

_spec = importlib.util.spec_from_file_location(
    "op_auto_fs2", Path(__file__).with_name("financial_record_store.py")
)
fs2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fs2)


class OperationalAutonomousStore(fs2.FinancialRecordStore):
    record_versions: ClassVar[dict] = {
        "pin": "QD_AUTO_OP_PIN_V1",
        "record": "QD_AUTO_OP_RECORD_V1",
        "intent": "QD_AUTO_OP_INTENT_V1",
        "commit": "QD_AUTO_OP_COMMIT_V1",
        "ack": "QD_AUTO_OP_ACK_V1",
        "projection_ack": "QD_AUTO_OP_PROJECTED_ACK_V1",
    }

    @staticmethod
    def provision_disposable(*args, **kwargs):
        raise ValueError(
            "OPERATIONAL_INCEPTION_REQUIRES_SEPARATE_PUBLICATION_AUTHORITY"
        )

    def __init__(
        self,
        *,
        enrollment=None,
        trust=None,
        authority=None,
        clock=None,
        projection=None,
    ):
        if any(v is None for v in (enrollment, trust, authority, clock, projection)):
            raise ValueError("OP_AUTO_ACCEPTED_DEPENDENCIES_REQUIRED")
        self.enrollment = validate_enrollment(enrollment)
        self.authority, self.clock, self._custody = authority, clock, trust
        if trust.current().get("schema") != self.record_versions["pin"]:
            raise ValueError("OP_AUTO_NO_TEST_OR_MANUAL_PIN_ADOPTION")
        if (
            trust.current().get("root")
            != self.enrollment["resources"]["source"]["native_id"]
            or projection.expected_root
            != self.enrollment["resources"]["projection"]["native_id"]
            or Path(projection.output.root)
            != Path(self.enrollment["resources"]["projection"]["path"])
        ):
            raise ValueError("OP_AUTO_RESOURCE_BINDING_BEFORE_ACCESS")
        try:
            with self._admitted(None):
                super().__init__(
                    self.enrollment["resources"]["source"]["path"],
                    trust,
                    projection=projection,
                )
                if (
                    trust.current()["root"]
                    != self.enrollment["resources"]["source"]["native_id"]
                ):
                    self.close()
                    raise ValueError("OP_AUTO_ENROLLED_ROOT_MISMATCH")
        except BaseException:
            if hasattr(self, "output"):
                self.close()
            raise

    @contextmanager
    def _admitted(self, command):
        now = self.clock()
        if type(now) is not int or now <= 0:
            raise ValueError("OP_AUTO_TRUSTED_CLOCK_REQUIRED")
        request = {
            "schema": "QD_AUTO_OP_ADMISSION_REQUEST_V1",
            "enrollment": self.enrollment,
            "current": self._custody.current(),
            "command": command,
        }
        with self.authority.lease(strict(body(request)), now) as lease:
            witness = strict(body(lease.snapshot))
            exact(
                witness,
                "QD_AUTO_OP_ADMISSION_V1",
                {"request_digest", "status", "reservation_id", "expires_at", "revoked"},
            )
            if (
                lease.check(witness, now) is not True
                or witness["request_digest"] != digest(request)
                or witness["status"]
                != ("READ_ACCEPTED" if command is None else "PENDING")
                or type(witness["expires_at"]) is not int
                or not now <= witness["expires_at"] <= now + 5
                or witness["revoked"] is not False
                or type(witness["reservation_id"]) is not str
                or not witness["reservation_id"]
            ):
                raise ValueError("OP_AUTO_ADMISSION_OR_DURABLE_RESERVATION_REFUSED")
            yield lease, request
            end = self.clock()
            if (
                type(end) is not int
                or not now <= end <= witness["expires_at"]
                or lease.check(witness, end) is not True
            ):
                raise ValueError("OP_AUTO_AUTHORITY_OR_CLOCK_CONTINUITY_LOST")

    def _read(self, leaf, binding):
        value = super()._read(leaf, binding)
        if leaf != "inception.json":
            return value
        exact(
            value,
            "QD_AUTO_OP_INCEPTION_V1",
            {"enrollment_digest", "parameters", "execution"},
        )
        parameters = value["parameters"]
        if (
            value["enrollment_digest"] != digest(self.enrollment)
            or value["execution"] != "SIMULATED"
            or parameters.get("schema") != "PAPER_EPOCH_AUTONOMOUS_QD_V1"
            or parameters.get("epoch") != self.enrollment["epoch"]
            or digest(parameters) != self.enrollment["inception_digest"]
            or digest(parameters.get("autonomous_policy"))
            != self.enrollment["policy_digest"]
            or parameters.get("release") != self.enrollment["release_digest"]
            or parameters.get("provenance") != "ACCEPTED_AUTONOMOUS_PAPER_PARAMETERS_V1"
        ):
            raise ValueError("OP_AUTO_INCEPTION_BINDING_OR_PARAMETERS_REFUSED")
        # Calculation parameters only; original bytes remain the distinct
        # operational inception envelope. No fixture account is converted.
        return parameters

    def snapshot(self):
        with self._admitted(None):
            value = super().snapshot()
            return {**value, "schema": "QD_AUTO_OP_ACKNOWLEDGED_VIEW_V1"}

    def execute(self, command, *, projection_required=True):
        if (
            command.get("schema") != "QD_AUTO_COMMAND_V1"
            or command.get("manual") is not False
            or projection_required is not True
        ):
            raise ValueError("OP_AUTO_AUTONOMOUS_PROJECTED_COMMAND_REQUIRED")
        lease, request = None, None
        try:
            with self._admitted(command) as (lease, request):
                receipt = super().execute(command, projection_required=True)
                ack = lease.acknowledge(request, receipt, self._custody.current())
                exact(
                    ack,
                    "QD_AUTO_OP_RESERVATION_ACK_V1",
                    {"request_digest", "receipt_digest", "status"},
                )
                if (
                    ack["request_digest"] != digest(request)
                    or ack["receipt_digest"] != digest(receipt)
                    or ack["status"] != "ACKNOWLEDGED"
                    or lease.verify_ack(ack) is not True
                ):
                    raise ValueError("OP_AUTO_RESERVATION_ACK_UNKNOWN")
                return receipt
        except BaseException:
            self.poisoned = True
            if lease is not None:
                try:
                    lease.mark_unknown(request)
                except (OSError, ValueError):
                    pass  # Failed authority cannot promise a durable UNKNOWN receipt.
            raise
