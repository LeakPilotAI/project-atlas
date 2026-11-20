"""R14 unselected CODE-ONLY native install adapter; no install approval.

Pins the fresh R14 source-only archive, previous native Python dependency
identity and exact R12 selector. This module cannot copy by default and has
no install CLI. Historic R13 one-shot permission is not reusable here.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

from scripts.atlas_r13_low_impact_installer import (
    LowImpactEnvelope, _exact_bytes, _selector_unchanged,
)
from scripts.install_verified_release import (
    installation_target, installed_readback, write_new_json,
)
from scripts.native_install_candidate import _copy_prepared_code
from scripts.native_install_plan import prepare_install_inputs
from scripts.observation_runtime.native_install_host_admission import (
    require_code_install_host_ready,
)

ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT / "logs/diagnostics"
SOURCE = "7ff9d3dba2eabe110f843c13efac49464805de2a"
ARCHIVE = DIAG / "atlas-r14-source-only-20261110-r01/atlas-source.zip"
ARCHIVE_SHA256 = "22e4d00cb61c56d0b298c059e597937696df8deeca25c7ec6b38ec5ff01e192a"
INVENTORY_SHA256 = "bf7c37a4e424a7947b46636df06fc860253ee46abc038aa80b496e09b9d09367"
DEPENDENCY = DIAG / "qd-d-runtime-coordination-installation-20261028.json"
DEPENDENCY_RECEIPT_SHA256 = "b1363f4514d3cdce4a1914e79d14842ece94136ed5d035ea195b4883da99a7a0"
DEPENDENCY_INVENTORY_SHA256 = "93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91"
REVIEW = DIAG / "atlas-r14-source-only-20261110-r01/source-preflight-not-approval.json"
REVIEW_SHA256 = "91c181a823c4dc20fd65067dce69356159c8beb202c4d416f68dd267c298f99d"
DESTINATION = Path("D:/AtlasRuntime/releases") / SOURCE
RECEIPT = DIAG / ("qd-unselected-release-" + SOURCE + ".json")
PREVIOUS_R13 = Path("D:/AtlasRuntime/releases/c7dfb85665bbcd5ba4494c33365d4dff8ea92b12")
PREVIOUS_R13_JOURNAL = DIAG / "qd-unselected-release-c7dfb85665bbcd5ba4494c33365d4dff8ea92b12.pending.jsonl"
PREVIOUS_R13_JOURNAL_SHA256 = "6ab85e9feb4842ea80d26008165df7741497de248959488ce651e2f20a2992ec"
PREVIOUS_R13_FINAL = DIAG / "qd-unselected-release-c7dfb85665bbcd5ba4494c33365d4dff8ea92b12.json"
APPROVAL = DIAG / "atlas-r14-code-only-install-one-shot-approval.json"
APPROVAL_SHA256 = None  # R14 one-shot CODE-ONLY approval consumed after verified native install on 2026-11-10; never retry.
CHECK_EVERY = 32
PACE_EVERY = 128
PAUSE_SECONDS = 0.06
MAX_SECONDS = 500
NTP_ADMISSION_REFRESH_SECONDS = 1.0
HOST_ADMISSION_REFRESH_SECONDS = 10.0


def _old_r13_refusal_preserved():
    if (not PREVIOUS_R13.is_dir() or PREVIOUS_R13.is_symlink()
            or PREVIOUS_R13.is_junction()
            or os.path.lexists(PREVIOUS_R13_FINAL)):
        raise ValueError("R14_OLD_FAILED_R13_EVIDENCE_REQUIRED")
    raw = _exact_bytes(PREVIOUS_R13_JOURNAL,
                       PREVIOUS_R13_JOURNAL_SHA256, max_bytes=4096)
    rows = raw.splitlines()
    if len(rows) != 2 or json.loads(rows[-1]).get("stage") != "REFUSED_PRESERVE_PARTIAL_NO_RETRY":
        raise ValueError("R14_OLD_R13_REFUSAL_JOURNAL_REQUIRED")


def _require_empty_target():
    _selector_unchanged()
    _old_r13_refusal_preserved()
    if any(os.path.lexists(path) for path in (
            DESTINATION, RECEIPT, RECEIPT.with_suffix(".pending.jsonl"))):
        raise ValueError("R14_CREATE_ONLY_TARGET_ALREADY_USED")
    if installation_target(SOURCE, RECEIPT) != (DESTINATION, RECEIPT):
        raise ValueError("R14_CREATE_ONLY_TARGET_NOT_PINNED")
    return True


def _review_pinned():
    review = json.loads(_exact_bytes(REVIEW, REVIEW_SHA256, max_bytes=8192))
    expected = {
        "schema": "ATLAS_R14_FROZEN_SOURCE_ONLY_PREFLIGHT_V1",
        "status": "SOURCE_ARCHIVE_AND_NATIVE_PLAN_VERIFIED_NOT_INSTALL_AUTHORIZATION",
        "frozen_source_commit": SOURCE,
        "source_archive_sha256": ARCHIVE_SHA256,
        "selected_source_inventory_sha256": INVENTORY_SHA256,
        "dependency_receipt_sha256": DEPENDENCY_RECEIPT_SHA256,
        "dependency_file_inventory_sha256": DEPENDENCY_INVENTORY_SHA256,
        "selected_source_files": 953,
        "native_python_dependency_files": 9566,
        "planned_native_files": 10519,
        "planned_native_directories": 912,
        "planned_native_bytes": 263456250,
        "future_new_native_release_target": str(DESTINATION),
        "old_failed_r13": PREVIOUS_R13.name,
        "source_artifact_dir": str(ARCHIVE.parent),
    }
    if type(review) is not dict or any(review.get(k) != v for k, v in expected.items()):
        raise ValueError("R14_EXACT_SOURCE_REVIEW_REFUSED")
    for key in ("selection_allowed", "installation_authorized", "installed",
                "financial_authority", "paper_orders_authorized",
                "live_orders_authorized", "provider_access"):
        if review.get(key) is not False:
            raise ValueError("R14_SOURCE_REVIEW_SCOPE_REFUSED")
    if set(review) != set(expected) | {
            "selection_allowed", "installation_authorized", "installed",
            "financial_authority", "paper_orders_authorized",
            "live_orders_authorized", "provider_access"}:
        raise ValueError("R14_UNREVIEWED_SOURCE_REVIEW_FIELDS")
    return review


def prepare_readonly():
    """Validate only already reviewed exact inputs and a NEW release target."""
    _require_empty_target()
    _review_pinned()
    dependency = json.loads(_exact_bytes(
        DEPENDENCY, DEPENDENCY_RECEIPT_SHA256, max_bytes=16*1024**2))
    _exact_bytes(ARCHIVE, ARCHIVE_SHA256, max_bytes=16*1024**2)
    prepared = prepare_install_inputs(
        archive=ARCHIVE, archive_sha256=ARCHIVE_SHA256, source_commit=SOURCE,
        inventory_digest=INVENTORY_SHA256, dependency_receipt=dependency,
        dependency_digest=DEPENDENCY_INVENTORY_SHA256, require_tracked=True)
    if (len(prepared["runtime"]) != 953 or len(prepared["dependencies"]) != 9566
            or len(prepared["names"]) != 10519
            or len(prepared["directories"]) + 1 != 912
            or prepared["total"] != 263456250):
        raise ValueError("R14_NATIVE_INSTALL_PLAN_CHANGED")
    _require_empty_target()
    return prepared


def inspect():
    """Read-only preflight, no install or provider/account access."""
    with LowImpactEnvelope(check_every=CHECK_EVERY, pace_every=PACE_EVERY,
                           pause_seconds=PAUSE_SECONDS, max_seconds=MAX_SECONDS) as guard:
        prepared = prepare_readonly()
        guard.tick()
    return {
        "schema": "ATLAS_R14_LOW_IMPACT_UNSELECTED_CODE_INSTALL_PREVIEW_V1",
        "status": "NATIVE_LAYOUT_AND_INPUTS_VERIFIED_NOT_INSTALL_APPROVAL",
        "source": SOURCE, "source_files": len(prepared["runtime"]),
        "dependency_files": len(prepared["dependencies"]),
        "planned_files": len(prepared["names"]), "planned_bytes": prepared["total"],
        "idle_priority_required": True, "check_every": CHECK_EVERY,
        "pace_every": PACE_EVERY, "pause_seconds": PAUSE_SECONDS,
        "installation_authorized": False, "installed": False,
        "selection_allowed": False, "paper_orders_authorized": False,
        "live_orders_authorized": False,
    }


def _require_separate_consent():
    if type(APPROVAL_SHA256) is not str or not re.fullmatch("[0-9a-f]{64}", APPROVAL_SHA256):
        raise ValueError("R14_SEPARATE_ONE_SHOT_CODE_INSTALL_APPROVAL_NOT_YET_GRANTED")
    record = json.loads(_exact_bytes(APPROVAL, APPROVAL_SHA256, max_bytes=4096))
    if (type(record) is not dict
            or set(record) != {
                "schema", "decision", "source", "archive_sha256",
                "dependency_sha256", "operator_sid", "one_shot",
                "selection_allowed", "financial_authority", "provider_access",
                "startup_authorized"}
            or record["schema"] != "ATLAS_R14_CODE_ONLY_INSTALL_APPROVAL_V1"
            or record["decision"] != "APPROVE_ONE_UNSELECTED_CODE_COPY"
            or record["source"] != SOURCE
            or record["archive_sha256"] != ARCHIVE_SHA256
            or record["dependency_sha256"] != DEPENDENCY_INVENTORY_SHA256
            or record["one_shot"] is not True
            or any(record[key] is not False for key in (
                "selection_allowed", "financial_authority",
                "provider_access", "startup_authorized"))):
        raise ValueError("R14_UNSELECTED_CODE_ONLY_APPROVAL_SCOPE_REFUSED")
    from scripts.volume_inspector.windows_output import current_sid
    if record["operator_sid"] != current_sid():
        raise ValueError("R14_INSTALL_OPERATOR_SID_REFUSED")
    return record


def _native_admission(clock, identity, guard):
    """Bound EVERY I/O admission; attest NTP at 32 calls or 1s, whichever first.

    An already qualified two-peer clock must remain valid throughout the copy.
    Avoid the timestamp-issuance cache cost of sampling on every 64KiB I/O,
    but never skip a clock check merely because a slow disk delays 32 calls.
    Final financial/selection authority remains entirely disabled.
    """
    guard.tick()  # Every native admission still checks the 500s deadline.
    now = guard.monotonic()
    last = getattr(guard, "last_ntp_admission", None)
    if (last is None or now < last
            or now - last >= NTP_ADMISSION_REFRESH_SECONDS
            or guard.checks % CHECK_EVERY == 0):
        clock.require_operational(identity)
        guard.last_ntp_admission = guard.monotonic()
    last_host = getattr(guard, "last_host_admission", None)
    if (last_host is None or now < last_host
            or now - last_host >= HOST_ADMISSION_REFRESH_SECONDS):
        # A game started during the copy or lost RAM/disk headroom must
        # fail closed, preserving any partial release with no automatic retry.
        require_code_install_host_ready(DESTINATION.parent)
        guard.last_host_admission = guard.monotonic()
    return True


def _remaining_installed_readback_timeout(guard):
    """Leave headroom for final checks; never overrun the 500-second gate."""
    guard.tick()
    left = guard.max_seconds - (guard.monotonic() - guard.started)
    if left <= 35:
        raise ValueError("R14_INSTALLED_READBACK_TIME_BUDGET_REFUSED_PRESERVE_PARTIAL")
    return min(120, left - 5)


def install(*, execute_approved=False, clock=None):
    """Install ONLY after new exact, separately pinned one-shot consent."""
    if execute_approved is not True:
        raise ValueError("R14_EXPLICIT_CODE_INSTALL_EXECUTION_REQUIRED")
    _require_separate_consent()  # Hard blocks everything in this source revision.
    # Check genuine host resources BEFORE spending 180 seconds on clock
    # qualification, and do not attempt bulk copy during NBA 2K27 gameplay.
    require_code_install_host_ready(DESTINATION.parent)
    from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R14_REAL_TWO_PEER_INDEPENDENT_CLOCK_REQUIRED")
    identity = "r14-code-only-" + SOURCE
    clock.require_operational(identity)
    from scripts.install_version_safe_candidate import _qualify_native_clock_180s
    _qualify_native_clock_180s(clock, identity)
    _require_separate_consent()
    require_code_install_host_ready(DESTINATION.parent)
    with LowImpactEnvelope(check_every=CHECK_EVERY, pace_every=PACE_EVERY,
                           pause_seconds=PAUSE_SECONDS, max_seconds=MAX_SECONDS) as guard:
        prepared = prepare_readonly()
        guard.tick()
        # Source hashing can take time; independently attest the live clock
        # again immediately before first create-only journal/write.
        clock.require_operational(identity)
        prepared["started"] = time.monotonic()
        def admit():
            return _native_admission(clock, identity, guard)
        admit()
        journal = RECEIPT.with_suffix(".pending.jsonl")
        write_new_json(journal, {
            "schema": "ATLAS_R14_UNSELECTED_LOW_IMPACT_CODE_INSTALL_INTENT_V1",
            "source_commit": SOURCE, "archive_sha256": ARCHIVE_SHA256,
            "destination": str(DESTINATION), "selection_allowed": False,
            "financial_authority": False, "provider_access": False,
        })
        def event(value):
            with journal.open("ab") as stream:
                stream.write(b"\n" + json.dumps(value, sort_keys=True).encode())
                stream.flush()
                os.fsync(stream.fileno())
        try:
            copied = _copy_prepared_code(
                destination=DESTINATION, archive_sha256=ARCHIVE_SHA256,
                source_commit=SOURCE, prepared=prepared, observer=None,
                admission=admit)
            admit()
            receipt = {
                "schema": "ATLAS_QD_D_RUNTIME_INSTALLATION_V1",
                "stage": "D_RUNTIME_LAYOUT_VERIFIED",
                "release_path": str(DESTINATION), "source_commit": SOURCE,
                "files": copied["files"], "directories": copied["directories"],
                "archive_sha256": ARCHIVE_SHA256,
                "inventory_sha256": INVENTORY_SHA256,
                "selected": False, "financial_effects": False,
                "provider_connections": False, "operational_acceptance": False,
            }
            digest = hashlib.sha256(json.dumps(
                receipt["files"],sort_keys=True,separators=(",",":")
            ).encode()).hexdigest()
            # Continuity is refreshed at the native phase boundary even if
            # the last copy admission was not exactly a 32-call checkpoint.
            clock.require_operational(identity)
            timeout = _remaining_installed_readback_timeout(guard)
            result = installed_readback(
                DESTINATION, receipt, digest, timeout=timeout)
            admit()
            # Require fresh two-peer continuity, selector and operator scope
            # immediately before any final nonfinancial acceptance receipt.
            clock.require_operational(identity)
            _selector_unchanged()
            _require_separate_consent()
            receipt.update(layout=result["layout"], artifact_digest=digest)
            # Durable pre-publication proof comes FIRST. The create-only final
            # receipt is the last side effect: a later journal failure must
            # never leave both a published acceptance receipt and a refusal.
            event({"stage": "NATIVE_READBACK_VERIFIED_FINAL_RECEIPT_PENDING",
                   "artifact_digest": digest, "selection_allowed": False,
                   "financial_authority": False})
            # The prepublication fsync may block. Re-check budget and real
            # two-peer clock AFTER it, immediately before the final receipt.
            guard.tick()
            clock.require_operational(identity)
            _selector_unchanged()
            _require_separate_consent()
            guard.tick()
            write_new_json(RECEIPT, receipt)
            return receipt
        except BaseException:
            event({"stage": "REFUSED_PRESERVE_PARTIAL_NO_RETRY"})
            raise


if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True))
