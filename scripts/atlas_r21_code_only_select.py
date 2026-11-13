"""One-time ORIGINAL R21 code-only selector, no financial authority.

Requires fully verified *installed* unselected R21 with exact original native
receipt and intent/ACK journal; original immutable R20 rev19 predecessor,
a separate one-shot SID-source-bound operator selection decision, 180s trusted
two-peer clock, native ACL/file-handle verification, and the original 12
financial namespaces empty. The selector itself is append-only native rev20.
No paper accounts, provider connection, trading activation or LIVE permission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from scripts import release_selection
from scripts.atlas_r13_low_impact_installer import LowImpactEnvelope
from scripts.atlas_r21_code_only_install import (
    ARCHIVE_SHA,
    EXPECTED_DIRECTORIES,
    EXPECTED_FILES,
    INVENTORY_SHA,
    JOURNAL,
    RECEIPT,
    SOURCE,
    TARGET,
    original_accounts,
    original_selected_r20,
)
from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
from scripts.observation_runtime.atlas_r17_cpu_budget import NativeR17CpuBudget
from scripts.observation_runtime.personal_version_safe_release_clock import (
    SELECTOR_NATIVE,
)
from scripts.release_selection import NativeInstalledReleaseVerifier
from scripts.release_selection_store import NativeSelectionStore

ROOT = Path("D:/Work/Project Atlas")
DIAG = ROOT / "logs/diagnostics"
APPROVAL = DIAG / "atlas-r21-code-only-select-approved-20261113.json"
APPROVAL_PIN = None  # Distinct R21 selected-native user approval canonicalized.
SCOPE = "APPROVE_ONE_R21_CODE_ONLY_NATIVE_SELECTION_NO_FINANCIAL_START"
CLOCK_IDENTITY = "atlas-r21-native-code-only-select-r0020"
RECORD_REVISION = 20
SELECTION_ROOT = Path("D:/AtlasRuntime/selection")
SELECTION_ACTION = b"ATLAS_R21_NATIVE_CODE_ONLY_REV20_SELECTION_V1"
DECISION_SCHEMA = "ATLAS_R21_CODE_ONLY_SELECT_USER_DECISION_V1"


def source_hash():
    raw = Path(__file__).read_bytes()
    canonical, count = re.subn(
        rb'(?m)^APPROVAL_PIN = (?:None|"[0-9a-f]{64}")'
        rb"  # Distinct R21 selected-native user approval canonicalized\.",
        b"APPROVAL_PIN = None  # Distinct R21 selected-native user approval canonicalized.",
        raw,
    )
    if count != 1:
        raise ValueError("R21_SELECTION_SOURCE_CANONICAL_APPROVAL_REQUIRED")
    return hashlib.sha256(canonical).hexdigest()


def _safe_bytes(path, maximum):
    if (
        not path.is_file() or path.is_symlink() or path.is_junction()
        or not 0 < path.stat().st_size <= maximum
    ):
        raise ValueError("R21_ORIGINAL_REGULAR_INSTALL_RECEIPT_REQUIRED")
    return path.read_bytes()


def candidate():
    previous = original_selected_r20()
    original_accounts()
    if (
        os.path.lexists(SELECTION_ROOT / "r0020.json")
        or os.path.lexists(SELECTION_ROOT / "r0020.pending")
    ):
        raise ValueError("R21_NATIVE_SELECTION_ALREADY_COMMITTED_OR_UNKNOWN")
    if not TARGET.is_dir() or TARGET.is_symlink() or TARGET.is_junction():
        raise ValueError("R21_NATIVE_UNSELECTED_CODE_INSTALL_REQUIRED")
    raw = _safe_bytes(RECEIPT, 10*1024*1024)
    journal = _safe_bytes(JOURNAL, 8192)
    receipt = release_selection.strict(raw)
    if (
        raw != json.dumps(
            receipt, sort_keys=True, allow_nan=False,
        ).encode()
        or type(receipt) is not dict
        or set(receipt) != {
            "schema", "stage", "release_path", "source_commit",
            "files", "directories", "archive_sha256", "inventory_sha256",
            "selected", "financial_effects", "provider_connections",
            "operational_acceptance", "layout", "artifact_digest",
        }
        or receipt["schema"] != "ATLAS_QD_D_RUNTIME_INSTALLATION_V1"
        or receipt["stage"] != "D_RUNTIME_LAYOUT_VERIFIED"
        or receipt["release_path"] != str(TARGET)
        or receipt["source_commit"] != SOURCE
        or receipt["archive_sha256"] != ARCHIVE_SHA
        or receipt["inventory_sha256"] != INVENTORY_SHA
        or len(receipt["files"]) != EXPECTED_FILES
        or len(receipt["directories"]) != EXPECTED_DIRECTORIES
        or any(receipt[k] is not False for k in (
            "selected", "financial_effects", "provider_connections",
            "operational_acceptance",
        ))
    ):
        raise ValueError("R21_ORIGINAL_IMMUTABLE_INSTALL_RECEIPT_CONFLICT")
    artifact = hashlib.sha256(json.dumps(
        receipt["files"], sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode()).hexdigest()
    if receipt["artifact_digest"] != artifact:
        raise ValueError("R21_ORIGINAL_ARTIFACT_FILE_INVENTORY_CHANGED")
    layout = receipt["layout"]
    if layout != {
        "executable": str(TARGET / "python/python.exe"),
        "base": str(TARGET / "python/python.exe"),
        "prefix": str(TARGET / "python"),
        "base_prefix": str(TARGET / "python"),
        "stdlib": str(TARGET / "python/Lib"),
        "bits": 64,
        "version": [3, 12],
    }:
        raise ValueError("R21_ACTUAL_NATIVE_INTERPRETER_LAYOUT_CHANGED")
    rows = journal.splitlines()
    if (
        len(rows) != 2
        or release_selection.strict(rows[0]) != {
            "schema": "ATLAS_R21_UNSELECTED_CODE_INSTALL_INTENT_V1",
            "source_commit": SOURCE,
            "archive_sha256": ARCHIVE_SHA,
            "target": str(TARGET),
            "financial_authority": False,
            "selection_allowed": False,
            "paper_start_authorized": False,
        }
    ):
        raise ValueError("R21_NATIVE_ORIGINAL_TWO_STAGE_INTENT_ACK_REQUIRED")
    receipt_sha = hashlib.sha256(raw).hexdigest()
    if release_selection.strict(rows[1]) != {
        "stage": "UNSELECTED_CODE_INSTALL_VERIFIED",
        "receipt_sha256": receipt_sha,
    }:
        raise ValueError("R21_ORIGINAL_NATIVE_INSTALL_ACK_REFUSED")
    spec = release_selection.validate_spec({
        "schema": "QD_INSTALLED_RELEASE_REFERENCE_V1",
        "domain": "WINDOWS_LOCAL",
        "release": SOURCE,
        "root": str(TARGET),
        "receipt": str(RECEIPT),
        "receipt_sha256": receipt_sha,
        "artifact_digest": artifact,
    }, "WINDOWS_LOCAL")
    release_selection.validate_native_install_ack(spec, receipt, journal)
    store = NativeSelectionStore(
        root=str(SELECTION_ROOT), native_root=list(SELECTOR_NATIVE),
    )
    try:
        with store.locked():
            records = store.records()
            if (
                len(records) != 19
                or records[-1].get("revision") != 19
                or records[-1].get("selected") != previous
            ):
                raise ValueError("R21_SELECTED_ORIGINAL_R20_PREDECESSOR_CHANGED")
            previous_head = release_selection.digest(records[-1])
    finally:
        store.close()
    operation = hashlib.sha256(
        SELECTION_ACTION + previous_head.encode()
        + receipt_sha.encode() + artifact.encode()
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
    if (
        type(APPROVAL_PIN) is not str
        or re.fullmatch(r"[0-9a-f]{64}", APPROVAL_PIN) is None
    ):
        raise ValueError("R21_DISTINCT_SELECTION_USER_APPROVAL_REQUIRED")
    from scripts.volume_inspector.windows_output import current_sid

    decision = release_selection.strict(
        _safe_bytes(APPROVAL, 4096),
    )
    if (
        type(decision) is not dict
        or set(decision) != {
            "schema", "action", "scope", "operator_sid",
            "source_commit", "native_predecessor", "previous_head",
            "revision", "installed_receipt_sha256", "artifact_digest",
            "proposed_record_sha256", "selector_source_sha256", "one_shot",
            "financial_authority", "provider_access", "paper_accounts",
            "paper_start_authorized", "live_trading_authorized",
        }
        or hashlib.sha256(
            _safe_bytes(APPROVAL, 4096),
        ).hexdigest() != APPROVAL_PIN
        or decision["schema"] != DECISION_SCHEMA
        or decision["action"] != "ONE_SHOT_R21_NATIVE_CODE_ONLY_SELECT"
        or decision["scope"] != SCOPE
        or decision["operator_sid"] != current_sid()
        or decision["source_commit"] != SOURCE
        or decision["native_predecessor"]
        != original_selected_r20()["release"]
        or decision["previous_head"] != row["previous"]
        or decision["revision"] != RECORD_REVISION
        or decision["installed_receipt_sha256"]
        != row["selected"]["receipt_sha256"]
        or decision["artifact_digest"]
        != row["selected"]["artifact_digest"]
        or decision["proposed_record_sha256"] != release_selection.digest(row)
        or decision["selector_source_sha256"] != source_hash()
        or decision["one_shot"] is not True
        or any(decision[k] is not False for k in (
            "financial_authority", "provider_access", "paper_accounts",
            "paper_start_authorized", "live_trading_authorized",
        ))
    ):
        raise ValueError("R21_ORIGINAL_SELECTED_SOURCE_SID_APPROVAL_REFUSED")
    return APPROVAL_PIN


def clock_required(clock):
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R21_ORIGINAL_TWO_PEER_NTP_REQUIRED")
    clock.require_operational(CLOCK_IDENTITY)
    evidence = clock.evidence
    if (
        evidence.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
        or type(evidence.get("bound_ms")) is not int
        or not 0 <= evidence["bound_ms"] <= 1000
        or evidence.get("financial_authority") is not False
    ):
        raise ValueError("R21_SELECTED_ORIGINAL_NTP_QUALITY_REFUSED")
    return True


def select(*, clock, approved=False):
    if approved is not True:
        raise ValueError("R21_SELECTED_OPERATOR_APPROVAL_REQUIRED")
    row = candidate()
    approval_digest(row)
    clock_required(clock)
    from scripts.install_version_safe_candidate import _qualify_native_clock_180s

    proof = _qualify_native_clock_180s(clock, CLOCK_IDENTITY)
    original_accounts()
    approval_digest(candidate())
    store = NativeSelectionStore(
        root=str(SELECTION_ROOT), native_root=list(SELECTOR_NATIVE),
    )
    try:
        with NativeR17CpuBudget() as cpu, LowImpactEnvelope(
            check_every=32, pace_every=128,
        ) as envelope:
            cpu.pulse()
            with store.locked():
                current = store.records()
                if (
                    len(current) != 19
                    or release_selection.digest(current[-1]) != row["previous"]
                    or current[-1].get("revision") != 19
                    or current[-1].get("selected", {}).get("release")
                    != original_selected_r20()["release"]
                    or os.path.lexists(SELECTION_ROOT / "r0020.pending")
                    or os.path.lexists(SELECTION_ROOT / "r0020.json")
                ):
                    raise ValueError("R21_NATIVE_ORIGINAL_R20_SELECTOR_CHANGED")
                approval_digest(row)
                clock_required(clock)
                envelope.tick()
                with NativeInstalledReleaseVerifier().open(
                    row["selected"],
                ) as installed:
                    if (
                        installed.get("source_commit") != SOURCE
                        or installed.get("artifact_digest")
                        != row["selected"]["artifact_digest"]
                        or len(installed.get("files", [])) != EXPECTED_FILES
                        or len(installed.get("directories", []))
                        != EXPECTED_DIRECTORIES
                        or any(installed.get(k) is not False for k in (
                            "selected", "financial_effects",
                            "provider_connections", "operational_acceptance",
                        ))
                    ):
                        raise ValueError(
                            "R21_REAL_ORIGINAL_INSTALLED_CODE_NOT_VERIFIED"
                        )
                    cpu.pulse()
                    clock_required(clock)
                approval_digest(row)
                if (
                    hashlib.sha256(
                        _safe_bytes(RECEIPT, 10*1024*1024),
                    ).hexdigest()
                    != row["selected"]["receipt_sha256"]
                    or release_selection.strict(
                        _safe_bytes(JOURNAL, 8192).splitlines()[-1],
                    ) != {
                        "stage": "UNSELECTED_CODE_INSTALL_VERIFIED",
                        "receipt_sha256": row["selected"]["receipt_sha256"],
                    }
                ):
                    raise ValueError(
                        "R21_ORIGINAL_NATIVE_INSTALL_RECEIPT_OR_ACK_CHANGED"
                    )
                original_accounts()
                clock_required(clock)
                cpu.pulse()
                store.publish(row)
                after = store.records()
                if (
                    len(after) != 20
                    or after[:19] != current
                    or after[-1] != row
                ):
                    raise ValueError(
                        "R21_NATIVE_SELECTOR_COMMIT_UNKNOWN_NO_RETRY"
                    )
    finally:
        store.close()
    return {
        "status": "R21_IMMUTABLE_CODE_ONLY_SELECTED",
        "native_revision": RECORD_REVISION,
        "source_commit": SOURCE,
        "selected_head": release_selection.digest(row),
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
            "status": "R21_CODE_ONLY_INSTALLED_READY_FOR_SEPARATE_SELECTION",
            "proposed_record_sha256": release_selection.digest(row),
            "revision": RECORD_REVISION,
            "financial_authority": False,
            "paper_start_authorized": False,
        }
    if args.confirm_scope != SCOPE:
        raise ValueError("R21_EXACT_SELECTION_SCOPE_FLAG_REQUIRED")
    approval_digest(candidate())
    clock = IndependentNtpClock(runtime_id=CLOCK_IDENTITY)
    try:
        return select(clock=clock, approved=True)
    finally:
        clock.revoke()


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
