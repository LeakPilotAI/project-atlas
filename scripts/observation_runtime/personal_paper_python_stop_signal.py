"""Opt-in, tokenless Windows Stop event owned by the installed Python PAPER runtime.

No runtime Start, provider, listener, trading adapter, or data file at import.
The external Stop shortcut only has permission to signal a per-user, per-logon
Windows event. A signal is NOT a completed financial stop or accepted gate.
"""
from __future__ import annotations

import ctypes as C
import os
import re
from ctypes import wintypes as W
from threading import get_ident

from app.services.personal_installed_stop_owner import PersonalInstalledPaperStopOwner

ERROR_ALREADY_EXISTS = 183
WAIT_TIMEOUT = 258
WAIT_OBJECT_0 = 0
WAIT_FAILED = 0xFFFFFFFF
TOKEN_QUERY = 0x0008


class SECURITY_ATTRIBUTES(C.Structure):
    _fields_ = [("nLength", W.DWORD), ("lpSecurityDescriptor", C.c_void_p),
                ("bInheritHandle", W.BOOL)]


class TOKEN_USER(C.Structure):
    _fields_ = [("Sid", C.c_void_p), ("Attributes", W.DWORD)]


class WindowsStopEvents:
    """Windows-only current-user ACL and exact handle-bound event operations."""

    def __init__(self):
        if os.name != "nt":
            raise ValueError("PERSONAL_PAPER_STOP_WINDOWS_ONLY")
        self.k = C.WinDLL("kernel32", use_last_error=True)
        self.a = C.WinDLL("advapi32", use_last_error=True)
        for library, name, args, restype in (
            (self.k, "GetCurrentProcess", [], W.HANDLE),
            (self.k, "GetCurrentProcessId", [], W.DWORD),
            (self.k, "ProcessIdToSessionId", [W.DWORD, C.POINTER(W.DWORD)], W.BOOL),
            (self.k, "CreateMutexW", [C.POINTER(SECURITY_ATTRIBUTES), W.BOOL, W.LPCWSTR], W.HANDLE),
            (self.k, "CreateEventW", [C.POINTER(SECURITY_ATTRIBUTES), W.BOOL, W.BOOL, W.LPCWSTR], W.HANDLE),
            (self.k, "WaitForSingleObject", [W.HANDLE, W.DWORD], W.DWORD),
            (self.k, "ReleaseMutex", [W.HANDLE], W.BOOL),
            (self.k, "CloseHandle", [W.HANDLE], W.BOOL),
            (self.k, "LocalFree", [C.c_void_p], C.c_void_p),
            (self.a, "OpenProcessToken", [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)], W.BOOL),
            (self.a, "GetTokenInformation", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)], W.BOOL),
            (self.a, "ConvertSidToStringSidW", [C.c_void_p, C.POINTER(C.c_void_p)], W.BOOL),
            (self.a, "ConvertStringSecurityDescriptorToSecurityDescriptorW", [W.LPCWSTR, W.DWORD, C.POINTER(C.c_void_p), C.c_void_p], W.BOOL),
        ):
            function = getattr(library, name)
            function.argtypes, function.restype = args, restype

    def fail(self, reason):
        raise OSError(reason + ":" + str(C.get_last_error()))

    def identity(self):
        token = W.HANDLE()
        if not self.a.OpenProcessToken(self.k.GetCurrentProcess(), TOKEN_QUERY, C.byref(token)):
            self.fail("PERSONAL_PAPER_STOP_TOKEN_UNAVAILABLE")
        try:
            size = W.DWORD()
            self.a.GetTokenInformation(token, 1, None, 0, C.byref(size))
            if not 16 <= size.value <= 4096:
                self.fail("PERSONAL_PAPER_STOP_TOKEN_SIZE_UNVERIFIED")
            buffer = C.create_string_buffer(size.value)
            if not self.a.GetTokenInformation(token, 1, buffer, size, C.byref(size)):
                self.fail("PERSONAL_PAPER_STOP_TOKEN_SID_UNAVAILABLE")
            sid_value = TOKEN_USER.from_buffer_copy(buffer).Sid
            sid_pointer = C.c_void_p()
            if not sid_value or not self.a.ConvertSidToStringSidW(sid_value, C.byref(sid_pointer)):
                self.fail("PERSONAL_PAPER_STOP_TOKEN_SID_UNVERIFIED")
            try:
                sid = C.wstring_at(sid_pointer)
            finally:
                self.k.LocalFree(sid_pointer)
            if re.fullmatch(r"S-1-(?:[0-9]+-){1,14}[0-9]+", sid) is None:
                raise ValueError("PERSONAL_PAPER_STOP_SID_INVALID")
            session = W.DWORD()
            if not self.k.ProcessIdToSessionId(self.k.GetCurrentProcessId(), C.byref(session)):
                self.fail("PERSONAL_PAPER_STOP_LOGON_SESSION_UNVERIFIED")
            return sid, session.value
        finally:
            self.k.CloseHandle(token)

    def secure_attributes(self, sid):
        pointer = C.c_void_p()
        # Explicit user + SYSTEM only; no Everyone/Users/admin broad ACE.
        descriptor = "D:P(A;;GA;;;SY)(A;;GA;;;" + sid + ")"
        if not self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                descriptor, 1, C.byref(pointer), None):
            self.fail("PERSONAL_PAPER_STOP_EVENT_ACL_UNAVAILABLE")
        attrs = SECURITY_ATTRIBUTES(C.sizeof(SECURITY_ATTRIBUTES), pointer, False)
        return attrs, pointer

    def create_unique(self, kind, attrs, name):
        handle = (self.k.CreateMutexW(C.byref(attrs), True, name)
                  if kind == "mutex" else
                  self.k.CreateEventW(C.byref(attrs), False, False, name))
        error = C.get_last_error()
        if not handle:
            self.fail("PERSONAL_PAPER_STOP_NATIVE_" + kind.upper() + "_CREATE_REFUSED")
        if error == ERROR_ALREADY_EXISTS:
            self.k.CloseHandle(handle)
            raise ValueError("PERSONAL_PAPER_STOP_OTHER_OWNER_OR_EVENT_EXISTS")
        return handle


