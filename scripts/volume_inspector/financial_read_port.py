"""Existing-only native immutable reader. No mutex recovery or publication API.

No default paths/trust. Never construct a FinancialRecordStore/ReportArchive:
their abandoned-writer guards can publish recovery markers. Reuse only their
immutable verification routines on read-only method surfaces instead.
"""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

_spec = importlib.util.spec_from_file_location("readonly_fs3", Path(__file__).with_name("financial_reporting.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


class BoundReader:
    _read = m.f.FinancialRecordStore._read

    def __init__(self, output, pin, projection=None):
        self.output, self.projection = output, projection
        frozen = copy.deepcopy(pin)
        self.trust = SimpleNamespace(current=lambda: copy.deepcopy(frozen))


class NativeFinancialReadPort:
    """Explicit paths must match independently enrolled handle identities.

    WindowsOutput's EXISTING-only constructor requests read/attribute/security
    handles; no create_root/write/guard/latch is invoked here. Namespaces are
    refusal checks, not directory-wide exclusion. Accepted authority must supply
    the read lease independently, including unknown/nonparticipating writers.
    """
    def __init__(self, *, source_root, projection_root, report_root):
        self.paths = (source_root, projection_root, report_root)

    def read_verified(self, enrollment, current):
        outputs = []
        try:
            for path, key in zip(self.paths, ("source_root", "projection_root", "report_root"), strict=True):
                output = m.f.w.WindowsOutput(path)
                outputs.append(output)
                m.f.require_identity(enrollment[key])
                if m.f.native.file_identity(output.root_handle) != enrollment[key]:
                    raise ValueError("ENROLLED_ROOT_MISMATCH")
            source, projection_output, report_output = outputs
            # Constructor-free projection verifier has no publisher reference.
            projection = ReadProjection(projection_output, enrollment["projection_root"])
            reader = BoundReader(source, current["source"], projection)
            loaded = m.f.FinancialRecordStore._load(reader)
            _, manifest, rows, state, _, _, _ = loaded
            archive = BoundReader(report_output, current["reports"])
            _, scope, documents = m.ReportArchive._load(archive)
            return {"manifest": manifest, "rows": rows, "state": state,
                    "scope": scope, "documents": documents}
        finally:
            for output in reversed(outputs):
                output.close()


class ReadProjection:
    _prefix = m.ProjectionTarget._prefix
    verify = m.ProjectionTarget.verify
    verify_inventory = m.ProjectionTarget.verify_inventory

    def __init__(self, output, expected_root):
        self.output, self.expected_root = output, expected_root
