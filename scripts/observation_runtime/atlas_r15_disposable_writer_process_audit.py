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


# Bounded live-handle pre-enrollment feasibility check. This is NOT a
# native writer enrollment, and handles are closed when the child exits.
ROOT_CHILD = r'''
import json
import os
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from scripts.observation_runtime.personal_paper_inception import native_primitives
from scripts.observation_runtime.quality_dips_read_service import observe_self
from scripts.observation_runtime.personal_version_safe_release_clock import (
    require_native_version_safe_clock_source,
)

planned = json.loads(sys.argv[1])
if (type(planned) is not list or len(planned) != 12
        or len({item["path"].casefold() for item in planned}) != 12):
    raise ValueError("NATIVE_READ_ONLY_TWELVE_ROOTS_REQUIRED")
native = native_primitives()
with ExitStack() as owned:
    first = []
    handles = []
    for item in planned:
        path = Path(item["path"])
        if (not path.is_dir() or path.is_symlink() or path.is_junction()
                or not str(path).startswith("D:\\")
                or any(path.iterdir())):
            raise ValueError("NATIVE_READ_ONLY_UNCHANGED_ROOT_REQUIRED")
        output = owned.enter_context(native.w.WindowsOutput(str(path)))
        actual = native.native.file_identity(output.root_handle)
        if actual != item["native_id"] or any(path.iterdir()):
            raise ValueError("NATIVE_READ_ONLY_ROOT_HANDLE_CHANGED")
        handles.append((path, output))
        first.append({"lane": item["lane"], "role": item["role"],
                      "path": str(path), "native_id": actual})
    # The existing genuine native handles stay open while this bounded
    # observation-only process is alive. No financial source or ledger opened.
    time.sleep(1.2)
    second = []
    for (path, output), item in zip(handles, first, strict=True):
        output._verify()
        actual = native.native.file_identity(output.root_handle)
        if actual != item["native_id"] or any(path.iterdir()):
            raise ValueError("NATIVE_READ_ONLY_ROOT_IDENTITY_LOST")
        second.append({"lane": item["lane"], "role": item["role"],
                       "path": str(path), "native_id": actual})
    result = {
        "schema": "ATLAS_R15_INSTALLED_EXISTING_12_ROOT_HANDLES_LIFETIME_V1",
        "installed_self": observe_self(),
        "selected_native_head": require_native_version_safe_clock_source(deep=False),
        "opened_first": first, "rechecked_before_exit": second,
        "financial_account_enrolled": False,
        "writer_lease_issued": False,
        "financial_paper_start": False,
        "live_trading": False,
        "native_files_created": 0,
        "provider_calls": 0,
    }
    print(json.dumps(result, sort_keys=True), flush=True)
'''


def verify_root_handle_lifetime(child, *, expected_roots, native_pid, parent,
                                release=RELEASE, selected_head=SELECTED_HEAD):
    """Pure strict comparison of temporary selected-R15 handle observations."""
    if (type(expected_roots) is not dict
            or expected_roots.get("schema") !=
                "ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1"
            or expected_roots.get("native_root_total") != 12
            or expected_roots.get("native_root_ids_verified") != 12
            or expected_roots.get("existing_empty_root_namespaces") != 12
            or expected_roots.get("all_twelve_distinct_and_empty") is not True
            or type(child) is not dict
            or set(child) != {
                "schema", "installed_self", "selected_native_head",
                "opened_first", "rechecked_before_exit",
                "financial_account_enrolled", "writer_lease_issued",
                "financial_paper_start", "live_trading",
                "native_files_created", "provider_calls"}
            or child["schema"] != "ATLAS_R15_INSTALLED_EXISTING_12_ROOT_HANDLES_LIFETIME_V1"
            or child["selected_native_head"] != selected_head
            or any(child[k] is not False for k in (
                "financial_account_enrolled", "writer_lease_issued",
                "financial_paper_start", "live_trading"))
            or child["native_files_created"] != 0 or child["provider_calls"] != 0):
        raise ValueError("R15_NATIVE_12_ROOT_AUTHORITY_OR_SOURCE_REFUSED")
    from scripts.observation_runtime.personal_existing_native_resource_evidence import ROLES

    expected = []
    if set(expected_roots.get("lanes", {})) != {"HYPERLIQUID", "QUALITY_DIPS"}:
        raise ValueError("R15_NATIVE_TWO_LANE_SCOPE_REQUIRED")
    for lane in ("HYPERLIQUID", "QUALITY_DIPS"):
        src = expected_roots["lanes"][lane]["roots"]
        if set(src) != set(ROLES):
            raise ValueError("R15_NATIVE_EXACT_ROOT_ROLES_REQUIRED")
        for role in ROLES:
            item = src[role]
            if (item["native_identity_verified"] is not True
                    or item["existing_empty_namespace_verified"] is not True
                    or type(item["native_id"]) is not list
                    or len(item["native_id"]) != 3):
                raise ValueError("R15_NATIVE_12_ROOT_EXPECTED_IDENTITY_REFUSED")
            expected.append({
                "lane": lane, "role": role,
                "path": item["path"], "native_id": item["native_id"],
            })
    if (child["opened_first"] != expected
            or child["rechecked_before_exit"] != expected
            or len({tuple(r["native_id"]) for r in expected}) != 12
            or len({r["path"].casefold() for r in expected}) != 12):
        raise ValueError("R15_NATIVE_12_ROOT_HANDLE_CONTINUITY_REFUSED")
    observed = child["installed_self"]
    expected_image = str(Path(release) / "python/python.exe")
    if (type(observed) is not dict
            or set(observed) != {"pid", "creation_filetime", "image"}
            or type(native_pid) is not int or native_pid <= 0
            or type(parent) is not dict
            or type(parent.get("creation_filetime")) is not int
            or parent["creation_filetime"] <= 0
            or type(parent.get("image")) is not str
            or type(observed["pid"]) is not int or observed["pid"] != native_pid
            or type(observed["creation_filetime"]) is not int
            or observed["creation_filetime"] != parent["creation_filetime"]
            or type(observed["image"]) is not str
            or ntpath.normcase(ntpath.normpath(observed["image"])) !=
                ntpath.normcase(ntpath.normpath(parent["image"]))
            or ntpath.normcase(ntpath.normpath(observed["image"])) !=
                ntpath.normcase(ntpath.normpath(expected_image))):
        raise ValueError("R15_NATIVE_ROOT_HANDLE_OR_PROCESS_IDENTITY_REFUSED")
    return {
        "schema": "ATLAS_R15_TWO_LANE_SHORT_LIVED_ROOT_HANDLE_PROOF_V1",
        "status": "INSTALLED_NATIVE_R15_TWELVE_READ_ONLY_ROOT_HANDLES_RECHECKED",
        "actual_existing_native_roots_verified": 12,
        "root_handles_held_and_rechecked_in_same_process": True,
        "process_native_pid_observed": native_pid,
        "process_native_creation_filetime": observed["creation_filetime"],
        "native_selected_release": str(release),
        "selected_native_head": selected_head,
        "financial_writer_process_enrolled": False,
        "financial_writer_lease_active": False,
        "native_paper_account_inception": False,
        "paper_start_authorized": False,
        "real_money_order_authorized": False,
        "native_financial_files_written": 0,
        "market_provider_requests": 0,
    }


