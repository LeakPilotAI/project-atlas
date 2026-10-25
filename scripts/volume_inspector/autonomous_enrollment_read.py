"""Existing-only V4 native enrollment evidence; no create/repair/write methods.

Custody supplies authenticated complete file cuts; the injected financial port
reuses accepted replay/report verification. This module installs neither port.
Retained namespace handles remain open throughout independent financial audit.
"""

import importlib.util
from pathlib import Path

from app.investment.quality_dips_operational_contract import exact, hashed, native_id
from app.services.paper_financial_replay import body, digest, strict, text
from app.services.quality_dips_autonomous_enrollment import ROLES, validate_enrollment

_spec = importlib.util.spec_from_file_location(
    "auto_enrollment_bound", Path(__file__).with_name("snapshot_store.py")
)
s = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s)


class BoundNativeEnrollmentEvidence:
    def __init__(self, *, cuts=None, financial=None):
        if cuts is None or financial is None:
            raise ValueError("AUTO_NATIVE_ACCEPTED_CUT_AND_FINANCIAL_PORT_REQUIRED")
        self.cuts, self.financial = cuts, financial

    def verify(self, enrollment, current, now, *, scope):
        if scope not in ("LOCAL_ENROLLED", "DISPOSABLE_TEST"):
            raise ValueError("AUTO_NATIVE_SCOPE_REQUIRED")
        e = validate_enrollment(enrollment)
        with self.cuts.lease(e, current, now, scope=scope) as lease:
            cut = strict(body(lease.snapshot))
            exact(
                cut,
                "QD_AUTO_NATIVE_RESOURCE_CUT_V4",
                {"enrollment_digest", "scope", "resources"},
            )
            if (
                lease.check(strict(body(cut)), now) is not True
                or cut["enrollment_digest"] != digest(e)
                or cut["scope"] != scope
                or digest(cut) != current["financial_digest"]
                or type(cut["resources"]) is not dict
                or set(cut["resources"]) != set(ROLES)
            ):
                raise ValueError("AUTO_NATIVE_CUT_NOT_AUTHENTICATED")
            outputs, documents = {}, {}
            try:
                for role in ROLES:
                    resource = e["resources"][role]
                    out = s.w.WindowsOutput(resource["path"])
                    outputs[role] = out
                    if s.native.file_identity(out.root_handle) != resource["native_id"]:
                        raise ValueError("AUTO_NATIVE_FOREIGN_ROOT")
                    files = cut["resources"][role]
                    if type(files) is not dict or len(files) > 128:
                        raise ValueError("AUTO_NATIVE_FILE_CAPACITY")
                    if {p.name for p in Path(out.root).iterdir()} != set(files):
                        raise ValueError("AUTO_NATIVE_NAMESPACE_MISMATCH")
                    documents[role] = {}
                    for name, pin in files.items():
                        if (
                            type(name) is not str
                            or not name.endswith(".json")
                            or any(c in name for c in ("/", "\\", ":"))
                        ):
                            raise ValueError("AUTO_NATIVE_LEAF_REQUIRED")
                        exact(
                            pin,
                            "QD_AUTO_NATIVE_FILE_V4",
                            {"native_id", "sha256", "record_schema"},
                        )
                        native_id(pin["native_id"])
                        hashed(pin["sha256"])
                        text(pin["record_schema"])
                        # Explicit schema separation, never accept manual records
                        # or fixture pin wrappers as operational financial evidence.
                        if scope == "LOCAL_ENROLLED" and not pin[
                            "record_schema"
                        ].startswith("QD_AUTO_NATIVE_"):
                            raise ValueError("AUTO_NATIVE_OPERATIONAL_RECORD_REQUIRED")
                        raw, _ = s.read_bound(
                            out, name, {"id": pin["native_id"], "sha256": pin["sha256"]}
                        )
                        value = strict(raw.decode("utf-8"))
                        if (
                            body(value).encode() != raw
                            or value.get("schema") != pin["record_schema"]
                        ):
                            raise ValueError("AUTO_NATIVE_CANONICAL_RECORD_REQUIRED")
                        documents[role][name] = value
                if (
                    self.financial.verify_cut(
                        e, current, strict(body(documents)), now, scope=scope
                    )
                    is not True
                ):
                    raise ValueError("AUTO_NATIVE_FINANCIAL_AUDIT_REQUIRED")
                for role, out in outputs.items():
                    out._verify()
                    if {p.name for p in Path(out.root).iterdir()} != set(
                        cut["resources"][role]
                    ):
                        raise ValueError("AUTO_NATIVE_NAMESPACE_CHANGED")
                    for name, pin in cut["resources"][role].items():
                        # Re-read identity-bound bytes after the external auditor;
                        # keeping only the parent handle does not lock file data.
                        s.read_bound(
                            out, name, {"id": pin["native_id"], "sha256": pin["sha256"]}
                        )
                if lease.check(strict(body(cut)), now) is not True:
                    raise ValueError("AUTO_NATIVE_CUT_CONTINUITY_LOST")
                return True
            finally:
                for out in outputs.values():
                    out.close()
