"""Actual selected R15 Python process dual-observer identity qualification.

Starts ONE disposable, read-only selected R15 Python child. Verifies the child
self-reported Windows creation FILETIME/image against its parent-owned genuine
Windows process HANDLE and authentic installed module paths. Child automatically
exits; the sampled PID must NEVER be reused for account enrollment or orders.
No native root creation, provider, clock network, lease, financial writer or
account authorization. Bounded local subprocess only.
"""
import ctypes
import hashlib
import json
import ntpath
import os
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    RELEASE, SELECTED_HEAD, selected_code,
)

SCHEMA = "ATLAS_R15_SELECTED_DISPOSABLE_NATIVE_SELF_HANDLE_AUDIT_V1"
EXECUTABLE = RELEASE / "python/python.exe"
CHILD = r'''
import inspect
import json
import os
import sys
from pathlib import Path
from scripts.observation_runtime import personal_writer_self_binding_probe as probe
from scripts.observation_runtime import quality_dips_read_service as reader
from scripts.observation_runtime import personal_version_safe_release_clock as clock

root=Path.cwd().resolve()
paths={
    'personal_writer_self_binding_probe':
        str(Path(inspect.getfile(probe)).resolve()),
    'quality_dips_read_service':
        str(Path(inspect.getfile(reader)).resolve()),
    'personal_version_safe_release_clock':
        str(Path(inspect.getfile(clock)).resolve()),
}
result={
    'schema':'ATLAS_SELECTED_R15_NATIVE_TEMPORARY_PROCESS_SELF_OBSERVATION_V1',
    'self_binding':probe.inspect(expected_executable=str(root/'python/python.exe')),
    'installed_source_paths':paths,
    'selected_clock_source_head':clock.require_native_version_safe_clock_source(deep=False),
    'financial_account_enrolled':False,
    'writer_ownership_lease_issued':False,
    'paper_start_authorized':False,
    'live_trading_authorized':False,
}
print(json.dumps(result,sort_keys=True),flush=True)
# The process exits by itself; a parent HANDLE is observed while the child
# imports installed modules. The PID is never accepted into a writer roster.
'''


