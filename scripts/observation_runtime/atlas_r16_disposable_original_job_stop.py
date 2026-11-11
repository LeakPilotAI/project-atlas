"""Genuine selected R16 original Job + external Windows Stop + durable observation.

ONE bounded, strictly disposable, nonfinancial experiment. Real installed R16
Python holds original twelve EMPTY native account directory handles inside the
original owned kill-on-close Windows Job. A SEPARATE PowerShell process sends
the installed selected R16 Stop module's TEST-NAMESPACE signal; the parent
observes the native event and only then cooperatively stops the SAME child.
The durable SQLite receipt is expressly NOT proof of financial flattening.
No Start authority, actual PAPER accounts, broker, provider or order action.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from app.services.paper_stop_receipt_ledger import (
    PaperStopReceiptLedger, StopReceiptConflict,
)
from scripts.observation_runtime.atlas_r16_parked_writer_owner import (
    inspect as inspect_original_job, validate_result,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    RELEASE, R16_HEAD, selected_code,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_paper_python_stop_signal import (
    WindowsStopEvents, WAIT_OBJECT_0,
)

ROOT = Path("D:/Work/Project Atlas")
STOP = RELEASE/"scripts/windows/Atlas-Paper-Owned-Stop-Signal.psm1"
STOP_SHA = "893a81bf11f7849f8ba20b31bb9e96b45e30ed09e35485ad018e1d7a21d1e9dc"
HANDOFF = RELEASE/"scripts/windows/Atlas-Paper-Stop-Handoff.psm1"
HANDOFF_SHA = "f4a795ecd4abcc9a632fd6fadbea4d74aaf4967f5fb3adc214bb553966dd4b4b"
SCHEMA = "ATLAS_R16_SELECTED_ORIGINAL_JOB_DISPOSABLE_EXTERNAL_STOP_V1"
REQUEST_SCHEMA = "ATLAS_R16_DISPOSABLE_WINDOWS_STOP_REQUEST_V1"
MODE = "SHUTDOWN_FLATTEN"
REQUEST_SCRIPT = r"""
$ErrorActionPreference='Stop'
Import-Module $env:ATLAS_R16_DISPOSABLE_SELECTED_STOP_MODULE -Force -ErrorAction Stop
$receipt=Request-AtlasPaperOwnedStopSignal -OfflineTestId $env:ATLAS_R16_DISPOSABLE_STOP_ID
if($receipt.status -cne 'REQUESTED_NOT_VERIFIED' -or
   $receipt.financial_flatness_verified -ne $false) {
    throw 'R16_DISPOSABLE_EXTERNAL_STOP_MISLABELLED_FINANCIAL_FLATNESS'
}
Write-Output 'R16_DISPOSABLE_NATIVE_SIGNAL_REQUESTED_NOT_VERIFIED'
"""


def require_installed_native_stop():
    # The immutable R16 source is independently pinned as CURRENT in native
    # selector revision 15; a host-workspace copy is not the installed module.
    selected = selected_code()
    if (selected["selected_revision"] != 15
            or selected["selected_native_head"] != R16_HEAD
            or selected["paper_start_authorized"] is not False
            or selected["financial_writer_operational_accepted"] is not False
            or not STOP.is_file() or not HANDOFF.is_file()
            or STOP.is_symlink() or HANDOFF.is_symlink()
            or hashlib.sha256(STOP.read_bytes()).hexdigest() != STOP_SHA
            or hashlib.sha256(HANDOFF.read_bytes()).hexdigest() != HANDOFF_SHA):
        raise ValueError("R16_DISPOSABLE_ORIGINAL_INSTALLED_STOP_MODULE_REQUIRED")
    return True


def request_disposable_external_stop(*, test_id):
    """A real per-user Windows event; ONLY an isolated test-uuid namespace."""
    if (type(test_id) is not str
            or re.fullmatch(r"test-[0-9a-f]{32}", test_id) is None):
        raise ValueError("R16_DISPOSABLE_EXTERNAL_STOP_TEST_NAMESPACE_REQUIRED")
    require_installed_native_stop()
    if os.name != "nt":
        raise ValueError("R16_DISPOSABLE_EXTERNAL_STOP_WINDOWS_REQUIRED")
    native = WindowsStopEvents()
    sid, session = native.identity()
    name = ("Local\\AtlasFinancialPaperStop_" + sid + "_" +
            str(session) + "_" + test_id)
    attrs, descriptor = native.secure_attributes(sid)
    mutex = event = None
    try:
        mutex = native.create_unique("mutex", attrs, name+"_Owner")
        event = native.create_unique("event", attrs, name)
        env = {
            **os.environ,
            "ATLAS_R16_DISPOSABLE_SELECTED_STOP_MODULE": str(STOP),
            "ATLAS_R16_DISPOSABLE_STOP_ID": test_id,
        }
        command = ["powershell.exe","-NoProfile","-NonInteractive",
                   "-Command",REQUEST_SCRIPT]
        response = subprocess.run(
            command, cwd=ROOT, env=env, capture_output=True,
            text=True, timeout=15)
        if (response.returncode != 0
                or response.stdout.strip() !=
                   "R16_DISPOSABLE_NATIVE_SIGNAL_REQUESTED_NOT_VERIFIED"):
            raise ValueError("R16_DISPOSABLE_SEPARATE_PROCESS_NATIVE_SIGNAL_REFUSED")
        if native.k.WaitForSingleObject(event, 3000) != WAIT_OBJECT_0:
            raise ValueError("R16_DISPOSABLE_NATIVE_STOP_EVENT_NOT_OBSERVED")
        return {
            "schema": REQUEST_SCHEMA,
            "status": "REQUESTED_NOT_VERIFIED",
            "native_signal_received": True,
            "financial_flatness_verified": False,
        }
    finally:
        try:
            if event is not None:
                native.k.CloseHandle(event)
            if mutex is not None:
                try:
                    if not native.k.ReleaseMutex(mutex):
                        raise OSError("R16_DISPOSABLE_OWNER_MUTEX_RELEASE_FAILED")
                finally:
                    native.k.CloseHandle(mutex)
        finally:
            native.k.LocalFree(descriptor)


def run():
    """Read-only original native Job plus real external Stop and isolated ledger."""
    require_installed_native_stop()
    before = inspect_two_lane_native_roots()
    if (before.get("native_root_total") != 12
            or before.get("all_twelve_distinct_and_empty") is not True):
        raise ValueError("R16_DISPOSABLE_ORIGINAL_EMPTY_NATIVE_ROOTS_REQUIRED")
    session = "test-r16-native-job-stop-" + uuid.uuid4().hex
    stop_token = "test-" + uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix="atlas-r16-disposable-stop-") as td:
        db = Path(td)/"disposable-stop-ledger.sqlite"
        ledger = PaperStopReceiptLedger(db)
        intent = ledger.reserve_fresh(session, MODE)
        if intent != {"state":"PENDING","mode":MODE,"receipt":None}:
            raise ValueError("R16_DISPOSABLE_FRESH_STOP_INTENT_REQUIRED")
        original = inspect_original_job(disposable_stop_requester=lambda:
            request_disposable_external_stop(test_id=stop_token))
        validate_result(original)
        if (original["owned_job_zero_processes_after_stop"] is not True
                or original["owned_job_closed_before_return"] is not True
                or original["original_native_roots_unchanged_after_stop"] is not True
                or original["financial_writer_roles_enrolled"] != 0
                or inspect_two_lane_native_roots() != before):
            raise ValueError("R16_DISPOSABLE_ORIGINAL_JOB_STOP_NOT_PROVEN")
        # Unlike a financial Stop, this original R16 child NEVER held
        # actual positions or financial ledger authority. Receipt MUST
        # explicitly retain UNKNOWN financial exposure semantics.
        receipt = {
            "schema": SCHEMA,
            "phase": "FINISHED",
            "outcome": {
                "mode": MODE,
                "status": "NONFINANCIAL_ORIGINAL_JOB_STOPPED",
                "position_state": "UNKNOWN_NOT_FINANCIAL_CUSTODY",
                "financial_flatness_verified": False,
                "paper_start_authorized": False,
                "native_original_job_closed": True,
                "native_original_process_exited": True,
                "twelve_original_empty_roots_unchanged": True,
            },
        }
        ledger.finish(session, MODE, receipt)
        # A fresh SQLite connection provides post-stop reopening;
        # RECEIPT_RECORDED never means that financial positions are FLAT.
        cold = PaperStopReceiptLedger(db)
        if (cold.recover(session, MODE) != {
                "state":"RECEIPT_RECORDED","mode":MODE,"receipt":receipt}
                or cold.summarize_recovery() != {
                    "schema":"ATLAS_PAPER_STOP_RECOVERY_INVENTORY_V1",
                    "pending_unverified":0,
                    "receipts_recorded_not_flat_verified":1,
                    "receipts_without_flatten_claim":1,
                    "requires_independent_position_reconciliation":True,
                    "financial_authorized":False,
                    "startup_authorized":False}):
            raise ValueError("R16_DISPOSABLE_DURABLE_NONFINANCIAL_STOP_RESTART_REFUSED")
        # Genuine separate Python reader after the native child and
        # PowerShell sender have both exited. No runtime/account restart.
        cold_script = """
