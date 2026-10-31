"""Uninstalled operational autonomous record codec over the existing FS2 engine.

No provisioning, migration, issuer, credentials, route or startup implementation.
Existing immutable operational inception and independently accepted dependencies
are mandatory. Test records/pins are never imported, renamed or adopted.
"""

import importlib.util
from contextlib import contextmanager
from functools import cache
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


@cache
def _report_read_module():
    # Cache trusted code loading only, never financial bytes, pins or results.
    # Every read still performs the original native identity/ACL/replay/audit.
    spec = importlib.util.spec_from_file_location(
        "op_auto_reports", Path(__file__).with_name("financial_read_port.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OperationalAutonomousStore(fs2.FinancialRecordStore):
    enrollment_validator = staticmethod(validate_enrollment)
    admission_request_schema = "QD_AUTO_OP_ADMISSION_REQUEST_V1"
    admission_schema = "QD_AUTO_OP_ADMISSION_V1"
    reservation_ack_schema = "QD_AUTO_OP_RESERVATION_ACK_V1"
    view_schema = "QD_AUTO_OP_ACKNOWLEDGED_VIEW_V1"
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
        self.enrollment = self.enrollment_validator(enrollment)
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
            "schema": self.admission_request_schema,
            "enrollment": self.enrollment,
            "current": self._custody.current(),
            "command": command,
        }
        with self.authority.lease(strict(body(request)), now) as lease:
            witness = strict(body(lease.snapshot))
            exact(
                witness,
                self.admission_schema,
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
            return {**value, "schema": self.view_schema}

    def _inspection(self):
        # Explicit operational read admission; never inherit the test-domain
        # inspection path or acquire a writer mutex from a preview/read.
        with self._admitted(None):
            return self._inspect_existing()

    def verified_cut(self):
        pin, manifest, _, state, head, operations, audit = self._inspection()
        return strict(body({"manifest": manifest, "root": pin['root'], "state": state, "head": head,
                            "audit": audit, "pin_schema": pin['schema'],
                            "acknowledged_operations": {key: digest(value[0]) for key, value in operations.items()}}))

    def preview(self, command):
        self._validate_command(command, True)
        pin, manifest, _, state, head, operations, _ = self._inspection()
        if command.get('operation_id') in operations:
            raise ValueError('OP_AUTO_EXISTING_OPERATION_PREVIEW_REFUSED')
        after, receipt = fs2.apply_event(manifest, state, command)
        return strict(body({'manifest': manifest, 'root': pin['root'], 'head': head,
                            'before': state, 'after': after, 'receipt': receipt}))

    def operation_receipt(self, operation_id, payload_digest):
        original = self._inspection()[5].get(operation_id)
        if original is None or digest(original[0]) != payload_digest:
            raise ValueError('OP_AUTO_MISSING_OR_CONFLICTING_ACK')
        return strict(body(original[1]))

    def _validate_command(self, command, projection_required):
        if (
            command.get("schema") != "QD_AUTO_COMMAND_V1"
            or command.get("manual") is not False
            or projection_required is not True
        ):
            raise ValueError("OP_AUTO_AUTONOMOUS_PROJECTED_COMMAND_REQUIRED")

    def execute(self, command, *, projection_required=True):
        self._validate_command(command, projection_required)
        lease, request = None, None
        try:
            with self._admitted(command) as (lease, request):
                receipt = super().execute(command, projection_required=True)
                ack = lease.acknowledge(request, receipt, self._custody.current())
                exact(
                    ack,
                    self.reservation_ack_schema,
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


class OperationalAutonomousReader:
    """Existing-only operational source/FS3 projection read. No guard or latch.

    Full daily-report/API composition still requires accepted report custody;
    this port does not silently substitute a fixture selected-account reader.
    """

    def __init__(self, *, enrollment, trust, authority, clock, projection):
        self.dependencies = enrollment, trust, authority, clock, projection

    @property
    def enrollment(self):
        return validate_enrollment(self.dependencies[0])

    def verify_resources(self):
        for resource in self.enrollment['resources'].values():
            with fs2.w.WindowsOutput(resource['path']) as out:
                if fs2.native.file_identity(out.root_handle) != resource['native_id']:
                    raise ValueError('OP_AUTO_NATIVE_RESOURCE_MISMATCH')
        return True

    def read_committed(self):
        enrollment, trust, authority, clock, projection = self.dependencies
        if any(v is None for v in self.dependencies):
            raise ValueError("OP_AUTO_ACCEPTED_READER_DEPENDENCIES_REQUIRED")
        e = validate_enrollment(enrollment)
        pin = trust.current()
        if (
            pin.get("schema") != "QD_AUTO_OP_PIN_V1"
            or pin.get("root") != e["resources"]["source"]["native_id"]
            or projection.expected_root != e["resources"]["projection"]["native_id"]
            or Path(projection.output.root)
            != Path(e["resources"]["projection"]["path"])
        ):
            raise ValueError("OP_AUTO_READER_RESOURCE_OR_PIN_MISMATCH")
        reader = OperationalAutonomousStore.__new__(OperationalAutonomousStore)
        reader.enrollment, reader._custody, reader.authority, reader.clock = (
            e,
            trust,
            authority,
            clock,
        )
        reader.trust, reader.projection = trust, projection
        with (
            reader._admitted(None),
            fs2.w.WindowsOutput(e["resources"]["source"]["path"]) as out,
        ):
            reader.output = out
            _, manifest, rows, state, head, _, audit = reader._load()
            if trust.current() != pin:
                raise ValueError("OP_AUTO_READER_CURRENT_CHANGED")
            return {
                "schema": "QD_AUTO_OP_READ_V1",
                "manifest": manifest,
                "rows": rows,
                "state": state,
                "head": head,
                "audit": audit,
                "source_pin": pin,
            }

    def read_verified(self, enrollment, current):
        """Port for the existing selected-account replay/report capability."""
        e, trust, _, _, _ = self.dependencies
        if (
            enrollment.get("schema") != "QD_AUTO_OP_READ_ENROLLMENT_V1"
            or enrollment["account_id"] != e["account_id"]
            or enrollment["epoch"] != e["epoch"]
            or enrollment["source_root"] != e["resources"]["source"]["native_id"]
            or enrollment["projection_root"]
            != e["resources"]["projection"]["native_id"]
            or enrollment["report_root"] != e["resources"]["report"]["native_id"]
            or current["source"] != trust.current()
        ):
            raise ValueError("OP_AUTO_READ_CAPABILITY_BINDING_REQUIRED")
        source = self.read_committed()
        m = _report_read_module()
        with fs2.w.WindowsOutput(e["resources"]["report"]["path"]) as out:
            if (
                fs2.native.file_identity(out.root_handle)
                != e["resources"]["report"]["native_id"]
            ):
                raise ValueError("OP_AUTO_REPORT_ROOT_MISMATCH")
            archive = m.BoundReader(out, current["reports"])
            _, scope, documents = m.m.ReportArchive._load(archive)
        if trust.current() != source["source_pin"]:
            raise ValueError("OP_AUTO_READ_SOURCE_CHANGED")
        return {
            **{k: source[k] for k in ("manifest", "rows", "state")},
            "scope": scope,
            "documents": documents,
        }
