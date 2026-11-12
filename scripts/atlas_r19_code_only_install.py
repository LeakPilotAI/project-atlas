"""R19 one-time original Windows CODE-ONLY install, successor to selected R18.

Source-only installer to *create* one exact new immutable R19 release. No
selector publication, activation, simulated account, real money, provider,
service, desktop Start, trading or financial orders. Refuse if target/receipt
already exists. Require separately operator-approved SID and source-bound
receipt, 180-second two-peer NTP quality, <=2 CPUs, installed-file native
readback and all twelve original financial namespaces empty.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path

from scripts import release_selection
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
from scripts.atlas_r19_source_review import (
    R18_ARTIFACT,
    R18_HEAD,
    R18_SOURCE,
)
from scripts.atlas_r19_source_review import (
    SCHEMA as REVIEW_SCHEMA,
)
from scripts.install_verified_release import (
    installation_target,
    installed_readback,
    write_new_json,
)
from scripts.native_install_candidate import _copy_prepared_code
from scripts.native_install_plan import prepare_install_inputs
from scripts.observation_runtime.atlas_r17_cpu_budget import NativeR17CpuBudget
from scripts.observation_runtime.native_install_host_admission import (
    require_code_install_host_ready,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    SELECTOR_NATIVE,
)
from scripts.release_selection import NativeInstalledReleaseVerifier
from scripts.release_selection_store import NativeSelectionStore

ROOT = Path("D:/Work/Project Atlas")
DIAG = ROOT / "logs/diagnostics"
REVIEW = DIAG / "atlas-r19-source-only-20261112-r02"
ARCHIVE = REVIEW / "package/atlas-source.zip"
REVIEW_FILE = REVIEW / "source-only-review.json"
SOURCE = "3de954bcfd8533bfaaf32f62745d912a24a71cfc"
ARCHIVE_SHA = "55d7da9e24b1c20fe1b9a72ea25efb2d6ce0bdd00199f2c60cb8c94ae55d6ed8"
INVENTORY_SHA = "5b1f8e9b5369bf048c7680dcc686ebf738e6f5b69c022cf6f19e106cb1e6e2d9"
TARGET = Path("D:/AtlasRuntime/releases") / SOURCE
RECEIPT = DIAG / ("qd-unselected-release-" + SOURCE + ".json")
JOURNAL = RECEIPT.with_suffix(".pending.jsonl")
APPROVAL = DIAG / "atlas-r19-r02-code-only-install-approved-20261112.json"
APPROVAL_PIN = None  # Distinct R19 one-time operator approval; source hash canonical.
SCOPE = "APPROVE_ONE_R19_CODE_ONLY_NATIVE_INSTALL_NO_FINANCIAL_START"
CLOCK_IDENTITY = "atlas-r19-code-only-native-install-" + SOURCE
EXPECTED_SOURCE_FILES = 1091
EXPECTED_DEPENDENCY_FILES = 9566
EXPECTED_FILES = 10657
EXPECTED_DIRECTORIES = 914
EXPECTED_BYTES = 265175967


def source_hash():
    data = Path(__file__).read_bytes()
    pattern = (rb'(?m)^APPROVAL_PIN = (?:None|"[0-9a-f]{64}")'
               rb'  # Distinct R19 one-time operator approval; source hash canonical\.')
    canonical, hits = re.subn(
        pattern, b"APPROVAL_PIN = None  # Distinct R19 one-time operator approval; "
                 b"source hash canonical.", data)
    if hits != 1:
        raise ValueError("R19_INSTALL_APPROVAL_SOURCE_CANONICAL_REFUSED")
    return hashlib.sha256(canonical).hexdigest()


def original_selected_r18(*, verify_files=False):
    store = NativeSelectionStore(root=r"D:\AtlasRuntime\selection",
                                 native_root=list(SELECTOR_NATIVE))
    try:
        with store.locked():
            records = store.records()
            if (len(records) != 17 or records[-1].get("revision") != 17
                    or release_selection.digest(records[-1]) != R18_HEAD):
                raise ValueError("R19_ORIGINAL_SELECTED_R18_SEVENTEEN_RECORDS_REQUIRED")
            spec = release_selection.validate_spec(
                records[-1].get("selected"), "WINDOWS_LOCAL")
            if (spec["release"] != R18_SOURCE
                    or spec["artifact_digest"] != R18_ARTIFACT):
                raise ValueError("R19_ORIGINAL_R18_SOURCE_AND_ARTIFACT_REQUIRED")
            if verify_files:
                with NativeInstalledReleaseVerifier().open(spec) as native:
                    if (native.get("source_commit") != R18_SOURCE
                            or native.get("artifact_digest") != R18_ARTIFACT
                            or any(native.get(k) is not False for k in (
                                "selected", "financial_effects",
                                "provider_connections", "operational_acceptance"))):
                        raise ValueError("R19_GENUINE_INSTALLED_R18_FILES_REQUIRED")
            return spec
    finally:
        store.close()


def original_accounts():
    roots = inspect_two_lane_native_roots()
    if (roots.get("native_root_total") != 12
            or roots.get("native_root_ids_verified") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True):
        raise ValueError("R19_ORIGINAL_FINANCIAL_ROOTS_MUST_STAY_EMPTY")
    return True


def frozen_prepared():
    original_selected_r18(verify_files=True)
    original_accounts()
    target, receipt = installation_target(SOURCE, RECEIPT)
    if target != TARGET or receipt != RECEIPT:
        raise ValueError("R19_CREATE_ONLY_INSTALLATION_TARGET_REFUSED")
    raw = _exact_bytes(REVIEW_FILE,
                       "62b01f35082d03d94bbfc5c472d9fa478875c4f97639cf32b7cbb617a0fb7aa3",
                       max_bytes=8192)
    review = release_selection.strict(raw)
    if (review.get("schema") != REVIEW_SCHEMA
            or review.get("status") != "TRACKED_SOURCE_AND_PINNED_DEPENDENCY_VERIFIED_ONLY"
            or review.get("selected_r18_source") != R18_SOURCE
            or review.get("selected_r18_native_head") != R18_HEAD
            or review.get("source_commit") != SOURCE
            or review.get("source_archive_sha256") != ARCHIVE_SHA
            or review.get("source_inventory_sha256") != INVENTORY_SHA
            or review.get("pinned_dependency_receipt_sha256") != DEPENDENCY_RECEIPT_SHA256
            or review.get("pinned_dependency_inventory_sha256") != DEPENDENCY_INVENTORY_SHA256
            or review.get("code_only_native_target") != str(TARGET)
            or review.get("planned_native_files") != EXPECTED_FILES
            or review.get("planned_native_directories") != EXPECTED_DIRECTORIES
            or review.get("planned_native_bytes") != EXPECTED_BYTES
            or review.get("planned_source_files") != EXPECTED_SOURCE_FILES
            or review.get("planned_dependency_files") != EXPECTED_DEPENDENCY_FILES
            or review.get("selected_r18_unchanged") is not True
            or review.get("original_financial_roots_untouched") is not True
            or any(review.get(k) is not False for k in (
                "native_code_installed", "new_release_selected",
                "financial_activation_accepted", "paper_accounts_opened",
                "market_feed_entitlements_accepted", "paper_start_authorized",
                "live_trading_authorized"))):
        raise ValueError("R19_FROZEN_EXACT_TRACKED_REVIEW_REQUIRED")
    dependencies = _exact_bytes(DEPENDENCY, DEPENDENCY_RECEIPT_SHA256,
                                max_bytes=16*1024*1024)
    prepared = prepare_install_inputs(
        archive=ARCHIVE, archive_sha256=ARCHIVE_SHA, source_commit=SOURCE,
        inventory_digest=INVENTORY_SHA,
        dependency_receipt=json.loads(dependencies),
        dependency_digest=DEPENDENCY_INVENTORY_SHA256,
        require_tracked=True)
    if (len(prepared["runtime"]) != EXPECTED_SOURCE_FILES
            or len(prepared["dependencies"]) != EXPECTED_DEPENDENCY_FILES
            or len(prepared["names"]) != EXPECTED_FILES
            or len(prepared["directories"])+1 != EXPECTED_DIRECTORIES
            or prepared["total"] != EXPECTED_BYTES
            or prepared["verified"].get("activation_approved") is not False):
        raise ValueError("R19_SOURCE_DEPENDENCY_NATIVE_PLAN_MISMATCH")
    return prepared


def approval_digest():
    if type(APPROVAL_PIN) is not str or re.fullmatch("[0-9a-f]{64}", APPROVAL_PIN) is None:
        raise ValueError("R19_DISTINCT_NATIVE_INSTALL_USER_APPROVAL_REQUIRED")
    from scripts.volume_inspector.windows_output import current_sid
    decision = release_selection.strict(_exact_bytes(
        APPROVAL, APPROVAL_PIN, max_bytes=4096))
    if (type(decision) is not dict or set(decision) != {
            "schema", "action", "scope", "operator_sid", "source_commit",
            "source_archive_sha256", "source_inventory_sha256",
            "dependency_inventory_sha256", "review_schema",
            "native_selected_predecessor", "native_predecessor_head",
            "installer_source_sha256", "destination", "receipt", "one_shot",
            "selection_allowed", "financial_authority", "provider_access",
            "paper_accounts", "paper_start_authorized", "live_trading_authorized"}
            or decision["schema"] != "ATLAS_R19_CODE_ONLY_INSTALL_USER_DECISION_V1"
            or decision["action"] != "ONE_SHOT_R19_NATIVE_CODE_ONLY_INSTALL"
            or decision["scope"] != SCOPE
            or decision["operator_sid"] != current_sid()
            or decision["source_commit"] != SOURCE
            or decision["source_archive_sha256"] != ARCHIVE_SHA
            or decision["source_inventory_sha256"] != INVENTORY_SHA
            or decision["dependency_inventory_sha256"] != DEPENDENCY_INVENTORY_SHA256
            or decision["review_schema"] != REVIEW_SCHEMA
            or decision["native_selected_predecessor"] != R18_SOURCE
            or decision["native_predecessor_head"] != R18_HEAD
            or decision["installer_source_sha256"] != source_hash()
            or decision["destination"] != str(TARGET)
            or decision["receipt"] != str(RECEIPT)
            or decision["one_shot"] is not True
            or any(decision[k] is not False for k in (
                "selection_allowed", "financial_authority", "provider_access",
                "paper_accounts", "paper_start_authorized", "live_trading_authorized"))):
        raise ValueError("R19_ONE_TIME_SID_SCOPED_APPROVAL_REFUSED")
    return APPROVAL_PIN


def clock_required(clock):
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,
    )
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R19_ORIGINAL_TWO_PEER_NTP_REQUIRED")
    clock.require_operational(CLOCK_IDENTITY)
    evidence = clock.evidence
    if (evidence.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
            or type(evidence.get("bound_ms")) is not int
            or not 0 <= evidence["bound_ms"] <= 1000
            or evidence.get("financial_authority") is not False):
        raise ValueError("R19_CLOCK_SOURCE_QUALITY_REFUSED")
    return True


def install(*, clock, approved=False):
    if approved is not True:
        raise ValueError("R19_OPERATOR_APPROVED_CODE_ONLY_INSTALL_REQUIRED")
    approval_digest()
    prepared = frozen_prepared()
    require_code_install_host_ready(TARGET.parent)
    clock_required(clock)
    from scripts.install_version_safe_candidate import _qualify_native_clock_180s
    proof = _qualify_native_clock_180s(clock, CLOCK_IDENTITY)
    approval_digest()
    original_selected_r18()
    original_accounts()
    with NativeR17CpuBudget() as cpu, LowImpactEnvelope(
        check_every=CHECK_EVERY, pace_every=PACE_EVERY,
        pause_seconds=PAUSE_SECONDS, max_seconds=MAX_SECONDS
    ) as envelope:
        last = None
        def admission():
            nonlocal last
            cpu.pulse()
            envelope.tick()
            now = envelope.monotonic()
            if last is None or now-last >= 30:
                approval_digest()
                clock_required(clock)
                require_code_install_host_ready(TARGET.parent)
                original_selected_r18()
                original_accounts()
                last = now
            return True
        admission()
        prepared["started"] = time.monotonic()
        write_new_json(JOURNAL, {
            "schema": "ATLAS_R19_UNSELECTED_CODE_INSTALL_INTENT_V1",
            "source_commit": SOURCE, "archive_sha256": ARCHIVE_SHA,
            "target": str(TARGET), "financial_authority": False,
            "selection_allowed": False, "paper_start_authorized": False,
        })
        def event(row):
            with JOURNAL.open("ab") as stream:
                stream.write(b"\n"+json.dumps(row, sort_keys=True, allow_nan=False).encode())
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
                raise ValueError("R19_NATIVE_INSTALL_INVENTORY_INCOMPLETE")
            receipt = {
                "schema": "ATLAS_QD_D_RUNTIME_INSTALLATION_V1",
                "stage": "D_RUNTIME_LAYOUT_VERIFIED",
                "release_path": str(TARGET),
                "source_commit": SOURCE,
                "files": copied["files"], "directories": copied["directories"],
                "archive_sha256": ARCHIVE_SHA,
                "inventory_sha256": INVENTORY_SHA,
                "selected": False, "financial_effects": False,
                "provider_connections": False, "operational_acceptance": False,
            }
            artifact = hashlib.sha256(json.dumps(
                receipt["files"], sort_keys=True,
                separators=(",", ":"), allow_nan=False).encode()).hexdigest()
            deadline = MAX_SECONDS-(envelope.monotonic()-envelope.started)
            if deadline < 50:
                raise ValueError("R19_INSTALLED_ORIGINAL_READBACK_DEADLINE")
            readback = installed_readback(
                TARGET, receipt, artifact, timeout=min(180, deadline-15))
            receipt.update(layout=readback["layout"], artifact_digest=artifact)
            approval_digest()
            admission()
            raw = json.dumps(receipt, sort_keys=True, allow_nan=False).encode()
            event({"stage": "UNSELECTED_CODE_INSTALL_VERIFIED",
                   "receipt_sha256": hashlib.sha256(raw).hexdigest()})
            write_new_json(RECEIPT, receipt)
            return {
                "status": "R19_CODE_ONLY_NATIVE_INSTALL_VERIFIED_UNSELECTED",
                "source_commit": SOURCE,
                "receipt_sha256": hashlib.sha256(RECEIPT.read_bytes()).hexdigest(),
                "artifact_digest": artifact,
                "native_files": len(copied["files"]),
                "native_directories": len(copied["directories"]),
                "clock_samples": proof["samples"],
                "financial_authority": False,
                "paper_start_authorized": False,
                "live_orders_authorized": False,
            }
        except BaseException:
            event({"stage": "REFUSED_PRESERVE_PARTIAL_NO_RETRY"})
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--inspect", action="store_true")
    modes.add_argument("--execute-approved-code-only", action="store_true")
    parser.add_argument("--confirm-scope", default=None)
    args = parser.parse_args(argv)
    if args.inspect:
        prepared = frozen_prepared()
        return {
            "status": "FROZEN_R19_CODE_ONLY_PLAN_NOT_INSTALLED",
            "source_commit": SOURCE,
            "native_files": len(prepared["names"]),
            "approval_pin_present": type(APPROVAL_PIN) is str,
            "financial_authority": False,
            "paper_start_authorized": False,
        }
    if args.confirm_scope != SCOPE:
        raise ValueError("R19_CODE_INSTALL_EXACT_APPROVAL_SCOPE_FLAG_REQUIRED")
    approval_digest()
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,
    )
    clock = IndependentNtpClock(runtime_id=CLOCK_IDENTITY)
    try:
        return install(clock=clock, approved=True)
    finally:
        clock.revoke()


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