class InstalledPythonPaperStopSignal:
    """One owner-thread event; no financial dispatch until explicitly polled."""

    def __init__(self, *, owner, offline_test_id=""):
        if type(owner) is not PersonalInstalledPaperStopOwner or owner.verify_session() is not True:
            raise ValueError("PERSONAL_PAPER_STOP_INSTALLED_OWNER_REQUIRED")
        if offline_test_id and re.fullmatch(r"test-[0-9a-f]{32}", offline_test_id) is None:
            raise ValueError("PERSONAL_PAPER_STOP_TEST_ID_INVALID")
        self._owner, self._creator_thread = owner, get_ident()
        self._session_id = owner.session_id
        self._test_name = offline_test_id
        self._used, self._closed = False, False
        self._mutex, self._event = None, None
        self.native = WindowsStopEvents()
        sid, session = self.native.identity()
        prefix = "Local\\AtlasFinancialPaperStop_" + sid + "_" + str(session)
        if offline_test_id:
            prefix += "_" + offline_test_id
        attrs, descriptor = self.native.secure_attributes(sid)
        try:
            self._mutex = self.native.create_unique("mutex", attrs, prefix + "_Owner")
            self._event = self.native.create_unique("event", attrs, prefix)
        except BaseException:
            self.close()
            raise
        finally:
            self.native.k.LocalFree(descriptor)

    def _thread(self):
        if get_ident() != self._creator_thread:
            raise ValueError("PERSONAL_PAPER_STOP_OWNER_THREAD_CHANGED")

    def poll(self, timeout_ms=0):
        self._thread()
        if self._closed or self._used or type(timeout_ms) is not int or not 0 <= timeout_ms <= 30000:
            raise ValueError("PERSONAL_PAPER_STOP_SIGNAL_ALREADY_USED_OR_INVALID")
        status = self.native.k.WaitForSingleObject(self._event, timeout_ms)
        if status == WAIT_TIMEOUT:
            return {"status": "NO_STOP_SIGNAL", "financial_flatness_verified": False}
        if status != WAIT_OBJECT_0:
            raise OSError("PERSONAL_PAPER_STOP_NATIVE_WAIT_UNVERIFIED:" + str(status))
        # Latch even if the owner dies during Stop, an exception is raised, or
        # durable readback returns UNKNOWN. Never retry a possibly fired Stop.
        self._used = True
        if (self._owner.session_id != self._session_id or
                self._owner.verify_session() is not True):
            raise ValueError("PERSONAL_PAPER_STOP_OWNER_IDENTITY_CHANGED")
        result = self._owner.request_stop("SHUTDOWN_FLATTEN")
        if self._owner.verify_durable_stop_receipt("SHUTDOWN_FLATTEN", result) is not True:
            raise ValueError("PERSONAL_PAPER_STOP_DURABLE_RECEIPT_UNVERIFIED")
        return result

    def close(self):
        self._thread()
        if self._closed:
            return
        self._closed = True
        if self._event is not None:
            self.native.k.CloseHandle(self._event)
            self._event = None
        if self._mutex is not None:
            if not self.native.k.ReleaseMutex(self._mutex):
                self.native.k.CloseHandle(self._mutex)
                self._mutex = None
                raise OSError("PERSONAL_PAPER_STOP_OWNER_MUTEX_RELEASE_UNVERIFIED")
            self.native.k.CloseHandle(self._mutex)
            self._mutex = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
