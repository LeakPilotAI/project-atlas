"""Windows Job Object API adapter for Atlas V5.

Source-bound to the confined fixture adapter.
Default invocation cannot create child processes without V5 execution approval.
NATIVE COMPATIBILITY EXECUTION REMAINS UNAUTHORIZED.

Job creation is available only through an explicit method call.
Importing this module does not create a Job Object.
"""

import ctypes
import os
from ctypes import wintypes

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9


class LARGE_INTEGER(ctypes.Structure):
    _fields_ = [("QuadPart", ctypes.c_longlong)]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", LARGE_INTEGER),
        ("PerJobUserTimeLimit", LARGE_INTEGER),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class STARTUPINFOW(ctypes.Structure):
    """64-bit Windows process startup structure."""

    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    """Windows process and primary-thread ownership handles."""

    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('TotalUserTime', LARGE_INTEGER), ('TotalKernelTime', LARGE_INTEGER),
        ('ThisPeriodTotalUserTime', LARGE_INTEGER), ('ThisPeriodTotalKernelTime', LARGE_INTEGER),
        ('TotalPageFaultCount', wintypes.DWORD), ('TotalProcesses', wintypes.DWORD),
        ('ActiveProcesses', wintypes.DWORD), ('TotalTerminatedProcesses', wintypes.DWORD),
    ]


class WindowsJobAPI:
    """Explicit Windows Job Object management only."""

    def __init__(self):
        if os.name != "nt":
            raise RuntimeError("NATIVE_WINDOWS_REQUIRED")

        self.kernel32 = ctypes.WinDLL(
            "kernel32",
            use_last_error=True,
        )

        self.kernel32.CreateJobObjectW.argtypes = [
            ctypes.c_void_p,
            wintypes.LPCWSTR,
        ]
        self.kernel32.CreateJobObjectW.restype = wintypes.HANDLE

        self.kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self.kernel32.SetInformationJobObject.restype = wintypes.BOOL

        self.kernel32.CloseHandle.argtypes = [
            wintypes.HANDLE,
        ]
        self.kernel32.CloseHandle.restype = wintypes.BOOL

        # Declarations only. No process execution is enabled.

        self.kernel32.CreateProcessW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.BOOL,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self.kernel32.CreateProcessW.restype = wintypes.BOOL

        self.kernel32.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
        ]
        self.kernel32.AssignProcessToJobObject.restype = wintypes.BOOL

        self.kernel32.ResumeThread.argtypes = [
            wintypes.HANDLE,
        ]
        self.kernel32.ResumeThread.restype = wintypes.DWORD

        self.kernel32.TerminateJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.UINT,
        ]
        self.kernel32.TerminateJobObject.restype = wintypes.BOOL

        self.kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel32.TerminateProcess.restype = wintypes.BOOL
        self.kernel32.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
            wintypes.DWORD, ctypes.c_void_p,
        ]
        self.kernel32.QueryInformationJobObject.restype = wintypes.BOOL

        self.kernel32.GetExitCodeProcess.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.kernel32.GetExitCodeProcess.restype = wintypes.BOOL

    def create_job(self):
        handle = self.kernel32.CreateJobObjectW(None, None)

        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())

        return handle

    def configure_kill_on_close(self, job):
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()

        info.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )

        ok = self.kernel32.SetInformationJobObject(
            job,
            JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )

        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())

    def close_handle(self, handle):
        if not self.kernel32.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def create_suspended_child(self, command):
        """Use only an explicitly injected suspended transport, never Popen."""
        creator = getattr(self, 'suspended_creator', None)
        if creator is None:
            raise RuntimeError('NATIVE_CHILD_LAUNCH_BLOCKED_PENDING_V5_INTEGRATION')
        return creator(command)

    def terminate_process(self, process):
        if not process:
            raise RuntimeError('NATIVE_PROCESS_INVALID_HANDLE')
        if not self.kernel32.TerminateProcess(process, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    # Named Win32 policy wrappers used by the existing fixture owner.
    CreateJobObject = create_job

    def SetInformationJobObject(self, job, limit_flags):
        if limit_flags != JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE:
            raise ValueError('EXACT_KILL_ON_CLOSE_POLICY_REQUIRED')
        return self.configure_kill_on_close(job)

    def assign_child(self, job, process):
        """Assign an explicitly owned process handle to a Job Object."""
        if not job or not process:
            raise RuntimeError("NATIVE_JOB_INVALID_HANDLE")

        ok = self.kernel32.AssignProcessToJobObject(job, process)

        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())

    def resume_child(self, thread):
        """Resume an explicitly owned suspended thread."""
        if not thread:
            raise RuntimeError("NATIVE_THREAD_INVALID_HANDLE")

        result = self.kernel32.ResumeThread(thread)

        if result == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())

        if result != 1:
            raise RuntimeError('NATIVE_UNEXPECTED_SUSPEND_COUNT')
        return result

    def terminate_job(self, job):
        """Terminate processes in an explicitly owned Job Object."""
        if not job:
            raise RuntimeError("NATIVE_JOB_INVALID_HANDLE")

        ok = self.kernel32.TerminateJobObject(job, 1)

        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())

    AssignProcessToJobObject = assign_child
    ResumeThread = resume_child

    def active_processes(self, job):
        info = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
        if not self.kernel32.QueryInformationJobObject(
            job, 1, ctypes.byref(info), ctypes.sizeof(info), None
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(info.ActiveProcesses)
