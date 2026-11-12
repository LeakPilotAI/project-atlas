"""R18 individually approved, create-only immutable code installation.

No selection, network data, account file, financial order, service, or PAPER
start. Requires original selected R17 Windows native chain, frozen R18 archive,
pinned local operator SID consent, independent two-peer UTC for 180 seconds,
CPU <=2 logical cores and genuine immutable installed-original-file readback.
Never retries a partial native install; failure evidence stays in place.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path

from scripts.atlas_r13_low_impact_installer import LowImpactEnvelope, _exact_bytes
from scripts.atlas_r14_low_impact_installer import (
    CHECK_EVERY,
    DEPENDENCY,
    DEPENDENCY_INVENTORY_SHA256,
    DEPENDENCY_RECEIPT_SHA256,
    MAX_SECONDS,
    PACE_EVERY,
    PAUSE_SECONDS,
)
from scripts.install_verified_release import (
    installation_target,
    installed_readback,
    write_new_json,
)
from scripts.native_install_candidate import _copy_prepared_code
from scripts.native_install_plan import prepare_install_inputs
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    ARTIFACT as R17_ARTIFACT,
)
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    HEAD as R17_HEAD,
)
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    SOURCE as R17_SOURCE,
)
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    require_selected_r17_nonfinancial,
)
from scripts.observation_runtime.atlas_r17_cpu_budget import NativeR17CpuBudget
from scripts.observation_runtime.native_install_host_admission import (
    require_code_install_host_ready,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)

ROOT = Path("D:/Work/Project Atlas")
DIAG = ROOT / "logs/diagnostics"
REVIEW = DIAG / "atlas-r18-source-only-20261112-r01"
SOURCE = "1389683b2a38a9accc0381c207d36abb2ce21e11"
ARCHIVE_SHA = "c162a0f9b5c608b70137a1e9415b4913151572e80678d0bfaf1f5dead6c771ef"
INVENTORY_SHA = "625363c611eb224cd813e1a7b07e769822b1ff0b0f8e7a37865b5545dfdf0874"
ARCHIVE = REVIEW / "package/atlas-source.zip"
REVIEW_FILE = REVIEW / "source-only-review.json"
REVIEW_SHA256 = "6d69c33eb197781ec0aaf556c3cd6a79cb87bb9bc60568d92a133dec63f2b656"
TARGET = Path("D:/AtlasRuntime/releases") / SOURCE
RECEIPT = DIAG / ("qd-unselected-release-" + SOURCE + ".json")
JOURNAL = RECEIPT.with_suffix(".pending.jsonl")
APPROVAL = DIAG / "atlas-r18-code-only-install-approved-20261112.json"
APPROVAL_PIN = "8dca8771acb280825914c8de5ed83404b4f10a966fcb20ecc1b7de556856307f"  # Distinct R18 one-time operator approval; source hash canonical.
SCOPE = "APPROVE_ONE_R18_CODE_ONLY_NATIVE_INSTALL_NO_FINANCIAL_START"
CLOCK_IDENTITY = "atlas-r18-code-only-native-install-" + SOURCE
EXPECTED_SOURCE_FILES = 1064
EXPECTED_DEPENDENCY_FILES = 9566
EXPECTED_FILES = 10630
EXPECTED_DIRECTORIES = 914
EXPECTED_BYTES = 264790106
REVIEW_SCHEMA = "ATLAS_R18_TRACKED_CODE_ONLY_SUCCESSOR_REVIEW_V1"


def source_hash():
    data = Path(__file__).read_bytes()
    pattern = (
        rb'(?m)^APPROVAL_PIN = (?:None|"[0-9a-f]{64}")'
        rb'  # Distinct R18 one-time operator approval; source hash canonical\.'
    )
    canonical, hits = re.subn(pattern, (
        b"APPROVAL_PIN = None  # Distinct R18 one-time operator approval; "
        b"source hash canonical."), data)
    if hits != 1:
        raise ValueError("R18_INSTALL_APPROVAL_SOURCE_CANONICAL_REFUSED")
    return hashlib.sha256(canonical).hexdigest()


def original_predecessor():
    selected = require_selected_r17_nonfinancial()
    if (selected.get("release") != R17_SOURCE
            or selected.get("artifact_digest") != R17_ARTIFACT):
        raise ValueError("R18_ORIGINAL_SELECTED_R17_CHANGED")
    from scripts.observation_runtime.personal_version_safe_release_clock import (
        SELECTOR_NATIVE,
    )
    from scripts.release_selection import digest
    from scripts.release_selection_store import NativeSelectionStore
    store = NativeSelectionStore(
        root="D:\\AtlasRuntime\\selection", native_root=list(SELECTOR_NATIVE))
    try:
        with store.locked():
            records = store.records()
        if (len(records) != 16 or records[-1].get("revision") != 16
                or digest(records[-1]) != R17_HEAD
                or records[-1].get("selected") != selected):
            raise ValueError("R18_ORIGINAL_16_RECORD_SELECTED_CHAIN_REFUSED")
    finally:
        store.close()
    return selected


def original_accounts():
    roots = inspect_two_lane_native_roots()
    if (roots.get("native_root_total") != 12
            or roots.get("native_root_ids_verified") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True):
        raise ValueError("R18_CODE_INSTALL_ORIGINAL_ACCOUNT_ROOTS_CHANGED")
    return True


def frozen_prepared():
    original_predecessor()
    original_accounts()
    target, receipt = installation_target(SOURCE, RECEIPT)
    if target != TARGET or receipt != RECEIPT:
        raise ValueError("R18_EXACT_NEW_CREATE_ONLY_TARGET_REQUIRED")
    record = json.loads(_exact_bytes(
        REVIEW_FILE,
        REVIEW_SHA256,
        max_bytes=8192))
    if (record.get("schema") != REVIEW_SCHEMA
            or record.get("status") != "TRACKED_SOURCE_AND_PINNED_DEPENDENCY_VERIFIED_ONLY"
            or record.get("source_commit") != SOURCE
            or record.get("source_archive_sha256") != ARCHIVE_SHA
            or record.get("source_inventory_sha256") != INVENTORY_SHA
            or record.get("planned_source_files") != EXPECTED_SOURCE_FILES
            or record.get("planned_dependency_files") != EXPECTED_DEPENDENCY_FILES
            or record.get("planned_native_files") != EXPECTED_FILES
            or record.get("planned_native_directories") != EXPECTED_DIRECTORIES
            or record.get("planned_native_bytes") != EXPECTED_BYTES
            or record.get("predecessor_r17") != R17_SOURCE
            or record.get("code_only_native_target") != str(TARGET)
            or record.get("pinned_dependency_receipt_sha256")
            != DEPENDENCY_RECEIPT_SHA256
            or record.get("pinned_dependency_inventory_sha256")
            != DEPENDENCY_INVENTORY_SHA256
            or record.get("selected_r17_unchanged") is not True
            or record.get("original_financial_roots_untouched") is not True
            or any(record.get(flag) is not False for flag in (
                "immutable_release_installed", "new_release_selected",
                "new_operator_install_approved", "financial_issuer_accepted",
                "native_paper_accounts_incepted", "paper_start_authorized",
                "live_trading_authorized"))):
        raise ValueError("R18_FROZEN_EXACT_CODE_ONLY_REVIEW_REFUSED")
    raw = _exact_bytes(
        DEPENDENCY, DEPENDENCY_RECEIPT_SHA256, max_bytes=16*1024*1024)
    prepared = prepare_install_inputs(
        archive=ARCHIVE, archive_sha256=ARCHIVE_SHA,
        source_commit=SOURCE, inventory_digest=INVENTORY_SHA,
        dependency_receipt=json.loads(raw),
        dependency_digest=DEPENDENCY_INVENTORY_SHA256, require_tracked=True)
    if (len(prepared["runtime"]) != EXPECTED_SOURCE_FILES
            or len(prepared["dependencies"]) != EXPECTED_DEPENDENCY_FILES
            or len(prepared["names"]) != EXPECTED_FILES
            or len(prepared["directories"])+1 != EXPECTED_DIRECTORIES
            or prepared["total"] != EXPECTED_BYTES
            or prepared["verified"].get("activation_approved") is not False):
        raise ValueError("R18_NATIVE_FROZEN_CODE_INSTALL_PLAN_REFUSED")
    return prepared


def approval_digest():
    if (type(APPROVAL_PIN) is not str
            or re.fullmatch(r"[0-9a-f]{64}", APPROVAL_PIN) is None):
        raise ValueError("R18_CODE_INSTALL_INDEPENDENT_USER_APPROVAL_REQUIRED")
    from scripts.release_selection import strict
    from scripts.volume_inspector.windows_output import current_sid
    value = strict(_exact_bytes(APPROVAL, APPROVAL_PIN, max_bytes=4096))
    if (type(value) is not dict
            or set(value) != {
                "schema", "action", "scope", "operator_sid", "source_commit",
                "source_archive_sha256", "source_inventory_sha256",
                "dependency_inventory_sha256", "review_schema",
                "native_selected_predecessor", "native_predecessor_head",
                "installer_source_sha256", "destination", "receipt",
                "one_shot", "selection_allowed", "financial_authority",
                "provider_access", "paper_accounts", "paper_start_authorized",
                "live_trading_authorized"}
            or value["schema"] != "ATLAS_R18_CODE_ONLY_INSTALL_USER_DECISION_V1"
            or value["action"] != "ONE_SHOT_R18_NATIVE_CODE_ONLY_INSTALL"
            or value["scope"] != SCOPE
            or value["operator_sid"] != current_sid()
            or value["source_commit"] != SOURCE
            or value["source_archive_sha256"] != ARCHIVE_SHA
            or value["source_inventory_sha256"] != INVENTORY_SHA
            or value["dependency_inventory_sha256"] != DEPENDENCY_INVENTORY_SHA256
            or value["review_schema"] != REVIEW_SCHEMA
            or value["native_selected_predecessor"] != R17_SOURCE
            or value["native_predecessor_head"] != R17_HEAD
            or value["installer_source_sha256"] != source_hash()
            or value["destination"] != str(TARGET)
            or value["receipt"] != str(RECEIPT)
            or value["one_shot"] is not True
            or any(value[key] is not False for key in (
                "selection_allowed", "financial_authority", "provider_access",
                "paper_accounts", "paper_start_authorized",
                "live_trading_authorized"))):
        raise ValueError("R18_CODE_INSTALL_EXACT_USER_SID_SCOPE_REFUSED")
    return APPROVAL_PIN


def clock_required(clock):
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,
    )
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R18_REAL_TWO_PEER_NTP_CLOCK_REQUIRED")
    clock.require_operational(CLOCK_IDENTITY)
    evidence = clock.evidence
    if (evidence.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
            or type(evidence.get("bound_ms")) is not int
            or not 0 <= evidence["bound_ms"] <= 1000
            or evidence.get("financial_authority") is not False):
        raise ValueError("R18_NATIVE_CLOCK_NOT_SOURCE_QUALIFIED")
    return True


def install(*, clock, approved=False):
    if approved is not True:
        raise ValueError("R18_OPERATOR_ONE_TIME_CODE_ONLY_INSTALL_EXECUTION_REQUIRED")
    approval_digest()
    prepared = frozen_prepared()
    require_code_install_host_ready(TARGET.parent)
    clock_required(clock)
    from scripts.install_version_safe_candidate import _qualify_native_clock_180s
    proof = _qualify_native_clock_180s(clock, CLOCK_IDENTITY)
    approval_digest()
    original_predecessor()
    original_accounts()
    with NativeR17CpuBudget() as cpu, LowImpactEnvelope(
        check_every=CHECK_EVERY, pace_every=PACE_EVERY,
        pause_seconds=PAUSE_SECONDS, max_seconds=MAX_SECONDS,
    ) as envelope:
        last = None
        def admission():
            nonlocal last
            cpu.pulse()
            envelope.tick()
            elapsed = envelope.monotonic()
            if (last is None or elapsed - last >= 30):
                approval_digest()
                clock_required(clock)
                require_code_install_host_ready(TARGET.parent)
                original_predecessor()
                original_accounts()
                last = elapsed
            return True
        admission()
        prepared["started"] = time.monotonic()
        write_new_json(JOURNAL, {
            "schema": "ATLAS_R18_UNSELECTED_CODE_INSTALL_INTENT_V1",
            "source_commit": SOURCE, "archive_sha256": ARCHIVE_SHA,
            "target": str(TARGET), "financial_authority": False,
            "selection_allowed": False, "paper_start_authorized": False,
        })
        def event(value):
            with JOURNAL.open("ab") as stream:
                stream.write(b"\n"+json.dumps(
                    value, sort_keys=True, allow_nan=False).encode())
                stream.flush()
                os.fsync(stream.fileno())
        try:
            copied = _copy_prepared_code(
                destination=TARGET, archive_sha256=ARCHIVE_SHA,
                source_commit=SOURCE, prepared=prepared,
                admission=admission)
            admission()
            if (len(copied["files"]) != EXPECTED_FILES
                    or len(copied["directories"]) != EXPECTED_DIRECTORIES):
                raise ValueError("R18_COPY_COMPLETE_ORIGINAL_INVENTORY_REFUSED")
            receipt = {
                "schema":"ATLAS_QD_D_RUNTIME_INSTALLATION_V1",
                "stage":"D_RUNTIME_LAYOUT_VERIFIED",
                "release_path":str(TARGET),
                "source_commit":SOURCE,
                "files":copied["files"], "directories":copied["directories"],
                "archive_sha256":ARCHIVE_SHA, "inventory_sha256":INVENTORY_SHA,
                "selected":False, "financial_effects":False,
                "provider_connections":False, "operational_acceptance":False,
            }
            artifact = hashlib.sha256(json.dumps(
                receipt["files"], sort_keys=True,
                separators=(",", ":"), allow_nan=False).encode()).hexdigest()
            deadline = MAX_SECONDS - (envelope.monotonic()-envelope.started)
            if deadline < 50:
                raise ValueError("R18_NATIVE_INSTALLED_READBACK_DEADLINE")
            result = installed_readback(
                TARGET, receipt, artifact, timeout=min(180, deadline-15))
            receipt.update(layout=result["layout"], artifact_digest=artifact)
            approval_digest()
            admission()
            # Keep journal exactly TWO rows for independent successor handoff.
            expected_raw = json.dumps(receipt, sort_keys=True,
                                      allow_nan=False).encode()
            event({"stage":"UNSELECTED_CODE_INSTALL_VERIFIED",
                   "receipt_sha256":hashlib.sha256(expected_raw).hexdigest()})
            write_new_json(RECEIPT,receipt)
            return {
                "status":"R18_CODE_ONLY_NATIVE_INSTALL_VERIFIED_UNSELECTED",
                "source_commit":SOURCE,"receipt_sha256":
                    hashlib.sha256(RECEIPT.read_bytes()).hexdigest(),
                "artifact_digest":artifact,"native_files":len(copied["files"]),
                "native_directories":len(copied["directories"]),
                "clock_samples":proof["samples"],
                "financial_authority":False,
                "paper_start_authorized":False,
                "live_orders_authorized":False,
            }
        except BaseException:
            # Stage/target remains for investigation. Never retry this operation.
            event({"stage":"REFUSED_PRESERVE_PARTIAL_NO_RETRY"})
            raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect",action="store_true")
    mode.add_argument("--execute-approved-code-only",action="store_true")
    parser.add_argument("--confirm-scope",default=None)
    args=parser.parse_args(argv)
    if args.inspect:
        prepared=frozen_prepared()
        return {
            "status":"FROZEN_R18_CODE_ONLY_PLAN_NOT_NATIVE_INSTALL",
            "source_commit":SOURCE,"native_files":len(prepared["names"]),
            "approval_pin_present":type(APPROVAL_PIN) is str,
            "financial_authority":False,"paper_start_authorized":False,
        }
    if args.confirm_scope != SCOPE:
        raise ValueError("R18_INSTALL_SCOPE_FLAG_REQUIRED")
    approval_digest()
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,
    )
    clock=IndependentNtpClock(runtime_id=CLOCK_IDENTITY)
    try:
        return install(clock=clock, approved=True)
    finally:
        clock.revoke()


if __name__=="__main__":
    print(json.dumps(main(),sort_keys=True))
