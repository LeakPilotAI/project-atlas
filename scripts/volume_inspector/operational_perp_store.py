"""Uninstalled perpetual codec on FS2; no provisioning, issuer or live routing.

Operational envelopes are distinct. The FS1 calculation parameters retain their
own operational schema; neither test pins nor fixture manifests are translated.
"""
import copy
import importlib.util
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import ClassVar

from app.investment.quality_dips_operational_contract import exact
from app.services.paper_financial_replay import body, digest, strict, validate_manifest
from app.services.perp_operational_contract import validate_enrollment

_spec = importlib.util.spec_from_file_location("perp_op_base", Path(__file__).with_name("operational_autonomous_store.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
_reports_spec = importlib.util.spec_from_file_location('perp_op_fs3', Path(__file__).with_name('financial_reporting.py'))
reports = importlib.util.module_from_spec(_reports_spec)
_reports_spec.loader.exec_module(reports)


class OperationalPerpStore(base.OperationalAutonomousStore):
    enrollment_validator = staticmethod(validate_enrollment)
    admission_request_schema = "PERP_AUTO_OP_ADMISSION_REQUEST_V1"
    admission_schema = "PERP_AUTO_OP_ADMISSION_V1"
    reservation_ack_schema = "PERP_AUTO_OP_RESERVATION_ACK_V1"
    view_schema = "PERP_AUTO_OP_ACKNOWLEDGED_VIEW_V1"
    record_versions: ClassVar[dict] = {
        "pin": "PERP_AUTO_OP_PIN_V1", "record": "PERP_AUTO_OP_RECORD_V1",
        "intent": "PERP_AUTO_OP_INTENT_V1", "commit": "PERP_AUTO_OP_COMMIT_V1",
        "ack": "PERP_AUTO_OP_ACK_V1", "projection_ack": "PERP_AUTO_OP_PROJECTED_ACK_V1",
    }

    def __init__(self, **kwargs):
        self._active_admission = ContextVar('perp_native_admission', default=False)
        super().__init__(**kwargs)

    @contextmanager
    def _admitted(self, command):
        with super()._admitted(command) as value:
            token = self._active_admission.set(True)
            try:
                yield value
            finally:
                self._active_admission.reset(token)

    @contextmanager
    def guard(self):
        if not self._active_admission.get():
            raise ValueError("PERP_NATIVE_ADMISSION_REQUIRED_BEFORE_WRITER_GUARD")
        with super().guard():
            yield

    def _read(self, leaf, binding):
        value = base.fs2.FinancialRecordStore._read(self, leaf, binding)
        if leaf != "inception.json":
            return value
        exact(value, "PERP_AUTO_OP_INCEPTION_V1", {"enrollment_digest", "parameters", "execution"})
        m = value["parameters"]
        if (value["enrollment_digest"] != digest(self.enrollment) or value["execution"] != "SIMULATED"
                or type(m) is not dict or m.get("schema") != "PAPER_EPOCH_PERP_OPERATIONAL_V1"
                or m.get("epoch") != self.enrollment["epoch"] or digest(m) != self.enrollment["inception_digest"]
                or digest(m.get("perp_policy")) != self.enrollment["policy_digest"]
                or m.get("release") != self.enrollment["release_digest"]):
            raise ValueError("PERP_OPERATIONAL_INCEPTION_BINDING_REQUIRED")
        validate_manifest(m)
        return m

    def _validate_command(self, command, projection_required):
        if (type(command) is not dict or command.get("schema") not in (
                "PAPER_PERP_COMMAND_V2", "PAPER_PERP_FUNDING_RECOVERY_V1", "PAPER_PERP_MARGIN_ENTRY_V1",
                "PAPER_PERP_MARGIN_MARK_V1", "PAPER_PERP_IOC_ENTRY_V1", "PAPER_PERP_IOC_MARGIN_ENTRY_V1",
                "PAPER_PERP_LIQUIDATION_V1", "PAPER_PERP_MAKER_FILL_V1") or projection_required is not True):
            raise ValueError("PERP_CANONICAL_PROJECTED_COMMAND_REQUIRED")

    def _inspection(self):
        # No writer mutex or failure latch: immutable reads under authenticated
        # read admission, bounded by identical custody pins before and after.
        with self._admitted(None):
            return self._inspect_existing()

    def verified_cut(self):
        pin, manifest, _, state, head, operations, audit = self._inspection()
        return copy.deepcopy({"manifest": manifest, "root": pin["root"], "state": state, "head": head,
                              "audit": audit, "pin_schema": pin["schema"],
                              "acknowledged_operations": {k: digest(v[0]) for k, v in operations.items()}})

    def preview(self, command):
        self._validate_command(command, True)
        pin, manifest, _, state, head, operations, _ = self._inspection()
        if command.get("operation_id") in operations:
            raise ValueError("PERP_EXISTING_OPERATION_PREVIEW_REFUSED")
        candidate, receipt = base.fs2.apply_event(manifest, state, command)
        return copy.deepcopy({"manifest": manifest, "root": pin["root"], "head": head,
                              "before": state, "after": candidate, "receipt": receipt})

    def operation_receipt(self, operation_id, payload_digest):
        original = self._inspection()[5].get(operation_id)
        if original is None or digest(original[0]) != payload_digest:
            raise ValueError("PERP_MISSING_OR_CONFLICTING_ACK")
        return strict(body(original[1]))


class OperationalPerpReportArchive(reports.ReportArchive):
    pin_schema = 'PERP_AUTO_OP_REPORT_PIN_V1'
    document_schema = 'PERP_AUTO_OP_REPORT_DOCUMENT_V1'

    @staticmethod
    def provision_disposable(*args, **kwargs):
        raise ValueError('PERP_REPORT_ENROLLMENT_REQUIRES_SEPARATE_PUBLICATION_AUTHORITY')

    def __init__(self, *, enrollment=None, trust=None, authority=None, clock=None):
        if any(v is None for v in (enrollment, trust, authority, clock)):
            raise ValueError('PERP_REPORT_ACCEPTED_DEPENDENCIES_REQUIRED')
        self.enrollment = validate_enrollment(enrollment)
        self.trust, self.authority, self.clock = trust, authority, clock
        self._active = ContextVar('perp_report_admission', default=False)
        self.poisoned = False
        pin = trust.current()
        if pin.get('schema') != self.pin_schema or pin.get('root') != self.enrollment['resources']['report']['native_id']:
            raise ValueError('PERP_REPORT_ENROLLED_PIN_REQUIRED_BEFORE_ACCESS')
        try:
            with self.admitted(write=False):
                super().__init__(self.enrollment['resources']['report']['path'], trust)
        except BaseException:
            if hasattr(self, 'output'):
                self.close()
            raise

    @contextmanager
    def admitted(self, *, write):
        if self.poisoned:
            raise ValueError('PERP_REPORT_PUBLICATION_UNKNOWN')
        now = self.clock()
        if type(now) is not int or now <= 0:
            raise ValueError('PERP_REPORT_TRUSTED_CLOCK_REQUIRED')
        request = {"schema": 'PERP_AUTO_OP_REPORT_REQUEST_V1', "enrollment": self.enrollment,
                       "current": self.trust.current(), "action": 'PUBLISH' if write else 'READ'}
        with self.authority.lease(request, now) as lease:
            witness = strict(body(lease.snapshot))
            exact(witness, 'PERP_AUTO_OP_REPORT_ADMISSION_V1', {'request_digest', 'status', 'reservation_id', 'expires_at', 'revoked'})
            if (lease.check(witness, now) is not True or witness['request_digest'] != digest(request)
                    or witness['status'] != ('PENDING' if write else 'READ_ACCEPTED')
                    or type(witness['expires_at']) is not int or not now <= witness['expires_at'] <= now + 5
                    or witness['revoked'] is not False or type(witness['reservation_id']) is not str or not witness['reservation_id']):
                raise ValueError('PERP_REPORT_AUTHORITY_REFUSED')
            token = self._active.set(True)
            try:
                yield lease, request
                end = self.clock()
                if type(end) is not int or not now <= end <= witness['expires_at'] or lease.check(witness, end) is not True:
                    raise ValueError('PERP_REPORT_CLOCK_OR_CUSTODY_CHANGED')
            except BaseException:
                if write:
                    self.poisoned = True
                    try:
                        lease.mark_unknown(request)
                    except (OSError, ValueError):
                        pass
                raise
            finally:
                self._active.reset(token)

    @contextmanager
    def guard(self):
        if not self._active.get():
            raise ValueError('PERP_REPORT_ADMISSION_REQUIRED_BEFORE_GUARD')
        with super().guard():
            yield


class OperationalPerpReportService(reports.ReportService):
    def __init__(self, store, archive):
        if (type(store) is not OperationalPerpStore or type(archive) is not OperationalPerpReportArchive
                or body(store.enrollment) != body(archive.enrollment)):
            raise ValueError('PERP_REPORT_SOURCE_COMPONENT_BINDING_REQUIRED')
        super().__init__(store, archive)

    def publish(self, day, observed_at):
        return self._publication(lambda: super(OperationalPerpReportService, self).publish(day, observed_at))

    def publish_session(self, **kwargs):
        return self._publication(lambda: super(OperationalPerpReportService, self).publish_session(**kwargs))

    def _publication(self, action):
        lease, request = None, None
        try:
            with self.store._admitted(None), self.archive.admitted(write=True) as (lease, request):
                document = action()
                ack = lease.acknowledge(request, document, self.archive.trust.current())
                exact(ack, 'PERP_AUTO_OP_REPORT_RESERVATION_ACK_V1', {'request_digest', 'receipt_digest', 'status'})
                if (ack['request_digest'] != digest(request) or ack['receipt_digest'] != digest(document)
                        or ack['status'] != 'ACKNOWLEDGED' or lease.verify_ack(ack) is not True):
                    raise ValueError('PERP_REPORT_ACK_UNKNOWN')
                return document
        except BaseException:
            # Also cover failure when the outer source lease exits after the
            # report ACK. Preserve uncertainty across the two custody stores.
            if lease is not None and not self.archive.poisoned:
                self.archive.poisoned = True
                try:
                    lease.mark_unknown(request)
                except (OSError, ValueError):
                    pass
            raise

    def history(self):
        # Dashboard reads must not consume abandoned writer mutex evidence or
        # publish recovery markers. Read immutable pins under both accepted leases.
        with self.store._admitted(None), self.archive.admitted(write=False):
            source = self.store._inspect_existing()
            pin, scope, documents = self.archive._load()
            self._history(source, scope, documents)
            if self.archive.trust.current() != pin or self.store.trust.current() != source[0]:
                raise ValueError('PERP_REPORT_SOURCE_OR_CUSTODY_CHANGED')
            return copy.deepcopy(documents)
