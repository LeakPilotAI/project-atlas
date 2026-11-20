"""Bounded real Windows suspended R15 child -> Job Object ownership rehearsal.

No accounts, source feeds, native root mutations, delegated financial authority,
writer roster, or persistent service. Exercises the existing dependency-injected
personal_native_job implementation using a narrowly bounded real Windows
suspended process creator, then proves normal exit and owned Job termination.
The creator is local to this diagnostic; the financial launch adapter stays
blocked. Never terminate by PID or kill an unknown process.
"""
import ctypes
import ntpath
import os
import subprocess
import sys
import time
from ctypes import wintypes

from scripts.observation_runtime.atlas_r15_disposable_writer_process_audit import (
    EXECUTABLE, RELEASE, _windows_handle_identity,
)
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    SELECTED_HEAD, selected_code,
)
from scripts.observation_runtime.personal_native_job import (
    AdmissionFailure, launch_contained_child,
)
from scripts.observation_runtime.personal_native_windows_api import (
    PROCESS_INFORMATION, STARTUPINFOW, WindowsJobAPI,
)

SCHEMA = "ATLAS_R15_REAL_SUSPENDED_JOB_CONTAINMENT_NONFINANCIAL_V1"
CREATE_SUSPENDED = 0x00000004
CREATE_NO_WINDOW = 0x08000000
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
STILL_ACTIVE = 259
EXPECTED_IMAGE = str(EXECUTABLE)


def _exact_process(api, handle, *, expected_pid=None):
    api.kernel32.GetProcessId.argtypes = [wintypes.HANDLE]
    api.kernel32.GetProcessId.restype = wintypes.DWORD
    pid = int(api.kernel32.GetProcessId(handle))
    observed = _windows_handle_identity(handle)
    if (pid <= 0 or (expected_pid is not None and pid != expected_pid)
            or type(observed["creation_filetime"]) is not int
            or observed["creation_filetime"] <= 0
            or ntpath.normcase(ntpath.normpath(observed["image"])) !=
               ntpath.normcase(ntpath.normpath(EXPECTED_IMAGE))):
        raise ValueError("R15_CONTAINED_CHILD_PROCESS_IMAGE_OR_INCARCATION_REFUSED")
    return {"pid": pid, "creation_filetime": observed["creation_filetime"],
            "image": observed["image"]}


def _exited_creation_filetime(api, handle):
    """Windows permits GetProcessTimes on owned exited handle, not always image."""
    ft = wintypes.FILETIME
    api.kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE, *([ctypes.POINTER(ft)] * 4)]
    api.kernel32.GetProcessTimes.restype = wintypes.BOOL
    stamps = [ft() for _ in range(4)]
    if not api.kernel32.GetProcessTimes(
            handle, *(ctypes.byref(stamp) for stamp in stamps)):
        raise ValueError("R15_JOB_EXITED_PROCESS_TIME_HANDLE_UNAVAILABLE")
    return (stamps[0].dwHighDateTime << 32) | stamps[0].dwLowDateTime


def _wait_exit(api, handle, *, timeout_ms):
    api.kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.kernel32.WaitForSingleObject.restype = wintypes.DWORD
    state = int(api.kernel32.WaitForSingleObject(handle, timeout_ms))
    if state != WAIT_OBJECT_0:
        raise ValueError("R15_CONTAINED_CHILD_EXIT_NOT_ACKNOWLEDGED")
    code = wintypes.DWORD()
    if not api.kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
        raise ctypes.WinError(ctypes.get_last_error())
    if code.value == STILL_ACTIVE:
        raise ValueError("R15_CONTAINED_CHILD_STILL_ACTIVE_AFTER_EXIT")
    return int(code.value)


def _creator(api, *, seconds):
    """Exact selected R15 isolated harmless no-output Python, suspended."""
    if type(seconds) is not float or seconds not in (0.25, 8.0):
        raise ValueError("R15_CONTAINMENT_TEST_ONLY_KNOWN_DURATION")
    program = (
        "import os,sys,time;"
        "assert os.path.normcase(sys.executable)=="
        "os.path.normcase("+repr(EXPECTED_IMAGE)+");"
        "time.sleep("+repr(seconds)+")"
    )
    command = [EXPECTED_IMAGE, "-I", "-B", "-S", "-c", program]
    expected = subprocess.list2cmdline(command)

    def create(user_command):
        if user_command != expected:
            raise ValueError("R15_JOB_EXACT_HARMLESS_TEST_CHILD_REQUIRED")
        startup = STARTUPINFOW()
        startup.cb = ctypes.sizeof(startup)
        process = PROCESS_INFORMATION()
        line = ctypes.create_unicode_buffer(expected)
        ok = api.kernel32.CreateProcessW(
            EXPECTED_IMAGE, line, None, None, False,
            CREATE_SUSPENDED | CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS,
            None, str(RELEASE), ctypes.byref(startup), ctypes.byref(process))
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())
        return process.hProcess, process.hThread

    return expected, create


