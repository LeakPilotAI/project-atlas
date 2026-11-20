"""Original-native R21 CODE ONLY installer, successor to installed selected R20.

Strict create-only release and receipt, genuine original R20 native selector,
all 12 source financial roots empty, pinned source/deps review, distinct
SID/source-scoped one-time operator authorization, 180s independent two-peer
UTC, <=2 CPU execution and full installed Windows handle readback. No
selection, original financial inception, provider, PAPER orders or live money.

Partial/uncertain original native copy MUST NOT be retried or overwritten.
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
from scripts.atlas_r20_code_only_install import SOURCE as R20_SOURCE
from scripts.atlas_r21_source_review import (
    REVIEW,
    selected_r20,
)
from scripts.atlas_r21_source_review import (
    SCHEMA as REVIEW_SCHEMA,
)
from scripts.install_verified_release import (
    installation_target,
    installed_readback,
    write_new_json,
)
from scripts.native_install_candidate import _copy_prepared_code
from scripts.native_install_plan import prepare_install_inputs
from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
from scripts.observation_runtime.atlas_r17_cpu_budget import NativeR17CpuBudget
from scripts.observation_runtime.native_install_host_admission import (
    require_code_install_host_ready,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)

ROOT = Path("D:/Work/Project Atlas")
DIAG = ROOT / "logs/diagnostics"
ARCHIVE = REVIEW / "package/atlas-source.zip"
REVIEW_FILE = REVIEW / "source-only-review.json"
SOURCE = "119dd8626da32e74bd7f86db9de1c1a8fd2c20ac"
ARCHIVE_SHA = "bb58601ac09de2f0e638ecc1aaf72d39179b295f227f09cdbd4bb1b75cf53e3b"
INVENTORY_SHA = "0dd6daf1cb11b13fd7e01669614bfed57aa5a907ebd82621f46850de60118c78"
REVIEW_SHA = "85e8c5813bc884d45c72f1fedaccb5bf8a3ab2cd3ca371a2881a3368f23b8dd9"
TARGET = Path("D:/AtlasRuntime/releases") / SOURCE
RECEIPT = DIAG / ("qd-unselected-release-" + SOURCE + ".json")
JOURNAL = RECEIPT.with_suffix(".pending.jsonl")
APPROVAL = DIAG / "atlas-r21-code-only-install-approved-20261113.json"
APPROVAL_PIN = "a6a433ab45d2b1277e05e50dc85b0b35171303cdaa1b41a0b200c216bfa81bbf"  # Original distinct R21 operator approval; canonical source hash.
SCOPE = "APPROVE_ONE_R21_CODE_ONLY_NATIVE_INSTALL_NO_FINANCIAL_START"
CLOCK_IDENTITY = "atlas-r21-code-only-install-" + SOURCE
EXPECTED_SOURCE_FILES = 1165
EXPECTED_DEPENDENCY_FILES = 9566
EXPECTED_FILES = 10731
EXPECTED_DIRECTORIES = 915
EXPECTED_BYTES = 265741912
DECISION_SCHEMA = "ATLAS_R21_CODE_ONLY_INSTALL_USER_DECISION_V1"


def source_hash():
    data = Path(__file__).read_bytes()
    canonical, hits = re.subn(
        rb"(?m)^APPROVAL_PIN = (?:None|\"[0-9a-f]{64}\")"
        rb"  # Original distinct R21 operator approval; canonical source hash\.",
        b"APPROVAL_PIN = None  # Original distinct R21 operator approval; canonical source hash.",
        data,
    )
    if hits != 1:
        raise ValueError("R21_INSTALL_APPROVAL_SOURCE_CANONICAL_REFUSED")
    return hashlib.sha256(canonical).hexdigest()


def original_accounts():
    roots = inspect_two_lane_native_roots()
    if (
        roots.get("native_root_total") != 12
        or roots.get("native_root_ids_verified") != 12
        or roots.get("all_twelve_distinct_and_empty") is not True
    ):
        raise ValueError("R21_ORIGINAL_FINANCIAL_ROOTS_MUST_STAY_EMPTY")
    return True


def original_selected_r20():
    spec = selected_r20()
    if spec["release"] != R20_SOURCE:
        raise ValueError("R21_SELECTED_ORIGINAL_R20_CHANGED")
    return spec


def frozen_prepared():
    original_selected_r20()
    original_accounts()
    target, receipt = installation_target(SOURCE, RECEIPT)
    if target != TARGET or receipt != RECEIPT or os.path.lexists(JOURNAL):
        raise ValueError("R21_ORIGINAL_CREATE_ONLY_DESTINATION_OR_PARTIAL_REFUSED")
    raw = _exact_bytes(REVIEW_FILE, REVIEW_SHA, max_bytes=24_576)
    review = json.loads(raw)
    if (
        type(review) is not dict
        or review.get("schema") != REVIEW_SCHEMA
        or review.get("status") != "AUDITED_SOURCE_ONLY_CODE_CANDIDATE_NOT_INSTALLED"
        or review.get("source_commit") != SOURCE
        or review.get("selected_predecessor") != R20_SOURCE
        or review.get("selected_predecessor_revision") != 19
        or review.get("selected_predecessor_artifact_digest")
        != original_selected_r20()["artifact_digest"]
        or review.get("source_archive_sha256") != ARCHIVE_SHA
        or review.get("source_inventory_sha256") != INVENTORY_SHA
        or review.get("pinned_dependency_receipt_sha256") != DEPENDENCY_RECEIPT_SHA256
        or review.get("pinned_dependency_inventory_sha256")
        != DEPENDENCY_INVENTORY_SHA256
        or review.get("code_only_native_target") != str(TARGET)
        or review.get("planned_native_files") != EXPECTED_FILES
        or review.get("planned_native_directories") != EXPECTED_DIRECTORIES
        or review.get("planned_native_bytes") != EXPECTED_BYTES
        or review.get("planned_source_files") != EXPECTED_SOURCE_FILES
        or review.get("planned_dependency_files") != EXPECTED_DEPENDENCY_FILES
        or review.get("required_operator_approval")
        != "R21_SEPARATE_EXPLICIT_APPROVAL_NOT_CREATED"
        or review.get("selected_r20_unchanged") is not True
        or review.get("original_native_financial_roots_untouched") is not True
        or any(review.get(k) is not False for k in (
            "native_code_installed", "new_release_selected",
            "original_operator_activation", "source_rights_accepted",
            "financial_inception_verified", "paper_start_authorized",
            "live_trading_authorized",
        ))
    ):
        raise ValueError("R21_EXACT_FROZEN_SOURCE_REVIEW_REQUIRED")
    dependencies = _exact_bytes(
        DEPENDENCY, DEPENDENCY_RECEIPT_SHA256,
        max_bytes=16*1024*1024,
    )
    prepared = prepare_install_inputs(
        archive=ARCHIVE,
        archive_sha256=ARCHIVE_SHA,
        source_commit=SOURCE,
        inventory_digest=INVENTORY_SHA,
        dependency_receipt=json.loads(dependencies),
        dependency_digest=DEPENDENCY_INVENTORY_SHA256,
        require_tracked=True,
    )
    if (
        len(prepared["runtime"]) != EXPECTED_SOURCE_FILES
        or len(prepared["dependencies"]) != EXPECTED_DEPENDENCY_FILES
        or len(prepared["names"]) != EXPECTED_FILES
        or len(prepared["directories"])+1 != EXPECTED_DIRECTORIES
        or prepared["total"] != EXPECTED_BYTES
        or prepared["verified"].get("activation_approved") is not False
    ):
        raise ValueError("R21_ORIGINAL_PACKAGED_SOURCE_DEPENDENCY_MISMATCH")
    return prepared


def approval_digest():
    if type(APPROVAL_PIN) is not str or re.fullmatch(r"[0-9a-f]{64}", APPROVAL_PIN) is None:
        raise ValueError("R21_DISTINCT_SID_OPERATOR_DECISION_REQUIRED")
    from scripts.volume_inspector.windows_output import current_sid

    decision = json.loads(_exact_bytes(APPROVAL, APPROVAL_PIN, max_bytes=4096))
    if (
        type(decision) is not dict
        or set(decision) != {
            "schema", "scope", "action", "operator_sid", "source_commit",
            "source_archive_sha256", "source_inventory_sha256",
            "dependency_inventory_sha256", "native_predecessor",
            "native_predecessor_artifact_digest", "installer_source_sha256",
            "destination", "receipt", "one_shot", "financial_authority",
            "provider_access", "paper_accounts", "paper_start_authorized",
            "live_trading_authorized",
        }
        or decision["schema"] != DECISION_SCHEMA
        or decision["scope"] != SCOPE
        or decision["action"] != "ONE_SHOT_R21_NATIVE_CODE_ONLY_INSTALL"
        or decision["operator_sid"] != current_sid()
        or decision["source_commit"] != SOURCE
        or decision["source_archive_sha256"] != ARCHIVE_SHA
        or decision["source_inventory_sha256"] != INVENTORY_SHA
        or decision["dependency_inventory_sha256"] != DEPENDENCY_INVENTORY_SHA256
        or decision["native_predecessor"] != R20_SOURCE
        or decision["native_predecessor_artifact_digest"]
        != original_selected_r20()["artifact_digest"]
        or decision["installer_source_sha256"] != source_hash()
        or decision["destination"] != str(TARGET)
        or decision["receipt"] != str(RECEIPT)
        or decision["one_shot"] is not True
        or any(decision[k] is not False for k in (
            "financial_authority", "provider_access", "paper_accounts",
            "paper_start_authorized", "live_trading_authorized",
        ))
    ):
        raise ValueError("R21_DISTINCT_OPERATOR_APPROVAL_SCOPE_REFUSED")
    return APPROVAL_PIN


def clock_required(clock):
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R21_ORIGINAL_INDEPENDENT_NTP_CLOCK_REQUIRED")
    clock.require_operational(CLOCK_IDENTITY)
    evidence = clock.evidence
    if (
        evidence.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
        or type(evidence.get("bound_ms")) is not int
        or not 0 <= evidence["bound_ms"] <= 1000
        or evidence.get("financial_authority") is not False
    ):
        raise ValueError("R21_ORIGINAL_TWO_PEER_NTP_QUALITY_REFUSED")
    return True


def install(*, clock, approved=False):
    if approved is not True:
        raise ValueError("R21_CODE_ONLY_INSTALL_OPERATOR_APPROVAL_REQUIRED")
    approval_digest()
    prepared = frozen_prepared()
    require_code_install_host_ready(TARGET.parent)
    clock_required(clock)
    from scripts.install_version_safe_candidate import _qualify_native_clock_180s
    proof = _qualify_native_clock_180s(clock, CLOCK_IDENTITY)
    approval_digest()
    original_selected_r20()
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
            now = envelope.monotonic()
            if last is None or now - last >= 30:
                approval_digest()
                clock_required(clock)
                require_code_install_host_ready(TARGET.parent)
                original_selected_r20()
                original_accounts()
                last = now
            return True

        admission()
        prepared["started"] = time.monotonic()
        write_new_json(JOURNAL, {
            "schema": "ATLAS_R21_UNSELECTED_CODE_INSTALL_INTENT_V1",
            "source_commit": SOURCE,
            "archive_sha256": ARCHIVE_SHA,
            "target": str(TARGET),
            "financial_authority": False,
            "selection_allowed": False,
            "paper_start_authorized": False,
        })

        def event(row):
            with JOURNAL.open("ab") as stream:
                stream.write(b"\n" + json.dumps(
                    row, sort_keys=True, allow_nan=False,
                ).encode())
                stream.flush()
                os.fsync(stream.fileno())

        try:
            copied = _copy_prepared_code(
                destination=TARGET, archive_sha256=ARCHIVE_SHA,
                source_commit=SOURCE, prepared=prepared,
                admission=admission,
            )
            admission()
            if (
                len(copied["files"]) != EXPECTED_FILES
                or len(copied["directories"]) != EXPECTED_DIRECTORIES
            ):
                raise ValueError("R21_NATIVE_ORIGINAL_COPY_INVENTORY_INCOMPLETE")
            receipt = {
                "schema": "ATLAS_QD_D_RUNTIME_INSTALLATION_V1",
                "stage": "D_RUNTIME_LAYOUT_VERIFIED",
                "release_path": str(TARGET),
                "source_commit": SOURCE,
                "files": copied["files"],
                "directories": copied["directories"],
                "archive_sha256": ARCHIVE_SHA,
                "inventory_sha256": INVENTORY_SHA,
                "selected": False,
                "financial_effects": False,
                "provider_connections": False,
                "operational_acceptance": False,
            }
            artifact = hashlib.sha256(json.dumps(
                receipt["files"], sort_keys=True, separators=(",", ":"),
                allow_nan=False,
            ).encode()).hexdigest()
            deadline = MAX_SECONDS - (
                envelope.monotonic() - envelope.started
            )
            if deadline < 50:
                raise ValueError("R21_NATIVE_ORIGINAL_READBACK_DEADLINE")
            readback = installed_readback(
                TARGET, receipt, artifact,
                timeout=min(180, deadline-15),
            )
            receipt.update(layout=readback["layout"], artifact_digest=artifact)
            approval_digest()
            admission()
            raw = json.dumps(receipt, sort_keys=True, allow_nan=False).encode()
            event({
                "stage": "UNSELECTED_CODE_INSTALL_VERIFIED",
                "receipt_sha256": hashlib.sha256(raw).hexdigest(),
            })
            write_new_json(RECEIPT, receipt)
            return {
                "status": "R21_CODE_ONLY_NATIVE_INSTALL_VERIFIED_UNSELECTED",
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
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--execute-approved-code-only", action="store_true")
    parser.add_argument("--confirm-scope", default=None)
    args = parser.parse_args(argv)
    if args.inspect:
        plan = frozen_prepared()
        return {
            "status": "R21_FULL_NATIVE_CODE_ONLY_FROZEN_PLAN_NOT_INSTALLED",
            "source_commit": SOURCE,
            "native_files": len(plan["names"]),
            "approval_pin_present": type(APPROVAL_PIN) is str,
            "financial_authority": False,
            "paper_start_authorized": False,
        }
    if args.confirm_scope != SCOPE:
        raise ValueError("R21_INSTALL_EXACT_OPERATOR_SCOPE_FLAG_REQUIRED")
    approval_digest()
    clock = IndependentNtpClock(runtime_id=CLOCK_IDENTITY)
    try:
        return install(clock=clock, approved=True)
    finally:
        clock.revoke()


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
