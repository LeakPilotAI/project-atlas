"""Exact R23 native code-only selector, original R21 rev20 successor.

No invocation in this module approves accounts, PAPER, LIVE, providers,
source policy, or financial runtime. Genuine original Windows selection
requires an independently approved local, SID/source/receipt/record-bound
one-shot decision and strict 180s independent-clock qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from scripts import atlas_r23_code_only_install as install
from scripts import release_selection as releases
from scripts.atlas_r13_low_impact_installer import LowImpactEnvelope
from scripts.atlas_r23_native_recovery import AUDIT_SHA as RECOVERY_AUDIT_SHA
from scripts.atlas_r23_native_recovery import (
    RECOVERY_JOURNAL,
    RECOVERY_RECEIPT,
)
from scripts.atlas_r23_native_recovery import (
    SCHEMA as RECOVERY_SCHEMA,
)
from scripts.atlas_r23_native_recovery import (
    approval_digest as recovery_approval_digest,
)
from scripts.build_release_candidate import source_bytes
from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
from scripts.observation_runtime.atlas_r17_cpu_budget import NativeR17CpuBudget
from scripts.observation_runtime.personal_version_safe_release_clock import (
    SELECTOR_NATIVE,
)
from scripts.release_selection import NativeInstalledReleaseVerifier
from scripts.release_selection_store import NativeSelectionStore

SELECTION_ROOT = Path("D:/AtlasRuntime/selection")
APPROVAL = install.DIAG / "atlas-r23-code-only-select-approved-20261113.json"
APPROVAL_PIN = None  # Distinct R23 one-shot selection user decision canonical source hash.
DECISION_SCHEMA = "ATLAS_R23_CODE_ONLY_SELECT_USER_DECISION_V1"
SCOPE = "APPROVE_ONE_R23_CODE_ONLY_NATIVE_SELECTION_NO_FINANCIAL_START"
ACTION = b"ATLAS_R23_NATIVE_CODE_ONLY_REV21_SELECTION_V1"
RECORD_REVISION = 21
CLOCK_IDENTITY = "atlas-r23-code-only-select-r0021"


def source_hash():
    original = Path(__file__).read_bytes()
    canonical, count = re.subn(
        rb"(?m)^APPROVAL_PIN = (?:None|\"[0-9a-f]{64}\")"
        rb"  # Distinct R23 one-shot selection user decision canonical source hash\.",
        b"APPROVAL_PIN = None  # Distinct R23 one-shot selection user decision canonical source hash.",
        original,
    )
    if count != 1:
        raise ValueError("R23_SELECTION_CANONICAL_SOURCE_REQUIRED")
    return hashlib.sha256(canonical).hexdigest()


def _receipt_and_journal():
    target = install.TARGET
    if (
        not target.is_dir()
        or target.is_symlink()
        or target.is_junction()
        or not install.RECEIPT.is_file()
        or install.RECEIPT.is_symlink()
        or not install.JOURNAL.is_file()
        or install.JOURNAL.is_symlink()
    ):
        raise ValueError("R23_ORIGINAL_NATIVE_INSTALL_AND_ACK_REQUIRED")
    raw = source_bytes(
        install.RECEIPT.parent, install.RECEIPT.name, maximum_bytes=8 * 1024**2,
    )
    receipt = releases.strict(raw)
    required = {
        "schema", "stage", "release_path", "source_commit", "files",
        "directories", "archive_sha256", "inventory_sha256", "selected",
        "financial_effects", "provider_connections", "operational_acceptance",
        "layout", "artifact_digest",
    }
    if (
        type(receipt) is not dict
        or set(receipt) != required
        or raw != json.dumps(receipt, sort_keys=True, allow_nan=False).encode()
        or receipt["schema"] != "ATLAS_QD_D_RUNTIME_INSTALLATION_V1"
        or receipt["stage"] != "D_RUNTIME_LAYOUT_VERIFIED"
        or receipt["release_path"] != str(target)
        or receipt["source_commit"] != install.SOURCE
        or receipt["archive_sha256"] != install.ARCHIVE_SHA
        or receipt["inventory_sha256"] != install.INVENTORY_SHA
        or type(receipt["files"]) is not list
        or type(receipt["directories"]) is not list
        or len(receipt["files"]) != install.EXPECTED_FILES
        or len(receipt["directories"]) != install.EXPECTED_DIRECTORIES
        or any(receipt[key] is not False for key in (
            "selected", "financial_effects", "provider_connections",
            "operational_acceptance",
        ))
    ):
        raise ValueError("R23_EXACT_ORIGINAL_CODE_ONLY_INSTALL_RECEIPT_REFUSED")
    artifact = hashlib.sha256(json.dumps(
        receipt["files"], sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode()).hexdigest()
    if receipt["artifact_digest"] != artifact:
        raise ValueError("R23_ORIGINAL_NATIVE_ARTIFACT_MISMATCH")
    expected_layout = {
        "executable": str(target / "python/python.exe"),
        "base": str(target / "python/python.exe"),
        "prefix": str(target / "python"),
        "base_prefix": str(target / "python"),
        "stdlib": str(target / "python/Lib"),
        "bits": 64,
        "version": [3, 12],
    }
    if receipt["layout"] != expected_layout:
        raise ValueError("R23_NATIVE_INTERPRETER_LAYOUT_CHANGED")
    journal = source_bytes(
        install.JOURNAL.parent, install.JOURNAL.name, maximum_bytes=8192,
    )
    rows = journal.splitlines()
    if (
        len(rows) not in (2, 3)
        or releases.strict(rows[0]) != {
            "schema": "ATLAS_R23_UNSELECTED_CODE_INSTALL_INTENT_V1",
            "source_commit": install.SOURCE,
            "archive_sha256": install.ARCHIVE_SHA,
            "target": str(target),
            "financial_authority": False,
            "selection_allowed": False,
            "paper_start_authorized": False,
        }
    ):
        raise ValueError("R23_EXACT_TWO_STAGE_NATIVE_INSTALL_REQUIRED")
    sha = hashlib.sha256(raw).hexdigest()
    spec = releases.validate_spec({
        "schema": "QD_INSTALLED_RELEASE_REFERENCE_V1",
        "domain": "WINDOWS_LOCAL",
        "release": install.SOURCE,
        "root": str(target),
        "receipt": str(install.RECEIPT),
        "receipt_sha256": sha,
        "artifact_digest": artifact,
    }, "WINDOWS_LOCAL")
    releases.validate_native_install_ack(spec, receipt, journal)
    if len(rows) == 2:
        if releases.strict(rows[1]) != {
            "stage": "UNSELECTED_CODE_INSTALL_VERIFIED",
            "receipt_sha256": sha,
        }:
            raise ValueError("R23_ORIGINAL_FINAL_INSTALLED_ACK_REFUSED")
    else:
        require_exact_original_recovered_install_ack(
            rows, receipt_sha=sha, artifact=artifact,
        )
    return spec


def require_exact_original_recovered_install_ack(
    rows, *, receipt_sha, artifact,
):
    """Recovery is accepted only with original refusal and new audited proof."""
    if (
        type(rows) is not list
        or len(rows) != 3
        or releases.strict(rows[1]) != {
            "stage": "REFUSED_PRESERVE_PARTIAL_NO_RETRY",
        }
        or releases.strict(rows[2]) != {
            "stage": "UNSELECTED_CODE_INSTALL_VERIFIED",
            "receipt_sha256": receipt_sha,
        }
    ):
        raise ValueError("R23_ORIGINAL_REFUSAL_AND_RECOVERED_ACK_REQUIRED")
    refused_sha = hashlib.sha256(b"\n".join(rows[:2])).hexdigest()
    receipt_bytes = source_bytes(
        RECOVERY_RECEIPT.parent, RECOVERY_RECEIPT.name, maximum_bytes=8192,
    )
    proof = releases.strict(receipt_bytes)
    if (
        type(proof) is not dict
        or receipt_bytes != json.dumps(
            proof, sort_keys=True, allow_nan=False,
        ).encode()
        or set(proof) != {
            "schema", "stage", "source_commit", "source_archive_sha256",
            "original_partial_native_files_rechecked",
            "new_native_create_only_files", "final_original_native_files",
            "final_original_native_directories",
            "original_refusal_journal_sha256",
            "independent_original_native_installed_readback",
            "source_release_artifact_digest", "code_only_release_selected",
            "financial_authority", "paper_start_authorized",
            "live_trading_authorized",
        }
        or proof["schema"] != RECOVERY_SCHEMA
        or proof["stage"] != "RECOVERY_FULL_NATIVE_ORIGINAL_READBACK_ACCEPTED"
        or proof["source_commit"] != install.SOURCE
        or proof["source_archive_sha256"] != install.ARCHIVE_SHA
        or proof["original_partial_native_files_rechecked"] != 7910
        or proof["new_native_create_only_files"] != 2853
        or proof["final_original_native_files"] != install.EXPECTED_FILES
        or proof["final_original_native_directories"]
        != install.EXPECTED_DIRECTORIES
        or proof["original_refusal_journal_sha256"] != refused_sha
        or proof["independent_original_native_installed_readback"] is not True
        or proof["source_release_artifact_digest"] != artifact
        or any(proof[k] is not False for k in (
            "code_only_release_selected", "financial_authority",
            "paper_start_authorized", "live_trading_authorized",
        ))
    ):
        raise ValueError("R23_EXACT_NATIVE_RECOVERY_RECEIPT_REQUIRED")
    journal_bytes = source_bytes(
        RECOVERY_JOURNAL.parent, RECOVERY_JOURNAL.name,
        maximum_bytes=8192,
    )
    journal_rows = journal_bytes.splitlines()
    if (
        len(journal_rows) != 2
        or releases.strict(journal_rows[0]) != {
            "schema": RECOVERY_SCHEMA,
            "stage": "RECOVERY_INTENT_VERIFY_EXISTING_CREATE_MISSING_ONLY",
            "original_audit_sha256": RECOVERY_AUDIT_SHA,
            "original_refusal_sha256": refused_sha,
            "new_original_root_allowed": False,
            "financial_authority": False,
            "selection_allowed": False,
        }
        or releases.strict(journal_rows[1]) != {
            "stage": "RECOVERED_FULL_CODE_ONLY_NATIVE_ACK",
            "receipt_sha256": receipt_sha,
        }
    ):
        raise ValueError("R23_EXACT_NATIVE_RECOVERY_JOURNAL_REQUIRED")
    # Bind the recovered release to the distinct, real Windows-local recovery
    # approval; the old installation decision alone never authorizes recovery.
    recovery_approval_digest()
    return True


def candidate():
    previous = install.original_selected_r21()
    install.original_accounts()
    if (
        os.path.lexists(SELECTION_ROOT / "r0021.json")
        or os.path.lexists(SELECTION_ROOT / "r0021.pending")
    ):
        raise ValueError("R23_ORIGINAL_SELECTOR_ALREADY_COMMITTED_OR_UNCERTAIN")
    spec = _receipt_and_journal()
    store = NativeSelectionStore(
        root=str(SELECTION_ROOT), native_root=list(SELECTOR_NATIVE),
    )
    try:
        with store.locked():
            rows = store.records()
            if (
                len(rows) != 20
                or rows[-1].get("revision") != 20
                or rows[-1].get("action") != "SELECT"
                or rows[-1].get("selected") != previous
            ):
                raise ValueError("R23_EXACT_SELECTED_R21_REV20_REQUIRED")
            previous_head = releases.digest(rows[-1])
    finally:
        store.close()
    operation = hashlib.sha256(
        ACTION + previous_head.encode()
        + spec["receipt_sha256"].encode()
        + spec["artifact_digest"].encode()
    ).hexdigest()[:32]
    return {
        "schema": "QD_RELEASE_SELECTION_RECEIPT_V1",
        "domain": "WINDOWS_LOCAL",
        "revision": RECORD_REVISION,
        "action": "SELECT",
        "operation": operation,
        "previous": previous_head,
        "selected": spec,
        "restores": None,
    }


def approval_digest(row):
    if type(APPROVAL_PIN) is not str or re.fullmatch("[0-9a-f]{64}", APPROVAL_PIN) is None:
        raise ValueError("R23_DISTINCT_NATIVE_SELECTION_OPERATOR_APPROVAL_REQUIRED")
    from scripts.volume_inspector.windows_output import current_sid

    raw = source_bytes(APPROVAL.parent, APPROVAL.name, maximum_bytes=4096)
    decision = releases.strict(raw)
    if (
        type(decision) is not dict
        or set(decision) != {
            "schema", "action", "scope", "operator_sid", "source_commit",
            "native_predecessor", "previous_head", "revision",
            "installed_receipt_sha256", "artifact_digest",
            "proposed_record_sha256", "selector_source_sha256", "one_shot",
            "financial_authority", "provider_access", "paper_accounts",
            "paper_start_authorized", "live_trading_authorized",
        }
        or hashlib.sha256(raw).hexdigest() != APPROVAL_PIN
        or decision["schema"] != DECISION_SCHEMA
        or decision["action"] != "ONE_SHOT_R23_NATIVE_CODE_ONLY_SELECT"
        or decision["scope"] != SCOPE
        or decision["operator_sid"] != current_sid()
        or decision["source_commit"] != install.SOURCE
        or decision["native_predecessor"] != install.R21_SOURCE
        or decision["previous_head"] != row["previous"]
        or decision["revision"] != RECORD_REVISION
        or decision["installed_receipt_sha256"] != row["selected"]["receipt_sha256"]
        or decision["artifact_digest"] != row["selected"]["artifact_digest"]
        or decision["proposed_record_sha256"] != releases.digest(row)
        or decision["selector_source_sha256"] != source_hash()
        or decision["one_shot"] is not True
        or any(decision[key] is not False for key in (
            "financial_authority", "provider_access", "paper_accounts",
            "paper_start_authorized", "live_trading_authorized",
        ))
    ):
        raise ValueError("R23_SELECTION_EXACT_SOURCE_SID_DECISION_REFUSED")
    return APPROVAL_PIN


def clock_required(clock):
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R23_SELECTION_ORIGINAL_TWO_PEER_CLOCK_REQUIRED")
    clock.require_operational(CLOCK_IDENTITY)
    evidence = clock.evidence
    if (
        evidence.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
        or type(evidence.get("bound_ms")) is not int
        or not 0 <= evidence["bound_ms"] <= 1000
        or evidence.get("financial_authority") is not False
    ):
        raise ValueError("R23_SELECTION_TWO_PEER_NTP_QUALITY_REFUSED")
    return True


def select(*, clock, approved=False):
    if approved is not True:
        raise ValueError("R23_SELECTION_OPERATOR_APPROVAL_REQUIRED")
    row = candidate()
    approval_digest(row)
    clock_required(clock)
    from scripts.install_version_safe_candidate import _qualify_native_clock_180s

    proof = _qualify_native_clock_180s(clock, CLOCK_IDENTITY)
    approval_digest(candidate())
    store = NativeSelectionStore(
        root=str(SELECTION_ROOT), native_root=list(SELECTOR_NATIVE),
    )
    try:
        with NativeR17CpuBudget() as cpu, LowImpactEnvelope() as envelope:
            cpu.pulse()
            with store.locked():
                current = store.records()
                if (
                    len(current) != 20
                    or current[-1].get("revision") != 20
                    or releases.digest(current[-1]) != row["previous"]
                    or current[-1].get("selected", {}).get("release") != install.R21_SOURCE
                    or os.path.lexists(SELECTION_ROOT / "r0021.pending")
                    or os.path.lexists(SELECTION_ROOT / "r0021.json")
                ):
                    raise ValueError("R23_SELECTED_NATIVE_ORIGINAL_HISTORY_CHANGED")
                approval_digest(row)
                clock_required(clock)
                envelope.tick()
                with NativeInstalledReleaseVerifier().open(row["selected"]) as proof_release:
                    if (
                        proof_release.get("source_commit") != install.SOURCE
                        or proof_release.get("artifact_digest") != row["selected"]["artifact_digest"]
                        or len(proof_release.get("files", [])) != install.EXPECTED_FILES
                        or len(proof_release.get("directories", []))
                        != install.EXPECTED_DIRECTORIES
                        or any(proof_release.get(key) is not False for key in (
                            "selected", "financial_effects", "provider_connections",
                            "operational_acceptance",
                        ))
                    ):
                        raise ValueError("R23_ORIGINAL_INSTALLED_CODE_READBACK_REFUSED")
                    cpu.pulse()
                if _receipt_and_journal() != row["selected"]:
                    raise ValueError("R23_ORIGINAL_INSTALL_RECEIPT_CHANGED")
                install.original_accounts()
                clock_required(clock)
                approval_digest(row)
                cpu.pulse()
                store.publish(row)
                after = store.records()
                if len(after) != 21 or after[:20] != current or after[-1] != row:
                    raise ValueError("R23_SELECTED_JOURNAL_UNKNOWN_NO_RETRY")
    finally:
        store.close()
    return {
        "status": "R23_NATIVE_CODE_ONLY_SELECTED_NO_FINANCIAL_START",
        "selected_revision": RECORD_REVISION,
        "source_commit": install.SOURCE,
        "head": releases.digest(row),
        "clock_samples": proof["samples"],
        "financial_authority": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--execute-approved-code-only", action="store_true")
    parser.add_argument("--confirm-scope", default=None)
    args = parser.parse_args(argv)
    if args.inspect:
        row = candidate()
        return {
            "status": "R23_NATIVE_VERIFIED_READY_FOR_DISTINCT_SELECTION",
            "proposed_record_sha256": releases.digest(row),
            "previous_head": row["previous"],
            "installed_receipt_sha256": row["selected"]["receipt_sha256"],
            "artifact_digest": row["selected"]["artifact_digest"],
            "selector_source_sha256": source_hash(),
            "revision": RECORD_REVISION,
            "financial_authority": False,
            "paper_start_authorized": False,
        }
    if args.confirm_scope != SCOPE:
        raise ValueError("R23_SELECTION_EXACT_OPERATOR_SCOPE_REQUIRED")
    approval_digest(candidate())
    clock = IndependentNtpClock(runtime_id=CLOCK_IDENTITY)
    try:
        return select(clock=clock, approved=True)
    finally:
        clock.revoke()


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
