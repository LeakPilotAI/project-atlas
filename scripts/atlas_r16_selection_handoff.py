"""R16 native code-selection HANDOFF, read-only until R16 install exists.

A pure row is eligible for separate reviewed selection only after an exact
completed create-only R16 native installation receipt and two-stage ACK.
The already-selected genuine R15 native 14-record chain stays untouched.
No approval, code selection, financial ownership, provider or order here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from scripts import release_selection as selection
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    selected_code as selected_r15_code, SELECTED_HEAD, SELECTED_SHA,
)
from scripts.observation_runtime.atlas_r16_code_install_plan_preflight import (
    SOURCE_COMMIT, ARCHIVE_SHA, INVENTORY_SHA, TARGET, RECEIPT,
    EXPECTED_FILES, EXPECTED_DIRECTORIES,
    validate_selected_r15,
)

JOURNAL = RECEIPT.with_suffix(".pending.jsonl")
SELECTION_ROOT = Path("D:/AtlasRuntime/selection")
REVISION = 15
OPERATION_DOMAIN = b"ATLAS_R16_NONFINANCIAL_CODE_SELECTION_OPERATION_V1"


def _strict_small(path: Path, *, max_bytes: int):
    if (not path.is_file() or path.is_symlink() or path.is_junction()
            or not 0 < path.stat().st_size <= max_bytes):
        raise ValueError("R16_SELECTION_EXACT_EXISTING_REGULAR_RECEIPT_REQUIRED")
    return path.read_bytes()


def _file_inventory_valid(rows, *, expected: int, directory: bool):
    if type(rows) is not list or len(rows) != expected:
        return False
    paths = set()
    identities = set()
    names = {"id", "path"} if directory else {"id", "path", "bytes", "sha256"}
    for row in rows:
        if type(row) is not dict or set(row) != names:
            return False
        path = row["path"]
        identity = row["id"]
        if (type(path) is not str or not path
                or path.startswith(("/", "\\"))
                or "\\" in path or "\x00" in path
                or any(part in ("", ".", "..") for part in path.split("/"))
                and not (directory and path == ".")
                or type(identity) is not list or len(identity) != 3
                or any(type(n) is not int or n < 0 for n in identity)):
            return False
        if not directory and (type(row["bytes"]) is not int or row["bytes"] < 0
                or type(row["sha256"]) is not str
                or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
            return False
        key = path.casefold()
        if key in paths or tuple(identity) in identities:
            return False
        paths.add(key)
        identities.add(tuple(identity))
    return True


def candidate_from_receipt(*, receipt, receipt_bytes, journal_bytes):
    """Validate strict, canonical unselected R16 receipt and exact ACK.

    This is a SOURCE-ONLY proposal. Native installed-handle verification and
    new R16 operator approval must be performed by a separate publisher.
    """
    if (type(receipt) is not dict
            or type(receipt_bytes) is not bytes or not 0 < len(receipt_bytes) <= 10*1024*1024
            or type(journal_bytes) is not bytes or not 0 < len(journal_bytes) <= 8192):
        raise ValueError("R16_SELECTION_EXACT_RECEIPT_AND_ACK_REQUIRED")
    try:
        decoded = selection.strict(receipt_bytes)
        if decoded != receipt or receipt_bytes != json.dumps(
                receipt, sort_keys=True, allow_nan=False).encode():
            raise ValueError("R16_SELECTION_NONCANONICAL_RECEIPT_REFUSED")
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("R16_SELECTION_EXACT_CANONICAL_RECEIPT_REQUIRED") from exc
    expected = {"schema", "stage", "source_commit", "release_path", "files",
                "directories", "archive_sha256", "inventory_sha256",
                "selected", "financial_effects", "provider_connections",
                "operational_acceptance", "layout", "artifact_digest"}
    if (set(receipt) != expected
            or receipt["schema"] != "ATLAS_QD_D_RUNTIME_INSTALLATION_V1"
            or receipt["stage"] != "D_RUNTIME_LAYOUT_VERIFIED"
            or receipt["source_commit"] != SOURCE_COMMIT
            or receipt["release_path"] != str(TARGET)
            or receipt["archive_sha256"] != ARCHIVE_SHA
            or receipt["inventory_sha256"] != INVENTORY_SHA
            or any(receipt[k] is not False for k in (
                "selected", "financial_effects", "provider_connections",
                "operational_acceptance"))
            or type(receipt["artifact_digest"]) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", receipt["artifact_digest"])
            or not _file_inventory_valid(
                receipt["files"], expected=EXPECTED_FILES, directory=False)
            or not _file_inventory_valid(
                receipt["directories"], expected=EXPECTED_DIRECTORIES, directory=True)):
        raise ValueError("R16_SELECTION_EXACT_NONFINANCIAL_NATIVE_RECEIPT_REQUIRED")
    layout = receipt["layout"]
    if (type(layout) is not dict
            or set(layout) != {"executable", "base", "prefix", "base_prefix",
                               "stdlib", "bits", "version"}
            or layout["bits"] != 64 or layout["version"] != [3, 12]
            or any(layout[k] != str(TARGET / suffix) for k, suffix in (
                ("executable", "python/python.exe"), ("base", "python/python.exe"),
                ("prefix", "python"), ("base_prefix", "python"),
                ("stdlib", "python/Lib")))):
        raise ValueError("R16_SELECTION_ORIGINAL_NATIVE_PYTHON_LAYOUT_REQUIRED")
    artifact_digest = hashlib.sha256(json.dumps(
        receipt["files"], sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode()).hexdigest()
    if artifact_digest != receipt["artifact_digest"]:
        raise ValueError("R16_SELECTION_NATIVE_ARTIFACT_DIGEST_CHANGED")
    receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
    spec = selection.validate_spec({
        "schema": "QD_INSTALLED_RELEASE_REFERENCE_V1",
        "domain": "WINDOWS_LOCAL",
        "release": SOURCE_COMMIT,
        "root": str(TARGET),
        "receipt": str(RECEIPT),
        "receipt_sha256": receipt_sha,
        "artifact_digest": artifact_digest,
    }, "WINDOWS_LOCAL")
    rows = journal_bytes.splitlines()
    if len(rows) != 2 or not journal_bytes.startswith(b"{"):
        raise ValueError("R16_SELECTION_EXACT_TWO_STAGE_INSTALL_JOURNAL_REQUIRED")
    first = selection.strict(rows[0])
    if first != {
        "schema": "ATLAS_R16_UNSELECTED_CODE_INSTALL_INTENT_V1",
        "source_commit": SOURCE_COMMIT,
        "archive_sha256": ARCHIVE_SHA,
        "target": str(TARGET),
        "selection_allowed": False,
        "financial_authority": False,
        "provider_access": False,
        "startup_authorized": False,
    }:
        raise ValueError("R16_SELECTION_CREATE_ONLY_INTENT_SCOPE_CHANGED")
    # The shared native receipt checker validates the terminal ACK digest,
    # but NEVER treats this source-level check as selected-code permission.
    selection.validate_native_install_ack(spec, receipt, journal_bytes)
    operation = hashlib.sha256(
        OPERATION_DOMAIN + SELECTED_HEAD.encode()
        + receipt_sha.encode() + artifact_digest.encode()
    ).hexdigest()[:32]
    return {
        "schema": "QD_RELEASE_SELECTION_RECEIPT_V1",
        "domain": "WINDOWS_LOCAL",
        "revision": REVISION,
        "action": "SELECT",
        "operation": operation,
        "previous": SELECTED_HEAD,
        "selected": spec,
        "restores": None,
    }


def inspect():
    """Selected-R15 native chain remains live; R16 selector is never written."""
    if (os.path.lexists(SELECTION_ROOT / "r0015.pending")
            or os.path.lexists(SELECTION_ROOT / "r0015.json")):
        raise ValueError("R16_SELECTION_ALREADY_ATTEMPTED_DO_NOT_RETRY")
    validate_selected_r15(selected_r15_code())
    observed = tuple(os.path.lexists(p) for p in (TARGET, RECEIPT, JOURNAL))
    if not any(observed):
        return {
            "schema": "ATLAS_R16_CODE_SELECTION_HANDOFF_V1",
            "status": "WAITING_FOR_SEPARATELY_APPROVED_R16_CODE_ONLY_NATIVE_INSTALL",
            "selected_native_predecessor": "R15",
            "selected_predecessor_head": SELECTED_HEAD,
            "selected_predecessor_record_sha256": SELECTED_SHA,
            "expected_revision": REVISION,
            "source_commit": SOURCE_COMMIT,
            "installed_receipt_verified": False,
            "new_selection_record_proposed": False,
            "new_selection_record_written": False,
            "selection_authorized": False,
            "financial_authority": False,
            "paper_start_authorized": False,
            "live_orders_authorized": False,
        }
    if (not all(observed) or not TARGET.is_dir()
            or TARGET.is_symlink() or TARGET.is_junction()):
        raise ValueError("R16_SELECTION_PARTIAL_NATIVE_INSTALL_PRESERVE_NO_RETRY")
    raw = _strict_small(RECEIPT, max_bytes=10*1024*1024)
    journal = _strict_small(JOURNAL, max_bytes=8192)
    row = candidate_from_receipt(
        receipt=selection.strict(raw), receipt_bytes=raw, journal_bytes=journal)
    return {
        "schema": "ATLAS_R16_CODE_SELECTION_HANDOFF_V1",
        "status": "NATIVE_INSTALL_RECEIPT_ELIGIBLE_FOR_SEPARATE_HANDLE_AND_OPERATOR_APPROVAL",
        "selected_native_predecessor": "R15",
        "selected_predecessor_head": SELECTED_HEAD,
        "selected_predecessor_record_sha256": SELECTED_SHA,
        "expected_revision": REVISION,
        "source_commit": SOURCE_COMMIT,
        "proposed_row": row,
        "proposed_row_digest": selection.digest(row),
        "installed_native_handle_verification_performed": False,
        "new_selection_record_written": False,
        "selection_authorized": False,
        "financial_authority": False,
        "paper_start_authorized": False,
        "live_orders_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true", required=True)
    parser.parse_args(argv)
    print(json.dumps(inspect(), sort_keys=True, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
