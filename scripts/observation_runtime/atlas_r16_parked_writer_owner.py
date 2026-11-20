"""Real selected R16 parked nonfinancial Windows Job / original native roots proof.

A single below-normal, suspended R16 Python child is assigned to an owned
kill-on-close Windows Job BEFORE resume. Its only capability is to hold the
twelve ORIGINAL EMPTY native PAPER account directory handles, report READY
via a one-shot event, wait for a bounded local STOP event, then exit.
This probe NEVER creates PAPER accounts, enrolls financial writers, accesses
providers, owns ledgers, authorizes activation, or executes trading.
"""
from __future__ import annotations

import ctypes
import json
import ntpath
import os
import secrets
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    SOURCE, RELEASE, R16_HEAD, selected_code,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    ROLES, inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_native_job import (
    AdmissionFailure, launch_contained_child,
)
from scripts.observation_runtime.personal_native_windows_api import (
    PROCESS_INFORMATION, STARTUPINFOW, WindowsJobAPI,
)
from scripts.observation_runtime.atlas_r15_native_job_admission_preflight import (
    BELOW_NORMAL_PRIORITY_CLASS, CREATE_SUSPENDED,
    _exited_creation_filetime, _wait_exit,
)
from scripts.observation_runtime.atlas_r15_parked_writer_owner import (
    CHILD as READ_ONLY_ROOT_HOLDER,
)
from scripts.observation_runtime.atlas_r15_disposable_writer_process_audit import (
    _windows_handle_identity,
)

SCHEMA = "ATLAS_R16_SELECTED_NATIVE_PARKED_OWNED_JOB_12_ORIGINAL_ROOTS_V1"
IMAGE = str(RELEASE / "python/python.exe")
WAIT_OBJECT_0 = 0
DETACHED_PROCESS = 0x00000008
# Child source is the previously audited immutable-handle/READY/STOP root
# holder. Adapt ERROR NAMES only, not runtime semantics or financial grants.
CHILD = READ_ONLY_ROOT_HOLDER.replace("R15_PARKED", "R16_PARKED")


def _exact_r16_process(api, handle, *, expected_pid=None):
    """Original Windows HANDLE identity; never inherit an R15 image pin."""
    k = api.kernel32
    k.GetProcessId.argtypes = [wintypes.HANDLE]
    k.GetProcessId.restype = wintypes.DWORD
    pid = int(k.GetProcessId(handle))
    observed = _windows_handle_identity(handle)
    if (pid <= 0
            or (expected_pid is not None and pid != expected_pid)
            or type(observed.get("creation_filetime")) is not int
            or observed["creation_filetime"] <= 0
            or ntpath.normcase(ntpath.normpath(observed["image"])) !=
               ntpath.normcase(ntpath.normpath(IMAGE))):
        raise ValueError("R16_PARKED_ORIGINAL_R16_PROCESS_IMAGE_OR_ID_REFUSED")
    return {"pid": pid, "creation_filetime": observed["creation_filetime"],
            "image": observed["image"]}


def validate_result(row):
    fields = {
        "schema", "status", "selected_native_head", "installed_release",
        "installed_source_commit", "parked_original_process_identity_verified",
        "created_suspended_before_owned_job_assignment",
        "original_selected_r16_executable_and_source_verified",
        "child_held_all_twelve_original_empty_native_roots",
        "original_native_roots_unchanged_after_stop",
        "owned_job_one_process_before_stop",
        "owned_job_zero_processes_after_stop",
        "cooperative_stop_acknowledged",
        "owned_process_exited_before_return",
        "owned_job_closed_before_return",
        "twelve_structural_roles_verified_under_original_retained_job",
        "retained_original_job_liveness_checked_three_times",
        "expired_retained_job_refused_after_stop",
        "live_original_job_financial_activation_explicitly_refused",
        "financial_writer_roles_enrolled",
        "financial_account_files_created", "market_provider_requests",
        "paper_start_authorized", "live_trading_authorized",
    }
    if (type(row) is not dict or set(row) != fields
            or row["schema"] != SCHEMA
            or row["status"] != "R16_OWNED_JOB_READ_ONLY_ROOT_HOLD_STOP_PASS"
            or row["selected_native_head"] != R16_HEAD
            or row["installed_release"] != str(RELEASE)
            or row["installed_source_commit"] != SOURCE
            or any(row[k] is not True for k in (
                "parked_original_process_identity_verified",
                "created_suspended_before_owned_job_assignment",
                "original_selected_r16_executable_and_source_verified",
                "child_held_all_twelve_original_empty_native_roots",
                "original_native_roots_unchanged_after_stop",
                "owned_job_one_process_before_stop",
                "owned_job_zero_processes_after_stop",
                "cooperative_stop_acknowledged",
                "owned_process_exited_before_return",
                "owned_job_closed_before_return",
                "twelve_structural_roles_verified_under_original_retained_job",
                "retained_original_job_liveness_checked_three_times",
                "expired_retained_job_refused_after_stop",
                "live_original_job_financial_activation_explicitly_refused"))
            or any(type(row[k]) is not int or row[k] != 0 for k in (
                "financial_writer_roles_enrolled",
                "financial_account_files_created",
                "market_provider_requests"))
            or row["paper_start_authorized"] is not False
            or row["live_trading_authorized"] is not False):
        raise ValueError("R16_PARKED_ORIGINAL_JOB_NONFINANCIAL_RESULT_REFUSED")
    return row


