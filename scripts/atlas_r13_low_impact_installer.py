"""R13 pinned CODE-ONLY installer with an IDLE-priority single-process envelope.

Review/inspect is read-only. The create-only native copy is *permanently
unavailable* until an independently reviewed one-shot operator approval pin
is installed in a separate deliberate source revision. It never selects R13,
touches finance/accounts, connects market providers, or starts Atlas.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import time
from pathlib import Path

from scripts.install_verified_release import (
    installation_target, installed_readback, write_new_json,
)
from scripts.native_install_candidate import _copy_prepared_code
from scripts.native_install_plan import prepare_install_inputs

ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT / "logs/diagnostics"
REVIEW = ROOT / "docs/ATLAS_R13_CODE_ONLY_INSTALL_DEPENDENCY_REVIEW_R1_2026-11-09.json"
REVIEW_SHA256 = "be11c3a9353b00014f11324eb94fa6e007de03c19d2ab2ec52a832319bbf601f"
SOURCE = "c7dfb85665bbcd5ba4494c33365d4dff8ea92b12"
ARCHIVE_SHA256 = "20167da274294223333ea4668d288514176a675e9308a298786abd0b46b8f39c"
INVENTORY_SHA256 = "c070130867636c27ae3ca31f01921a186445e7f4bc8b7ea2e9b14900893680e4"
DEPENDENCY_SHA256 = "93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91"
DEPENDENCY_RECEIPT_SHA256 = "b1363f4514d3cdce4a1914e79d14842ece94136ed5d035ea195b4883da99a7a0"
PREVIOUS_R12_SHA256 = "f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7"
PREVIOUS_R12 = Path("D:/AtlasRuntime/selection/r0012.json")
ARCHIVE = DIAG / "atlas-r13-source-only-20261109-r01/atlas-source.zip"
DEPENDENCY = DIAG / "qd-d-runtime-coordination-installation-20261028.json"
RECEIPT = DIAG / ("qd-unselected-release-" + SOURCE + ".json")
DESTINATION = Path("D:/AtlasRuntime/releases") / SOURCE
APPROVAL = DIAG / "atlas-r13-code-only-install-one-shot-approval.json"
APPROVAL_SHA256 = None  # One-time operator permission consumed/refused on 2026-11-09; never retry partial.
IDLE_PRIORITY_CLASS = 0x40


def _exact_bytes(path, sha256, *, max_bytes):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= max_bytes:
        raise ValueError("R13_PINNED_REGULAR_FILE_REQUIRED")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("R13_PINNED_SOURCE_DIGEST_MISMATCH")
    return raw


def _selector_unchanged():
    _exact_bytes(PREVIOUS_R12, PREVIOUS_R12_SHA256, max_bytes=64 * 1024)
    return True


def _r12_unchanged():
    _selector_unchanged()
    # Check create-only namespace before, never during, a planned copy.
    if os.path.lexists(DESTINATION) or os.path.lexists(RECEIPT) or os.path.lexists(
            RECEIPT.with_suffix(".pending.jsonl")):
        raise ValueError("R13_CREATE_ONLY_DESTINATION_ALREADY_USED")
    return True


def _read_review():
    review = json.loads(_exact_bytes(REVIEW, REVIEW_SHA256, max_bytes=64 * 1024))
    if (type(review) is not dict
            or review.get("schema") != "ATLAS_R13_CODE_ONLY_INSTALL_DEPENDENCY_REVIEW_R1"
            or review.get("status") != "SOURCE_AND_NATIVE_DEPENDENCY_REVIEW_VERIFIED_NOT_INSTALL_AUTHORIZATION"
            or review.get("source", {}).get("commit") != SOURCE
            or review["source"].get("artifact_sha256") != ARCHIVE_SHA256
            or review["source"].get("inventory_sha256") != INVENTORY_SHA256
            or review.get("dependency", {}).get("receipt_sha256") != DEPENDENCY_RECEIPT_SHA256
            or review["dependency"].get("inventory_sha256") != DEPENDENCY_SHA256
            or review["dependency"].get("native_python_dependency_files_sha256_verified") != 9566
            or review.get("existing_selection", {}).get("selector_sha256") != PREVIOUS_R12_SHA256
            or review.get("dry_run_install_plan", {}).get("files") != 10518
            or review["dry_run_install_plan"].get("bytes") != 263440156
            or review["dry_run_install_plan"].get("destination") is not None
            or review["dry_run_install_plan"].get("native_install_executed") is not False
            or type(review.get("flags")) is not dict
            or any(value is not False for value in review["flags"].values())):
        raise ValueError("R13_REVIEW_IS_NOT_INSTALL_AUTHORITY")
    return review


def prepare_readonly():
    """Reverify exact archive/receipt, selectors and namespace; never create."""
    _r12_unchanged()
    _read_review()
    receipt = json.loads(_exact_bytes(
        DEPENDENCY, DEPENDENCY_RECEIPT_SHA256, max_bytes=16 * 1024**2))
    selected = _exact_bytes(ARCHIVE, ARCHIVE_SHA256, max_bytes=64 * 1024**2)
    prepared = prepare_install_inputs(
        archive=ARCHIVE, archive_sha256=ARCHIVE_SHA256,
        source_commit=SOURCE, inventory_digest=INVENTORY_SHA256,
        dependency_receipt=receipt, dependency_digest=DEPENDENCY_SHA256,
        require_tracked=True)
    if (len(prepared["runtime"]) != 952
            or len(prepared["dependencies"]) != 9566
            or len(prepared["names"]) != 10518
            or len(prepared["directories"]) + 1 != 912
            or prepared["total"] != 263440156):
        raise ValueError("R13_EXACT_NATIVE_PLAN_CHANGED")
    if len(selected) == 0:
        raise ValueError("R13_EMPTY_ARCHIVE_REFUSED")
    installation_target(SOURCE, RECEIPT)  # checks ancestors, create-only; no writing.
    return prepared


class LowImpactEnvelope:
    """One owning Windows process; priority restored after scope exits.

    Pace the *existing* _copy_prepared_code admission callback, which is
    invoked during file copy AND post-copy native readback. No worker pool.
    """

    def __init__(self, *, wait=time.sleep, monotonic=time.monotonic, kernel=None,
                 check_every=32, pause_seconds=0.06, max_seconds=500):
        if (type(check_every) is not int or not 8 <= check_every <= 128
                or type(pause_seconds) not in (int, float)
                or not 0.01 <= pause_seconds <= 0.25
                or type(max_seconds) not in (int, float)
                or not 30 <= max_seconds <= 590):
            raise ValueError("R13_BOUNDED_LOW_RESOURCE_POLICY_REQUIRED")
        self.wait, self.monotonic = wait, monotonic
        self.kernel = kernel
        self.check_every, self.pause_seconds = check_every, pause_seconds
        self.max_seconds = max_seconds
        self.started = None
        self.original_priority = None
        self.checks = 0

    def __enter__(self):
        if self.kernel is None:
            if os.name != "nt":
                raise ValueError("R13_WINDOWS_NATIVE_ONLY")
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel.GetCurrentProcess.restype = ctypes.c_void_p
            self.kernel.GetPriorityClass.argtypes = [ctypes.c_void_p]
            self.kernel.GetPriorityClass.restype = ctypes.c_uint32
            self.kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            self.kernel.SetPriorityClass.restype = ctypes.c_int
        self.process = self.kernel.GetCurrentProcess()
        self.original_priority = self.kernel.GetPriorityClass(self.process)
        if not self.original_priority or not self.kernel.SetPriorityClass(
                self.process, IDLE_PRIORITY_CLASS):
            raise ValueError("R13_IDLE_PRIORITY_REQUIRED_BEFORE_NATIVE_IO")
        if self.kernel.GetPriorityClass(self.process) != IDLE_PRIORITY_CLASS:
            # A successful API call without a matching OS readback is not proof
            # that CPU-intensive native work will actually run at idle priority.
            try:
                if not self.kernel.SetPriorityClass(self.process, self.original_priority):
                    raise OSError("R13_PRIORITY_ROLLBACK_REFUSED")
            finally:
                self.original_priority = None
            raise ValueError("R13_IDLE_PRIORITY_READBACK_REFUSED_BEFORE_NATIVE_IO")
        self.started = self.monotonic()
        return self

    def __exit__(self, typ, value, traceback):
        if self.original_priority:
            if not self.kernel.SetPriorityClass(self.process, self.original_priority):
                raise OSError("R13_ORIGINAL_PRIORITY_RESTORE_FAILED")
        self.original_priority = None
        self.started = None

    def tick(self):
        if self.started is None:
            raise ValueError("R13_ENVELOPE_NOT_ACTIVE")
        if self.monotonic() - self.started >= self.max_seconds:
            raise ValueError("R13_LOW_IMPACT_INSTALL_DEADLINE_PRESERVE_PARTIAL")
        self.checks += 1
        if self.checks % self.check_every == 0:
            self.wait(self.pause_seconds)
            if self.kernel.GetPriorityClass(self.process) != IDLE_PRIORITY_CLASS:
                raise ValueError("R13_IDLE_PRIORITY_LOST_PRESERVE_PARTIAL")
            if self.monotonic() - self.started >= self.max_seconds:
                raise ValueError("R13_LOW_IMPACT_INSTALL_DEADLINE_PRESERVE_PARTIAL")
            # Additional lightweight selector check; not a cache of permission.
            _selector_unchanged()
        return True


def _require_separate_consent():
    # Explicit approvals or historic local receipts are not sufficient.
    if type(APPROVAL_SHA256) is not str or not re.fullmatch(
            r"[0-9a-f]{64}", APPROVAL_SHA256):
        raise ValueError("R13_SEPARATE_PINNED_INSTALL_APPROVAL_NOT_YET_GRANTED")
    consent = json.loads(_exact_bytes(APPROVAL, APPROVAL_SHA256, max_bytes=4096))
    if (type(consent) is not dict or set(consent) != {
            "schema", "decision", "source", "archive_sha256",
            "dependency_sha256", "operator_sid", "one_shot",
            "selection_allowed", "financial_authority", "provider_access",
            "startup_authorized"}
            or consent["schema"] != "ATLAS_R13_CODE_ONLY_INSTALL_APPROVAL_V1"
            or consent["decision"] != "APPROVE_ONE_UNSELECTED_CODE_COPY"
            or consent["source"] != SOURCE
            or consent["archive_sha256"] != ARCHIVE_SHA256
            or consent["dependency_sha256"] != DEPENDENCY_SHA256
            or consent["one_shot"] is not True
            or any(consent[key] is not False for key in (
                "selection_allowed", "financial_authority",
                "provider_access", "startup_authorized"))):
        raise ValueError("R13_SEPARATE_INSTALL_APPROVAL_SCOPE_REFUSED")
    from scripts.volume_inspector.windows_output import current_sid
    if consent["operator_sid"] != current_sid():
        raise ValueError("R13_OPERATOR_OWNERSHIP_NOT_APPROVED")
    return consent


def inspect():
    # The read-only CLI itself hashes and validates local release inputs;
    # protect the operator's desktop just as the future installer is protected.
    with LowImpactEnvelope() as envelope:
        prepared = prepare_readonly()
        envelope.tick()
    return {
        "schema": "ATLAS_R13_LOW_IMPACT_CODE_INSTALL_PREVIEW_V1",
        "status": "SOURCE_DEPENDENCY_AND_LAYOUT_VERIFIED_NOT_INSTALL_APPROVAL",
        "source_commit": SOURCE, "runtime_source_files": len(prepared["runtime"]),
        "native_python_files": len(prepared["dependencies"]),
        "planned_files": len(prepared["names"]),
        "planned_bytes": prepared["total"],
        "idle_priority_required": True,
        "paced_native_copy_and_readback_required": True,
        "installation_authorized": False,
        "installed": False, "selected": False,
        "startup_authorized": False, "paper_orders_authorized": False,
        "live_orders_authorized": False,
    }


def install(*, execute_approved=False, clock=None):
    """Only a separately pinned, qualified one-shot code-only native copy.

    No execution is possible in this version: APPROVAL_SHA256 is None.
    """
    if execute_approved is not True:
        raise ValueError("R13_EXPLICIT_CODE_INSTALL_EXECUTION_REQUIRED")
    _require_separate_consent()  # before even source preflight
    from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R13_REAL_INDEPENDENT_NTP_CLOCK_REQUIRED")
    identity = "r13-code-only-" + SOURCE
    clock.require_operational(identity)
    # Existing independent 180s qualification; no Windows clock modification.
    from scripts.install_version_safe_candidate import _qualify_native_clock_180s
    _qualify_native_clock_180s(clock, identity)
    _require_separate_consent()
    # Preflight walks and hashes the source/dependency inputs. It must run
    # under the same IDLE CPU policy as the later native copy/readback.
    with LowImpactEnvelope() as envelope:
        prepared = prepare_readonly()
        envelope.tick()  # Refuse deadline/priority drift before any journal.
        prepared["started"] = time.monotonic()
        def admission():
            envelope.tick()
            clock.require_operational(identity)
            return True
        admission()
        journal = RECEIPT.with_suffix(".pending.jsonl")
        write_new_json(journal, {
            "schema": "ATLAS_R13_UNSELECTED_LOW_IMPACT_CODE_INSTALL_INTENT_V1",
            "source_commit": SOURCE, "archive_sha256": ARCHIVE_SHA256,
            "destination": str(DESTINATION), "selection_allowed": False,
            "financial_authority": False, "low_impact": True,
        })
        def event(value):
            with journal.open("ab") as f:
                f.write(b"\n" + json.dumps(value, sort_keys=True).encode())
                f.flush()
                os.fsync(f.fileno())
        try:
            # Do not materialize massive cumulative JSON snapshots every 250
            # files: the native copier supports observer=None. The create-only
            # journal below still records intent + terminal completion/refusal.
            copy = _copy_prepared_code(
                destination=DESTINATION, archive_sha256=ARCHIVE_SHA256,
                source_commit=SOURCE, prepared=prepared, observer=None,
                admission=admission)
            admission()
            receipt = {
                "schema": "ATLAS_QD_D_RUNTIME_INSTALLATION_V1",
                "stage": "D_RUNTIME_LAYOUT_VERIFIED",
                "release_path": str(DESTINATION), "source_commit": SOURCE,
                "files": copy["files"], "directories": copy["directories"],
                "archive_sha256": ARCHIVE_SHA256,
                "inventory_sha256": INVENTORY_SHA256,
                "selected": False, "financial_effects": False,
                "provider_connections": False, "operational_acceptance": False,
            }
            artifact_digest = hashlib.sha256(json.dumps(
                receipt["files"], sort_keys=True, separators=(",", ":")
            ).encode()).hexdigest()
            result = installed_readback(
                DESTINATION, receipt, artifact_digest,
                timeout=min(120, max(1, 540 - (time.monotonic() - prepared["started"]))))
            admission()
            _require_separate_consent()
            receipt.update(layout=result["layout"], artifact_digest=artifact_digest)
            write_new_json(RECEIPT, receipt)
            event({"stage": "CODE_ONLY_COPY_READBACK_VERIFIED_UNSELECTED"})
            return receipt
        except BaseException:
            event({"stage": "REFUSED_PRESERVE_PARTIAL_NO_RETRY"})
            raise


if __name__ == "__main__":
    # Read-only: deliberately no CLI for install().
    print(json.dumps(inspect(), sort_keys=True))
