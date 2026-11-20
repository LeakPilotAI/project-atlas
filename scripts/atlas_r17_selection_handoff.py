"""R17 exact unselected native install -> read-only selector revision 16 handoff.

Never installs, selects, adopts partial releases, opens providers, starts PAPER,
or turns financial gates green. A proposed native selection row requires an
exact two-stage install journal, canonical completed native receipt and a
separately verified R16 original selected anchor. Physical original-handle
installed-code verification and SID-bound one-shot selection approval belong
to a later independent selection publisher.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from scripts import release_selection as selection
from scripts.atlas_r16_selection_handoff import _file_inventory_valid
from scripts.atlas_r17_code_only_installer import (
    ARCHIVE_SHA,
    EXPECTED_TOTAL_DIRECTORIES,
    EXPECTED_TOTAL_FILES,
    INVENTORY_SHA,
    RECEIPT,
    SOURCE,
    TARGET,
    require_original_financial_roots_untouched,
    require_selected_r16,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    R16_HEAD,
    R16_RECORD_SHA,
)

JOURNAL = RECEIPT.with_suffix(".pending.jsonl")
SELECTION_ROOT = Path("D:/AtlasRuntime/selection")
REVISION = 16
OPERATION_DOMAIN = b"ATLAS_R17_NATIVE_CODE_ONLY_SELECT_REV16_V1"
SCHEMA = "ATLAS_R17_NONFINANCIAL_NATIVE_CODE_SELECTION_HANDOFF_V1"


def read_small_regular(path, *, maximum):
    if (not path.is_file() or path.is_symlink() or path.is_junction()
            or not 0 < path.stat().st_size <= maximum):
        raise ValueError("R17_SELECTION_EXACT_REGULAR_INSTALL_RECEIPT_REQUIRED")
    return path.read_bytes()


def candidate_from_receipt(*, receipt, receipt_bytes, journal_bytes):
    """Pure strict future row; NEVER selection permission."""
    if (type(receipt) is not dict or type(receipt_bytes) is not bytes
            or not 0 < len(receipt_bytes) <= 10*1024*1024
            or type(journal_bytes) is not bytes
            or not 0 < len(journal_bytes) <= 8192):
        raise ValueError("R17_SELECTION_CANONICAL_COMPLETE_INSTALL_REQUIRED")
    if (selection.strict(receipt_bytes) != receipt
            or receipt_bytes != json.dumps(
                receipt, sort_keys=True, allow_nan=False).encode()):
        raise ValueError("R17_SELECTION_NONCANONICAL_INSTALL_RECEIPT_REFUSED")
    expected = {
        "schema", "stage", "source_commit", "release_path", "files",
        "directories", "archive_sha256", "inventory_sha256", "selected",
        "financial_effects", "provider_connections",
        "operational_acceptance", "layout", "artifact_digest",
    }
    if (set(receipt) != expected
            or receipt["schema"] != "ATLAS_QD_D_RUNTIME_INSTALLATION_V1"
            or receipt["stage"] != "D_RUNTIME_LAYOUT_VERIFIED"
            or receipt["source_commit"] != SOURCE
            or receipt["release_path"] != str(TARGET)
            or receipt["archive_sha256"] != ARCHIVE_SHA
            or receipt["inventory_sha256"] != INVENTORY_SHA
            or any(receipt[key] is not False for key in (
                "selected", "financial_effects", "provider_connections",
                "operational_acceptance",
            ))
            or not _file_inventory_valid(
                receipt["files"], expected=EXPECTED_TOTAL_FILES,
                directory=False)
            or not _file_inventory_valid(
                receipt["directories"], expected=EXPECTED_TOTAL_DIRECTORIES,
                directory=True)):
        raise ValueError("R17_SELECTION_EXACT_NONFINANCIAL_NATIVE_RECEIPT_REQUIRED")
    layout = receipt["layout"]
    if (type(layout) is not dict
            or set(layout) != {
                "executable", "base", "prefix", "base_prefix",
                "stdlib", "bits", "version",
            }
            or layout["bits"] != 64
            or layout["version"] != [3, 12]
            or any(layout[name] != str(TARGET / suffix)
                   for name, suffix in (
                       ("executable", "python/python.exe"),
                       ("base", "python/python.exe"),
                       ("prefix", "python"), ("base_prefix", "python"),
                       ("stdlib", "python/Lib"),
                   ))):
        raise ValueError("R17_SELECTION_NATIVE_PYTHON_LAYOUT_REQUIRED")
    artifact_digest = hashlib.sha256(json.dumps(
        receipt["files"],sort_keys=True,separators=(",",":"),
        allow_nan=False).encode()).hexdigest()
    if receipt["artifact_digest"] != artifact_digest:
        raise ValueError("R17_SELECTION_NATIVE_ARTIFACT_DIGEST_CHANGED")
    receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
    spec = selection.validate_spec({
        "schema": "QD_INSTALLED_RELEASE_REFERENCE_V1",
        "domain": "WINDOWS_LOCAL", "release": SOURCE,
        "root": str(TARGET), "receipt": str(RECEIPT),
        "receipt_sha256": receipt_sha,
        "artifact_digest": artifact_digest,
    }, "WINDOWS_LOCAL")
    rows = journal_bytes.splitlines()
    if len(rows) != 2 or not journal_bytes.startswith(b"{"):
        raise ValueError("R17_SELECTION_EXACT_TWO_STAGE_INSTALL_ACK_REQUIRED")
    original = selection.strict(rows[0])
    if original != {
        "schema": "ATLAS_R17_UNSELECTED_CODE_INSTALL_INTENT_V1",
        "source_commit": SOURCE, "archive_sha256": ARCHIVE_SHA,
        "target": str(TARGET), "financial_authority": False,
        "selection_allowed": False, "paper_start_authorized": False,
    }:
        raise ValueError("R17_SELECTION_CREATE_ONLY_NONFINANCIAL_SCOPE_CHANGED")
    selection.validate_native_install_ack(spec, receipt, journal_bytes)
    operation = hashlib.sha256(
        OPERATION_DOMAIN + R16_HEAD.encode()
        + receipt_sha.encode() + artifact_digest.encode()).hexdigest()[:32]
    return {
        "schema": "QD_RELEASE_SELECTION_RECEIPT_V1",
        "domain": "WINDOWS_LOCAL",
        "revision": REVISION,
        "action": "SELECT",
        "operation": operation,
        "previous": R16_HEAD,
        "selected": spec,
        "restores": None,
    }


def inspect():
    require_selected_r16()
    require_original_financial_roots_untouched()
    if (os.path.lexists(SELECTION_ROOT / "r0016.json")
            or os.path.lexists(SELECTION_ROOT / "r0016.pending")):
        raise ValueError("R17_SELECTION_ALREADY_ATTEMPTED_NO_RETRY")
    observed = tuple(os.path.lexists(item) for item in (
        TARGET, RECEIPT, JOURNAL))
    if not any(observed):
        return {
            "schema": SCHEMA,
            "status": "WAITING_FOR_SEPARATELY_APPROVED_R17_NATIVE_CODE_INSTALL",
            "native_selected_predecessor": "R16",
            "native_selected_head": R16_HEAD,
            "native_predecessor_record_sha256": R16_RECORD_SHA,
            "proposed_revision": REVISION,
            "r17_source_commit": SOURCE,
            "native_selection_published": False,
            "selection_authorized": False,
            "financial_authority": False,
            "paper_start_authorized": False,
            "live_orders_authorized": False,
        }
    if (not all(observed) or not TARGET.is_dir()
            or TARGET.is_symlink() or TARGET.is_junction()):
        raise ValueError("R17_SELECTION_PARTIAL_NATIVE_INSTALL_NO_RETRY")
    raw = read_small_regular(RECEIPT, maximum=10*1024*1024)
    journal = read_small_regular(JOURNAL, maximum=8192)
    row = candidate_from_receipt(
        receipt=selection.strict(raw),
        receipt_bytes=raw, journal_bytes=journal)
    return {
        "schema": SCHEMA,
        "status": "INSTALLED_RECEIPT_PROPOSED_NOT_NATIVE_HANDLE_ACCEPTED",
        "native_selected_predecessor": "R16",
        "native_selected_head": R16_HEAD,
        "native_predecessor_record_sha256": R16_RECORD_SHA,
        "proposed_revision": REVISION,
        "r17_source_commit": SOURCE,
        "proposed_selection_record": row,
        "proposed_record_sha256": selection.digest(row),
        "installed_original_handle_readback_accepted": False,
        "native_selection_published": False,
        "selection_authorized": False,
        "financial_authority": False,
        "paper_start_authorized": False,
        "live_orders_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true", required=True)
    parser.parse_args(argv)
    print(json.dumps(inspect(),sort_keys=True,indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
