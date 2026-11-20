"""R15 selection handoff: deterministic, read-only until native install exists.

A pure proposal binds the existing selected revision-13 R14 head to a future
R15 installed receipt, file digest and exact terminal ACK. No selected file,
native release, approval, provider, account or trade is ever written here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from scripts import release_selection as selection
from scripts.observation_runtime.atlas_r14_selected_paper_readiness import (
    collect_selected_reference,
)
from scripts.observation_runtime.atlas_r15_code_install_plan_preflight import (
    SOURCE_COMMIT, ARCHIVE_SHA, INVENTORY_SHA, TARGET, RECEIPT,
    R14_HEAD, EXPECTED_FILES, EXPECTED_DIRECTORIES,
)
from scripts.observation_runtime.atlas_r15_code_install_plan_preflight import (
    ROOT as WORKSPACE,
)

JOURNAL = RECEIPT.with_suffix(".pending.jsonl")
SELECTION_ROOT = Path("D:/AtlasRuntime/selection")
REVISION = 14
OPERATION_DOMAIN = b"ATLAS_R15_NONFINANCIAL_CODE_SELECTION_OPERATION_V1"


def _strict_small(path, *, max_bytes, required=True):
    if (path.is_symlink() or path.is_junction()
            or (required and not path.is_file())
            or (path.is_file() and not 0 < path.stat().st_size <= max_bytes)):
        raise ValueError("R15_SELECTION_RECEIPT_REGULAR_FILE_REQUIRED")
    if not path.is_file():
        return None
    return path.read_bytes()


def validate_existing_r14_selected(selected):
    if (type(selected) is not dict
            or selected.get("revision")!=13
            or selected.get("selected_release")!="7ff9d3dba2eabe110f843c13efac49464805de2a"
            or selected.get("native_selection_head")!=R14_HEAD
            or selected.get("native_selection_record_verified") is not True
            or selected.get("financial_authority") is not False):
        raise ValueError("R15_SELECTION_NATIVE_R14_ANCHOR_REQUIRED")
    return True


def candidate_from_receipt(*, receipt, receipt_bytes, journal_bytes):
    """Validate exact create-only native R15 receipt and return pure r0014 row."""
    if (type(receipt) is not dict
            or type(receipt_bytes) is not bytes or len(receipt_bytes)>10*1024*1024
            or type(journal_bytes) is not bytes or len(journal_bytes)>8192):
        raise ValueError("R15_SELECTION_EXACT_RECEIPT_AND_ACK_REQUIRED")
    try:
        original=selection.strict(receipt_bytes)
    except (ValueError,TypeError) as err:
        raise ValueError("R15_SELECTION_EXACT_RECEIPT_AND_ACK_REQUIRED") from err
    if original!=receipt or receipt_bytes!=json.dumps(
            receipt,sort_keys=True,allow_nan=False).encode():
        raise ValueError("R15_SELECTION_EXACT_RECEIPT_CANONICAL_BYTES_REQUIRED")
    if (receipt.get("schema")!="ATLAS_QD_D_RUNTIME_INSTALLATION_V1"
            or receipt.get("stage")!="D_RUNTIME_LAYOUT_VERIFIED"
            or receipt.get("source_commit")!=SOURCE_COMMIT
            or receipt.get("release_path")!=str(TARGET)
            or receipt.get("archive_sha256")!=ARCHIVE_SHA
            or receipt.get("inventory_sha256")!=INVENTORY_SHA
            or receipt.get("selected") is not False
            or receipt.get("financial_effects") is not False
            or receipt.get("provider_connections") is not False
            or receipt.get("operational_acceptance") is not False
            or type(receipt.get("files")) is not list
            or len(receipt["files"])!=EXPECTED_FILES
            or type(receipt.get("directories")) is not list
            or len(receipt["directories"])!=EXPECTED_DIRECTORIES
            or type(receipt.get("artifact_digest")) is not str):
        raise ValueError("R15_SELECTION_EXACT_UNSELECTED_CODE_RECEIPT_REQUIRED")
    digest=hashlib.sha256(json.dumps(
        receipt["files"],sort_keys=True,separators=(",",":"),
        allow_nan=False).encode()).hexdigest()
    if receipt["artifact_digest"]!=digest:
        raise ValueError("R15_SELECTION_NATIVE_ARTIFACT_DIGEST_CHANGED")
    receipt_sha=hashlib.sha256(receipt_bytes).hexdigest()
    spec=selection.validate_spec({
        "schema":"QD_INSTALLED_RELEASE_REFERENCE_V1",
        "domain":"WINDOWS_LOCAL",
        "release":SOURCE_COMMIT,
        "root":str(TARGET),
        "receipt":str(RECEIPT),
        "receipt_sha256":receipt_sha,
        "artifact_digest":digest,
    },"WINDOWS_LOCAL")
    rows=journal_bytes.splitlines()
    if len(rows)!=2:
        raise ValueError("R15_SELECTION_EXACT_TWO_STAGE_INSTALL_JOURNAL_REQUIRED")
    initial=selection.strict(rows[0])
    if initial != {
        "schema":"ATLAS_R15_UNSELECTED_CODE_INSTALL_INTENT_V1",
        "source_commit":SOURCE_COMMIT,
        "archive_sha256":ARCHIVE_SHA,
        "target":str(TARGET),
        "selection_allowed":False,
        "financial_authority":False,
        "provider_access":False,
        "startup_authorized":False,
    }:
        raise ValueError("R15_SELECTION_CREATE_ONLY_INTENT_SCOPE_CHANGED")
    selection.validate_native_install_ack(spec,receipt,journal_bytes)
    operation=hashlib.sha256(
        OPERATION_DOMAIN + R14_HEAD.encode()+receipt_sha.encode()+digest.encode()
    ).hexdigest()[:32]
    return {
        "schema":"QD_RELEASE_SELECTION_RECEIPT_V1",
        "domain":"WINDOWS_LOCAL",
        "revision":REVISION,
        "action":"SELECT",
        "operation":operation,
        "previous":R14_HEAD,
        "selected":spec,
        "restores":None,
    }


def inspect():
    """No native-write/clock/provider operations, including if R15 is missing."""
    # Check for an existing or uncertain one-shot publication before
    # consulting the R14-only predecessor inspector, which is naturally
    # obsolete after R15 has been selected.
    if os.path.lexists(SELECTION_ROOT/"r0014.pending") or os.path.lexists(
            SELECTION_ROOT/"r0014.json"):
        raise ValueError("R15_SELECTION_ALREADY_ATTEMPTED_DO_NOT_RETRY")
    validate_existing_r14_selected(collect_selected_reference())
    if (not os.path.lexists(TARGET) and not os.path.lexists(RECEIPT)
            and not os.path.lexists(JOURNAL)):
        return {
            "schema":"ATLAS_R15_CODE_SELECTION_HANDOFF_V1",
            "status":"WAITING_FOR_SEPARATELY_AUTHORIZED_R15_CODE_ONLY_NATIVE_INSTALL",
            "selected_native_predecessor":"R14",
            "selected_predecessor_head":R14_HEAD,
            "expected_revision":REVISION,
            "source_commit":SOURCE_COMMIT,
            "installed_receipt_verified":False,
            "new_selection_record_proposed":False,
            "new_selection_record_written":False,
            "selection_authorized":False,
            "financial_authority":False,
            "paper_start_authorized":False,
            "live_orders_authorized":False,
        }
    # Refuse a partial/uncertain install rather than inventing an ACK.
    if not all(p.is_file() and not p.is_symlink() and not p.is_junction()
               for p in (TARGET, RECEIPT, JOURNAL) if p != TARGET) or not TARGET.is_dir():
        raise ValueError("R15_SELECTION_INCOMPLETE_NATIVE_INSTALL_PRESERVE_NO_RETRY")
    receipt_bytes=_strict_small(RECEIPT,max_bytes=10*1024*1024)
    journal_bytes=_strict_small(JOURNAL,max_bytes=8192)
    row=candidate_from_receipt(receipt=selection.strict(receipt_bytes),
                               receipt_bytes=receipt_bytes,journal_bytes=journal_bytes)
    return {
        "schema":"ATLAS_R15_CODE_SELECTION_HANDOFF_V1",
        "status":"SOURCE_ONLY_CANDIDATE_REQUIRES_NATIVE_HANDLE_VERIFIER_AND_ONE_SHOT_SELECTION_APPROVAL",
        "selected_native_predecessor":"R14",
        "selected_predecessor_head":R14_HEAD,
        "expected_revision":REVISION,
        "source_commit":SOURCE_COMMIT,
        "proposed_row":row,
        "proposed_row_digest":selection.digest(row),
        "installed_receipt_present":True,
        "installed_native_handle_verification_performed":False,
        "new_selection_record_written":False,
        "selection_authorized":False,
        "financial_authority":False,
        "paper_start_authorized":False,
        "live_orders_authorized":False,
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect",action="store_true",required=True)
    parser.parse_args(argv)
    print(json.dumps(inspect(),sort_keys=True,indent=2))
    return 2


if __name__=="__main__":
    raise SystemExit(main())