def inspect(*, disposable_stop_requester=None):
    # Optional test-only external request hook. The observed native Job stays
    # in this process; this does not constitute a financial Stop owner.
    if (disposable_stop_requester is not None
            and not callable(disposable_stop_requester)):
        raise ValueError("R16_PARKED_DISPOSABLE_STOP_CALLBACK_REQUIRED")
    if os.name != "nt" or sys.platform != "win32":
        raise ValueError("R16_PARKED_NATIVE_WINDOWS_REQUIRED")
    selection = selected_code(verify_original_installed_handles=True)
    if (selection.get("selected_revision") != 15
            or selection.get("selected_native_head") != R16_HEAD
            or selection.get("financial_writer_operational_accepted") is not False
            or selection.get("paper_start_authorized") is not False
            or not Path(IMAGE).is_file()):
        raise ValueError("R16_PARKED_EXACT_CURRENT_SELECTED_RELEASE_REQUIRED")
    before = inspect_two_lane_native_roots()
    if (before.get("native_root_total") != 12
            or before.get("native_root_ids_verified") != 12
            or before.get("existing_empty_root_namespaces") != 12
            or before.get("all_twelve_distinct_and_empty") is not True):
        raise ValueError("R16_PARKED_PREINCEPTION_TWELVE_EMPTY_NATIVE_ROOTS_REQUIRED")
    entries = {}
    for lane in ("QUALITY_DIPS", "HYPERLIQUID"):
        original = before["lanes"][lane]["roots"]
        if type(original) is not dict or set(original) != set(ROLES):
            raise ValueError("R16_PARKED_SIX_ROLES_PER_LANE_REQUIRED")
        entries[lane] = {
            role: {
                "path": original[role]["path"],
                "native_id": original[role]["native_id"],
            }
            for role in ROLES
        }
    api = WindowsJobAPI()
    k = api.kernel32
    k.CreateEventW.argtypes = [
        ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR,
    ]
    k.CreateEventW.restype = wintypes.HANDLE
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.IsProcessInJob.argtypes = [
        wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL),
    ]
    k.IsProcessInJob.restype = wintypes.BOOL
    name = "Local\\AtlasR16ParkedRootReady-" + secrets.token_hex(16)
    stop_name = "Local\\AtlasR16ParkedRootStop-" + secrets.token_hex(16)
    signal = k.CreateEventW(None, False, False, name)
    if not signal:
        raise ctypes.WinError(ctypes.get_last_error())
    stop = None
    child = None
    ready = {}
    try:
        stop = k.CreateEventW(None, False, False, stop_name)
        if not stop:
            raise ctypes.WinError(ctypes.get_last_error())
        args = json.dumps({
            "selected_head": R16_HEAD,
            "installed_root": str(RELEASE),
            "ready_event": name,
            "stop_event": stop_name,
            "roots": entries,
        }, sort_keys=True, separators=(",", ":"))
        command = subprocess.list2cmdline([
            IMAGE, "-I", "-B", "-S", "-c", CHILD, args,
        ])
        if len(command) > 28000:
            raise ValueError("R16_PARKED_CHILD_ARGUMENTS_EXCEED_BOUND")

        def creator(candidate):
            if candidate != command:
                raise ValueError("R16_PARKED_FOREIGN_CHILD_COMMAND_REFUSED")
            startup = STARTUPINFOW()
            startup.cb = ctypes.sizeof(startup)
            process = PROCESS_INFORMATION()
            line = ctypes.create_unicode_buffer(command)
            if not k.CreateProcessW(
                IMAGE, line, None, None, False,
                CREATE_SUSPENDED | DETACHED_PROCESS | BELOW_NORMAL_PRIORITY_CLASS,
                None, str(RELEASE),
                ctypes.byref(startup), ctypes.byref(process),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            return process.hProcess, process.hThread

        api.suspended_creator = creator

        def suspended_check(process, thread):
            ready.update(_exact_r16_process(api, process))
            return True

        try:
            child = launch_contained_child(
                api, command, verify_suspended=suspended_check)
        except AdmissionFailure as exc:
            if not exc.cleanup.closed:
                exc.cleanup.close()
            raise ValueError("R16_PARKED_JOB_ADMISSION_REFUSED") from exc
        if int(k.WaitForSingleObject(signal, 7000)) != WAIT_OBJECT_0:
            raise ValueError("R16_PARKED_ORIGINAL_ROOT_HOLDER_NOT_READY")
        if _exact_r16_process(api, child.process, expected_pid=ready["pid"]) != ready:
            raise ValueError("R16_PARKED_PROCESS_ORIGINAL_IDENTITY_CHANGED")
        member = wintypes.BOOL()
        if (not k.IsProcessInJob(child.process, child.job, ctypes.byref(member))
                or not member.value or api.active_processes(child.job) != 1):
            raise ValueError("R16_PARKED_CHILD_NOT_EXACT_ONE_OWNED_JOB_PROCESS")
        if inspect_two_lane_native_roots() != before:
            raise ValueError("R16_PARKED_NATIVE_ROOT_IDENTITY_CHANGED_WHILE_ALIVE")
        # In-process handoff retains THIS very Job and original PROCESS handle.
        # The candidate rosters have explicitly synthetic/unaccepted policy,
        # inception and operator IDs; validate STRUCTURE/ownership only.
        from copy import deepcopy
        from app.services.quality_dips_autonomous_enrollment import (
            WRITERS as QD_WRITERS, validate_enrollment as qd_validate,
        )
        from app.services.perp_operational_contract import (
            WRITERS as HL_WRITERS, validate_enrollment as hl_validate,
        )
        from scripts.observation_runtime.atlas_independent_ntp_clock import (
            SOURCE as CLOCK_SOURCE,
        )
        from scripts.observation_runtime.atlas_r16_selected_code_readback import (
            ARTIFACT_DIGEST,
        )
        from scripts.observation_runtime.personal_r16_owned_job_activation import (
            RetainedSelectedR16OwnerJob,
        )
        process_identity = {"schema": "QD_OP_PROCESS_ID_V1", **ready}
        rosters = {}
        for lane, roles, validator, native_schema, enrollment_schema in (
            ("QUALITY_DIPS", QD_WRITERS, qd_validate,
             "QD_AUTO_NATIVE_ROOT_V4", "QD_AUTO_NATIVE_ENROLLMENT_V4"),
            ("HYPERLIQUID", HL_WRITERS, hl_validate,
             "PERP_AUTO_NATIVE_ROOT_V1", "PERP_AUTO_NATIVE_ENROLLMENT_V1"),
        ):
            candidate = {
                "schema": enrollment_schema,
                "profile": "AUTONOMOUS_PAPER_ONLY_V1",
                "account_id": "R16_DISPOSABLE_" + lane,
                "epoch": before["lanes"][lane]["epoch"],
                "policy_digest": "0" * 64,
                "inception_digest": "1" * 64,
                "release_digest": ARTIFACT_DIGEST,
                "resources": {
                    role: {"schema": native_schema, **deepcopy(entry)}
                    for role, entry in entries[lane].items()
                },
                "writers": {role: deepcopy(process_identity) for role in roles},
                "clock_source": CLOCK_SOURCE,
                "acceptance_id": "DISPOSABLE_R16_" + lane + "_NOT_ACCEPTED",
            }
            rosters[lane] = validator(candidate)
        qd, perp = rosters["QUALITY_DIPS"], rosters["HYPERLIQUID"]
        retained = RetainedSelectedR16OwnerJob(child=child, qd=qd, perp=perp)
        from scripts.observation_runtime.personal_activation_commission import (
            retain_r16_nonfinancial_original_job,
            retain_activation_writer_guard,
        )
        with retain_r16_nonfinancial_original_job(
                qd=qd, perp=perp, owned_job=retained) as observed_owner:
            if observed_owner is not retained:
                raise ValueError("R16_PARKED_ORIGINAL_GUARD_CHANGED_OWNER")
            for index in range(3):
                if retained.require_exact_roster(qd=qd, perp=perp) is not True:
                    raise ValueError("R16_PARKED_ORIGINAL_RETAINED_JOB_ROSTER_CHANGED")
                if index != 2:
                    time.sleep(.2)
            held = retained.nonfinancial_handoff_readback()
            if (held["twelve_structural_writer_roles_bound_to_same_process"] is not True
                    or held["twelve_original_empty_native_directory_identities_verified"] is not True
                    or held["financial_writer_lease_issued"] is not False
                    or held["paper_start_authorized"] is not False):
                raise ValueError("R16_PARKED_NONFINANCIAL_OWNED_ROSTER_REFUSED")
            # Even while the ORIGINAL Windows Job is alive, the real
            # commission guard MUST refuse financial publication before
            # any clock/ledger/market/provider is opened.
            try:
                with retain_activation_writer_guard(
                        qd=qd, perp=perp, release_digest=ARTIFACT_DIGEST,
                        owned_job=retained):
                    raise ValueError("R16_FINANCIAL_ACTIVATION_UNEXPECTEDLY_GRANTED")
            except ValueError as exc:
                if str(exc) != "ACTIVATION_R16_INDEPENDENT_FINANCIAL_LEASE_NOT_ACCEPTED":
                    raise
            else:
                raise ValueError("R16_FINANCIAL_ACTIVATION_GUARD_BYPASSED")
        # Test-only external Windows event request must be observed by the
        # host BEFORE signaling the original R16 child to drain. A requester
        # returning an unverified financial flatness claim is never accepted.
        if disposable_stop_requester is not None:
            request = disposable_stop_requester()
            if (type(request) is not dict or set(request) != {
                    "schema", "status", "native_signal_received",
                    "financial_flatness_verified"}
                    or request["schema"] !=
                       "ATLAS_R16_DISPOSABLE_WINDOWS_STOP_REQUEST_V1"
                    or request["status"] != "REQUESTED_NOT_VERIFIED"
                    or request["native_signal_received"] is not True
                    or request["financial_flatness_verified"] is not False):
                raise ValueError("R16_PARKED_UNVERIFIED_EXTERNAL_STOP_REQUEST_REFUSED")
            if retained.require_exact_roster(qd=qd, perp=perp) is not True:
                raise ValueError("R16_PARKED_NATIVE_OWNER_CHANGED_AFTER_EXTERNAL_STOP")
        # Cooperatively exit, then prove the actual original owned process
        # and Job drain. Never return any adoptable live PID/financial lease.
        k.SetEvent.argtypes = [wintypes.HANDLE]
        k.SetEvent.restype = wintypes.BOOL
        if not k.SetEvent(stop):
            raise ValueError("R16_PARKED_LOCAL_STOP_SIGNAL_REFUSED")
        result = _wait_exit(api, child.process, timeout_ms=5000)
        if (result != 0
                or _exited_creation_filetime(api, child.process) !=
                ready["creation_filetime"]):
            raise ValueError("R16_PARKED_ORIGINAL_PROCESS_STOP_REFUSED")
        deadline = time.monotonic() + 2
        while api.active_processes(child.job) and time.monotonic() < deadline:
            time.sleep(.025)
        if api.active_processes(child.job) != 0:
            raise ValueError("R16_PARKED_NATIVE_JOB_NOT_DRAINED")
        # The in-process authority expires with the original child. An
        # exited process must NEVER be reusable via the same retained object.
        try:
            retained.require_exact_roster(qd=qd, perp=perp)
        except ValueError:
            pass
        else:
            raise ValueError("R16_PARKED_EXPIRED_RETAINED_OWNER_REUSED")
        if inspect_two_lane_native_roots() != before:
            raise ValueError("R16_PARKED_NATIVE_ROOTS_CHANGED_AFTER_STOP")
        if selected_code()["selected_native_head"] != R16_HEAD:
            raise ValueError("R16_PARKED_SELECTED_RELEASE_CHANGED")
        child.close()
        if not child.closed:
            raise ValueError("R16_PARKED_NATIVE_JOB_NOT_CLOSED")
        child = None
        return validate_result({
            "schema": SCHEMA,
            "status": "R16_OWNED_JOB_READ_ONLY_ROOT_HOLD_STOP_PASS",
            "selected_native_head": R16_HEAD,
            "installed_release": str(RELEASE),
            "installed_source_commit": SOURCE,
            "parked_original_process_identity_verified": True,
            "created_suspended_before_owned_job_assignment": True,
            "original_selected_r16_executable_and_source_verified": True,
            "child_held_all_twelve_original_empty_native_roots": True,
            "original_native_roots_unchanged_after_stop": True,
            "owned_job_one_process_before_stop": True,
            "owned_job_zero_processes_after_stop": True,
            "cooperative_stop_acknowledged": True,
            "owned_process_exited_before_return": True,
            "owned_job_closed_before_return": True,
            "twelve_structural_roles_verified_under_original_retained_job": True,
            "retained_original_job_liveness_checked_three_times": True,
            "expired_retained_job_refused_after_stop": True,
            "live_original_job_financial_activation_explicitly_refused": True,
            "financial_writer_roles_enrolled": 0,
            "financial_account_files_created": 0,
            "market_provider_requests": 0,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        })
    finally:
        try:
            if child is not None:
                child.close()
        finally:
            try:
                if stop is not None:
                    api.close_handle(stop)
            finally:
                api.close_handle(signal)


def main():
    print(json.dumps(inspect(), sort_keys=True))


if __name__ == "__main__":
    main()