def _rehearse(mode):
    if mode not in ("NORMAL_EXIT", "OWNED_JOB_STOP"):
        raise ValueError("R15_JOB_REHEARSAL_MODE")
    api = WindowsJobAPI()
    duration = 0.25 if mode == "NORMAL_EXIT" else 8.0
    command, api.suspended_creator = _creator(api, seconds=duration)
    verified = {}

    def check_suspended(process, thread):
        observed = _exact_process(api, process)
        verified.update(observed)
        return True

    owner = None
    try:
        try:
            owner = launch_contained_child(
                api, command, verify_suspended=check_suspended)
        except AdmissionFailure as exc:
            # The caller retains cleanup on failure; never discard it.
            if not exc.cleanup.closed:
                exc.cleanup.close()
            raise ValueError("R15_REAL_WINDOWS_JOB_ADMISSION_REFUSED") from exc
        before = _exact_process(api, owner.process, expected_pid=verified["pid"])
        if before != verified:
            raise ValueError("R15_JOB_PROCESS_CHANGED_AFTER_RESUME")
        if mode == "NORMAL_EXIT":
            exit_code = _wait_exit(api, owner.process, timeout_ms=5000)
            if exit_code != 0:
                raise ValueError("R15_JOB_HARMLESS_CHILD_NONZERO_EXIT")
        else:
            # Explicit termination only of our own Job handle, not by PID.
            api.terminate_job(owner.job)
            exit_code = _wait_exit(api, owner.process, timeout_ms=5000)
            if exit_code == 0:
                raise ValueError("R15_JOB_TERMINATED_PROCESS_EXITED_NORMALLY")
        if _exited_creation_filetime(api, owner.process) != verified["creation_filetime"]:
            raise ValueError("R15_JOB_PROCESS_INCARCATION_CHANGED")
        # Kernel Job accounting can lag a signaled process handle briefly.
        # Keep the Job handle owned, then accept only actual zero children.
        deadline = time.monotonic() + 2.0
        while api.active_processes(owner.job) != 0 and time.monotonic() < deadline:
            time.sleep(.025)
        if api.active_processes(owner.job) != 0:
            raise ValueError("R15_JOB_CHILD_OR_DESCENDANT_ACTIVE")
        return {
            "mode": mode, "native_pid": verified["pid"],
            "native_creation_filetime": verified["creation_filetime"],
            "installed_image_verified": True,
            "suspended_identity_checked_before_resume": True,
            "assigned_to_real_job_before_resume": True,
            "job_kill_on_close_configured": True,
            "bounded_child_exit_observed": True,
            "exit_code": exit_code,
            "owned_job_active_processes_after_exit": 0,
            "no_financial_account_or_provider_usage": True,
        }
    finally:
        if owner is not None:
            owner.close()
            if not owner.closed:
                raise ValueError("R15_JOB_OWNED_HANDLES_NOT_CLOSED")


def validate_result(value):
    """Pure final proof: no subprocess result can be promoted to enrollment."""
    if (type(value) is not dict or set(value) != {
            "schema", "status", "selected_native_head", "selected_release",
            "runs", "active_children_after_check",
            "new_financial_accounts", "native_financial_writes",
            "persistent_writer_enrolled", "paper_start_authorized",
            "real_money_orders_authorized", "network_requests"}
            or value["schema"] != SCHEMA
            or value["status"] != "REAL_SUSPENDED_R15_JOB_CONTAINMENT_REHEARSAL_PASS"
            or value["selected_native_head"] != SELECTED_HEAD
            or value["selected_release"] != str(RELEASE)
            or type(value["runs"]) is not list or len(value["runs"]) != 2
            or [r.get("mode") for r in value["runs"]] != [
                "NORMAL_EXIT", "OWNED_JOB_STOP"]
            or value["runs"][0]["native_pid"] == value["runs"][1]["native_pid"]
            or value["runs"][0]["native_creation_filetime"] ==
                value["runs"][1]["native_creation_filetime"]
            or any(type(r.get("native_pid")) is not int or r["native_pid"] <= 0
                   or type(r.get("native_creation_filetime")) is not int
                   or r["native_creation_filetime"] <= 0
                   or r.get("owned_job_active_processes_after_exit") != 0
                   or any(r.get(k) is not True for k in (
                       "installed_image_verified",
                       "suspended_identity_checked_before_resume",
                       "assigned_to_real_job_before_resume",
                       "job_kill_on_close_configured",
                       "bounded_child_exit_observed",
                       "no_financial_account_or_provider_usage"))
                   for r in value["runs"])
            or value["runs"][0]["exit_code"] != 0
            or value["runs"][1]["exit_code"] == 0
            or value["active_children_after_check"] != 0
            or value["new_financial_accounts"] != 0
            or value["native_financial_writes"] != 0
            or value["network_requests"] != 0
            or any(value.get(k) is not False for k in (
                "persistent_writer_enrolled", "paper_start_authorized",
                "real_money_orders_authorized"))):
        raise ValueError("R15_REAL_JOB_CONTAINMENT_PROOF_OR_FINANCIAL_AUTHORITY_REFUSED")
    return value


def inspect():
    if os.name != "nt" or sys.platform != "win32":
        raise ValueError("R15_REAL_JOB_WINDOWS_ONLY")
    selected = selected_code()
    if (selected.get("revision") != 14
            or selected.get("selected_native_head") != SELECTED_HEAD
            or selected.get("financial_authority") is not False
            or not EXECUTABLE.is_file()
            or EXECUTABLE.is_symlink()):
        raise ValueError("R15_JOB_SELECTED_RELEASE_OR_AUTHORITY_REFUSED")
    runs = []
    for mode in ("NORMAL_EXIT", "OWNED_JOB_STOP"):
        runs.append(_rehearse(mode))
    if selected_code() != selected:
        raise ValueError("R15_JOB_SELECTED_RELEASE_CHANGED")
    return validate_result({
        "schema": SCHEMA,
        "status": "REAL_SUSPENDED_R15_JOB_CONTAINMENT_REHEARSAL_PASS",
        "selected_native_head": SELECTED_HEAD,
        "selected_release": str(RELEASE),
        "runs": runs,
        "active_children_after_check": 0,
        "new_financial_accounts": 0,
        "native_financial_writes": 0,
        "persistent_writer_enrolled": False,
        "paper_start_authorized": False,
        "real_money_orders_authorized": False,
        "network_requests": 0,
    })


if __name__ == "__main__":
    import json
    print(json.dumps(inspect(), sort_keys=True))
