"""Selected R17 original Windows Job + 12 EMPTY PAPER roots: bounded probe.

One genuine installed R17 below-normal suspended child; Job assignment before
resume, original Job/PROCESS handles retained, empty original account-root
handles checked inside child, native READY -> STOP -> Job fully drained.
No activation/financial writer, accounts, provider, source grants, or PAPER
orders. A stopped owner is never a reusable financial capability.
"""
from __future__ import annotations

import argparse
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

from scripts.observation_runtime.atlas_r15_disposable_writer_process_audit import (
    _windows_handle_identity,
)
from scripts.observation_runtime.atlas_r15_native_job_admission_preflight import (
    BELOW_NORMAL_PRIORITY_CLASS,
    CREATE_SUSPENDED,
    _exited_creation_filetime,
    _wait_exit,
)
from scripts.observation_runtime.atlas_r15_parked_writer_owner import (
    CHILD as R15_EMPTY_ROOT_CHILD,
)
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    HEAD,
    SOURCE,
    require_selected_r17_nonfinancial,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    ROLES,
    inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_native_job import (
    AdmissionFailure,
    launch_contained_child,
)
from scripts.observation_runtime.personal_native_windows_api import (
    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    PROCESS_INFORMATION,
    STARTUPINFOW,
    WindowsJobAPI,
)

SCHEMA = "ATLAS_R17_SELECTED_ORIGINAL_WINDOWS_JOB_EMPTY_ROOT_STOP_V1"
RELEASE = Path("D:/AtlasRuntime/releases") / SOURCE
IMAGE = str(RELEASE / "python/python.exe")
CHILD = R15_EMPTY_ROOT_CHILD.replace("R15_PARKED", "R17_PARKED")
WAIT_OBJECT_0 = 0
DETACHED_PROCESS = 0x00000008
RECEIPT = Path(
    'D:/Work/Project Atlas/logs/diagnostics/'
    'atlas-r17-r07-original-nonfinancial-job-20261112.json'
)


def exact_process(api, handle, *, expected_pid=None):
    k = api.kernel32
    k.GetProcessId.argtypes = [wintypes.HANDLE]
    k.GetProcessId.restype = wintypes.DWORD
    pid = int(k.GetProcessId(handle))
    observed = _windows_handle_identity(handle)
    if (pid <= 0 or (expected_pid is not None and pid != expected_pid)
            or type(observed.get("creation_filetime")) is not int
            or observed["creation_filetime"] <= 0
            or ntpath.normcase(ntpath.normpath(observed.get("image","")))
               != ntpath.normcase(ntpath.normpath(IMAGE))):
        raise ValueError("R17_PARKED_ORIGINAL_INSTALLED_PROCESS_CHANGED")
    return {
        "pid": pid, "creation_filetime": observed["creation_filetime"],
        "image": observed["image"],
    }


def validate_report(row):
    fields = {
        "schema", "status", "selected_head", "installed_release",
        "installed_original_python_image_verified",
        "suspended_before_owned_job_assignment",
        "one_original_job_process_while_ready",
        "child_held_all_twelve_original_empty_account_roots",
        "original_windows_job_and_process_identity_stable",
        "kill_on_job_close_native_policy_verified",
        "cooperative_stop_acknowledged",
        "owned_child_exited_before_return",
        "owned_job_zero_active_processes_after_stop",
        "original_native_root_ids_unchanged",
        "financial_writer_enrolled", "native_financial_account_files_created",
        "provider_requests", "paper_start_authorized",
        "live_trading_authorized", "owned_child_retained_after_return",
    }
    if (type(row) is not dict or set(row) != fields
            or row["schema"] != SCHEMA
            or row["status"] != "R17_ORIGINAL_JOB_NONFINANCIAL_ROOT_HOLD_STOP_PASS"
            or row["selected_head"] != HEAD
            or row["installed_release"] != str(RELEASE)
            or any(row[k] is not True for k in (
                "installed_original_python_image_verified",
                "suspended_before_owned_job_assignment",
                "one_original_job_process_while_ready",
                "child_held_all_twelve_original_empty_account_roots",
                "original_windows_job_and_process_identity_stable",
                "kill_on_job_close_native_policy_verified",
                "cooperative_stop_acknowledged",
                "owned_child_exited_before_return",
                "owned_job_zero_active_processes_after_stop",
                "original_native_root_ids_unchanged"))
            or any(type(row[k]) is not int or row[k] != 0 for k in (
                "financial_writer_enrolled", "native_financial_account_files_created",
                "provider_requests"))
            or any(row[k] is not False for k in (
                "paper_start_authorized", "live_trading_authorized",
                "owned_child_retained_after_return"))):
        raise ValueError("R17_PARKED_ORIGINAL_JOB_NONFINANCIAL_REPORT_REFUSED")
    return row


