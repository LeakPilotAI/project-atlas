"""Explicit disposable native ownership validation, never installed acceptance.

Runs only with --disposable-root, confined below repository diagnostics. No
operational paths, selection, installation, service, provider or socket access.
"""

import argparse
import ctypes as C
import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from ctypes import wintypes as W
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.observation_runtime.launch_ownership import (
    LaunchRequest,
    OwnershipRefused,
    RetainedLaunchBinding,
    require,
)
from scripts.observation_runtime.launch_ownership_windows import (
    ImageLease,
    NativeQueries,
    WindowsLaunchObserver,
)


class BasicLimits(C.Structure):
    _fields_ = [
        ("user", C.c_longlong),
        ("job_user", C.c_longlong),
        ("flags", W.DWORD),
        ("min_working", C.c_size_t),
        ("max_working", C.c_size_t),
        ("active_limit", W.DWORD),
        ("affinity", C.c_size_t),
        ("priority", W.DWORD),
        ("scheduling", W.DWORD),
    ]


class ExtendedLimits(C.Structure):
    _fields_ = [
        ("basic", BasicLimits),
        ("io", C.c_ulonglong * 6),
        ("process_memory", C.c_size_t),
        ("job_memory", C.c_size_t),
        ("peak_process", C.c_size_t),
        ("peak_job", C.c_size_t),
    ]


def native_refusals(observer, request, parent, launch, runtime, native):
    """Real live observations with deliberately wrong requests/retained parents."""
    checks = []
    wrong_command = replace(
        request, launch_command=request.launch_command + " unexpected"
    )
    if request.topology == "direct":
        wrong_command = replace(
            wrong_command, runtime_command=wrong_command.launch_command
        )
    wrong_image = replace(request, launch_image=(*request.launch_image[:2], "0" * 64))
    if request.topology == "direct":
        wrong_image = replace(wrong_image, runtime_image=wrong_image.launch_image)
    callbacks = [
        (
            "command_mismatch",
            lambda: RetainedLaunchBinding(observer, wrong_command, parent, launch),
        ),
        (
            "executable_hash_mismatch",
            lambda: RetainedLaunchBinding(observer, wrong_image, parent, launch),
        ),
        (
            "wrong_retained_parent",
            lambda: RetainedLaunchBinding(observer, request, runtime, launch),
        ),
        (
            "missing_original_handle",
            lambda: RetainedLaunchBinding(observer, request, parent, None),
        ),
    ]

    def closed_parent():
        duplicate = native.check(native.k.OpenProcess(0x101000, False, os.getpid()))
        native.check(native.k.CloseHandle(duplicate))
        return RetainedLaunchBinding(observer, request, duplicate, launch)

    callbacks.append(("closed_parent_handle", closed_parent))
    for name, callback in callbacks:
        try:
            callback()
        except (OwnershipRefused, OSError) as exc:
            checks.append({"case": name, "refused": True, "reason": str(exc)})
        else:
            raise OwnershipRefused("UNSAFE_NATIVE_NEGATIVE_PASS:" + name)
    return checks


