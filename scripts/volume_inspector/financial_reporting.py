"""Confined FS3 report archive and projection target; no operational registration.

All roots/current pins are explicitly injected test resources. This supplies no
issuer, independent clock, rollback authority, recovery override or live writer.
"""
import copy
import importlib.util
from itertools import islice
from pathlib import Path

from app.services.paper_daily_report import (
    audit_daily_report,
    build_daily_report,
    validate_scope,
)

_spec = importlib.util.spec_from_file_location("fs3_financial", Path(__file__).with_name("financial_record_store.py"))
f = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(f)
MAX_REPORTS = 128


class ProjectionTarget:
    """An explicit disposable native view, not a financial execution callback."""
    def __init__(self, root, expected_root):
        f.require_identity(expected_root)
        self.output = f.w.WindowsOutput(root)
        self.expected_root = copy.deepcopy(expected_root)
        if f.native.file_identity(self.output.root_handle) != expected_root:
            self.output.close()
            raise f.Refused("Wrong projection root")

    @staticmethod
    def provision_disposable(root):
        with f.w.WindowsOutput.create_root(root) as output:
            return f.native.file_identity(output.root_handle)

    def close(self):
        self.output.close()

    def _prefix(self, context):
        return f.digest([context["epoch"], context["operation_id"]])[:32]

    def verify_inventory(self, proofs):
        self.output._verify()
        if f.native.file_identity(self.output.root_handle) != self.expected_root:
            raise f.Refused("Projection root changed")
        expected = {proof["prefix"] + "-" + phase + ".json" for proof in proofs for phase in ("intent", "view", "ack")}
        actual = {p.name for p in islice(Path(self.output.root).iterdir(), f.MAX_OPERATIONS * 3 + 1)}
        if actual != expected:
            raise f.Refused("Unresolved or unexpected projection namespace")

    def publish(self, context, state):
        if f.digest(state) != context["state_digest"]:
            raise f.Refused("Projection state differs from committed receipt")
        prefix = self._prefix(context)
        intent = {"schema": "FS3_PROJECTION_INTENT_V1", "context": context}
        ib = self.output.write_bound(prefix + "-intent.json", f.encoded(intent))
        vb = self.output.write_bound(prefix + "-view.json", f.encoded(state))
        ack = {"schema": "FS3_PROJECTION_ACK_V1", "context": context, "intent": ib, "view": vb}
        ab = self.output.write_bound(prefix + "-ack.json", f.encoded(ack))
        proof = {"schema": "FS3_PROJECTION_PROOF_V1", "root": self.expected_root,
                 "prefix": prefix, "intent": ib, "view": vb, "ack": ab}
        self.verify(context, proof)
        return proof

    def verify(self, context, proof):
        if type(proof) is not dict:
            raise f.Refused("Projection proof required")
        f.require_identity(proof.get("root"))
        if (type(proof) is not dict or set(proof) != {"schema", "root", "prefix", "intent", "view", "ack"}
                or proof["schema"] != "FS3_PROJECTION_PROOF_V1" or proof["root"] != self.expected_root
                or f.native.file_identity(self.output.root_handle) != self.expected_root
                or proof["prefix"] != self._prefix(context)):
            raise f.Refused("Projection proof context/root mismatch")
        values = {phase: f.FinancialRecordStore._read(self, proof["prefix"] + "-" + phase + ".json", proof[phase])
                  for phase in ("intent", "view", "ack")}
        if (f.body(values["intent"]) != f.body({"schema": "FS3_PROJECTION_INTENT_V1", "context": context})
                or f.digest(values["view"]) != context["state_digest"]
                or f.body(values["ack"]) != f.body({"schema": "FS3_PROJECTION_ACK_V1", "context": context,
                                                  "intent": proof["intent"], "view": proof["view"]})):
            raise f.Refused("Projection intent/view/ack disagreement")


