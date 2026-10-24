"""Existing-only operational native reader; no financial writer or provisioning API."""
import importlib.util
from contextlib import contextmanager
from itertools import islice
from pathlib import Path

from app.investment.quality_dips_operational_contract import (
    binding,
    exact,
    validate_bundle,
)
from app.investment.quality_dips_operational_replay import history, replay
from app.services.paper_financial_replay import body, digest, strict

_spec = importlib.util.spec_from_file_location("qd_op_bound_primitives", Path(__file__).with_name("snapshot_store.py"))
s = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s)


class NativeOperationalReadPort:
    """Accepted custody must cover complete roster/exclusion, not local hashes.

    Read leases must support nested/shared readers: the outer capability and this
    independently callable native boundary both authenticate before file access.
    host_identity/observer come from the accepted composition, never JSON claims.
    """
    def __init__(self, *, authority, clock, observer, host_identity):
        if any(value is None for value in (authority, clock, observer, host_identity)):
            raise ValueError("OPERATIONAL_NATIVE_TRUST_REQUIRED")
        self.authority, self.clock = authority, clock
        self.observer, self.host_identity = observer, host_identity

    @contextmanager
    def _admitted(self, enrollment, current):
        now = self.clock()
        identity = {"schema": "QD_OP_PROCESS_ID_V1", **self.observer()}
        host = self.host_identity()
        with self.authority.lease(strict(body(enrollment)), now) as lease:
            bundle = strict(body(lease.snapshot))
            if lease.check(bundle, now) is not True or body(bundle["current"]) != body(current):
                raise ValueError("OPERATIONAL_NATIVE_CUSTODY_REFUSED")
            validate_bundle(enrollment, bundle, now, identity, host)
            yield now
            end = self.clock()
            if (type(end) is not int or end < now or self.observer() != {k: v for k, v in identity.items() if k != "schema"}
                    or self.host_identity() != host or lease.check(bundle, end) is not True):
                raise ValueError("OPERATIONAL_NATIVE_CONTINUITY_LOST")
            validate_bundle(enrollment, bundle, end, identity, host)
            checked = self.clock()
            if type(checked) is not int or checked < end:
                raise ValueError("OPERATIONAL_NATIVE_CLOCK_CHANGED")
            validate_bundle(enrollment, bundle, checked, identity, host)

    @staticmethod
    def _read(output, leaf, pin, schema):
        binding(pin, schema)
        raw, _ = s.read_bound(output, leaf, {"id": pin["native_id"], "sha256": pin["sha256"]})
        value = strict(raw.decode("utf-8"))
        if body(value).encode() != raw or value.get("schema") != schema:
            raise ValueError("OPERATIONAL_NATIVE_CANONICAL_SCHEMA_REQUIRED")
        return value

    @staticmethod
    def _inventory(output, expected):
        output._verify()
        actual = {p.name for p in islice(Path(output.root).iterdir(), 132)}
        if actual != expected:
            raise ValueError("OPERATIONAL_NATIVE_NAMESPACE_INCOMPLETE")

    def _load(self, enrollment, current, now):
        if current["report"]["schema"] != "QD_OP_REPORT_PIN_V2":
            raise ValueError("OPERATIONAL_HISTORICAL_REPORT_V2_REQUIRED")
        outputs = {}
        try:
            for role in ("source", "projection", "report"):
                resource = enrollment["resources"][role]
                output = s.w.WindowsOutput(resource["root_path"])
                outputs[role] = output
                if s.native.file_identity(output.root_handle) != resource["native_root"]:
                    raise ValueError("OPERATIONAL_NATIVE_ROOT_MISMATCH")
            expected = {"source": {"inception.json", *(f"{i:04d}-record.json" for i in range(1, current["revision"] + 1))},
                        "projection": {"projection.json"}, "report": {"report.json"}}
            for role, output in outputs.items():
                self._inventory(output, expected[role])
            account = self._read(outputs["source"], "inception.json", current["source"]["inception"], "QD_OP_ACCOUNT_V1")
            if body(account) != body(enrollment["account"]):
                raise ValueError("OPERATIONAL_NATIVE_ACCOUNT_MISMATCH")
            records = [self._read(outputs["source"], f"{i:04d}-record.json", pin, "QD_OP_FINANCIAL_RECORD_V1")
                       for i, pin in enumerate(current["source"]["records"], 1)]
            state, snapshots = replay(enrollment, current, records, now)
            documents = {"schema": "QD_OP_DOCUMENTS_V1"}
            for role, version in (("projection", "V1"), ("report", "V2")):
                doc = self._read(outputs[role], role + ".json", current[role]["record"],
                                 "QD_OP_" + role.upper() + "_DOCUMENT_" + version)
                fields = {"enrollment_digest", "source_pin_digest", "revision", "state"} if role == "projection" else {
                    "enrollment_digest", "source_pin_digest", "revision", "status", "timezone", "cutoff", "history"}
                exact(doc, "QD_OP_" + role.upper() + "_DOCUMENT_" + version, fields)
                if (doc["enrollment_digest"] != digest(enrollment) or type(doc["revision"]) is not int
                        or doc["revision"] != current["revision"] or doc["source_pin_digest"] != digest(current["source"])):
                    raise ValueError("OPERATIONAL_NATIVE_DOCUMENT_SCOPE")
                documents[role] = doc
            report = documents["report"]
            if (type(report["cutoff"]) is not int or not state["last_clock"] <= report["cutoff"] <= now
                    or body(documents["projection"]["state"]) != body(state)
                    or body(report["history"]) != body(history(records, snapshots, report["cutoff"], report["timezone"]))
                    or report["status"] != ("COMPLETE" if all(row["status"] == "COMPLETE" for row in report["history"]) else "INCOMPLETE")):
                raise ValueError("OPERATIONAL_NATIVE_FINANCIAL_RECONCILIATION")
            for role, output in outputs.items():
                self._inventory(output, expected[role])
            return documents
        finally:
            for output in reversed(list(outputs.values())):
                output.close()

    def read_operational(self, enrollment, current):
        with self._admitted(enrollment, current) as now:
            return self._load(enrollment, current, now)

    def verify_operational(self, enrollment, current, documents):
        # A fresh native read and independent audit, never a cached TRUE/digest.
        with self._admitted(enrollment, current) as now:
            verified = self._load(enrollment, current, now)
            return body(documents) == body(verified)
