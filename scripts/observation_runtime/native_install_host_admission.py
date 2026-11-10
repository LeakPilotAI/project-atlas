"""Small, fail-closed Windows host admission for one-time native CODE-ONLY copy.

No process spawning, watchers, writes, provider access, or trading. A single
snapshot enumerates executable basenames, not command-lines or private data.
This is a host resource guard, not a financial/source/ownership approval.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import shutil

MAX_PROCESSES = 4096
MIN_FREE_RAM_BYTES = 8 * 1024**3
MIN_FREE_DISK_BYTES = 4 * 1024**3
BUSY_GAME_EXE = frozenset({"nba2k27.exe"})
TH32CS_SNAPPROCESS = 0x00000002


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _snapshot_windows_process_names():
    if os.name != "nt":
        raise ValueError("NATIVE_HOST_WINDOWS_REQUIRED")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel.Process32FirstW.restype = wintypes.BOOL
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel.Process32NextW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if handle in (None, ctypes.c_void_p(-1).value):
        raise ValueError("NATIVE_HOST_PROCESS_SNAPSHOT_REFUSED")
    names = []
    error = None
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if not kernel.Process32FirstW(handle, ctypes.byref(entry)):
            raise ValueError("NATIVE_HOST_PROCESS_FIRST_REFUSED")
        while True:
            if len(names) >= MAX_PROCESSES:
                raise ValueError("NATIVE_HOST_PROCESS_COUNT_LIMIT")
            names.append(str(entry.szExeFile).casefold())
            if not kernel.Process32NextW(handle, ctypes.byref(entry)):
                if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                    raise ValueError("NATIVE_HOST_PROCESS_SNAPSHOT_INCOMPLETE")
                break
    except BaseException as exc:
        error = exc
    finally:
        if not kernel.CloseHandle(handle):
            raise ValueError("NATIVE_HOST_PROCESS_SNAPSHOT_CLOSE_REFUSED") from error
    if error is not None:
        raise error
    return frozenset(names)


def _windows_free_ram_bytes():
    if os.name != "nt":
        raise ValueError("NATIVE_HOST_WINDOWS_REQUIRED")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MEMORYSTATUSEX)]
    kernel.GlobalMemoryStatusEx.restype = wintypes.BOOL
    memory = MEMORYSTATUSEX()
    memory.dwLength = ctypes.sizeof(memory)
    if not kernel.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise ValueError("NATIVE_HOST_MEMORY_EVIDENCE_UNAVAILABLE")
    return int(memory.ullAvailPhys)


def require_code_install_host_ready(release_parent, *,
                                    process_names=None, free_ram_bytes=None,
                                    free_disk_bytes=None):
    """Return tiny read-only evidence or refuse BEFORE heavy native I/O.

    Optional injected inputs are for offline deterministic tests. Operational
    adapter calls without injection and reads the genuine Windows APIs.
    """
    parent = Path(release_parent)
    if os.name != "nt":
        raise ValueError("NATIVE_HOST_WINDOWS_REQUIRED")
    if parent != Path("D:/AtlasRuntime/releases") or not parent.is_dir():
        raise ValueError("NATIVE_HOST_EXACT_RELEASE_PARENT_REQUIRED")
    names = _snapshot_windows_process_names() if process_names is None else process_names
    ram = _windows_free_ram_bytes() if free_ram_bytes is None else free_ram_bytes
    disk = shutil.disk_usage(parent).free if free_disk_bytes is None else free_disk_bytes
    if (type(names) not in (set, frozenset, tuple, list)
            or len(names) > MAX_PROCESSES
            or any(type(name) is not str for name in names)
            or type(ram) is not int or ram < 0
            or type(disk) is not int or disk < 0):
        raise ValueError("NATIVE_HOST_RESOURCE_EVIDENCE_INVALID")
    busy = BUSY_GAME_EXE & frozenset(name.casefold() for name in names)
    if busy:
        raise ValueError("NATIVE_HOST_GAME_ACTIVE_DEFER_BULK_COPY")
    if ram < MIN_FREE_RAM_BYTES:
        raise ValueError("NATIVE_HOST_RAM_HEADROOM_REFUSED")
    if disk < MIN_FREE_DISK_BYTES:
        raise ValueError("NATIVE_HOST_DISK_HEADROOM_REFUSED")
    return {
        "schema": "ATLAS_NATIVE_CODE_INSTALL_HOST_ADMISSION_V1",
        "status": "RESOURCE_ADMITTED_NOT_INSTALL_AUTHORIZATION",
        "available_ram_bytes": ram,
        "available_disk_bytes": disk,
        "interactive_game_detected": False,
        "selection_allowed": False,
        "financial_authority": False,
    }