class ReportArchive:
    """Immutable report versions with injected test high-water custody."""
    guard = f.FinancialRecordStore.guard
    _read = f.FinancialRecordStore._read
    _latch = f.FinancialRecordStore._latch
    close = f.FinancialRecordStore.close
    pin_schema = "FS3_REPORT_PIN_V1"
    document_schema = "FS3_REPORT_DOCUMENT_V1"

    @staticmethod
    def provision_disposable(root, scope, manifest):
        validate_scope(scope, manifest)
        with f.w.WindowsOutput.create_root(root) as output:
            binding = output.write_bound("scope.json", f.encoded(scope))
            return {"schema": "FS3_REPORT_PIN_V1", "root": f.native.file_identity(output.root_handle),
                    "scope": binding, "reports": []}

    def __init__(self, root, trust):
        self.trust, self.poisoned, self.mutex = trust, False, None
        self.output = f.w.WindowsOutput(root)
        try:
            pin = trust.current()
            f.require_identity(pin["root"])
            if f.native.file_identity(self.output.root_handle) != pin["root"]:
                raise f.Refused("Wrong report root")
            self.coordinator = f.native.Registry.__new__(f.native.Registry)
            self.coordinator.output, self.coordinator.root_id = self.output, pin["root"]
            self.coordinator._create_mutex()
            self.mutex = self.coordinator.mutex
            with self.guard(): self._load()
        except BaseException:
            self.close()
            raise

    def _load(self):
        pin = copy.deepcopy(self.trust.current())
        if (type(pin) is not dict or set(pin) != {"schema", "root", "scope", "reports"}
                or pin["schema"] != getattr(self, 'pin_schema', 'FS3_REPORT_PIN_V1') or type(pin["reports"]) is not list
                or len(pin["reports"]) > MAX_REPORTS
                or f.native.file_identity(self.output.root_handle) != pin["root"]):
            raise f.Refused("Malformed current report pin")
        f.require_identity(pin["root"])
        scope = self._read("scope.json", pin["scope"])
        documents, previous = [], pin["scope"]
        expected = {"scope.json"}
        for revision, binding in enumerate(pin["reports"], 1):
            leaf = f"{revision:04d}-report.json"
            expected.add(leaf)
            document = self._read(leaf, binding)
            if (set(document) != {"schema", "revision", "previous", "report_id", "report"}
                    or document["schema"] != getattr(self, 'document_schema', 'FS3_REPORT_DOCUMENT_V1') or type(document["revision"]) is not int
                    or document["revision"] != revision or f.body(document["previous"]) != f.body(previous)
                    or document["report_id"] != f.digest(document["report"])):
                raise f.Refused("Report revision lineage mismatch")
            documents.append(document)
            previous = binding
        if {p.name for p in islice(Path(self.output.root).iterdir(), MAX_REPORTS + 2)} != expected:
            raise f.Refused("Unresolved report publication or substituted namespace")
        return pin, scope, documents

    def _publish(self, pin, documents, report):
        for document in documents:
            if document["report_id"] == f.digest(report):
                if f.body(document["report"]) != f.body(report):
                    raise f.Refused("Conflicting deterministic report identity")
                return copy.deepcopy(document)
        if len(documents) >= MAX_REPORTS:
            raise f.Refused("Report capacity exhausted")
        revision = len(documents) + 1
        document = {"schema": self.document_schema, "revision": revision,
                    "previous": pin["reports"][-1] if documents else pin["scope"],
                    "report_id": f.digest(report), "report": report}
        try:
            binding = self.output.write_bound(f"{revision:04d}-report.json", f.encoded(document))
            self._read(f"{revision:04d}-report.json", binding)
            next_pin = copy.deepcopy(pin)
            next_pin["reports"].append(binding)
            self.trust.advance(pin, next_pin)
            self._load()
            return document
        except BaseException:
            self.poisoned = True
            self._latch()
            raise

    def remaining_reports(self):
        """Immutable pin/inventory verification only; never publishes a latch."""
        return MAX_REPORTS-len(self._load()[2])


class ReportService:
    """Store-bound read/report-only interface; never executes a financial event."""
    def __init__(self, store, archive):
        self.store, self.archive = store, archive

    def _history(self, source, scope, documents):
        pin, manifest, rows, _, _, _, _ = source
        validate_scope(scope, manifest)
        for document in documents:
            report = document["report"]
            n = report["source"]["revision"]
            if type(n) is not int or not 0 <= n <= len(rows):
                raise f.Refused("Historical report source revision mismatch")
            subpin = {**pin, "entries": pin["entries"][:n]}
            subrows = rows[:n]
            state, _, _ = f.replay_verified_events(manifest, subrows)
            if report['schema'] == 'FS3_PERP_SESSION_REPORT_V1':
                from app.services.paper_perp_session_report import audit_session_report
                audit_session_report(report, scope, manifest, subpin, subrows, state)
            else:
                audit_daily_report(report, scope, manifest, subpin, subrows, state)

    def publish(self, day, observed_at):
        # Fixed lock order: source then reports. No provider/process waits.
        with self.store.guard(), self.archive.guard():
            source = self.store._load()
            pin, scope, documents = self.archive._load()
            self._history(source, scope, documents)
            self.store.trust.check_clock(observed_at)
            source_pin, manifest, rows, _, _, _, _ = source
            report = build_daily_report(scope, manifest, source_pin, rows, day, observed_at)
            return self.archive._publish(pin, documents, report)

    def history(self):
        with self.store.guard(), self.archive.guard():
            source = self.store._load()
            _, scope, documents = self.archive._load()
            self._history(source, scope, documents)
            return copy.deepcopy(documents)

    def publish_session(self, *, session_id, started_at, cutoff_at, observed_at):
        from app.services.paper_perp_session_report import build_session_report
        with self.store.guard(), self.archive.guard():
            source = self.store._load()
            pin, scope, documents = self.archive._load()
            self._history(source, scope, documents)
            self.store.trust.check_clock(observed_at)
            source_pin, manifest, rows, _, _, _, _ = source
            if scope['schema'] == 'FS3_QD_REPORT_SCOPE_V2':
                from datetime import datetime
                from zoneinfo import ZoneInfo
                day = datetime.fromtimestamp(cutoff_at, ZoneInfo(scope['timezone'])).date().isoformat()
                report = build_daily_report(scope, manifest, source_pin, rows, day, observed_at,
                    session={'session_id': session_id, 'started_at': started_at, 'cutoff_at': cutoff_at})
            else:
                report = build_session_report(scope, manifest, source_pin, rows, session_id=session_id,
                                             started_at=started_at, cutoff_at=cutoff_at, observed_at=observed_at)
            return self.archive._publish(pin, documents, report)

    def try_publish(self, day, observed_at):
        try:
            return self.publish(day, observed_at)
        except (f.Refused, OSError, ValueError, KeyError, TypeError):
            return {"schema": "FS3_REPORT_UNAVAILABLE_V1", "status": "UNKNOWN", "source": None,
                    "cash": None, "realized": None, "valuation": None,
                    "reasons": ["SOURCE_PROJECTION_OR_PUBLICATION_UNVERIFIED"],
                    "startup_authorized": False, "production_authorized": False}
