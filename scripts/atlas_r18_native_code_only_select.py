"""Separate approved R18 immutable CODE-only selection, revision 17.

Never installation, account opening, provider acquisition, PAPER/live orders,
or silent rollback/retry. Original R17 predecessor and independently proved
R18 install receipt must match exact durable native original handles before
ONE append-only selected record is published.
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
from scripts.atlas_r18_native_code_only_install import (
    ARCHIVE_SHA,
    EXPECTED_DIRECTORIES,
    EXPECTED_FILES,
    INVENTORY_SHA,
    JOURNAL,
    RECEIPT,
    SOURCE,
    TARGET,
    original_accounts,
    original_predecessor,
)
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    HEAD as R17_HEAD,
)
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    SOURCE as R17_SOURCE,
)
from scripts.observation_runtime.atlas_r17_cpu_budget import NativeR17CpuBudget
from scripts.observation_runtime.personal_version_safe_release_clock import (
    SELECTOR_NATIVE,
)
from scripts.release_selection import NativeInstalledReleaseVerifier
from scripts.release_selection_store import NativeSelectionStore

ROOT = Path("D:/Work/Project Atlas")
APPROVAL = ROOT / "logs/diagnostics/atlas-r18-code-only-select-approved-20261112.json"
APPROVAL_PIN = "aabbc4278110aa109292792d4c86760c910c50928cd8df719076118f81ac41d8"  # Distinct R18 one-time selection operator scope pin.
SCOPE = "APPROVE_ONE_R18_CODE_ONLY_NATIVE_SELECTION_NO_FINANCIAL_START"
CLOCK_IDENTITY = "atlas-r18-native-code-only-select-r0017"
RECORD_REVISION = 17
SELECTION_ROOT = Path("D:/AtlasRuntime/selection")
SELECTION_ACTION = b"ATLAS_R18_CODE_ONLY_NATIVE_REV17_SELECTION_V1"


def approval_source_sha():
    original = Path(__file__).read_bytes()
    canonical, count = re.subn(
        rb'(?m)^APPROVAL_PIN = (?:None|"[0-9a-f]{64}")'
        rb'  # Distinct R18 one-time selection operator scope pin\.',
        b'APPROVAL_PIN = None  # Distinct R18 one-time selection operator scope pin.',
        original)
    if count != 1:
        raise ValueError("R18_SELECT_APPROVAL_SOURCE_PIN_REFUSED")
    return hashlib.sha256(canonical).hexdigest()


def _safe_bytes(path, maximum):
    if (not path.is_file() or path.is_symlink() or path.is_junction()
            or not 0 < path.stat().st_size <= maximum):
        raise ValueError("R18_SELECT_ORIGINAL_REGULAR_INSTALL_RECEIPT_REQUIRED")
    return path.read_bytes()


def candidate():
    """Pure selection row, NO native selector publication."""
    original_predecessor()
    original_accounts()
    if (os.path.lexists(SELECTION_ROOT/"r0017.json")
            or os.path.lexists(SELECTION_ROOT/"r0017.pending")):
        raise ValueError("R18_SELECTION_ALREADY_PUBLISHED_OR_PARTIAL_NO_RETRY")
    if (not TARGET.is_dir() or TARGET.is_symlink() or TARGET.is_junction()):
        raise ValueError("R18_CODE_ONLY_NATIVE_INSTALLED_SOURCE_REQUIRED")
    raw = _safe_bytes(RECEIPT, 10*1024*1024)
    journal = _safe_bytes(JOURNAL, 8192)
    receipt = release_selection.strict(raw)
    if (raw != json.dumps(receipt, sort_keys=True, allow_nan=False).encode()
            or set(receipt) != {
                "schema", "stage", "release_path", "source_commit",
                "files", "directories", "archive_sha256",
                "inventory_sha256", "selected", "financial_effects",
                "provider_connections", "operational_acceptance",
                "layout", "artifact_digest"}
            or receipt["schema"] != "ATLAS_QD_D_RUNTIME_INSTALLATION_V1"
            or receipt["stage"] != "D_RUNTIME_LAYOUT_VERIFIED"
            or receipt["release_path"] != str(TARGET)
            or receipt["source_commit"] != SOURCE
            or receipt["archive_sha256"] != ARCHIVE_SHA
            or receipt["inventory_sha256"] != INVENTORY_SHA
            or type(receipt["files"]) is not list
            or len(receipt["files"]) != EXPECTED_FILES
            or type(receipt["directories"]) is not list
            or len(receipt["directories"]) != EXPECTED_DIRECTORIES
            or any(receipt[name] is not False for name in (
                "selected", "financial_effects", "provider_connections",
                "operational_acceptance"))):
        raise ValueError("R18_ONLY_EXACT_NONFINANCIAL_NATIVE_INSTALL_CAN_SELECT")
    artifact = hashlib.sha256(json.dumps(
        receipt["files"], sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode()).hexdigest()
    if receipt["artifact_digest"] != artifact:
        raise ValueError("R18_INSTALL_ARTIFACT_DIGEST_CHANGED")
    layout = receipt["layout"]
    if (type(layout) is not dict or layout != {
            "executable":str(TARGET/"python/python.exe"),
            "base":str(TARGET/"python/python.exe"),
            "prefix":str(TARGET/"python"),
            "base_prefix":str(TARGET/"python"),
            "stdlib":str(TARGET/"python/Lib"),
            "bits":64, "version":[3,12]}):
        raise ValueError("R18_SELECTED_INSTALLED_PYTHON_LAYOUT_REFUSED")
    rows = journal.splitlines()
    if (len(rows) != 2 or release_selection.strict(rows[0]) != {
            "schema":"ATLAS_R18_UNSELECTED_CODE_INSTALL_INTENT_V1",
            "source_commit":SOURCE, "archive_sha256":ARCHIVE_SHA,
            "target":str(TARGET), "financial_authority":False,
            "selection_allowed":False, "paper_start_authorized":False}):
        raise ValueError("R18_EXACT_TWO_STAGE_CODE_ONLY_JOURNAL_REQUIRED")
    receipt_sha = hashlib.sha256(raw).hexdigest()
    spec = release_selection.validate_spec({
        "schema":"QD_INSTALLED_RELEASE_REFERENCE_V1",
        "domain":"WINDOWS_LOCAL",
        "release":SOURCE, "root":str(TARGET),
        "receipt":str(RECEIPT),
        "receipt_sha256":receipt_sha, "artifact_digest":artifact,
    }, "WINDOWS_LOCAL")
    release_selection.validate_native_install_ack(spec, receipt, journal)
    op = hashlib.sha256(
        SELECTION_ACTION+R17_HEAD.encode()
        +receipt_sha.encode()+artifact.encode()).hexdigest()[:32]
    row = {
        "schema":"QD_RELEASE_SELECTION_RECEIPT_V1",
        "domain":"WINDOWS_LOCAL",
        "revision":RECORD_REVISION,
        "action":"SELECT",
        "operation":op,
        "previous":R17_HEAD,
        "selected":spec,
        "restores":None,
    }
    return row


def approval_digest(row):
    if (type(APPROVAL_PIN) is not str
            or re.fullmatch(r"[0-9a-f]{64}", APPROVAL_PIN) is None):
        raise ValueError("R18_NATIVE_SELECT_DISTINCT_USER_APPROVAL_REQUIRED")
    from scripts.release_selection import strict
    from scripts.volume_inspector.windows_output import current_sid
    decision = strict(_exact_bytes(APPROVAL, APPROVAL_PIN, max_bytes=4096))
    if (type(decision) is not dict or set(decision) != {
            "schema", "action", "scope", "operator_sid",
            "source_commit", "native_predecessor", "previous_head",
            "revision", "installed_receipt_sha256", "artifact_digest",
            "proposed_record_sha256", "selector_source_sha256",
            "one_shot", "financial_authority", "provider_access",
            "paper_accounts", "paper_start_authorized",
            "live_trading_authorized"}
            or decision["schema"] != "ATLAS_R18_CODE_ONLY_SELECT_USER_DECISION_V1"
            or decision["action"] != "ONE_SHOT_R18_NATIVE_CODE_ONLY_SELECT"
            or decision["scope"] != SCOPE
            or decision["operator_sid"] != current_sid()
            or decision["source_commit"] != SOURCE
            or decision["native_predecessor"] != R17_SOURCE
            or decision["previous_head"] != R17_HEAD
            or decision["revision"] != RECORD_REVISION
            or decision["installed_receipt_sha256"]
            != row["selected"]["receipt_sha256"]
            or decision["artifact_digest"] != row["selected"]["artifact_digest"]
            or decision["proposed_record_sha256"] != release_selection.digest(row)
            or decision["selector_source_sha256"] != approval_source_sha()
            or decision["one_shot"] is not True
            or any(decision[k] is not False for k in (
                "financial_authority", "provider_access", "paper_accounts",
                "paper_start_authorized", "live_trading_authorized"))):
        raise ValueError("R18_NATIVE_SELECTION_OPERATOR_APPROVAL_SCOPE_REFUSED")
    return APPROVAL_PIN


def clock_required(clock):
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,
    )
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R18_SELECTED_REAL_TWO_PEER_CLOCK_REQUIRED")
    clock.require_operational(CLOCK_IDENTITY)
    evidence = clock.evidence
    if (type(evidence.get("bound_ms")) is not int
            or not 0 <= evidence["bound_ms"] <= 1000
            or evidence.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
            or evidence.get("financial_authority") is not False):
        raise ValueError("R18_SELECTED_QUALIFIED_NTP_SOURCE_REFUSED")
    return True


def select(*, clock, approved=False):
    if approved is not True:
        raise ValueError("R18_SELECTION_EXACT_EXPLICIT_APPROVAL_REQUIRED")
    row = candidate()
    approval_digest(row)
    clock_required(clock)
    from scripts.install_version_safe_candidate import _qualify_native_clock_180s
    # Established monotonically timed 180-second two-peer NTP qualification.
    proof = _qualify_native_clock_180s(clock, CLOCK_IDENTITY)
    approval_digest(candidate())
    store = NativeSelectionStore(
        root=str(SELECTION_ROOT), native_root=list(SELECTOR_NATIVE))
    try:
        with NativeR17CpuBudget() as cpu, LowImpactEnvelope(
            check_every=32, pace_every=128) as envelope:
            cpu.pulse()
            with store.locked():
                current = store.records()
                if (len(current) != 16
                        or release_selection.digest(current[-1]) != R17_HEAD
                        or current[-1].get("selected", {}).get("release") != R17_SOURCE
                        or os.path.lexists(SELECTION_ROOT/"r0017.pending")
                        or os.path.lexists(SELECTION_ROOT/"r0017.json")):
                    raise ValueError("R18_SELECTED_NATIVE_16_RECORD_CHAIN_DRIFT")
                approval_digest(row)
                clock_required(clock)
                envelope.tick()
                with NativeInstalledReleaseVerifier().open(row["selected"]) as verified:
                    if (verified.get("source_commit") != SOURCE
                            or verified.get("artifact_digest") !=
                               row["selected"]["artifact_digest"]
                            or len(verified.get("files", [])) != EXPECTED_FILES
                            or len(verified.get("directories", []))
                               != EXPECTED_DIRECTORIES
                            or any(verified.get(flag) is not False for flag in (
                                "selected", "financial_effects",
                                "provider_connections", "operational_acceptance"))):
                        raise ValueError("R18_SELECTED_ORIGINAL_NATIVE_HANDLES_REFUSED")
                    cpu.pulse()
                    clock_required(clock)
                approval_digest(row)
                if (hashlib.sha256(_safe_bytes(RECEIPT, 10*1024*1024)).hexdigest()
                    != row["selected"]["receipt_sha256"]
                    or release_selection.strict(_safe_bytes(JOURNAL, 8192).splitlines()[-1])
                    != {"stage":"UNSELECTED_CODE_INSTALL_VERIFIED",
                        "receipt_sha256":row["selected"]["receipt_sha256"]}):
                    raise ValueError("R18_SELECTION_RECEIPT_OR_JOURNAL_DRIFT")
                original_accounts()
                clock_required(clock)
                cpu.pulse()
                store.publish(row)
                after = store.records()
                if (len(after) != 17 or after[:16] != current
                        or after[-1] != row):
                    raise ValueError("R18_SELECTOR_NATIVE_COMMIT_UNKNOWN_NO_RETRY")
    finally:
        store.close()
    return {
        "status":"R18_IMMUTABLE_CODE_ONLY_SELECTED",
        "native_revision":RECORD_REVISION,
        "source_commit":SOURCE,
        "selected_head":release_selection.digest(row),
        "clock_samples":proof["samples"],
        "financial_authority":False,
        "paper_start_authorized":False,
        "live_trading_authorized":False,
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    choice=parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--inspect",action="store_true")
    choice.add_argument("--execute-approved-code-only",action="store_true")
    parser.add_argument("--confirm-scope",default=None)
    args=parser.parse_args(argv)
    if args.inspect:
        row=candidate()
        return {
            "status":"R18_INSTALLED_RECEIPT_READY_FOR_SEPARATE_APPROVED_SELECTION",
            "proposed_record_sha256":release_selection.digest(row),
            "revision":RECORD_REVISION,"financial_authority":False,
            "paper_start_authorized":False,
        }
    if args.confirm_scope != SCOPE:
        raise ValueError("R18_SELECTION_EXPLICIT_FLAG_SCOPE_REQUIRED")
    approval_digest(candidate())
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,
    )
    clock=IndependentNtpClock(runtime_id=CLOCK_IDENTITY)
    try:
        return select(clock=clock,approved=True)
    finally:
        clock.revoke()


if __name__=="__main__":
    print(json.dumps(main(),sort_keys=True))
