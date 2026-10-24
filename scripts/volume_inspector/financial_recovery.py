"""Disposable archival recovery, never FS2 writer admission or operational authority.

Original logical bindings stay in immutable bytes. A separately accepted recovery
authority must bind the original cut AND new physical mapping. No default trust,
issuer, clock, filesystem custody, or financial execution interface is provided.
"""
import copy
import hashlib
import importlib.util
from itertools import islice
from pathlib import Path

from app.services.paper_daily_report import audit_daily_report, validate_scope
from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import (
    body,
    digest,
    replay_verified_events,
    strict,
)

_spec = importlib.util.spec_from_file_location("recovery_read_port", Path(__file__).with_name("financial_read_port.py"))
r = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r)
f = r.m.f
ROLES = ("source", "projection", "reports")
MAX_FILES = 1027


def original_evidence(enrollment, current, files):
    """Verify original logical identities/lineage from an authenticated backup.

    This does NOT pretend old physical IDs identify backup or destination files.
    Transport must verify those distinct physical bindings before passing bytes.
    """
    entries = current["source"]["entries"]
    reports = current["reports"]["reports"]
    for key in ("source_root", "projection_root", "report_root"):
        f.require_identity(enrollment[key])
    if (current["schema"] != "QD_READ_CURRENT_V1" or enrollment["schema"] != "QD_READ_ENROLLMENT_V1"
            or current["enrollment_digest"] != digest(enrollment)
            or current["status"] != "ACKNOWLEDGED"
            or type(current["generation"]) is not int or current["generation"] < 1
            or type(current["high_water"]) is not int
            or type(current["acknowledged_revision"]) is not int
            or current["high_water"] != len(entries) or current["acknowledged_revision"] != len(entries)
            or type(entries) is not list or type(reports) is not list
            or current["source"]["schema"] != "FS2_TEST_PIN_V1"
            or set(current["source"]) != {"schema", "root", "inception", "epoch", "entries"}
            or current["reports"]["schema"] != "FS3_REPORT_PIN_V1"
            or set(current["reports"]) != {"schema", "root", "scope", "reports"}
            or len(entries) > f.MAX_OPERATIONS or len(reports) > r.m.MAX_REPORTS
            or current["source"]["root"] != enrollment["source_root"]
            or current["source"]["inception"] != enrollment["inception"]
            or current["source"]["epoch"] != enrollment["epoch"]
            or current["reports"]["root"] != enrollment["report_root"]):
        raise ValueError("BACKUP_SOURCE_CUT_CONFLICT")
    used = set()
    def read(role, leaf, binding):
        key = (role, leaf)
        if key in used:
            raise ValueError("BACKUP_REUSED_LOGICAL_RECORD")
        used.add(key)
        raw, original = files[key]
        if body(original) != body(binding) or hashlib.sha256(raw).hexdigest() != binding["sha256"]:
            raise ValueError("BACKUP_LOGICAL_BINDING_CONFLICT")
        value = strict(raw.decode())
        if f.encoded(value) != raw:
            raise ValueError("BACKUP_NONCANONICAL")
        return value
    manifest = read("source", "inception.json", enrollment["inception"])
    f.validate_manifest(manifest)
    if (digest(manifest) != enrollment["manifest_digest"]
            or digest(manifest["account_policy"]) != enrollment["policy_digest"]
            or manifest["epoch"] != enrollment["epoch"]
            or manifest["account_policy"]["account_id"] != enrollment["account_id"]):
        raise ValueError("BACKUP_INCEPTION_SCOPE")
    rows = []
    previous = {"revision": 0, "record": enrollment["inception"], "event_digest": digest(manifest)}
    for revision, entry in enumerate(entries, 1):
        if set(entry) != {"intent", "record", "commit", "ack"}:
            raise ValueError("BACKUP_INCOMPLETE_OPERATION")
        values = {phase: read("source", f.name(revision, phase), entry[phase])
                  for phase in ("intent", "record", "commit", "ack")}
        if any(type(value.get("revision")) is not int for value in values.values()):
            raise ValueError("BACKUP_TYPED_REVISION")
        record = values["record"]
        row = record["event"]
        receipt = strict(row["receipt"])
        if receipt.get("projection_required") is not True:
            raise ValueError("BACKUP_SELECTED_PROJECTION_REQUIRED")
        proof = values["ack"]["projection"]
        context = f.projection_context(receipt, entry["record"], entry["commit"])
        prefix = digest([context["epoch"], context["operation_id"]])[:32]
        if (set(proof) != {"schema", "root", "prefix", "intent", "view", "ack"}
                or proof["schema"] != "FS3_PROJECTION_PROOF_V1"
                or proof["root"] != enrollment["projection_root"] or proof["prefix"] != prefix):
            raise ValueError("BACKUP_PROJECTION_IDENTITY")
        projected = {phase: read("projection", prefix + "-" + phase + ".json", proof[phase])
                     for phase in ("intent", "view", "ack")}
        if (body(projected["intent"]) != body({"schema": "FS3_PROJECTION_INTENT_V1", "context": context})
                or digest(projected["view"]) != context["state_digest"]
                or body(projected["ack"]) != body({"schema": "FS3_PROJECTION_ACK_V1", "context": context,
                                                   "intent": proof["intent"], "view": proof["view"]})):
            raise ValueError("BACKUP_PROJECTION_LINEAGE")
        expected = {
            "record": {"schema": "FS2_RECORD_V1", "revision": revision, "previous": previous, "event": row},
            "intent": {"schema": "FS2_INTENT_V1", "revision": revision, "previous": previous,
                       "record_digest": digest(record)},
            "commit": {"schema": "FS2_COMMIT_V1", "revision": revision, "previous": previous,
                       "intent": entry["intent"], "record": entry["record"]},
            "ack": {"schema": "FS3_ACK_V1", "revision": revision, "commit": entry["commit"], "projection": proof}}
        if body(expected) != body(values):
            raise ValueError("BACKUP_FINANCIAL_LINEAGE")
        rows.append(row)
        previous = {"revision": revision, "record": entry["record"], "event_digest": row["digest"]}
    scope = read("reports", "scope.json", current["reports"]["scope"])
    documents, previous = [], current["reports"]["scope"]
    for revision, binding in enumerate(reports, 1):
        document = read("reports", f"{revision:04d}-report.json", binding)
        if (type(document["revision"]) is not int or document["revision"] != revision
                or body(document) != body({"schema": "FS3_REPORT_DOCUMENT_V1", "revision": revision,
                                           "previous": previous, "report_id": digest(document["report"]),
                                           "report": document["report"]})):
            raise ValueError("BACKUP_REPORT_LINEAGE")
        documents.append(document)
        previous = binding
    if used != set(files):
        raise ValueError("BACKUP_INCOMPLETE_OR_EXTRA_SET")
    state, _, _ = replay_verified_events(manifest, rows)
    evidence = {"manifest": manifest, "rows": rows, "state": state, "scope": scope, "documents": documents}
    check_evidence(evidence, current)
    return evidence


