"""Locally visible human consent for one exact R23 native recovery and selection.

This is NOT the failed original installer: it preserves original refusal,
re-verifies 7,910 original files, and creates ONLY missing code files under
the separately approved R23 recovery controller. It does not commission
financial accounts, provider access, PAPER or LIVE orders.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import tempfile
from pathlib import Path

from scripts import atlas_r23_code_only_select as selector
from scripts import atlas_r23_local_operator_consent as local
from scripts import atlas_r23_native_recovery as recovery

EXPECTED_RECOVERY_SOURCE_SHA256 = (
    "dfd00fdc341581bb5d61930d67bed66c6c0a85721b268e1b2adb3343f7058d26"
)
SOURCE_ROOT = Path("D:/Work/Project Atlas")


def review_recovery():
    if (
        os.name != "nt"
        or Path(recovery.__file__).resolve()
        != SOURCE_ROOT / "scripts/atlas_r23_native_recovery.py"
        or recovery.APPROVAL_PIN is not None
        or recovery.source_hash() != EXPECTED_RECOVERY_SOURCE_SHA256
        or os.path.lexists(recovery.APPROVAL)
    ):
        raise ValueError("R23_RECOVERY_EXACT_NEW_UNAPPROVED_SOURCE_REQUIRED")
    from scripts.observation_runtime.atlas_r17_cpu_budget import NativeR17CpuBudget

    with NativeR17CpuBudget() as cpu:
        cpu.pulse()
        state = recovery.main(["--inspect"])
        cpu.pulse()
    if (
        state.get("status")
        != "ORIGINAL_PARTIAL_NATIVE_AUDIT_READY_FOR_SEPARATE_RECONCILIATION"
        or state.get("old_native_verified_files") != 7910
        or state.get("only_new_files_planned") != 2853
        or state.get("approval_pin_present") is not False
        or state.get("financial_authority") is not False
        or state.get("paper_start_authorized") is not False
    ):
        raise ValueError("R23_RECOVERY_EXACT_READONLY_PLAN_REFUSED")
    return {
        "status": "R23_ORIGINAL_REFUSAL_PRESERVED_READY_FOR_DISTINCT_RECOVERY_DECISION",
        "recovery_scope": recovery.SCOPE,
        "source_commit": recovery.SOURCE,
        "recovery_controller_source_sha256": EXPECTED_RECOVERY_SOURCE_SHA256,
        "audit_sha256": recovery.AUDIT_SHA,
        "existing_native_verified_files": 7910,
        "new_files_create_only": 2853,
        "final_planned_files": 10763,
        "selection_requires_separate_scope": local.SELECTION_SCOPE,
        "financial_authority": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }


def decision_record(audit):
    from scripts.volume_inspector.windows_output import current_sid

    predecessor = recovery.original_selected_r21()
    return {
        "schema": "ATLAS_R23_NATIVE_PARTIAL_CODE_RECOVERY_APPROVAL_V1",
        "scope": recovery.SCOPE,
        "action": "ONE_SHOT_VERIFY_EXISTING_AND_CREATE_MISSING",
        "operator_sid": current_sid(),
        "installer_source_sha256": EXPECTED_RECOVERY_SOURCE_SHA256,
        "release_source_commit": recovery.SOURCE,
        "original_native_refusal_sha256": audit["original_refused_journal_sha256"],
        "read_only_native_audit_sha256": recovery.AUDIT_SHA,
        "native_prefix_files": 7910,
        "remaining_create_only_files": 2853,
        "selected_predecessor_release": predecessor["release"],
        "selected_predecessor_artifact_digest": predecessor["artifact_digest"],
        "target_native_root": str(recovery.TARGET),
        "original_pending_journal": str(recovery.JOURNAL),
        "final_release_receipt": str(recovery.RECEIPT),
        "separate_recovery_journal": str(recovery.RECOVERY_JOURNAL),
        "separate_recovery_receipt": str(recovery.RECOVERY_RECEIPT),
        "one_shot": True,
        "financial_authority": False,
        "provider_access": False,
        "simulated_accounts": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }


def pin_after_distinct_human_recovery_approval():
    local.require_visible_local_console()
    review_recovery()
    _, original_audit = recovery._readonly_preflight()
    decision = decision_record(original_audit)
    raw = json.dumps(decision, sort_keys=True, allow_nan=False).encode()
    decision_sha256 = hashlib.sha256(raw).hexdigest()
    marker = (
        b"APPROVAL_PIN = None  # Distinct source/SDDL/partial audit-bound "
        b"recovery approval."
    )
    updated = (
        b'APPROVAL_PIN = "' + decision_sha256.encode("ascii")
        + b'"  # Distinct source/SDDL/partial audit-bound recovery approval.'
    )
    path = Path(recovery.__file__)
    original = path.read_bytes()
    pinned_source = local._pin_single_exact_assignment(
        original, marker, updated, "R23_EXACT_RECOVERY_SOURCE_PIN_MARKER_REQUIRED",
    )
    # Decision is written once only. Any partial stage is a preserved refusal.
    with recovery.APPROVAL.open("xb") as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".atlas-r23-recovery-human-",
            suffix=".tmp", dir=path.parent, delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(pinned_source)
            output.flush()
            os.fsync(output.fileno())
        if path.read_bytes() != original:
            raise ValueError("R23_RECOVERY_CONTROLLER_CHANGED_DURING_APPROVAL")
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    importlib.reload(recovery)
    if (
        recovery.source_hash() != EXPECTED_RECOVERY_SOURCE_SHA256
        or recovery.approval_digest() != decision_sha256
    ):
        raise ValueError("R23_SEPARATE_RECOVERY_APPROVAL_READBACK_REFUSED")
    return decision_sha256


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--review", action="store_true")
    modes.add_argument("--recover-and-select", action="store_true")
    args = parser.parse_args(argv)
    if args.review:
        print(json.dumps(review_recovery(), sort_keys=True, indent=2))
        return 0
    local.require_visible_local_console()
    print("Inspecting R23 original refusal and 7,910 native files. No writes yet.",
          flush=True)
    review = review_recovery()
    print(json.dumps(review, sort_keys=True, indent=2), flush=True)
    print("\nThis decision is ONLY to RECOVER the existing R23 CODE COPY.",
          flush=True)
    print("No simulated accounts, no PAPER, no live orders.", flush=True)
    typed = input("\nType the exact RECOVERY scope above (or press Enter to decline): ")
    if typed != recovery.SCOPE:
        print("R23 recovery remains UNAPPROVED. Existing files preserved.")
        return 2
    local.require_visible_local_console()
    sha = pin_after_distinct_human_recovery_approval()
    print("R23_DISTINCT_LOCAL_RECOVERY_APPROVAL_PIN=" + sha, flush=True)
    result = recovery.main([
        "--execute-approved-recovery", "--confirm-scope", recovery.SCOPE,
    ])
    print(json.dumps(result, sort_keys=True), flush=True)
    if (
        result.get("status")
        != "R23_ORIGINAL_NATIVE_RECOVERY_FULL_CODE_ONLY_VERIFIED_UNSELECTED"
        or result.get("native_installed_files") != 10763
        or result.get("original_native_files_revalidated") != 7910
        or result.get("new_native_create_only_files") != 2853
        or result.get("financial_authority") is not False
        or result.get("paper_start_authorized") is not False
        or result.get("live_trading_authorized") is not False
    ):
        raise ValueError("R23_ORIGINAL_RECOVERY_INCOMPLETE_NO_SELECTION")
    local.require_visible_local_console()
    second = local.selection_review()
    print("\nR23 recovery verified. SELECTION is a SECOND, independent decision.",
          flush=True)
    print(json.dumps(second, sort_keys=True, indent=2), flush=True)
    typed_second = input(
        "\nType the exact distinct SELECTION scope above, "
        "or press Enter to leave R21 selected: "
    )
    if typed_second != local.SELECTION_SCOPE:
        print("R23 recovered but remains unselected; R21 retained.",
              flush=True)
        return 2
    local.require_visible_local_console()
    pin = local.pin_selection_after_human_action()
    print("R23_DISTINCT_LOCAL_SELECTION_APPROVAL_PIN=" + pin, flush=True)
    selected = selector.main([
        "--execute-approved-code-only", "--confirm-scope", local.SELECTION_SCOPE,
    ])
    print(json.dumps(selected, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
