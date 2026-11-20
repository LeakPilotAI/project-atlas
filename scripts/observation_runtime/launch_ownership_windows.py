"""Read-only native handle/CIM observations for explicit launch owners.

No process creation, ownership discovery/adoption, process termination or
operational authority. Callers retain all process/Job handles and image leases.
"""

import ctypes as C
import hashlib
import json
import os
import subprocess
import time
from ctypes import wintypes as W
from pathlib import Path

from scripts.observation_runtime.launch_ownership import require
from scripts.observation_runtime import aip06_fixture_guard as guarded


class FileInfo(C.Structure):
    _fields_ = [
        ("attrs", W.DWORD),
        ("created", W.FILETIME),
        ("access", W.FILETIME),
        ("written", W.FILETIME),
        ("volume", W.DWORD),
        ("size_hi", W.DWORD),
        ("size_lo", W.DWORD),
        ("links", W.DWORD),
        ("index_hi", W.DWORD),
        ("index_lo", W.DWORD),
    ]


class NativeQueries:
    def __init__(self):
        require(os.name == "nt", "WINDOWS_REQUIRED")
        self.k = C.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateFileW": (
                [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE],
                W.HANDLE,
            ),
            "CloseHandle": ([W.HANDLE], W.BOOL),
            "GetFileInformationByHandle": ([W.HANDLE, C.POINTER(FileInfo)], W.BOOL),
            "GetProcessId": ([W.HANDLE], W.DWORD),
            "GetProcessTimes": ([W.HANDLE] + [C.POINTER(W.FILETIME)] * 4, W.BOOL),
            "QueryFullProcessImageNameW": (
                [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)],
                W.BOOL,
            ),
            "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
            "GetExitCodeProcess": ([W.HANDLE, C.POINTER(W.DWORD)], W.BOOL),
            "QueryInformationJobObject": (
                [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p],
                W.BOOL,
            ),
            "IsProcessInJob": ([W.HANDLE, W.HANDLE, C.POINTER(W.BOOL)], W.BOOL),
        }
        for name, (args, restype) in signatures.items():
            f = getattr(self.k, name)
            f.argtypes, f.restype = args, restype

    @staticmethod
    def check(value):
        if not value:
            raise C.WinError(C.get_last_error())
        return value

    def lifetime(self, handle):
        pid = self.check(self.k.GetProcessId(handle))
        times = [W.FILETIME() for _ in range(4)]
        self.check(self.k.GetProcessTimes(handle, *(C.byref(t) for t in times)))
        created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        return pid, created

    def native(self, handle):
        pid, created = self.lifetime(handle)
        buf, size = C.create_unicode_buffer(32768), W.DWORD(32768)
        self.check(self.k.QueryFullProcessImageNameW(handle, 0, buf, C.byref(size)))
        return pid, created, str(Path(buf.value).absolute()).casefold()


class ImageLease:
    """Keep executable bytes, native file identity and pathname stable."""

    def __init__(self, api, path, *, linked_windows_console=False):
        self.api, self.handle = api, None
        p = Path(path).absolute()
        if linked_windows_console:
            require(
                str(p).casefold()
                == str(
                    Path(os.environ["SystemRoot"]) / "System32/conhost.exe"
                ).casefold(),
                "EXACT_WINDOWS_CONSOLE_IMAGE_REQUIRED",
            )
        require(
            all(not x.is_symlink() and not x.is_junction() for x in (p, *p.parents)),
            "IMAGE_REPARSE_REFUSED",
        )
        h = guarded.image_open(api, str(p))
        require(h not in (None, C.c_void_p(-1).value), "IMAGE_READ_LEASE_REQUIRED")
        self.handle = h
        try:
            info = FileInfo()
            api.check(api.k.GetFileInformationByHandle(h, C.byref(info)))
            require(
                (info.links == 1 or linked_windows_console and info.links >= 1)
                and not info.attrs & 0x400,
                "IMAGE_NAMESPACE_REFUSED",
            )
            # Component-store hardlinks share the same file object. The read
            # lease excludes write/delete through every alias; no project or
            # financial image receives this explicit Windows-console allowance.
            self.pin = (
                str(p).casefold(),
                (info.volume, info.index_hi, info.index_lo),
                hashlib.sha256(p.read_bytes()).hexdigest(),
            )
        except Exception:
            self.close()
            raise

    def close(self):
        if self.handle is not None:
            self.api.check(guarded.image_close(self.api, self.handle))
            self.handle = None