def check_evidence(evidence, current):
    """Independent financial and historical report recomputation, no writes."""
    manifest, rows = evidence["manifest"], evidence["rows"]
    if (current["status"] != "ACKNOWLEDGED" or type(current["high_water"]) is not int
            or len(rows) != current["high_water"]
            or current["acknowledged_revision"] != len(rows)):
        raise ValueError("RECOVERY_UNKNOWN_OR_STALE")
    state, _, _ = replay_verified_events(manifest, rows)
    audit_financial_events(manifest, rows, state)
    if body(state) != body(evidence["state"]):
        raise ValueError("RECOVERY_STATE_CONFLICT")
    scope = evidence["scope"]
    validate_scope(scope, manifest)
    if not evidence["documents"]:
        raise ValueError("RECOVERY_REPORT_MISSING")
    for document in evidence["documents"]:
        report = document["report"]
        n = report["source"]["revision"]
        if type(n) is not int or not 0 <= n <= len(rows):
            raise ValueError("RECOVERY_REPORT_REVISION")
        substate, _, _ = replay_verified_events(manifest, rows[:n])
        pin = {**current["source"], "entries": current["source"]["entries"][:n]}
        audit_daily_report(report, scope, manifest, pin, rows[:n], substate)
    if evidence["documents"][-1]["report"]["source"]["revision"] != len(rows):
        raise ValueError("RECOVERY_REPORT_NOT_CURRENT")


