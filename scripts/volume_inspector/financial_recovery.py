"""Disposable archival recovery, never FS2 writer admission or operational authority.

Original logical bindings stay in immutable bytes. A separately accepted recovery
authority must bind the original cut AND new physical mapping. No default trust,
issuer, clock, filesystem custody, or financial execution interface is provided.
"""
import copy
import hashlib
import importlib.util
from pathlib import Path

from app.services.paper_daily_report import audit_daily_report, validate_scope
from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import body, replay_verified_events, strict

_spec = importlib.util.spec_from_file_location("recovery_read_port", Path(__file__).with_name("financial_read_port.py"))
r = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r)
f = r.m.f
ROLES = ("source", "projection", "reports")
MAX_FILES = 1027


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
            with f.w.WindowsOutput.create_root(str(destination)) as output:
                intent = output.write_bound("intent.json", f.encoded(request))
                mapping = []
                for index, (role, leaf, raw, original) in enumerate(files):
                    target = f"copy-{index:04d}.json"
                    restored = output.write_bound(target, raw)
                    f.s.read_bound(output, target, restored)
                    mapping.append({"role": role, "leaf": leaf, "original": original,
                                    "target": target, "restored": restored})
                descriptor = {"schema": "FS_RECOVERY_ARCHIVE_V1", "request": request,
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
            if f.encoded(descriptor) != raw or descriptor["root"] != receipt["root"]:
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
            if {p.name for p in Path(destination).iterdir()} != names:
                raise ValueError("RECOVERY_INCOMPLETE_NAMESPACE")
            check_evidence(descriptor["evidence"], descriptor["request"]["current"])
            evidence = descriptor["evidence"]
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