class WindowsLaunchObserver:
    def __init__(
        self,
        native,
        job,
        images,
        temp_root,
        *,
        deadline_ns=None,
        query_creation_flags=None,
    ):
        self.native, self.job, self.images = native, job, images
        self.temp_root = Path(temp_root).absolute()
        require(self.temp_root.is_dir(), "EXISTING_DISPOSABLE_QUERY_TEMP_REQUIRED")
        self.evidence = []
        self.deadline_ns = deadline_ns
        self.query_creation_flags = (
            subprocess.CREATE_NO_WINDOW
            if query_creation_flags is None
            else query_creation_flags
        )

    def lifecycle(self, handle):
        # The retained creation handle still identifies an exited process.
        # QueryFullProcessImageName may fail after exit; do not reopen by PID.
        pid, created = self.native.lifetime(handle)
        wait = self.native.k.WaitForSingleObject(handle, 0)
        require(wait in (0, 258), "NATIVE_LIFECYCLE_QUERY_FAILED")
        code = W.DWORD()
        self.native.check(self.native.k.GetExitCodeProcess(handle, C.byref(code)))
        return {
            "pid": pid,
            "created": created,
            "exited": wait == 0,
            "exit_code": code.value,
        }

    def observe(self, handle):
        started = time.perf_counter_ns()
        require(
            self.deadline_ns is None or started + 30_000_000_000 < self.deadline_ns,
            "OWNED_CLEANUP_TIME_RESERVE_REQUIRED",
        )
        require(
            self.native.k.WaitForSingleObject(handle, 0) == 258,
            "LIVE_RETAINED_PROCESS_REQUIRED",
        )
        before = self.native.native(handle)
        lease = self.images.get(before[2])
        require(
            lease is not None and lease.handle is not None,
            "RETAINED_IMAGE_LEASE_REQUIRED",
        )
        # Exact-PID independent WMI evidence. Integer PID comes from the retained
        # native handle, never from an environment claim or a shell expression.
        command = (
            "$ErrorActionPreference='Stop';"
            f"$r=@(Get-CimInstance Win32_Process -Filter 'ProcessId={before[0]}' -OperationTimeoutSec 2);"
            "if($r.Count -ne 1){throw 'EXACT_PROCESS_UNAVAILABLE'};$p=$r[0];"
            "@{pid=[long]$p.ProcessId;parent_pid=[long]$p.ParentProcessId;"
            "created=[long]$p.CreationDate.ToUniversalTime().ToFileTimeUtc();"
            "image=[string]$p.ExecutablePath;command_line=[string]$p.CommandLine}|ConvertTo-Json -Compress"
        )
        env = dict(
            os.environ,
            TEMP=str(self.temp_root),
            TMP=str(self.temp_root),
            PSModuleAnalysisCachePath=str(self.temp_root / "query-module.cache"),
        )
        ps = (
            Path(os.environ["SystemRoot"])
            / "System32/WindowsPowerShell/v1.0/powershell.exe"
        )
        query_runner = subprocess.run if guarded.current() is None else guarded.query
        observed = query_runner(
            [str(ps), "-NoProfile", "-NonInteractive", "-Command", command],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=6,
            check=False,
            creationflags=self.query_creation_flags,
        )
        if observed.returncode or observed.stderr or len(observed.stdout) >= 65536:
            # Preserve the failed independent query; an empty successful-looking
            # process observation must never replace an access/query refusal.
            self.evidence.append(
                {
                    "pid": before[0],
                    "query_returncode": observed.returncode,
                    "query_stdout": observed.stdout[:65536].decode(errors="replace"),
                    "query_stderr": observed.stderr[:65536].decode(errors="replace"),
                }
            )
        require(
            observed.returncode == 0
            and not observed.stderr
            and len(observed.stdout) < 65536,
            "INDEPENDENT_COMMAND_ANCESTRY_QUERY_FAILED",
        )
        require(bool(observed.stdout), "INDEPENDENT_QUERY_JSON_REQUIRED")
        row = json.loads(observed.stdout)
        after = self.native.native(handle)
        require(
            before == after and self.native.k.WaitForSingleObject(handle, 0) == 258,
            "RETAINED_LIFETIME_CHANGED_DURING_QUERY",
        )
        identity_agrees = (
            type(row.get("pid")) is int
            and row["pid"] == before[0]
            and type(row.get("created")) is int
            and row["created"] // 10 == before[1] // 10
            and row.get("image", "").casefold() == before[2]
            and type(row.get("parent_pid")) is int
            and row["parent_pid"] > 0
            and type(row.get("command_line")) is str
            and bool(row["command_line"])
        )
        if not identity_agrees:
            self.evidence.append(
                {
                    "native_before": before,
                    "native_after": after,
                    "independent_cim": row,
                    "accepted": False,
                }
            )
        require(identity_agrees, "INDEPENDENT_NATIVE_CIM_IDENTITY_DISAGREEMENT")
        require(
            time.perf_counter_ns() - started <= 5_000_000_000,
            "STALE_PROCESS_OBSERVATION",
        )
        require(len(self.evidence) < 256, "OBSERVATION_CAPACITY")
        row.update(
            created=before[1],
            image=before[2],
            file_id=lease.pin[1],
            sha256=lease.pin[2],
        )
        self.evidence.append(
            {"started_ns": started, "finished_ns": time.perf_counter_ns(), **row}
        )
        return row

    def members(self):
        # A fixed bounded complete Job PID list; overflow/error is refusal,
        # never a partial roster presented as complete.
        class Pids(C.Structure):
            _fields_ = [
                ("assigned", W.DWORD),
                ("count", W.DWORD),
                ("pids", C.c_size_t * 16),
            ]

        value = Pids()
        self.native.check(
            self.native.k.QueryInformationJobObject(
                self.job, 3, C.byref(value), C.sizeof(value), None
            )
        )
        require(
            value.assigned == value.count and value.count <= 16,
            "COMPLETE_JOB_ROSTER_REQUIRED",
        )
        return set(value.pids[: value.count])