def inspect_two_lane_native_root_handles():
    """Bounded one-child real R15 root-handle check, followed by confirmed exit."""
    import time
    from scripts.observation_runtime.personal_existing_native_resource_evidence import (
        ROLES, inspect_two_lane_native_roots,
    )

    selected_before = selected_code()
    roots_before = inspect_two_lane_native_roots()
    if (selected_before.get("revision") != 14
            or selected_before.get("selected_native_head") != SELECTED_HEAD
            or selected_before.get("financial_authority") is not False
            or roots_before.get("all_twelve_distinct_and_empty") is not True
            or not EXECUTABLE.is_file() or EXECUTABLE.is_symlink()):
        raise ValueError("R15_ROOT_HANDLES_SELECTED_RELEASE_OR_ROOT_PRECONDITION_REFUSED")
    requested = []
    for lane in ("HYPERLIQUID", "QUALITY_DIPS"):
        for role in ROLES:
            row = roots_before["lanes"][lane]["roots"][role]
            requested.append({
                "lane": lane, "role": role, "path": row["path"],
                "native_id": row["native_id"],
            })
    process = None
    try:
        env = {
            k: os.environ[k] for k in (
                "SystemRoot", "WINDIR", "TEMP", "TMP", "PATH")
        }
        env["PYTHONPATH"] = ";".join((str(RELEASE), str(RELEASE / "backend")))
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        flags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
        flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(
            [str(EXECUTABLE), "-B", "-u", "-c", ROOT_CHILD,
             json.dumps(requested, separators=(",", ":"))],
            cwd=str(RELEASE), env=env, creationflags=flags,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8")
        # Native HANDLE observations and liveness throughout a short interval,
        # NEVER PID lookup or termination of a process we do not own.
        samples = []
        for _ in range(3):
            if process.poll() is not None:
                raise ValueError("R15_ROOT_HANDLES_CHILD_PREMATURE_EXIT")
            samples.append(_windows_handle_identity(process._handle))
            time.sleep(.15)
        if any(sample != samples[0] for sample in samples[1:]):
            raise ValueError("R15_ROOT_HANDLES_PARENT_PROCESS_INCARNATION_CHANGED")
        stdout, stderr = process.communicate(timeout=12)
        if (process.returncode != 0
                or stderr.strip()
                or len(stdout.splitlines()) != 1):
            raise ValueError("R15_ROOT_HANDLES_CHILD_OUTPUT_OR_EXIT_REFUSED")
        child = json.loads(stdout)
        qualified = verify_root_handle_lifetime(
            child, expected_roots=roots_before, native_pid=process.pid,
            parent=samples[0])
        if (selected_code() != selected_before
                or inspect_two_lane_native_roots() != roots_before):
            raise ValueError("R15_ROOT_HANDLES_NATIVE_RELEASE_OR_ROOTS_CHANGED")
        qualified["sample_count_while_process_alive"] = len(samples)
        qualified["child_exited_and_handles_closed"] = True
        qualified["all_twelve_root_ids_unchanged_after_exit"] = True
        return qualified
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
