"""One explicitly approved disposable run, with an owned Windows Job watchdog.

Never starts an operational service. The Job contains only this run's worker
and descendants. A limit/containment failure terminates that owned Job, preserves
the fixture and refuses acceptance. The root is never adopted or reused.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from ctypes import wintypes as W
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "logs/diagnostics/qd-selector-v1-native-support-final-20261101"
PROPOSAL = REPO / "docs/QD_SUPPORT_DEPLOYMENT_AUTHORIZATION_PROPOSAL_V1_2026-11-01.md"
PROPOSAL_SHA = "bf1303ec30c514c0039596d0c06259d7502973cdfaca64d35e1d1777876fece2"
MAX_SECONDS, MAX_ENTRIES, MAX_BYTES = 600, 40000, 512 * 1024**2
TESTS = ["tests/test_support_deployment.py", "tests/test_support_deployment_native.py",
         "tests/test_installed_nonfinancial_launcher.py", "tests/test_release_selection.py",
         "tests/test_release_selection_native.py", "tests/test_unselected_release_adapter.py"]


def encoded(value):
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def measure(root):
    """Count every name, including hardlink aliases; never traverse reparse nodes."""
    total, entries = 0, 1
    pending = [root]
    while pending:
        with os.scandir(pending.pop()) as rows:
            for row in rows:
                info = row.stat(follow_symlinks=False); entries += 1
                if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                    raise ValueError("RUN_REPARSE_CONTAINMENT_REFUSED")
                if stat.S_ISDIR(info.st_mode):
                    pending.append(Path(row.path))
                elif stat.S_ISREG(info.st_mode):
                    total += info.st_size
                else:
                    raise ValueError("RUN_SPECIAL_ENTRY_REFUSED")
    return {"entries": entries, "logical_bytes": total, "accounted_bytes": total + entries * 4096}


def worker():
    sys.path[:0] = [str(REPO), str(REPO / "backend"), str(REPO / "tests")]
    from scripts.native_copy_test_scope import install_write_audit
    audit = install_write_audit(ROOT)
    import pytest
    class Evidence:
        def __init__(self):
            self.cases, self.details = {}, {}
        def pytest_runtest_logreport(self, report):
            if report.when == "call" or report.failed or report.skipped:
                self.cases[report.nodeid] = report.outcome
                if report.failed:
                    self.details[report.nodeid] = str(report.longrepr)[-16384:]
    evidence = Evidence(); started = time.monotonic()
    rc = pytest.main(["-q", "-p", "no:cacheprovider", "--basetemp", str(ROOT / "pytest"), *TESTS], plugins=[evidence])
    result = {"exit_code": int(rc), "counts": {key: list(evidence.cases.values()).count(key)
              for key in ("passed", "failed", "skipped")}, "cases": evidence.cases,
              "failures": evidence.details, "seconds": round(time.monotonic() - started, 3), "write_audit": audit}
    with (ROOT / "worker-result.json").open("xb") as stream:
        stream.write(encoded(result)); stream.flush(); os.fsync(stream.fileno())
    return int(rc)


class JobLimits(C.Structure):
    _fields_ = [("user", C.c_longlong), ("job_user", C.c_longlong), ("flags", W.DWORD),
                ("min_working", C.c_size_t), ("max_working", C.c_size_t), ("active_limit", W.DWORD),
                ("affinity", C.c_size_t), ("priority", W.DWORD), ("scheduling", W.DWORD)]


class ExtendedLimits(C.Structure):
    _fields_ = [("basic", JobLimits), ("io", C.c_ulonglong * 6), ("process_memory", C.c_size_t),
                ("job_memory", C.c_size_t), ("peak_process", C.c_size_t), ("peak_job", C.c_size_t)]


class Accounting(C.Structure):
    _fields_ = [("times", C.c_longlong * 4), ("faults", W.DWORD), ("total", W.DWORD),
                ("active", W.DWORD), ("terminated", W.DWORD)]


def supervisor():
    import _winapi
    import msvcrt
    sys.path[:0] = [str(REPO), str(REPO / "backend")]
    from scripts.native_copy_test_scope import confined_environment
    from scripts.support_deployment import prepare
    if os.name != "nt" or Path.cwd() != REPO:
        raise ValueError("EXACT_WINDOWS_WORKSPACE_REQUIRED")
    if hashlib.sha256(PROPOSAL.read_bytes()).hexdigest() != PROPOSAL_SHA:
        raise ValueError("APPROVED_PROPOSAL_CHANGED")
    if os.path.lexists(ROOT):
        raise ValueError("ONE_RUN_ROOT_EXISTS_NO_RETRY")
    for p in ROOT.parents:
        if getattr(p.lstat(), "st_file_attributes", 0) & 0x400 or p.is_symlink():
            raise ValueError("APPROVED_ROOT_ANCESTOR_REFUSED")
    if shutil.disk_usage(ROOT.parent).free < MAX_BYTES:
        raise ValueError("INSUFFICIENT_APPROVED_FIXTURE_CAPACITY")
    m = json.loads((REPO / "docs/QD_SUPPORT_DEPLOYMENT_MANIFEST_V1_2026-11-01.json").read_bytes())
    _, files = prepare(m, REPO / "logs/diagnostics/qd-support-deployment-reviewed-source-20261101/support-source.zip",
                       "260438e7ca62713ce5911cf0f43c7be0ef01115dc22d4f9c3fb014cc2175bc8f")
    for name, raw in files.items():
        if name != "support-manifest.json" and (REPO / name).read_bytes().replace(b"\r\n", b"\n") != raw:
            raise ValueError("REVIEWED_SOURCE_CHANGED_BEFORE_RUN")
    k = C.WinDLL("kernel32", use_last_error=True)
    declarations = {
        "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
        "SetInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
        "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
        "ResumeThread": ([W.HANDLE], W.DWORD),
        "QueryInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL),
        "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL), "CloseHandle": ([W.HANDLE], W.BOOL),
    }
    for name, (args, result) in declarations.items():
        getattr(k, name).argtypes, getattr(k, name).restype = args, result
    def check(value):
        if not value:
            raise C.WinError(C.get_last_error())
    job = k.CreateJobObjectW(None, None); check(job)
    config = ExtendedLimits(); config.basic.flags = 0x2000  # own descendants only, kill on close
    try:
        check(k.SetInformationJobObject(job, 9, C.byref(config), C.sizeof(config)))
    except BaseException:
        check(k.CloseHandle(job)); raise
    started = time.monotonic(); ROOT.mkdir(exist_ok=False)
    initial = ROOT.stat(); root_id = initial.st_dev, initial.st_ino
    result = {"schema": "QD_SUPPORT_NATIVE_SINGLE_RUN_V1", "authorization_consumed": True,
              "base_commit": "5f92dcd185b8810d99ece2407bcd8af8a9abb763", "proposal_sha256": PROPOSAL_SHA,
              "limits": {"seconds": MAX_SECONDS, "entries": MAX_ENTRIES, "accounted_bytes": MAX_BYTES},
              "fixture_selector_only_operator_clarified": True, "operational_effects": False,
              "forced_job_cleanup": False, "peak_entries": 0, "peak_accounted_bytes": 0}
    (ROOT / "authorization-consumed.json").write_bytes(encoded(result))
    hp = ht = None
    assigned = False
    try:
        env = confined_environment(ROOT)
        env.update(PSModulePath=r"C:\Windows\System32\WindowsPowerShell\v1.0\Modules",
                   PSModuleAnalysisCachePath=str(ROOT / "ps-module-analysis.cache"),
                   ATLAS_SUPPORT_NATIVE_FIXTURE=str(ROOT), ATLAS_SELECTOR_NATIVE_FIXTURE=str(ROOT))
        with (ROOT / "pytest-stdout.log").open("xb") as out, (ROOT / "pytest-stderr.log").open("xb") as err, open(os.devnull, "rb") as null:
            handles = [msvcrt.get_osfhandle(s.fileno()) for s in (null, out, err)]
            for handle in handles:
                os.set_handle_inheritable(handle, True)
            si = subprocess.STARTUPINFO(); si.dwFlags = subprocess.STARTF_USESTDHANDLES
            si.hStdInput, si.hStdOutput, si.hStdError = handles
            si.lpAttributeList = {"handle_list": handles}
            python = str(REPO / "backend/.venv/Scripts/python.exe")
            command = subprocess.list2cmdline([python, "-I", "-B", str(Path(__file__).resolve()), "--worker"])
            hp, ht, pid, _ = _winapi.CreateProcess(python, command, None, None, True,
                0x08000000 | 4 | 0x00080000, env, str(REPO), si)
            result["worker_pid"] = pid
            check(k.AssignProcessToJobObject(job, hp))
            assigned = True
            if k.ResumeThread(ht) != 1:
                raise RuntimeError("OWNED_WORKER_SUSPEND_STATE_REFUSED")
            _winapi.CloseHandle(ht); ht = None
            for handle in handles:
                os.set_handle_inheritable(handle, False)
            print("ONE_RUN_STARTED " + str(ROOT), flush=True)
            while True:
                current = ROOT.stat()
                if (current.st_dev, current.st_ino) != root_id:
                    raise ValueError("FIXTURE_ROOT_SUBSTITUTION")
                counts = measure(ROOT)
                result["peak_entries"] = max(result["peak_entries"], counts["entries"])
                result["peak_accounted_bytes"] = max(result["peak_accounted_bytes"], counts["accounted_bytes"])
                # Reserve for in-flight writes, final evidence and cleanup; never
                # wait until the operator's actual ceiling has been exhausted.
                if time.monotonic() - started >= 540 or counts["entries"] >= 38000 or counts["accounted_bytes"] >= 480 * 1024**2:
                    raise ValueError("SINGLE_RUN_CONSERVATIVE_LIMIT_STOP")
                code = _winapi.GetExitCodeProcess(hp)
                if code != 259:
                    result["worker_exit_code"] = code
                    break
                time.sleep(0.25)
        active = Accounting()
        check(k.QueryInformationJobObject(job, 1, C.byref(active), C.sizeof(active), None))
        result["job_active_after_worker"] = active.active
        if active.active:
            raise ValueError("OWNED_DESCENDANTS_REMAIN_AFTER_WORKER")
        result["status"] = "PASS" if result["worker_exit_code"] == 0 else "TEST_FAILURE_PRESERVED"
    except BaseException as failure:  # noqa: BLE001 - Every exit must clean up the exact owned Job/process.
        result.update(status="REFUSED_PRESERVE_PARTIAL", failure=repr(failure), forced_job_cleanup=True)
        check(k.TerminateJobObject(job, 1))
        if hp and not assigned:
            _winapi.TerminateProcess(hp, 1)  # exact creation handle, never a PID lookup
        if hp:
            _winapi.WaitForSingleObject(hp, 10000)
    finally:
        active = Accounting()
        check(k.QueryInformationJobObject(job, 1, C.byref(active), C.sizeof(active), None))
        result["job_active_before_close"] = active.active
        if ht:
            _winapi.CloseHandle(ht)
        if hp:
            _winapi.CloseHandle(hp)
        check(k.CloseHandle(job))
        result["job_and_process_handles_closed"] = True
        result["seconds"] = round(time.monotonic() - started, 3)
        result["final_accounting_before_result"] = measure(ROOT)
        counts = result["final_accounting_before_result"]
        if result["seconds"] >= MAX_SECONDS or counts["entries"] + 1 >= MAX_ENTRIES or counts["accounted_bytes"] + 65536 >= MAX_BYTES:
            result["status"] = "LIMIT_ACCEPTANCE_REFUSED"
        (ROOT / "run-result.json").write_bytes(encoded(result))
        print(json.dumps(result), flush=True)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-approved-once", action="store_true")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    if args.worker:
        if Path(os.environ.get("ATLAS_SUPPORT_NATIVE_FIXTURE", "")) != ROOT or not (ROOT / "authorization-consumed.json").is_file():
            raise SystemExit("EXACT_SINGLE_RUN_PARENT_REQUIRED")
        if (ROOT / "run-result.json").exists() or (ROOT / "worker-result.json").exists():
            raise SystemExit("SINGLE_RUN_ALREADY_COMPLETE_NO_WORKER_REUSE")
        with (ROOT / "worker-started.json").open("xb") as claim:
            claim.write(encoded({"schema": "QD_SUPPORT_NATIVE_WORKER_SINGLE_CLAIM_V1", "pid": os.getpid()}))
        raise SystemExit(worker())
    if not args.execute_approved_once:
        raise SystemExit("EXPLICIT_FRESH_SINGLE_RUN_APPROVAL_REQUIRED")
    raise SystemExit(supervisor())