import sys
from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger
ledger=PaperStopReceiptLedger(sys.argv[1])
session=sys.argv[2]
row=ledger.recover(session,"SHUTDOWN_FLATTEN")
assert row["state"]=="RECEIPT_RECORDED"
assert row["receipt"]["outcome"]["status"]=="NONFINANCIAL_ORIGINAL_JOB_STOPPED"
assert row["receipt"]["outcome"]["financial_flatness_verified"] is False
state=ledger.summarize_recovery()
assert state["receipts_without_flatten_claim"]==1
assert state["requires_independent_position_reconciliation"] is True
assert state["startup_authorized"] is False
print("R16_SEPARATE_PROCESS_SQLITE_STOP_OBSERVATION_COLD_READBACK_PASS")
"""
        check = subprocess.run(
            [sys.executable, "-B", "-c", cold_script, str(db), session],
            cwd=ROOT, capture_output=True, text=True, timeout=12)
        if (check.returncode != 0 or check.stdout.strip() !=
                "R16_SEPARATE_PROCESS_SQLITE_STOP_OBSERVATION_COLD_READBACK_PASS"):
            raise ValueError("R16_DISPOSABLE_COLD_SEPARATE_PROCESS_RECEIPT_REFUSED")
        observed = cold.reconcile_restart_observation(
            session, lane_positions={
                "QUALITY_DIPS":{"open_positions":0,"unsettled_orders":0},
                "HYPERLIQUID":{"open_positions":0,"unsettled_orders":0},
            })
        if (observed["stop_record_state"] != "FINISHED"
                or observed["startup_authorized"] is not False
                or observed["financial_authorized"] is not False
                or observed["reconciliation_required"] is not True):
            raise ValueError("R16_DISPOSABLE_NO_FINANCIAL_START_GRANT_REQUIRED")
        try:
            cold.reserve_fresh(session, MODE)
        except StopReceiptConflict as exc:
            if str(exc) != "STOP_INTENT_ALREADY_EXISTS":
                raise
        else:
            raise ValueError("R16_DISPOSABLE_STOP_REPLAY_FALSELY_ACCEPTED")
    if inspect_two_lane_native_roots() != before:
        raise ValueError("R16_DISPOSABLE_ROOTS_CHANGED_AFTER_LEDGER_CLEANUP")
    return {
        "schema": SCHEMA,
        "status": "R16_ORIGINAL_JOB_EXTERNAL_WINDOWS_STOP_OBSERVED",
        "selected_native_head": R16_HEAD,
        "installed_original_job_process_exited": True,
        "external_windows_stop_request_observed": True,
        "durable_observation_receipt_reopened": True,
        "cold_separate_process_sqlite_recovery_verified": True,
        "double_stop_intent_refused": True,
        "requires_independent_financial_reconciliation": True,
        "actual_financial_flatness_verified": False,
        "native_financial_roots_changed": False,
        "financial_writer_roles_enrolled": 0,
        "native_financial_account_files_created": 0,
        "provider_requests": 0,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