def probe():
    """Bounded one-shot local native PROCESS; all handles closed on every exit."""
    if os.name != "nt" or sys.platform != "win32":
        raise ValueError("R17_PARKED_EXACT_WINDOWS_HOST_REQUIRED")
    selected = require_selected_r17_nonfinancial()
    if (selected["release"] != SOURCE or selected["artifact_digest"] == ""
            or not Path(IMAGE).is_file()):
        raise ValueError("R17_PARKED_REAL_SELECTED_INSTALLED_IMAGE_REQUIRED")
    before = inspect_two_lane_native_roots()
    if (before["native_root_total"] != 12
            or before["native_root_ids_verified"] != 12
            or before["existing_empty_root_namespaces"] != 12
            or before["all_twelve_distinct_and_empty"] is not True):
        raise ValueError("R17_PARKED_TWELVE_EMPTY_ORIGINAL_ROOTS_REQUIRED")
    roots = {}
    for lane in ("QUALITY_DIPS", "HYPERLIQUID"):
        items = before["lanes"][lane]["roots"]
        if type(items) is not dict or set(items) != set(ROLES):
            raise ValueError("R17_PARKED_REAL_SIX_ORIGINAL_ROOT_ROLES_REQUIRED")
        roots[lane] = {
            role: {
                "path": items[role]["path"], "native_id": items[role]["native_id"],
            } for role in ROLES
        }
    api = WindowsJobAPI()
    k = api.kernel32
    k.CreateEventW.argtypes = [
        ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR,
    ]
    k.CreateEventW.restype = wintypes.HANDLE
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.SetEvent.argtypes = [wintypes.HANDLE]
    k.SetEvent.restype = wintypes.BOOL
    k.IsProcessInJob.argtypes = [
        wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL),
    ]
    k.IsProcessInJob.restype = wintypes.BOOL
    ready_name = "Local\\AtlasR17NonfinancialRootReady-" + secrets.token_hex(16)
    stop_name = "Local\\AtlasR17NonfinancialRootStop-" + secrets.token_hex(16)
    ready = k.CreateEventW(None, False, False, ready_name)
    if not ready:
        raise ctypes.WinError(ctypes.get_last_error())
    stop, child = None, None
    try:
        stop = k.CreateEventW(None, False, False, stop_name)
        if not stop:
            raise ctypes.WinError(ctypes.get_last_error())
        arguments = json.dumps({
            "selected_head": HEAD,
            "installed_root": str(RELEASE),
            "ready_event": ready_name, "stop_event": stop_name,
            "roots": roots,
        }, sort_keys=True, separators=(",",":"))
        command = subprocess.list2cmdline(
            [IMAGE, "-I", "-B", "-S", "-c", CHILD, arguments],
        )
        if len(command) > 28000:
            raise ValueError("R17_PARKED_NATIVE_CHILD_ARGUMENTS_TOO_LARGE")

        def suspended_creator(candidate):
            if candidate != command:
                raise ValueError("R17_PARKED_EXACT_HARMLESS_CHILD_COMMAND_REQUIRED")
            startup = STARTUPINFOW()
            startup.cb = ctypes.sizeof(startup)
            proc = PROCESS_INFORMATION()
            line = ctypes.create_unicode_buffer(command)
            if not k.CreateProcessW(
                IMAGE, line, None, None, False,
                CREATE_SUSPENDED | DETACHED_PROCESS | BELOW_NORMAL_PRIORITY_CLASS,
                None, str(RELEASE),
                ctypes.byref(startup), ctypes.byref(proc),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            return proc.hProcess, proc.hThread

        api.suspended_creator = suspended_creator
        first = {}
        try:
            child = launch_contained_child(
                api, command,
                verify_suspended=lambda process, _thread:
                    first.update(exact_process(api, process)) is None,
            )
        except AdmissionFailure as exc:
            if not exc.cleanup.closed:
                exc.cleanup.close()
            raise ValueError("R17_PARKED_JOB_CHILD_ADMISSION_REFUSED") from exc
        if k.WaitForSingleObject(ready, 9000) != WAIT_OBJECT_0:
            raise ValueError("R17_PARKED_CHILD_DID_NOT_HOLD_ORIGINAL_ROOTS")
        if exact_process(api, child.process, expected_pid=first["pid"]) != first:
            raise ValueError("R17_PARKED_ORIGINAL_PROCESS_ID_CHANGED")
        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        if (not k.QueryInformationJobObject(
                child.job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                ctypes.byref(limits), ctypes.sizeof(limits), None)
                or not (limits.BasicLimitInformation.LimitFlags
                        & JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)):
            raise ValueError("R17_PARKED_NATIVE_KILL_ON_JOB_CLOSE_REQUIRED")
        member = wintypes.BOOL()
        if (not k.IsProcessInJob(
                child.process, child.job, ctypes.byref(member))
                or not member.value or api.active_processes(child.job) != 1):
            raise ValueError("R17_PARKED_ORIGINAL_PROCESS_NOT_IN_OWNED_JOB")
        for _ in range(3):
            if (exact_process(api,child.process, expected_pid=first["pid"]) != first
                    or api.active_processes(child.job) != 1
                    or inspect_two_lane_native_roots() != before
                    or require_selected_r17_nonfinancial() != selected):
                raise ValueError("R17_PARKED_LIVE_ORIGINAL_NATIVE_OWNER_DRIFT")
            time.sleep(.05)
        if not k.SetEvent(stop):
            raise ValueError("R17_PARKED_COOPERATIVE_LOCAL_STOP_NOT_SIGNALED")
        if (_wait_exit(api, child.process, timeout_ms=5000) != 0
                or _exited_creation_filetime(api,child.process)
                   != first["creation_filetime"]):
            raise ValueError("R17_PARKED_CHILD_NOT_DURABLY_STOPPED")
        deadline = time.monotonic()+2.0
        while api.active_processes(child.job) and time.monotonic()<deadline:
            time.sleep(.025)
        if api.active_processes(child.job) != 0:
            raise ValueError("R17_PARKED_ORIGINAL_JOB_NOT_FULLY_DRAINED")
    finally:
        try:
            if child is not None:
                child.close()
                if not child.closed:
                    raise ValueError("R17_PARKED_OWNED_CHILD_HANDLES_NOT_CLOSED")
        finally:
            if stop is not None:
                api.close_handle(stop)
            api.close_handle(ready)
    if (inspect_two_lane_native_roots()!=before
            or require_selected_r17_nonfinancial()!=selected):
        raise ValueError("R17_PARKED_AFTER_STOP_ORIGINAL_NATIVE_IDENTITY_CHANGED")
    return validate_report({
        "schema": SCHEMA,
        "status": "R17_ORIGINAL_JOB_NONFINANCIAL_ROOT_HOLD_STOP_PASS",
        "selected_head": HEAD,
        "installed_release": str(RELEASE),
        "installed_original_python_image_verified": True,
        "suspended_before_owned_job_assignment": True,
        "one_original_job_process_while_ready": True,
        "child_held_all_twelve_original_empty_account_roots": True,
        "original_windows_job_and_process_identity_stable": True,
        "kill_on_job_close_native_policy_verified": True,
        "cooperative_stop_acknowledged": True,
        "owned_child_exited_before_return": True,
        "owned_job_zero_active_processes_after_stop": True,
        "original_native_root_ids_unchanged": True,
        "financial_writer_enrolled": 0,
        "native_financial_account_files_created": 0,
        "provider_requests": 0,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
        "owned_child_retained_after_return": False,
    })


SCOPE = "R17_ORIGINAL_JOB_TWELVE_EMPTY_NATIVE_ROOTS_READONLY_NO_TRADING"


def inspect():
    """Inspect genuine current selected code + empty roots WITHOUT launch."""
    selected = require_selected_r17_nonfinancial()
    roots = inspect_two_lane_native_roots()
    if (roots["native_root_total"] != 12
            or roots["all_twelve_distinct_and_empty"] is not True):
        raise ValueError("R17_PARKED_READONLY_GENUINE_ROOTS_NOT_EMPTY")
    return {
        "schema": SCHEMA,
        "status": "R17_EXACT_NONFINANCIAL_JOB_TEST_NOT_EXECUTED",
        "selected_source_commit": selected["release"],
        "selected_release_digest": selected["artifact_digest"],
        "original_twelve_native_roots_verified_empty": True,
        "windows_job_child_started": False,
        "financial_writer_enrolled": False,
        "native_paper_account_created": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect", action="store_true")
    group.add_argument("--execute-readonly", action="store_true")
    parser.add_argument("--confirm-scope")
    args = parser.parse_args(argv)
    if args.inspect:
        if args.confirm_scope is not None:
            parser.error("R17_PARKED_INSPECTION_MUST_NOT_INCLUDE_EXECUTION_SCOPE")
        print(json.dumps(inspect(), sort_keys=True), flush=True)
        return 0
    if args.confirm_scope != SCOPE:
        parser.error("R17_PARKED_EXACT_NONFINANCIAL_CHILD_SCOPE_REQUIRED")
    # The real bounded native child inherits the host's restricted process
    # affinity and low-priority startup. Refuse busy-host admission; never
    # launch multiple workers or run a permanent financial process here.
    from scripts.observation_runtime.atlas_r17_cpu_budget import NativeR17CpuBudget

    if os.path.lexists(RECEIPT):
        raise ValueError('R17_PARKED_EXACT_RECEIPT_EXISTS_NO_SECOND_LAUNCH')
    with NativeR17CpuBudget() as cpu:
        cpu.pulse()
        report = probe()
        cpu.pulse()
    raw = (json.dumps(report, sort_keys=True, indent=2)+'\n').encode('utf-8')
    fd = os.open(RECEIPT, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_BINARY, 0o600)
    with os.fdopen(fd, 'wb') as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
