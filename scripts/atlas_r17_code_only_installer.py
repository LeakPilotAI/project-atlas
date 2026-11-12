"""R17 exact frozen CODE-ONLY native installation; isolated from financial PAPER.

Read-only --inspect validates selected R16, pinned source/dependencies and a
fresh native release namespace. One-shot copy requires a separately recorded,
hash-pinned, exact Windows SID operator decision and independently qualified
two-peer UTC. No general "execute" authorizes installation. Installation
cannot select R17, create financial accounts, start PAPER or place orders.
Any uncertain partial native copy is permanently refused for automatic retry.
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
    HOST_ADMISSION_REFRESH_SECONDS,
    MAX_SECONDS,
    NTP_ADMISSION_REFRESH_SECONDS,
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
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    ARTIFACT_DIGEST as PREDECESSOR_ARTIFACT,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    R16_HEAD as PREDECESSOR_HEAD,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    R16_RECORD_SHA as PREDECESSOR_RECORD_SHA,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    selected_code,
)
from scripts.observation_runtime.native_install_host_admission import (
    require_code_install_host_ready,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)

ROOT = Path("D:/Work/Project Atlas")
DIAG = ROOT / "logs/diagnostics"
REVIEW_DIR = DIAG / "atlas-r17-source-only-20261111-r05"
REVIEW = REVIEW_DIR / "source-and-native-plan-review.json"
REVIEW_SHA = "eee3edfae944add14bca04e3ffcf80cbea971998f59f1a0d1418437617fc7a3f"
SOURCE = "7aeb2b279316b6db34c988a8e4204c104684d1a6"
ARCHIVE_SHA = "41899a0b10202646c1a9cb75f5cbf716d65bf91da8cfcdecc0cbf2503da55420"
INVENTORY_SHA = "9313c78a28ce3b3b26af67be154086a1e750b9527a8a03c7dc16da34d9edbd55"
ARCHIVE = REVIEW_DIR / "package/atlas-source.zip"
TARGET = Path("D:/AtlasRuntime/releases") / SOURCE
RECEIPT = DIAG / ("qd-unselected-release-" + SOURCE + ".json")
APPROVAL = DIAG / "atlas-r17-code-only-install-one-shot-approval.json"
APPROVAL_SHA256 = None  # Fresh R17 one-shot install approval, distinct from every prior release.
SCOPE = "INSTALL_EXACT_R17_UNSELECTED_CODE_ONLY_NO_FINANCIAL_START"
OPERATION = "APPROVE_ONE_R17_CODE_ONLY_NATIVE_INSTALL"
CLOCK_IDENTITY = "atlas-r17-code-only-install-" + SOURCE

EXPECTED_SOURCE_FILES = 1033
EXPECTED_DEPENDENCY_FILES = 9566
EXPECTED_TOTAL_FILES = 10599
EXPECTED_TOTAL_DIRECTORIES = 914
EXPECTED_TOTAL_BYTES = 264437110
REVIEW_MAX_BYTES = 8192


def source_digest_for_approval():
    """Bind a future approval to these EXACT installer bytes excluding its pin."""
    actual = Path(__file__).read_bytes()
    marker = (b"APPROVAL_SHA256 = None  # Fresh R17 one-shot install approval, "
              b"distinct from every prior release.")
    expression = (rb"(?m)^APPROVAL_SHA256 = (?:None|\"[0-9a-f]{64}\")  # Fresh R17 "
                  rb"one-shot install approval, distinct from every prior release\.")
    canonical, matches = re.subn(expression, marker, actual)
    if matches != 1:
        raise ValueError("R17_INSTALLER_APPROVAL_PIN_SOURCE_INVALID")
    return hashlib.sha256(canonical).hexdigest()


def validate_operator_decision(value, *, sid, installer_source_sha256):
    """Pure, exact single-scope check; no permissions outside CODE-only copy."""
    fields = {
        "schema", "operation", "scope", "operator_sid", "source_commit",
        "archive_sha256", "inventory_sha256", "dependency_inventory_sha256",
        "selected_predecessor_head", "selected_predecessor_record_sha256",
        "selected_predecessor_artifact_digest", "installer_source_sha256",
        "destination", "receipt", "one_shot", "selection_allowed",
        "financial_authority", "provider_access", "paper_accounts",
        "startup_authorized", "paper_orders_authorized",
        "live_orders_authorized",
    }
    if (type(value) is not dict or set(value) != fields
            or type(sid) is not str or not sid.startswith("S-1-")
            or type(installer_source_sha256) is not str
            or not re.fullmatch("[0-9a-f]{64}", installer_source_sha256)
            or value.get("schema") != "ATLAS_R17_CODE_ONLY_NATIVE_INSTALL_APPROVAL_V1"
            or value.get("operation") != OPERATION
            or value.get("scope") != SCOPE
            or value.get("operator_sid") != sid
            or value.get("source_commit") != SOURCE
            or value.get("archive_sha256") != ARCHIVE_SHA
            or value.get("inventory_sha256") != INVENTORY_SHA
            or value.get("dependency_inventory_sha256") != DEPENDENCY_INVENTORY_SHA256
            or value.get("selected_predecessor_head") != PREDECESSOR_HEAD
            or value.get("selected_predecessor_record_sha256") != PREDECESSOR_RECORD_SHA
            or value.get("selected_predecessor_artifact_digest") != PREDECESSOR_ARTIFACT
            or value.get("installer_source_sha256") != installer_source_sha256
            or value.get("destination") != str(TARGET)
            or value.get("receipt") != str(RECEIPT)
            or value.get("one_shot") is not True
            or any(value.get(name) is not False for name in (
                "selection_allowed", "financial_authority", "provider_access",
                "paper_accounts", "startup_authorized", "paper_orders_authorized",
                "live_orders_authorized",
            ))):
        raise ValueError("R17_EXACT_SID_BOUND_ONE_SHOT_CODE_INSTALL_APPROVAL_REQUIRED")
    return value


def require_separate_approval():
    if type(APPROVAL_SHA256) is not str or not re.fullmatch(
            "[0-9a-f]{64}", APPROVAL_SHA256):
        raise ValueError("R17_CODE_INSTALL_SEPARATE_PINNED_OPERATOR_DECISION_MISSING")
    from scripts.volume_inspector.windows_output import current_sid
    raw = _exact_bytes(APPROVAL, APPROVAL_SHA256, max_bytes=4096)
    from scripts.release_selection import strict
    return validate_operator_decision(
        strict(raw), sid=current_sid(),
        installer_source_sha256=source_digest_for_approval(),
    )


def require_selected_r16():
    current = selected_code()
    if (type(current) is not dict or current.get("selected_revision") != 15
            or current.get("selected_release") != "cadb3b5a163b31f9ee7bda32453a5983e809ccc0"
            or current.get("selected_native_head") != PREDECESSOR_HEAD
            or current.get("selected_native_record_sha256") != PREDECESSOR_RECORD_SHA
            or current.get("installed_artifact_digest") != PREDECESSOR_ARTIFACT):
        raise ValueError("R17_EXACT_NATIVE_R16_PREDECESSOR_REQUIRED")
    return True


def require_original_financial_roots_untouched():
    roots = inspect_two_lane_native_roots()
    if (roots.get("native_root_total") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True):
        raise ValueError("R17_ORIGINAL_TWELVE_FINANCIAL_ROOTS_NOT_EMPTY")
    return True


def require_create_only_target():
    installed, receipt = installation_target(SOURCE, RECEIPT)
    if installed != TARGET or receipt != RECEIPT:
        raise ValueError("R17_CREATE_ONLY_RELEASE_TARGET_REFUSED")
    return True


def inspect_prepared():
    """Read only: exact R16 selector + frozen source/native dependency plan."""
    require_selected_r16()
    require_create_only_target()
    require_original_financial_roots_untouched()
    review = json.loads(_exact_bytes(
        REVIEW, REVIEW_SHA, max_bytes=REVIEW_MAX_BYTES))
    # JSON lives inside diagnostics but must precisely match the frozen
    # SOURCE archive. It has NO approval effect.
    if (review.get("schema") != "ATLAS_R17_DURABLE_TWO_ACCOUNT_HANDOFF_SOURCE_ONLY_REVIEW_V1"
            or review.get("status") != "VERIFIED_NOT_INSTALLED_NOT_SELECTED"
            or review.get("source_commit") != SOURCE
            or review.get("source_archive_sha256") != ARCHIVE_SHA
            or review.get("selected_source_inventory_sha256") != INVENTORY_SHA
            or review.get("selected_tracked_source_files") != EXPECTED_SOURCE_FILES
            or review.get("pinned_dependency_files") != EXPECTED_DEPENDENCY_FILES
            or review.get("planned_native_total_files") != EXPECTED_TOTAL_FILES
            or review.get("planned_native_directories") != EXPECTED_TOTAL_DIRECTORIES
            or review.get("planned_native_bytes") != EXPECTED_TOTAL_BYTES
            or review.get("unoccupied_create_only_release_target") != str(TARGET)
            or review.get("original_selected_r16_release_and_roots_unchanged") is not True
            or any(review.get(k) is not False for k in (
                "native_code_installed", "native_code_selected",
                "installed_financial_issuer_present", "paper_start_authorized",
                "live_trading_authorized",
            ))):
        raise ValueError("R17_EXACT_FROZEN_SOURCE_REVIEW_REQUIRED")
    dependency_raw = _exact_bytes(
        DEPENDENCY, DEPENDENCY_RECEIPT_SHA256, max_bytes=16*1024*1024)
    prepared = prepare_install_inputs(
        archive=ARCHIVE, archive_sha256=ARCHIVE_SHA,
        source_commit=SOURCE, inventory_digest=INVENTORY_SHA,
        dependency_receipt=json.loads(dependency_raw),
        dependency_digest=DEPENDENCY_INVENTORY_SHA256, require_tracked=True,
    )
    if (len(prepared["runtime"]) != EXPECTED_SOURCE_FILES
            or len(prepared["dependencies"]) != EXPECTED_DEPENDENCY_FILES
            or len(prepared["names"]) != EXPECTED_TOTAL_FILES
            or len(prepared["directories"])+1 != EXPECTED_TOTAL_DIRECTORIES
            or prepared["total"] != EXPECTED_TOTAL_BYTES
            or prepared["verified"]["activation_approved"] is not False):
        raise ValueError("R17_EXACT_NATIVE_INSTALL_PLAN_CHANGED")
    require_create_only_target()
    require_selected_r16()
    return prepared


def inspect():
    prepared = inspect_prepared()
    return {
        "schema": "ATLAS_R17_CODE_ONLY_UNSELECTED_INSTALL_PREVIEW_V1",
        "status": "FROZEN_PLAN_VERIFIED_NOT_INSTALL_AUTHORIZATION",
        "source_commit": SOURCE,
        "archive_sha256": ARCHIVE_SHA,
        "selected_predecessor": "R16",
        "planned_source_files": len(prepared["runtime"]),
        "planned_native_files": len(prepared["names"]),
        "planned_bytes": prepared["total"],
        "native_target": str(TARGET),
        "separate_approval_pinned": False,
        "installed": False,
        "selection_allowed": False,
        "financial_authority": False,
        "paper_start_authorized": False,
        "live_orders_authorized": False,
    }


def _check_live_copy_admission(*, clock, envelope):
    envelope.tick()
    elapsed = envelope.monotonic()
    last_clock = getattr(envelope, "_r17_clock_last", None)
    if (last_clock is None or elapsed < last_clock
            or elapsed - last_clock >= NTP_ADMISSION_REFRESH_SECONDS):
        clock.require_operational(CLOCK_IDENTITY)
        envelope._r17_clock_last = elapsed
    last = getattr(envelope, "_r17_host_last", None)
    if (last is None or elapsed < last
            or elapsed - last >= HOST_ADMISSION_REFRESH_SECONDS):
        require_code_install_host_ready(TARGET.parent)
        require_selected_r16()
        require_original_financial_roots_untouched()
        require_separate_approval()
        envelope._r17_host_last = elapsed
    return True


def install(*, approved_execution=False, clock=None):
    """ONE approved native code copy; no fallback, retry, selection, or finance."""
    if approved_execution is not True:
        raise ValueError("R17_ONE_SHOT_CODE_INSTALL_EXPLICIT_EXECUTION_REQUIRED")
    require_separate_approval()
    require_selected_r16()
    require_create_only_target()
    require_original_financial_roots_untouched()
    require_code_install_host_ready(TARGET.parent)
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,
    )
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R17_GENUINE_TWO_PEER_NTP_CLOCK_REQUIRED")
    clock.require_operational(CLOCK_IDENTITY)
    from scripts.install_version_safe_candidate import _qualify_native_clock_180s
    _qualify_native_clock_180s(clock, CLOCK_IDENTITY)
    require_separate_approval()
    with LowImpactEnvelope(
        check_every=CHECK_EVERY, pace_every=PACE_EVERY,
        pause_seconds=PAUSE_SECONDS, max_seconds=MAX_SECONDS,
    ) as envelope:
        prepared = inspect_prepared()
        _check_live_copy_admission(clock=clock, envelope=envelope)
        prepared["started"] = time.monotonic()
        write_new_json(RECEIPT.with_suffix(".pending.jsonl"), {
            "schema": "ATLAS_R17_UNSELECTED_CODE_INSTALL_INTENT_V1",
            "source_commit": SOURCE, "archive_sha256": ARCHIVE_SHA,
            "target": str(TARGET), "financial_authority": False,
            "selection_allowed": False, "paper_start_authorized": False,
        })
        journal = RECEIPT.with_suffix(".pending.jsonl")

        def event(row):
            with journal.open("ab") as stream:
                stream.write(b"\n"+json.dumps(row,sort_keys=True).encode())
                stream.flush()
                os.fsync(stream.fileno())

        try:
            copied = _copy_prepared_code(
                destination=TARGET, archive_sha256=ARCHIVE_SHA,
                source_commit=SOURCE, prepared=prepared,
                admission=lambda: _check_live_copy_admission(
                    clock=clock, envelope=envelope))
            _check_live_copy_admission(clock=clock, envelope=envelope)
            receipt = {
                "schema": "ATLAS_QD_D_RUNTIME_INSTALLATION_V1",
                "stage": "D_RUNTIME_LAYOUT_VERIFIED",
                "release_path": str(TARGET), "source_commit": SOURCE,
                "files": copied["files"], "directories": copied["directories"],
                "archive_sha256": ARCHIVE_SHA, "inventory_sha256": INVENTORY_SHA,
                "selected": False, "financial_effects": False,
                "provider_connections": False, "operational_acceptance": False,
            }
            artifact_digest = hashlib.sha256(json.dumps(
                receipt["files"],sort_keys=True,separators=(",",":")).encode()).hexdigest()
            remaining = MAX_SECONDS - (envelope.monotonic()-envelope.started)
            if remaining <= 45:
                raise ValueError("R17_INSTALLED_CHILD_READBACK_DEADLINE")
            installed = installed_readback(
                TARGET, receipt, artifact_digest, timeout=min(120,remaining-10))
            _check_live_copy_admission(clock=clock, envelope=envelope)
            require_selected_r16()
            require_original_financial_roots_untouched()
            require_separate_approval()
            receipt.update(layout=installed["layout"],artifact_digest=artifact_digest)
            # Exact terminal ACK precedes final receipt for selection verifier.
            event({"stage":"UNSELECTED_CODE_INSTALL_VERIFIED",
                   "receipt_sha256":hashlib.sha256(json.dumps(
                       receipt,sort_keys=True,allow_nan=False).encode()).hexdigest()})
            write_new_json(RECEIPT,receipt)
            return receipt
        except BaseException:
            event({"stage":"REFUSED_PRESERVE_PARTIAL_NO_RETRY"})
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--execute-one-shot-code-install", action="store_true")
    parser.add_argument("--confirm-scope", default=None)
    args = parser.parse_args(argv)
    if args.inspect:
        if args.confirm_scope is not None:
            raise ValueError("R17_INSPECT_MIXED_INSTALL_SCOPE_REFUSED")
        return inspect()
    if args.confirm_scope != SCOPE:
        raise ValueError("R17_ONE_SHOT_EXACT_SCOPE_REQUIRED")
    require_separate_approval()  # BEFORE NTP, native target or process creation.
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,
    )
    clock = IndependentNtpClock(runtime_id=CLOCK_IDENTITY)
    try:
        receipt = install(approved_execution=True,clock=clock)
        return {"status":"R17_CODE_INSTALLED_UNSELECTED",
                "source_commit":receipt["source_commit"],
                "artifact_digest":receipt["artifact_digest"],
                "selection_allowed":False,"paper_start_authorized":False,
                "live_trading_authorized":False}
    finally:
        clock.revoke()


if __name__ == "__main__":
    print(json.dumps(main(),sort_keys=True))
