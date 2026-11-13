"""R20 one-shot CODE-ONLY selected-native revision 18, successor to R19.

Require independently installed and fully verified original Windows R20
release receipt, genuine 17-record immutable R19 predecessor, exact SID-
bound one-time user approval, two-peer 180-second NTP and bounded CPU.
Never create accounts, publish financial leases, make orders, or Start PAPER.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from scripts import release_selection
from scripts.atlas_r13_low_impact_installer import LowImpactEnvelope, _exact_bytes
from scripts.atlas_r20_code_only_install import (
    ARCHIVE_SHA,
    EXPECTED_DIRECTORIES,
    EXPECTED_FILES,
    INVENTORY_SHA,
    JOURNAL,
    RECEIPT,
    SOURCE,
    TARGET,
    original_accounts,
    original_selected_r19,
)
from scripts.atlas_r20_source_review import R19_HEAD, R19_SOURCE
from scripts.observation_runtime.atlas_r17_cpu_budget import NativeR17CpuBudget
from scripts.observation_runtime.personal_version_safe_release_clock import (
    SELECTOR_NATIVE,
)
from scripts.release_selection import NativeInstalledReleaseVerifier
from scripts.release_selection_store import NativeSelectionStore

ROOT = Path("D:/Work/Project Atlas")
APPROVAL = ROOT / "logs/diagnostics/atlas-r20-r01-code-only-select-approved-20261112.json"
APPROVAL_PIN = None  # Distinct R20 one-time selection operator scope pin.
SCOPE = "APPROVE_ONE_R20_CODE_ONLY_NATIVE_SELECTION_NO_FINANCIAL_START"
CLOCK_IDENTITY = "atlas-r20-native-code-only-select-r0019"
RECORD_REVISION = 19
SELECTION_ROOT = Path("D:/AtlasRuntime/selection")
SELECTION_ACTION = b"ATLAS_R20_CODE_ONLY_NATIVE_REV19_SELECTION_V1"


def approval_source_sha():
    original = Path(__file__).read_bytes()
    canonical, count = re.subn(
        rb'(?m)^APPROVAL_PIN = (?:None|"[0-9a-f]{64}")'
        rb'  # Distinct R20 one-time selection operator scope pin\.',
        b'APPROVAL_PIN = None  # Distinct R20 one-time selection operator scope pin.',
        original)
    if count != 1:
        raise ValueError("R20_SELECT_APPROVAL_SOURCE_PIN_REFUSED")
    return hashlib.sha256(canonical).hexdigest()


def _safe_bytes(path, maximum):
    if (not path.is_file() or path.is_symlink() or path.is_junction()
            or not 0 < path.stat().st_size <= maximum):
        raise ValueError("R20_SELECT_ORIGINAL_REGULAR_INSTALL_RECEIPT_REQUIRED")
    return path.read_bytes()


def candidate():
    original_selected_r19(verify_files=True)
    original_accounts()
    if (os.path.lexists(SELECTION_ROOT/"r0019.json")
            or os.path.lexists(SELECTION_ROOT/"r0019.pending")):
        raise ValueError("R20_SELECTION_ALREADY_PUBLISHED_OR_PARTIAL_NO_RETRY")
    if not TARGET.is_dir() or TARGET.is_symlink() or TARGET.is_junction():
        raise ValueError("R20_UNSELECTED_NATIVE_INSTALLED_CODE_REQUIRED")
    raw = _safe_bytes(RECEIPT, 10*1024*1024)
    journal = _safe_bytes(JOURNAL, 8192)
    receipt = release_selection.strict(raw)
    if (raw != json.dumps(receipt, sort_keys=True, allow_nan=False).encode()
            or set(receipt) != {
                "schema", "stage", "release_path", "source_commit", "files",
                "directories", "archive_sha256", "inventory_sha256",
                "selected", "financial_effects", "provider_connections",
                "operational_acceptance", "layout", "artifact_digest"}
            or receipt["schema"] != "ATLAS_QD_D_RUNTIME_INSTALLATION_V1"
            or receipt["stage"] != "D_RUNTIME_LAYOUT_VERIFIED"
            or receipt["release_path"] != str(TARGET)
            or receipt["source_commit"] != SOURCE
            or receipt["archive_sha256"] != ARCHIVE_SHA
            or receipt["inventory_sha256"] != INVENTORY_SHA
            or len(receipt["files"]) != EXPECTED_FILES
            or len(receipt["directories"]) != EXPECTED_DIRECTORIES
            or any(receipt[k] is not False for k in (
                "selected", "financial_effects",
                "provider_connections", "operational_acceptance"))):
        raise ValueError("R20_NATIVE_INSTALL_RECEIPT_INCONSISTENT")
    artifact = hashlib.sha256(json.dumps(
        receipt["files"], sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode()).hexdigest()
    if receipt["artifact_digest"] != artifact:
        raise ValueError("R20_INSTALL_ARTIFACT_DIGEST_CHANGED")
    layout = receipt["layout"]
    if (layout != {
            "executable": str(TARGET/"python/python.exe"),
            "base": str(TARGET/"python/python.exe"),
            "prefix": str(TARGET/"python"),
            "base_prefix": str(TARGET/"python"),
            "stdlib": str(TARGET/"python/Lib"),
            "bits": 64, "version": [3, 12]}):
        raise ValueError("R20_NATIVE_PYTHON_ORIGINAL_LAYOUT_CHANGED")
    rows = journal.splitlines()
    if (len(rows) != 2 or release_selection.strict(rows[0]) != {
            "schema": "ATLAS_R20_UNSELECTED_CODE_INSTALL_INTENT_V1",
            "source_commit": SOURCE,
            "archive_sha256": ARCHIVE_SHA,
            "target": str(TARGET),
            "financial_authority": False,
            "selection_allowed": False, "paper_start_authorized": False}):
        raise ValueError("R20_NATIVE_INSTALL_TWO_STAGE_JOURNAL_REQUIRED")
    receipt_sha = hashlib.sha256(raw).hexdigest()
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
    operation = hashlib.sha256(
        SELECTION_ACTION + R19_HEAD.encode()
        + receipt_sha.encode()+artifact.encode()).hexdigest()[:32]
    return {
        "schema": "QD_RELEASE_SELECTION_RECEIPT_V1",
        "domain": "WINDOWS_LOCAL",
        "revision": RECORD_REVISION,
        "action": "SELECT",
        "operation": operation,
        "previous": R19_HEAD,
        "selected": spec,
        "restores": None,
    }


def approval_digest(row):
    if (type(APPROVAL_PIN) is not str
            or re.fullmatch("[0-9a-f]{64}", APPROVAL_PIN) is None):
        raise ValueError("R20_SELECTION_DISTINCT_USER_APPROVAL_REQUIRED")
    from scripts.volume_inspector.windows_output import current_sid
    decision = release_selection.strict(
        _exact_bytes(APPROVAL, APPROVAL_PIN, max_bytes=4096))
    if (type(decision) is not dict or set(decision) != {
            "schema", "action", "scope", "operator_sid",
            "source_commit", "native_predecessor", "previous_head",
            "revision", "installed_receipt_sha256", "artifact_digest",
            "proposed_record_sha256", "selector_source_sha256",
            "one_shot", "financial_authority", "provider_access",
            "paper_accounts", "paper_start_authorized", "live_trading_authorized"}
            or decision["schema"] != "ATLAS_R20_CODE_ONLY_SELECT_USER_DECISION_V1"
            or decision["action"] != "ONE_SHOT_R20_NATIVE_CODE_ONLY_SELECT"
            or decision["scope"] != SCOPE
            or decision["operator_sid"] != current_sid()
            or decision["source_commit"] != SOURCE
            or decision["native_predecessor"] != R19_SOURCE
            or decision["previous_head"] != R19_HEAD
            or decision["revision"] != RECORD_REVISION
            or decision["installed_receipt_sha256"] != row["selected"]["receipt_sha256"]
            or decision["artifact_digest"] != row["selected"]["artifact_digest"]
            or decision["proposed_record_sha256"] != release_selection.digest(row)
            or decision["selector_source_sha256"] != approval_source_sha()
            or decision["one_shot"] is not True
            or any(decision[k] is not False for k in (
                "financial_authority", "provider_access",
                "paper_accounts", "paper_start_authorized",
                "live_trading_authorized"))):
        raise ValueError("R20_CODE_ONLY_SELECTION_OPERATOR_SCOPE_REFUSED")
    return APPROVAL_PIN


def clock_required(clock):
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,
    )
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R20_CODE_SELECTION_ORIGINAL_TWO_PEER_CLOCK_REQUIRED")
    clock.require_operational(CLOCK_IDENTITY)
    evidence = clock.evidence
    if (type(evidence.get("bound_ms")) is not int
            or not 0 <= evidence["bound_ms"] <= 1000
            or evidence.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
            or evidence.get("financial_authority") is not False):
        raise ValueError("R20_SELECTION_NTP_SOURCE_QUALITY_REFUSED")
    return True


def select(*, clock, approved=False):
    if approved is not True:
        raise ValueError("R20_CODE_SELECTION_EXACT_APPROVAL_REQUIRED")
    row = candidate()
    approval_digest(row)
    clock_required(clock)
    from scripts.install_version_safe_candidate import _qualify_native_clock_180s
    proof = _qualify_native_clock_180s(clock, CLOCK_IDENTITY)
    approval_digest(candidate())
    store = NativeSelectionStore(
        root=str(SELECTION_ROOT), native_root=list(SELECTOR_NATIVE))
    try:
        with NativeR17CpuBudget() as cpu, LowImpactEnvelope(
            check_every=32, pace_every=128
        ) as envelope:
            cpu.pulse()
            with store.locked():
                current = store.records()
                if (len(current) != 18
                        or release_selection.digest(current[-1]) != R19_HEAD
                        or current[-1].get("selected", {}).get("release") != R19_SOURCE
                        or os.path.lexists(SELECTION_ROOT/"r0019.pending")
                        or os.path.lexists(SELECTION_ROOT/"r0019.json")):
                    raise ValueError("R20_SELECTION_NATIVE_R19_HEAD_CHANGED")
                approval_digest(row)
                clock_required(clock)
                envelope.tick()
                with NativeInstalledReleaseVerifier().open(row["selected"]) as proof_native:
                    if (proof_native.get("source_commit") != SOURCE
                            or proof_native.get("artifact_digest") !=
                               row["selected"]["artifact_digest"]
                            or len(proof_native.get("files", [])) != EXPECTED_FILES
                            or len(proof_native.get("directories", [])) != EXPECTED_DIRECTORIES
                            or any(proof_native.get(k) is not False for k in (
                                "selected", "financial_effects",
                                "provider_connections", "operational_acceptance"))):
                        raise ValueError("R20_GENUINE_ORIGINAL_INSTALLED_FILES_REFUSED")
                    cpu.pulse()
                    clock_required(clock)
                approval_digest(row)
                if (hashlib.sha256(_safe_bytes(RECEIPT, 10*1024*1024)).hexdigest()
                    != row["selected"]["receipt_sha256"]
                    or release_selection.strict(_safe_bytes(JOURNAL, 8192).splitlines()[-1])
                    != {"stage": "UNSELECTED_CODE_INSTALL_VERIFIED",
                        "receipt_sha256": row["selected"]["receipt_sha256"]}):
                    raise ValueError("R20_ORIGINAL_RECEIPT_OR_JOURNAL_DRIFT")
                original_accounts()
                clock_required(clock)
                cpu.pulse()
                store.publish(row)
                after = store.records()
                if len(after) != 19 or after[:18] != current or after[-1] != row:
                    raise ValueError("R20_NATIVE_SELECTOR_COMMIT_UNKNOWN_NO_RETRY")
    finally:
        store.close()
    return {
        "status": "R20_IMMUTABLE_CODE_ONLY_SELECTED",
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
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--inspect", action="store_true")
    modes.add_argument("--execute-approved-code-only", action="store_true")
    parser.add_argument("--confirm-scope", default=None)
    args = parser.parse_args(argv)
    if args.inspect:
        row = candidate()
        return {
            "status": "R20_CODE_INSTALL_READY_FOR_SEPARATE_APPROVED_SELECTION",
            "proposed_record_sha256": release_selection.digest(row),
            "revision": RECORD_REVISION,
            "financial_authority": False,
            "paper_start_authorized": False,
        }
    if args.confirm_scope != SCOPE:
        raise ValueError("R20_CODE_SELECTION_EXACT_SCOPE_FLAG_REQUIRED")
    approval_digest(candidate())
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,
    )
    clock = IndependentNtpClock(runtime_id=CLOCK_IDENTITY)
    try:
        return select(clock=clock, approved=True)
    finally:
        clock.revoke()


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