def run_case(root, native, images, kind, deadline_ns):
    import _winapi
    import msvcrt

    k = native.k
    case = root / kind
    case.mkdir(exist_ok=False)
    hp = ht = parent = runtime = job = None
    output = incoming = outgoing = stderr = None
    read_thread = None
    result = {"case": kind, "forced_cleanup": False, "passed": False}
    observer = None
    extra_handles = {}
    begun = time.perf_counter()
    try:
        parent = native.check(k.OpenProcess(0x101000, False, os.getpid()))
        job = native.check(k.CreateJobObjectW(None, None))
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # Kill only this Job on failure/owner loss.
        native.check(
            k.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits))
        )
        venv = kind.startswith("venv")
        executable = (
            REPO / "backend/.venv/Scripts/python.exe"
            if venv
            else Path(sys._base_executable)
        )
        nonce = uuid.uuid4().hex
        role = (
            "acceptance_worker" if kind.endswith("worker") else "acceptance_supervisor"
        )
        args = [
            str(executable),
            "-I",
            "-B",
            str(REPO / "tests/launch_ownership_child.py"),
            "--nonce",
            nonce,
            "--role",
            role,
        ]
        unexpected = "unexpected" in kind
        if unexpected:
            args.append("--unexpected-child")
        command = subprocess.list2cmdline(args)
        read_fd, write_fd = os.pipe()
        child_read, parent_write = os.pipe()
        output = os.fdopen(read_fd, "rb")
        incoming = os.fdopen(child_read, "rb")
        outgoing = os.fdopen(parent_write, "wb")
        stderr = (case / "child-stderr.log").open("xb")
        handles = [
            msvcrt.get_osfhandle(fd) for fd in (child_read, write_fd, stderr.fileno())
        ]
        for h in handles:
            os.set_handle_inheritable(h, True)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESTDHANDLES
        si.hStdInput, si.hStdOutput, si.hStdError = handles
        si.lpAttributeList = {"handle_list": handles}
        env = dict(
            os.environ, TEMP=str(case), TMP=str(case), PYTHONDONTWRITEBYTECODE="1"
        )
        for name in ("PYTHONHOME", "PYTHONPATH"):
            env.pop(name, None)
        hp, ht, launch_pid, _ = _winapi.CreateProcess(
            str(executable),
            command,
            None,
            None,
            True,
            0x4 | 0x8,  # CREATE_SUSPENDED | DETACHED_PROCESS: no implicit conhost.
            env,
            str(REPO),
            si,
        )
        native.check(k.AssignProcessToJobObject(job, hp))
        for h in handles:
            os.set_handle_inheritable(h, False)
        os.close(write_fd)
        incoming.close()
        observer = WindowsLaunchObserver(
            native, job, images, case, deadline_ns=deadline_ns
        )
        # Explicit expected child command is pinned before resume. CPython's
        # venv redirector command behavior must agree; disagreement refuses.
        request = LaunchRequest(
            role,
            nonce,
            "one_redirector" if venv else "direct",
            images[str(executable).casefold()].pin,
            images[str(Path(sys._base_executable)).casefold()].pin,
            command,
            (
                '"'
                + str(Path(sys._base_executable))
                + '" '
                + subprocess.list2cmdline(args[1:])
            )
            if venv
            else command,
            images[
                str(Path(os.environ["SystemRoot"]) / "System32/conhost.exe").casefold()
            ].pin
            if venv
            else None,
            "\\??\\" + os.environ["SystemRoot"] + "\\system32\\conhost.exe 0x4"
            if venv
            else None,
            109
            if venv
            else None,  # Exact console broken-pipe terminal status, never Python success.
        )
        # A suspended process has a retained kernel identity, but WMI may not
        # expose its command line until initialization. Keep it contained;
        # require the full independent command/ancestry cut after real READY.
        result["suspended_native_identity"] = native.native(hp)
        request.validate()
        require(k.ResumeThread(ht) != 0xFFFFFFFF, "RESUME_FAILED")
        native.check(k.CloseHandle(ht))
        ht = None
        q = queue.Queue()

        def read_ready():
            q.put(output.readline(65537))

        read_thread = threading.Thread(target=read_ready)
        read_thread.start()
        raw = q.get(timeout=8)
        require(
            len(raw) <= 65536 and raw.endswith(b"\n"), "BOUNDED_REAL_READY_REQUIRED"
        )
        ready = json.loads(raw)
        binding = RetainedLaunchBinding(observer, request, parent, hp)
        members = observer.members()
        result.update(
            launch_pid=launch_pid,
            ready=ready,
            initial_job_pids=sorted(members),
            request={
                "role": role,
                "nonce": nonce,
                "topology": request.topology,
                "launch_command": command,
                "runtime_command": request.runtime_command,
                "auxiliary_image": request.auxiliary_image,
                "auxiliary_command": request.auxiliary_command,
                "auxiliary_exit_code": request.auxiliary_exit_code,
            },
        )
        unexpected_members = members - {launch_pid, ready["pid"]}
        if unexpected_members:
            # Diagnostic capture only, never an ownership claim or allowlist.
            # Keep native query handles through independent CIM inspection.
            result["unclaimed_members"] = []
            for member in sorted(unexpected_members):
                require(
                    time.perf_counter_ns() + 30_000_000_000 < deadline_ns,
                    "NATIVE_CAPTURE_CLEANUP_RESERVE",
                )
                extra = native.check(k.OpenProcess(0x101000, False, member))
                try:
                    native_identity = native.native(extra)
                    extra_handles[member] = extra
                    query = f"Get-CimInstance Win32_Process -Filter 'ProcessId={member}' | Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress"
                    query_result = subprocess.run(
                        [
                            str(
                                Path(os.environ["SystemRoot"])
                                / "System32/WindowsPowerShell/v1.0/powershell.exe"
                            ),
                            "-NoProfile",
                            "-NonInteractive",
                            "-Command",
                            query,
                        ],
                        capture_output=True,
                        timeout=6,
                        check=False,
                        env=dict(
                            env,
                            PSModuleAnalysisCachePath=str(case / "query-module.cache"),
                        ),
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    result["unclaimed_members"].append(
                        {
                            "native_identity": native_identity,
                            "independent_query": query_result.stdout.decode(
                                errors="replace"
                            ),
                            "query_exit": query_result.returncode,
                            "ownership_accepted": False,
                        }
                    )
                except Exception:
                    if member not in extra_handles:
                        native.check(k.CloseHandle(extra))
                    raise
        if ready["pid"] == launch_pid:
            runtime = hp
        else:
            require(
                type(ready["pid"]) is int and ready["pid"] in members,
                "RUNTIME_NOT_IN_EXACT_OWNED_JOB",
            )
            runtime = native.check(k.OpenProcess(0x101000, False, ready["pid"]))
        auxiliary = None
        try:
            if request.auxiliary_image is not None:
                candidates = [
                    h
                    for h in extra_handles.values()
                    if native.native(h)[2] == request.auxiliary_image[0]
                ]
                require(
                    len(candidates) == 1, "EXACT_PINNED_AUXILIARY_CANDIDATE_REQUIRED"
                )
                auxiliary = candidates[0]
            claims = binding.bind_runtime(runtime, ready, auxiliary)
        except OwnershipRefused as exc:
            require(
                unexpected and str(exc) == "UNEXPECTED_OR_MISSING_JOB_PROCESS",
                "UNEXPECTED_NATIVE_REFUSAL:" + str(exc),
            )
            result["expected_refusal"] = str(exc)
        else:
            require(not unexpected, "UNEXPECTED_CHILD_WAS_ACCEPTED")
            result["verified_claims"] = claims
            result["reverified_claims"] = binding.verify()
            result["native_adversarial_checks"] = native_refusals(
                observer, request, parent, hp, runtime, native
            )
        # EOF through the retained private pipe; no PID-based termination.
        outgoing.close()
        require(k.WaitForSingleObject(hp, 8000) == 0, "LAUNCH_NORMAL_EXIT_TIMEOUT")
        require(
            k.WaitForSingleObject(runtime, 1000) == 0, "RUNTIME_NORMAL_EXIT_TIMEOUT"
        )
        if auxiliary is not None:
            require(
                k.WaitForSingleObject(auxiliary, 2000) == 0,
                "AUXILIARY_NORMAL_EXIT_TIMEOUT",
            )
        for extra in extra_handles.values():
            require(
                k.WaitForSingleObject(extra, 2000) == 0,
                "OWNED_EXTRA_FIXTURE_EXIT_TIMEOUT",
            )
        result["retained_exit_observations"] = {
            "launch": observer.lifecycle(hp),
            "runtime": observer.lifecycle(runtime),
            "auxiliary": observer.lifecycle(auxiliary)
            if auxiliary is not None
            else None,
        }
        if not unexpected:
            try:
                observer.observe(runtime)
            except OwnershipRefused as exc:
                result["exited_live_claim_refused"] = str(exc)
            else:
                raise OwnershipRefused("EXITED_PROCESS_WAS_ACCEPTED_AS_LIVE")
            result["exit"] = binding.verify_exit()
        else:
            require(observer.members() == set(), "REFUSED_FIXTURE_JOB_NOT_DRAINED")
            result["exit"] = {
                "job_empty": True,
                "normal_exit": observer.lifecycle(hp)["exit_code"] == 0,
            }
        require(result["exit"]["normal_exit"], "NONZERO_FIXTURE_EXIT")
        result["passed"] = True
    except Exception as exc:  # noqa: BLE001 - retain native failure evidence and exact owned cleanup.
        result["error"] = repr(exc)
    finally:
        if observer is not None:
            result["observations"] = observer.evidence
        if outgoing is not None and not outgoing.closed:
            outgoing.close()
        if hp and k.WaitForSingleObject(hp, 2000) != 0:
            # Exactly owned disposable containment only; never acceptance.
            result["forced_cleanup"] = True
            native.check(k.TerminateJobObject(job, 75))
            require(k.WaitForSingleObject(hp, 5000) == 0, "OWNED_CLEANUP_INCOMPLETE")
        if observer is not None and observer.members():
            result["forced_cleanup"] = True
            native.check(k.TerminateJobObject(job, 75))
            until = time.perf_counter() + 5
            while observer.members() and time.perf_counter() < until:
                time.sleep(0.01)
            require(observer.members() == set(), "OWNED_DESCENDANT_CLEANUP_INCOMPLETE")
        if read_thread is not None:
            read_thread.join(timeout=2)
            require(not read_thread.is_alive(), "READ_THREAD_NOT_DRAINED")
        for stream in (output, incoming, outgoing, stderr):
            if stream is not None and not stream.closed:
                stream.close()
        if observer is not None:
            result["final_job_pids"] = sorted(observer.members())
        for h in (
            *extra_handles.values(),
            ht,
            runtime if runtime != hp else None,
            hp,
            job,
            parent,
        ):
            if h:
                native.check(k.CloseHandle(h))
        result["handles_closed"] = True
        result["seconds"] = time.perf_counter() - begun
        (case / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    require(
        result["passed"]
        and not result["forced_cleanup"]
        and result.get("final_job_pids") == [],
        "NATIVE_CASE_FAILED:" + kind,
    )
    return {
        k: result[k]
        for k in (
            "case",
            "passed",
            "seconds",
            "launch_pid",
            "ready",
            "handles_closed",
            "final_job_pids",
        )
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--disposable-root", required=True)
    allowed_cases = (
        "direct-supervisor",
        "venv-supervisor",
        "direct-worker",
        "venv-worker",
        "direct-unexpected",
        "venv-unexpected",
    )
    parser.add_argument(
        "--cases", nargs="+", choices=allowed_cases, default=allowed_cases
    )
    args = parser.parse_args()
    root = Path(args.disposable_root).absolute()
    require(
        root.parent == REPO / "logs/diagnostics"
        and root.name.startswith("qd-v5-launch-ownership-")
        and root.is_dir()
        and not (root / "native-claim.json").exists()
        and all(
            not p.is_symlink() and not p.is_junction() for p in (root, *root.parents)
        ),
        "FRESH_CONFINED_DISPOSABLE_SCOPE_REQUIRED",
    )
    started = time.perf_counter()
    (root / "native-claim.json").write_text(
        json.dumps(
            {
                "maximum_seconds": 180,
                "maximum_entries": 1024,
                "maximum_bytes": 16 * 1024**2,
            }
        )
    )
    native = NativeQueries()
    k = native.k
    declarations = {
        "OpenProcess": ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
        "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
        "SetInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
        "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
        "ResumeThread": ([W.HANDLE], W.DWORD),
        "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
    }
    for name, (types, restype) in declarations.items():
        getattr(k, name).argtypes, getattr(k, name).restype = types, restype
    images = {}
    summary = {
        "passed": False,
        "cases": [],
        "installed_launches": 0,
        "selection_mutations": 0,
        "source_hashes": {
            str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                Path(__file__),
                REPO / "tests/launch_ownership_child.py",
                REPO / "scripts/observation_runtime/launch_ownership.py",
                REPO / "scripts/observation_runtime/launch_ownership_windows.py",
            ]
        },
    }
    try:
        for p in (
            Path(sys._base_executable),
            REPO / "backend/.venv/Scripts/python.exe",
            Path(os.environ["SystemRoot"]) / "System32/conhost.exe",
        ):
            lease = ImageLease(
                native, p, linked_windows_console=(p.name.casefold() == "conhost.exe")
            )
            images[lease.pin[0]] = lease
        summary["image_pins"] = [v.pin for v in images.values()]
        require(len(args.cases) == len(set(args.cases)), "NO_DUPLICATE_NATIVE_CASES")
        for kind in args.cases:
            require(time.perf_counter() - started < 140, "NATIVE_TOTAL_RESERVE_REACHED")
            summary["cases"].append(
                run_case(root, native, images, kind, int((started + 180) * 1e9))
            )
            paths = list(root.rglob("*"))
            require(
                len(paths) <= 1024
                and sum(p.stat().st_size for p in paths if p.is_file()) < 16 * 1024**2,
                "DISPOSABLE_RESOURCE_CAPACITY",
            )
        summary["passed"] = True
    except Exception as exc:  # noqa: BLE001 - preserve all partial cases before closing image leases.
        summary["error"] = repr(exc)
    finally:
        for lease in images.values():
            lease.close()
        summary["image_handles_closed"] = True
        summary["seconds"] = time.perf_counter() - started
        summary["within_time_limit"] = summary["seconds"] <= 180
        paths = list(root.rglob("*"))
        summary["entries_before_summary"] = len(paths) + 1
        summary["bytes_before_summary"] = sum(
            p.stat().st_size for p in paths if p.is_file()
        )
        (root / "native-result.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    return 0 if summary["passed"] and summary["within_time_limit"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