def _windows_handle_identity(handle):
    if os.name != "nt":
        raise ValueError("R15_PROCESS_HANDLE_WINDOWS_ONLY")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetProcessTimes.argtypes = [
        wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD,
        wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    stamps = [wintypes.FILETIME() for _ in range(4)]
    image = ctypes.create_unicode_buffer(32768)
    length = wintypes.DWORD(32768)
    if (not kernel.GetProcessTimes(
            handle, *(ctypes.byref(stamp) for stamp in stamps))
            or not kernel.QueryFullProcessImageNameW(
                handle, 0, image, ctypes.byref(length))):
        raise ValueError("R15_PROCESS_PARENT_WINDOWS_HANDLE_UNAVAILABLE")
    return {
        "pid_observed_by_parent_process_handle": None,
        "creation_filetime": (
            (stamps[0].dwHighDateTime << 32) |
            stamps[0].dwLowDateTime),
        "image": image.value,
    }


def validate_report(*, child, native_pid, parent, release, expected_head):
    """Pure tamper/refusal check; never creates or accepts a writer identity."""
    release = Path(release)
    expected_executable = str(release / "python/python.exe")
    if (type(child) is not dict
            or set(child) != {
                "schema", "self_binding", "installed_source_paths",
                "selected_clock_source_head", "financial_account_enrolled",
                "writer_ownership_lease_issued", "paper_start_authorized",
                "live_trading_authorized"}
            or child["schema"] !=
                "ATLAS_SELECTED_R15_NATIVE_TEMPORARY_PROCESS_SELF_OBSERVATION_V1"
            or any(child.get(flag) is not False for flag in (
                "financial_account_enrolled", "writer_ownership_lease_issued",
                "paper_start_authorized", "live_trading_authorized"))
            or child["selected_clock_source_head"] != expected_head
            or type(native_pid) is not int or native_pid <= 0
            or type(parent) is not dict
            or type(parent.get("creation_filetime")) is not int
            or parent["creation_filetime"] <= 0
            or type(parent.get("image")) is not str):
        raise ValueError("R15_PROCESS_NATIVE_CHILD_OR_SELECTION_REFUSED")
    source = child["installed_source_paths"]
    expected_paths = {
        "personal_writer_self_binding_probe":
            str(release / "scripts/observation_runtime/personal_writer_self_binding_probe.py"),
        "quality_dips_read_service":
            str(release / "scripts/observation_runtime/quality_dips_read_service.py"),
        "personal_version_safe_release_clock":
            str(release / "scripts/observation_runtime/personal_version_safe_release_clock.py"),
    }
    if (type(source) is not dict or set(source) != set(expected_paths)
            or any(type(source[k]) is not str
                   or ntpath.normcase(ntpath.normpath(source[k])) !=
                      ntpath.normcase(ntpath.normpath(v))
                   for k, v in expected_paths.items())):
        raise ValueError("R15_PROCESS_INSTALLED_SOURCE_NOT_NATIVE")
    binding = child["self_binding"]
    if (type(binding) is not dict
            or set(binding) != {
                "schema", "expected_executable", "observed_process",
                "installed_executable_matched", "enrolled_writer_verified",
                "ownership_lease_issued", "paper_start_authorized"}
            or binding["schema"] != "ATLAS_PERSONAL_WRITER_SELF_BINDING_PROBE_V1"
            or binding["installed_executable_matched"] is not True
            or any(binding.get(flag) is not False for flag in (
                "enrolled_writer_verified", "ownership_lease_issued",
                "paper_start_authorized"))
            or ntpath.normcase(ntpath.normpath(binding["expected_executable"])) !=
               ntpath.normcase(ntpath.normpath(expected_executable))):
        raise ValueError("R15_PROCESS_SELF_BINDING_REFUSED")
    observed = binding["observed_process"]
    if (type(observed) is not dict
            or set(observed) != {"pid", "creation_filetime", "image"}
            or type(observed["pid"]) is not int or observed["pid"] != native_pid
            or type(observed["creation_filetime"]) is not int
            or observed["creation_filetime"] != parent["creation_filetime"]
            or type(observed["image"]) is not str
            or ntpath.normcase(ntpath.normpath(observed["image"])) !=
               ntpath.normcase(ntpath.normpath(parent["image"]))
            or ntpath.normcase(ntpath.normpath(observed["image"])) !=
               ntpath.normcase(ntpath.normpath(expected_executable))):
        raise ValueError("R15_PROCESS_PARENT_HANDLE_SELF_IDENTITY_CONFLICT")
    return {
        "schema": SCHEMA,
        "status": "INSTALLED_R15_SHORT_LIVED_PROCESS_SELF_AND_PARENT_HANDLE_AGREE",
        "selected_native_head": expected_head,
        "installed_executable": expected_executable,
        "observed_expired_disposable_child_pid": native_pid,
        "observed_creation_filetime": observed["creation_filetime"],
        "native_module_paths_verified": 3,
        "child_owns_installed_selected_release": True,
        "independent_parent_windows_handle_identity_agreed": True,
        "native_writer_identity_enrollment_usable": False,
        "real_writer_process_currently_enrolled": False,
        "financial_account_activated": False,
        "financial_start_authorized": False,
        "live_trading_authorized": False,
        "provider_requests": 0,
        "native_account_mutations": 0,
    }


def inspect():
    if os.name != "nt" or sys.platform != "win32":
        raise ValueError("R15_PROCESS_NATIVE_WINDOWS_REQUIRED")
    before = selected_code()
    if (before.get("revision") != 14
            or before.get("selected_native_head") != SELECTED_HEAD
            or before.get("financial_authority") is not False
            or before.get("independent_live_financial_clock_lease_accepted") is not False
            or not EXECUTABLE.is_file()
            or EXECUTABLE.is_symlink()):
        raise ValueError("R15_PROCESS_INSTALLED_RELEASE_OR_AUTHORITY_REFUSED")
    process = None
    try:
        env = {
            "SystemRoot": os.environ["SystemRoot"],
            "WINDIR": os.environ["WINDIR"],
            "TEMP": os.environ["TEMP"],
            "TMP": os.environ["TMP"],
            "PATH": os.environ["PATH"],
            "PYTHONPATH": ";".join((str(RELEASE), str(RELEASE / "backend"))),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        process = subprocess.Popen(
            [str(EXECUTABLE), "-B", "-u", "-c", CHILD],
            cwd=str(RELEASE), env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8")
        # Query native HANDLE before waiting, then always finish with a bounded
        # communicate() rather than an unbounded blocking stdout.readline().
        parent = _windows_handle_identity(process._handle)
        stdout, stderr = process.communicate(timeout=15)
        lines = stdout.splitlines()
        if (process.returncode != 0 or len(lines) != 1
                or not lines[0].startswith("{") or stderr.strip()
                or process.poll() is None):
            raise ValueError("R15_PROCESS_SHORT_LIVED_CHILD_EXIT_REFUSED")
        report = validate_report(
            child=json.loads(lines[0]), native_pid=process.pid, parent=parent,
            release=RELEASE, expected_head=SELECTED_HEAD)
        after = selected_code()
        if after != before:
            raise ValueError("R15_PROCESS_SELECTED_RELEASE_CHANGED")
        report["child_exited_and_expired"] = True
        report["parent_reverified_selector_after_exit"] = True
        report["installed_executable_sha256"] = hashlib.sha256(
            EXECUTABLE.read_bytes()).hexdigest()
        return report
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()


if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True))