class DisposableRecovery:
    """Explicit authority lease must exclude all writers and retain current custody.

    authority.lease(request) yields check() and accept(descriptor, commit_binding).
    check() must reject expired authority, rollback, stale backups and UNKNOWN.
    accept is a durable single-use/CAS external acknowledgement, NOT implemented
    here. validate(descriptor, binding) must independently recheck that custody.
    A callback failure leaves immutable intent/commit and an unrecoverable local
    UNKNOWN, never an automatically replayed financial or authority callback.
    """
    def __init__(self, authority):
        if authority is None:
            raise ValueError("RECOVERY_AUTHORITY_REQUIRED")
        self.authority = authority

    def restore_offline(self, *, backup_root, backup_manifest, source_cut, destination, recovery_id):
        """Ingest an independently authenticated backup, with no original paths.

        The injected lease must authenticate the exact manifest digest and cut
        against custody outside the backup's rollback domain, before any copy.
        This method neither issues that receipt nor exports/enrolls a backup.
        """
        manifest = strict(body(backup_manifest))
        cut = strict(body(source_cut))
        if (type(recovery_id) is not str or not 1 <= len(recovery_id) <= 128
                or set(manifest) != {"schema", "backup_id", "root", "enrollment", "current", "files"}
                or manifest["schema"] != "FS_OFFLINE_BACKUP_V1"
                or type(manifest["backup_id"]) is not str or not 1 <= len(manifest["backup_id"]) <= 128
                or type(manifest["files"]) is not list or not 1 <= len(manifest["files"]) <= MAX_FILES
                or len(f.encoded(manifest)) > 65536):
            raise ValueError("BACKUP_MANIFEST_SCHEMA_OR_CAPACITY")
        enrollment, current = manifest["enrollment"], manifest["current"]
        expected_cut = {"schema": "FS_BACKUP_CUT_V1", "backup_manifest_digest": digest(manifest),
                        "enrollment_digest": digest(enrollment), "source_pin_digest": digest(current),
                        "high_water": current["high_water"], "generation": current["generation"],
                        "status": "ACKNOWLEDGED"}
        if (body(cut) != body(expected_cut) or type(cut["high_water"]) is not int
                or type(cut["generation"]) is not int):
            raise ValueError("BACKUP_SOURCE_CUT_RECEIPT_MISMATCH")
        origin, target = Path(backup_root).resolve(), Path(destination).resolve()
        if origin.is_relative_to(target) or target.is_relative_to(origin):
            raise ValueError("RECOVERY_SOURCE_DESTINATION_OVERLAP")
        request = {"schema": "FS_OFFLINE_RECOVERY_REQUEST_V1", "recovery_id": recovery_id,
                   "enrollment": enrollment, "current": current, "source_cut": cut,
                   "backup_id": manifest["backup_id"], "backup_root": manifest["root"]}
        with self.authority.lease(copy.deepcopy(request)) as lease:
            if lease.check() is not True:
                raise ValueError("BACKUP_AUTHORITY_UNVERIFIED")
            files, originals, names = [], {}, set()
            with f.w.WindowsOutput(str(backup_root)) as output:
                f.require_identity(manifest["root"])
                if f.native.file_identity(output.root_handle) != manifest["root"]:
                    raise ValueError("BACKUP_ROOT_SUBSTITUTED")
                for item in manifest["files"]:
                    if (type(item) is not dict
                            or set(item) != {"role", "leaf", "original", "backup_leaf", "backup_binding"}
                            or item["role"] not in ROLES or type(item["leaf"]) is not str
                            or type(item["backup_leaf"]) is not str):
                        raise ValueError("BACKUP_FILE_SCHEMA")
                    key = (item["role"], item["leaf"])
                    if key in originals or item["backup_leaf"].casefold() in names:
                        raise ValueError("BACKUP_DUPLICATE_RECORD")
                    names.add(item["backup_leaf"].casefold())
                    for binding in (item["original"], item["backup_binding"]):
                        if type(binding) is not dict or set(binding) != {"id", "sha256"}:
                            raise ValueError("BACKUP_BINDING_SCHEMA")
                        f.require_identity(binding["id"])
                        if (type(binding["sha256"]) is not str or len(binding["sha256"]) != 64
                                or any(c not in "0123456789abcdef" for c in binding["sha256"])):
                            raise ValueError("BACKUP_BINDING_DIGEST")
                    raw, _ = f.s.read_bound(output, item["backup_leaf"], item["backup_binding"])
                    if hashlib.sha256(raw).hexdigest() != item["original"]["sha256"]:
                        raise ValueError("BACKUP_ORIGINAL_BYTES_CHANGED")
                    originals[key] = raw, item["original"]
                    files.append((item["role"], item["leaf"], raw, item["original"]))
                if {p.name.casefold() for p in islice(Path(backup_root).iterdir(), MAX_FILES + 1)} != names:
                    raise ValueError("BACKUP_INCOMPLETE_OR_EXTRA_NAMESPACE")
                evidence = original_evidence(enrollment, current, originals)
                if lease.check() is not True:
                    raise ValueError("BACKUP_CUSTODY_CHANGED")
                return self._publish(destination, request, evidence, files, lease, "FS_RECOVERY_ARCHIVE_V2")

    def restore(self, *, roots, destination, enrollment, current, recovery_id):
        if type(recovery_id) is not str or not recovery_id or len(recovery_id) > 128:
            raise ValueError("RECOVERY_ID_REQUIRED")
        if len(roots) != 3 or len(set(map(str, roots))) != 3:
            raise ValueError("DISTINCT_SOURCE_ROOTS_REQUIRED")
        destination_path = Path(destination).resolve()
        source_paths = [Path(root).resolve() for root in roots]
        if any(destination_path.is_relative_to(root) or root.is_relative_to(destination_path)
               for root in source_paths):
            raise ValueError("RECOVERY_SOURCE_DESTINATION_OVERLAP")
        request = copy.deepcopy({"schema": "FS_RECOVERY_REQUEST_V1", "recovery_id": recovery_id,
                                 "enrollment": enrollment, "current": current})
        # Authority is checked BEFORE destination allocation or source access.
        with self.authority.lease(copy.deepcopy(request)) as lease:
            if lease.check() is not True:
                raise ValueError("RECOVERY_AUTHORITY_UNVERIFIED")
            port = r.NativeFinancialReadPort(**dict(zip(
                ("source_root", "projection_root", "report_root"), map(str, roots), strict=True)))
            before = port.read_verified(enrollment, current)
            check_evidence(before, current)
            expected = {"source": {"inception.json": current["source"]["inception"]},
                        "projection": {}, "reports": {"scope.json": current["reports"]["scope"]}}
            with f.w.WindowsOutput(str(roots[0])) as source:
                for revision, entry in enumerate(current["source"]["entries"], 1):
                    for phase in ("intent", "record", "commit", "ack"):
                        expected["source"][f.name(revision, phase)] = entry[phase]
                    raw, _ = f.s.read_bound(source, f.name(revision, "ack"), entry["ack"])
                    ack = strict(raw.decode())
                    if "projection" in ack:
                        proof = ack["projection"]
                        for phase in ("intent", "view", "ack"):
                            expected["projection"][proof["prefix"] + "-" + phase + ".json"] = proof[phase]
            for revision, binding in enumerate(current["reports"]["reports"], 1):
                expected["reports"][f"{revision:04d}-report.json"] = binding
            files = []
            # Existing-only, identity-before-read. Never follow copied pins.
            for role, root in zip(ROLES, roots, strict=True):
                with f.w.WindowsOutput(str(root)) as output:
                    if f.native.file_identity(output.root_handle) != enrollment[{
                            "source": "source_root", "projection": "projection_root", "reports": "report_root"}[role]]:
                        raise ValueError("RECOVERY_ORIGIN_CHANGED")
                    names = sorted(p.name for p in Path(root).iterdir())
                    if set(names) != set(expected[role]):
                        raise ValueError("RECOVERY_SOURCE_NAMESPACE_CHANGED")
                    if len(files) + len(names) > MAX_FILES:
                        raise ValueError("RECOVERY_CAPACITY")
                    for leaf in names:
                        raw, original = f.s.read_bound(output, leaf, expected[role][leaf])
                        files.append((role, leaf, raw, original))
            # Complete source revalidation under externally supplied exclusion.
            if body(port.read_verified(enrollment, current)) != body(before) or lease.check() is not True:
                raise ValueError("RECOVERY_SOURCE_CHANGED")
            return self._publish(destination, request, before, files, lease, "FS_RECOVERY_ARCHIVE_V1")

    def _publish(self, destination, request, before, files, lease, schema):
        with f.w.WindowsOutput.create_root(str(destination)) as output:
            intent = output.write_bound("intent.json", f.encoded(request))
            mapping = []
            for index, (role, leaf, raw, original) in enumerate(files):
                target = f"copy-{index:04d}.json"
                restored = output.write_bound(target, raw)
                f.s.read_bound(output, target, restored)
                mapping.append({"role": role, "leaf": leaf, "original": original,
                                "target": target, "restored": restored})
            descriptor = {"schema": schema, "request": request,
                          "root": f.native.file_identity(output.root_handle), "intent": intent,
                          "mapping": mapping, "evidence": before,
                          "startup_authorized": False, "financial_writes_authorized": False}
            raw_descriptor = f.encoded(descriptor)
            if len(raw_descriptor) > 65536:
                raise ValueError("RECOVERY_DESCRIPTOR_CAPACITY")
            binding = output.write_bound("commit.json", raw_descriptor)
            f.s.read_bound(output, "commit.json", binding)
            if lease.check() is not True or lease.accept(copy.deepcopy(descriptor), copy.deepcopy(binding)) is not True:
                raise ValueError("RECOVERY_COMMITTED_UNACKNOWLEDGED_UNKNOWN")
            # The independent authority owns acknowledgement; a copied local
            # ack would not make a second restored root authoritative.
            return {"schema": "FS_RECOVERY_RECEIPT_V1", "root": descriptor["root"], "commit": binding}

    def read(self, destination, receipt):
        """Read-only archival verification. No normal-store pins are returned."""
        if set(receipt) != {"schema", "root", "commit"} or receipt["schema"] != "FS_RECOVERY_RECEIPT_V1":
            raise ValueError("RECOVERY_RECEIPT_SCHEMA")
        with f.w.WindowsOutput(str(destination)) as output:
            if f.native.file_identity(output.root_handle) != receipt["root"]:
                raise ValueError("RECOVERY_ROOT_SUBSTITUTED")
            raw, _ = f.s.read_bound(output, "commit.json", receipt["commit"])
            descriptor = strict(raw.decode())
            if (f.encoded(descriptor) != raw or descriptor["root"] != receipt["root"]
                    or descriptor.get("schema") not in ("FS_RECOVERY_ARCHIVE_V1", "FS_RECOVERY_ARCHIVE_V2")
                    or descriptor.get("startup_authorized") is not False
                    or descriptor.get("financial_writes_authorized") is not False):
                raise ValueError("RECOVERY_DESCRIPTOR_CONFLICT")
            if self.authority.validate(copy.deepcopy(descriptor), copy.deepcopy(receipt["commit"])) is not True:
                raise ValueError("RECOVERY_CUSTODY_UNVERIFIED")
            raw_intent, _ = f.s.read_bound(output, "intent.json", descriptor["intent"])
            if raw_intent != f.encoded(descriptor["request"]):
                raise ValueError("RECOVERY_INTENT_CONFLICT")
            mapping = descriptor["mapping"]
            if not 1 <= len(mapping) <= MAX_FILES:
                raise ValueError("RECOVERY_CAPACITY")
            names, originals = {"intent.json", "commit.json"}, set()
            values = {}
            originals_for_replay = {}
            for item in mapping:
                key = (item["role"], item["leaf"])
                if key in originals or item["role"] not in ROLES or item["target"] in names:
                    raise ValueError("RECOVERY_DUPLICATE_MAPPING")
                originals.add(key)
                names.add(item["target"])
                raw_copy, _ = f.s.read_bound(output, item["target"], item["restored"])
                if hashlib.sha256(raw_copy).hexdigest() != item["original"]["sha256"]:
                    raise ValueError("RECOVERY_ORIGINAL_BYTES_CHANGED")
                values[key] = strict(raw_copy.decode())
                originals_for_replay[key] = raw_copy, item["original"]
            if {p.name for p in Path(destination).iterdir()} != names:
                raise ValueError("RECOVERY_INCOMPLETE_NAMESPACE")
            check_evidence(descriptor["evidence"], descriptor["request"]["current"])
            evidence = descriptor["evidence"]
            if descriptor["schema"] == "FS_RECOVERY_ARCHIVE_V2":
                verified = original_evidence(descriptor["request"]["enrollment"],
                                             descriptor["request"]["current"], originals_for_replay)
                if body(verified) != body(evidence):
                    raise ValueError("BACKUP_RESTORED_EVIDENCE_CONFLICT")
            if (body(values[("source", "inception.json")]) != body(evidence["manifest"])
                    or body(values[("reports", "scope.json")]) != body(evidence["scope"])):
                raise ValueError("RECOVERY_SOURCE_EVIDENCE_CONFLICT")
            for index, row in enumerate(evidence["rows"], 1):
                if body(values[("source", f.name(index, "record"))]["event"]) != body(row):
                    raise ValueError("RECOVERY_EVENT_CONFLICT")
            for index, document in enumerate(evidence["documents"], 1):
                if body(values[("reports", f"{index:04d}-report.json")]) != body(document):
                    raise ValueError("RECOVERY_REPORT_CONFLICT")
            # Recheck authority after all native reads, not merely at entry.
            if self.authority.validate(copy.deepcopy(descriptor), copy.deepcopy(receipt["commit"])) is not True:
                raise ValueError("RECOVERY_CUSTODY_CHANGED")
            return {"schema": "FS_RECOVERED_RESEARCH_VIEW_V1", "status": "VERIFIED_ARCHIVE_ONLY",
                    "evidence": descriptor["evidence"], "startup_authorized": False,
                    "financial_writes_authorized": False}
