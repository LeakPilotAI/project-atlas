"""R14 immutable native code-only selection proposal; read-only by default.

This cannot approve, select, launch, access providers or place orders.
The only optional write is an EXCLUSIVE new source-review JSON under docs,
never under D:/AtlasRuntime. Requires exact existing R12 native-head chain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from scripts.release_selection import (
    R14_ARTIFACT_DIGEST, R14_CODE_RELEASE, R14_RECEIPT_SHA256,
    R14_NTP_SELECTION_PROFILE, digest, encoded, strict, validate_native_install_ack,
    validate_spec,
)

ROOT = Path(__file__).resolve().parents[1]
SEL = Path("D:/AtlasRuntime/selection")
NATIVE_ID = [4004218753, 65536, 1532785]
R12_RELEASE = "2d4879878bf58bea5a3ed0a986b809791f638fec"
R12_HEAD = "f4cf83bb1e98ecb7cfa3be37fe27e80a79b339dc26f73358a1702349b47958fd"
R12_ENVELOPE_SHA256 = "f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7"
R12_INSTALLED_RECEIPT_SHA256 = "acdae2f01fb5defdf0e302240dc589eca0f1c99e3fcc15ec319d98260125cbb6"
SELECTOR = ROOT / "scripts/release_selection.py"
SELECTOR_SHA256 = "26d605076ff8c6d50ee7ef3b6d6ebbf7819fa2b11cbae5f5b0cbad861fed9da0"
SELECTOR_STORE = ROOT / "scripts/release_selection_store.py"
SELECTOR_STORE_SHA256 = "d7bfa6fbea33e28af1fda04e33c643e280623f5933170c98cc73afe3db94ad20"
R14_RECEIPT = ROOT / "logs/diagnostics" / ("qd-unselected-release-" + R14_CODE_RELEASE + ".json")
R14_DEST = Path("D:/AtlasRuntime/releases") / R14_CODE_RELEASE
REVIEW = ROOT / "docs/ATLAS_R14_NONFINANCIAL_CODE_SELECTION_PROPOSAL_2026-11-10.json"
APPROVAL = ROOT / "logs/diagnostics/atlas-r14-code-only-selection-approval.json"
R14_INSTALLER_SOURCE = ROOT / "scripts/atlas_r14_low_impact_installer.py"


def refuse_if(condition, reason):
    if condition:
        raise ValueError(reason)


def checked(path, expected, maximum):
    path = Path(path)
    refuse_if(not path.is_file() or path.is_symlink()
              or path.stat().st_size > maximum,
              "R14_SELECTION_SMALL_EXACT_SOURCE_REQUIRED")
    data = path.read_bytes()
    refuse_if(hashlib.sha256(data).hexdigest() != expected,
              "R14_SELECTION_PINNED_BYTES_CHANGED")
    return data


def chain(rows):
    """Pure replay of the existing 12 immutable native selection records."""
    refuse_if(type(rows) is not list or len(rows) != 12,
              "R14_SELECTION_EXACT_R12_PREDECESSORS_REQUIRED")
    previous = None
    operations = set()
    known = {}
    for index, row in enumerate(rows, 1):
        refuse_if(type(row) is not dict or set(row) != {
            "schema","domain","revision","action","operation",
            "previous","selected","restores",
        } or row.get("schema") != "QD_RELEASE_SELECTION_RECEIPT_V1"
            or row.get("domain") != "WINDOWS_LOCAL"
            or type(row.get("revision")) is not int or row["revision"] != index
            or row.get("action") not in ("SELECT","ROLLBACK")
            or type(row.get("operation")) is not str
            or not re.fullmatch("[0-9a-f]{32}", row["operation"])
            or row["operation"] in operations or row.get("previous") != previous,
            "R14_SELECTION_NATIVE_PREDECESSOR_CHAIN_REFUSED")
        if row["selected"] is not None:
            validate_spec(row["selected"], "WINDOWS_LOCAL")
        if row["action"] == "SELECT":
            refuse_if(row["selected"] is None or row["restores"] is not None,
                      "R14_SELECTION_PREDECESSOR_SELECT_REFUSED")
        else:
            restores = row["restores"]
            if restores == "BASELINE":
                refuse_if(index != 2 or row["selected"] is not None,
                          "R14_SELECTION_PREDECESSOR_BASELINE_REFUSED")
            else:
                refuse_if(restores not in known
                          or row["selected"] != known[restores]["selected"],
                          "R14_SELECTION_PREDECESSOR_ROLLBACK_REFUSED")
        operations.add(row["operation"])
        previous = digest(row)
        known[previous] = row
    last = rows[-1]
    refuse_if(previous != R12_HEAD or last["revision"] != 12
              or last["action"] != "SELECT"
              or last["selected"]["release"] != R12_RELEASE
              or last["selected"]["receipt_sha256"] != R12_INSTALLED_RECEIPT_SHA256,
              "R14_SELECTION_SELECTED_R12_PREDECESSOR_CHANGED")
    return operations


def exact_r14_reference():
    raw = checked(R14_RECEIPT, R14_RECEIPT_SHA256, 3 * 1024**2)
    receipt = strict(raw)
    target = validate_spec({
        "schema":"QD_INSTALLED_RELEASE_REFERENCE_V1",
        "domain":"WINDOWS_LOCAL",
        "release":R14_CODE_RELEASE,
        "root":str(R14_DEST),
        "receipt":str(R14_RECEIPT),
        "receipt_sha256":R14_RECEIPT_SHA256,
        "artifact_digest":R14_ARTIFACT_DIGEST,
    }, "WINDOWS_LOCAL")
    refuse_if(receipt.get("source_commit") != R14_CODE_RELEASE
              or receipt.get("release_path") != str(R14_DEST)
              or receipt.get("artifact_digest") != R14_ARTIFACT_DIGEST
              or any(receipt.get(k) is not False for k in (
                  "selected","financial_effects","provider_connections",
                  "operational_acceptance")),
              "R14_SELECTION_NONFINANCIAL_INSTALLED_RECEIPT_REQUIRED")
    journal = R14_RECEIPT.with_suffix(".pending.jsonl")
    refuse_if(not journal.is_file() or journal.stat().st_size > 4096,
              "R14_SELECTION_EXACT_SHORT_JOURNAL_REQUIRED")
    validate_native_install_ack(target, receipt, journal.read_bytes())
    refuse_if(not R14_DEST.is_dir() or R14_DEST.is_symlink() or R14_DEST.is_junction(),
              "R14_SELECTION_NATIVE_RELEASE_MISSING")
    return target


def read_only_proposal():
    # A review is NOT a consent record. Keep both authority and publication
    # out of this read-only stage, even if a stale selection file appears.
    refuse_if(os.path.lexists(APPROVAL),
              "R14_SELECTION_APPROVAL_FILE_PRESENT_REVIEW_REFUSED")
    # No independent NTP socket, native-copy, installed-child or release switch.
    checked(SELECTOR, SELECTOR_SHA256, 64 * 1024)
    checked(SELECTOR_STORE, SELECTOR_STORE_SHA256, 64 * 1024)
    refuse_if("APPROVAL_SHA256 = None" not in
              R14_INSTALLER_SOURCE.read_text(encoding="utf-8"),
              "R14_SELECTION_INSTALLER_APPROVAL_NOT_CONSUMED")
    target = exact_r14_reference()
    from scripts.release_selection_store import NativeSelectionStore
    store = NativeSelectionStore(root=str(SEL), native_root=list(NATIVE_ID))
    try:
        with store.locked():
            rows = store.records()
            operations = chain(rows)
            tail = checked(SEL / "r0012.json", R12_ENVELOPE_SHA256, 65536)
            refuse_if(strict(tail).get("record") != rows[-1],
                      "R14_SELECTION_NATIVE_R12_TAIL_NOT_BOUND")
            refuse_if(os.path.lexists(SEL / "r0013.json")
                      or os.path.lexists(SEL / "r0013.pending"),
                      "R14_SELECTION_R13_ALREADY_PRESENT_OR_PARTIAL")
            operation = hashlib.sha256(encoded({
                "scope":"R14_CODE_ONLY_SELECT_UNSELECTED_NATIVE_SOURCE_V1",
                "r12_head":R12_HEAD,
                "r12_envelope_sha256":R12_ENVELOPE_SHA256,
                "r14_receipt_sha256":R14_RECEIPT_SHA256,
                "r14_artifact_digest":R14_ARTIFACT_DIGEST,
                "selector_source_sha256":SELECTOR_SHA256,
                "clock_profile":R14_NTP_SELECTION_PROFILE,
            })).hexdigest()[:32]
            refuse_if(operation in operations, "R14_SELECTION_OPERATION_REUSED")
            proposed = {
                "schema":"QD_RELEASE_SELECTION_RECEIPT_V1",
                "domain":"WINDOWS_LOCAL",
                "revision":13,
                "action":"SELECT",
                "operation":operation,
                "previous":R12_HEAD,
                "selected":target,
                "restores":None,
            }
            result = {
                "schema":"ATLAS_R14_NONFINANCIAL_CODE_SELECTION_PROPOSAL_V1",
                "status":"READ_ONLY_PROPOSAL_NOT_OPERATOR_PERMISSION",
                "previous_release":R12_RELEASE,
                "previous_revision":12,
                "previous_head":R12_HEAD,
                "previous_selection_envelope_sha256":R12_ENVELOPE_SHA256,
                "native_selection_root":str(SEL),
                "native_selection_root_identity":list(NATIVE_ID),
                "predecessor_records_verified":len(rows),
                "r14_installed_receipt_sha256":R14_RECEIPT_SHA256,
                "r14_installed_artifact_digest":R14_ARTIFACT_DIGEST,
                "selection_source_sha256":SELECTOR_SHA256,
                "selection_store_source_sha256":SELECTOR_STORE_SHA256,
                "clock_profile":R14_NTP_SELECTION_PROFILE,
                "fresh_180s_independent_two_peer_clock_required":True,
                "clock_qualification_performed":False,
                "native_installed_child_readback_required_before_publication":True,
                "native_installed_child_readback_performed":False,
                "row":proposed,
                "proposed_head":digest(proposed),
                "r14_selected":False,
                "operator_approval_present":False,
                "selection_authorized":False,
                "selection_mutation_performed":False,
                "financial_authority":False,
                "paper_accounts":False,
                "providers":False,
                "paper_start":False,
                "simulated_orders":False,
                "live_orders":False,
                "automatic_startup":False,
            }
    finally:
        store.close()
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    flags=parser.add_mutually_exclusive_group(required=True)
    flags.add_argument("--inspect",action="store_true")
    flags.add_argument("--write-review-once",action="store_true")
    args=parser.parse_args(argv)
    result=read_only_proposal()
    if args.write_review_once:
        refuse_if(os.path.lexists(REVIEW),
                  "R14_SELECTION_CREATE_ONLY_REVIEW_ALREADY_USED")
        with REVIEW.open("xb") as stream:
            stream.write(encoded(result))
            stream.flush()
            os.fsync(stream.fileno())
    return {
        "status":result["status"],
        "proposed_revision":13,
        "proposed_head":result["proposed_head"],
        "current_release":result["previous_release"],
        "proposed_release":R14_CODE_RELEASE,
        "predecessor_records_verified":12,
        "review_recorded":REVIEW.is_file(),
        "selection_authorized":False,
        "selection_mutation_performed":False,
        "financial_authority":False,
    }


if __name__ == "__main__":
    print(json.dumps(main(),sort_keys=True),flush=True)
