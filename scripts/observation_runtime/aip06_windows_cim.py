"""In-process, bounded Win32_Process CIM query. No PowerShell child recursion.

Uses the supported IWbemLocator/IWbemServices interfaces. Construction and
import are inert; query() is the explicit Windows boundary, injected offline.
"""

import ctypes as C
import uuid
from datetime import UTC, datetime, timedelta, timezone

from scripts.observation_runtime.aip06_harness import integer, need


class GUID(C.Structure):
    _fields_ = [
        ("a", C.c_uint32),
        ("b", C.c_uint16),
        ("c", C.c_uint16),
        ("d", C.c_ubyte * 8),
    ]

    @classmethod
    def parse(cls, text):
        return cls.from_buffer_copy(uuid.UUID(text).bytes_le)


class VariantValue(C.Union):
    _fields_ = [
        ("ptr", C.c_void_p),
        ("i32", C.c_int32),
        ("u32", C.c_uint32),
        ("i64", C.c_int64),
        ("record", C.c_void_p * 2),
    ]


class Variant(C.Structure):
    _fields_ = [
        ("vt", C.c_uint16),
        ("reserved", C.c_uint16 * 3),
        ("value", VariantValue),
    ]


class ComAPI:
    def __init__(self, ole, automation):
        self.ole, self.auto = ole, automation

    @classmethod
    def load(cls):
        ole = C.WinDLL("ole32", use_last_error=True)
        auto = C.WinDLL("oleaut32", use_last_error=True)
        for name, args, result in [
            ("CoInitializeEx", [C.c_void_p, C.c_uint32], C.c_int32),
            (
                "CoCreateInstance",
                [
                    C.POINTER(GUID),
                    C.c_void_p,
                    C.c_uint32,
                    C.POINTER(GUID),
                    C.POINTER(C.c_void_p),
                ],
                C.c_int32,
            ),
            (
                "CoSetProxyBlanket",
                [
                    C.c_void_p,
                    C.c_uint32,
                    C.c_uint32,
                    C.c_void_p,
                    C.c_uint32,
                    C.c_uint32,
                    C.c_void_p,
                    C.c_uint32,
                ],
                C.c_int32,
            ),
            ("CoUninitialize", [], None),
            ("CoEnableCallCancellation", [C.c_void_p], C.c_int32),
            ("CoDisableCallCancellation", [C.c_void_p], C.c_int32),
            ("CoCancelCall", [C.c_uint32, C.c_uint32], C.c_int32),
        ]:
            f = getattr(ole, name)
            f.argtypes, f.restype = args, result
        auto.SysAllocString.argtypes = [C.c_wchar_p]
        auto.SysAllocString.restype = C.c_void_p
        auto.SysFreeString.argtypes = [C.c_void_p]
        auto.SysFreeString.restype = None
        auto.VariantClear.argtypes = [C.POINTER(Variant)]
        auto.VariantClear.restype = C.c_int32
        return cls(ole, auto)

    @staticmethod
    def ok(hr):
        need(hr >= 0, "CIM_HRESULT_FAILURE")

    @staticmethod
    def method(obj, index, args, result=C.c_int32):
        table = C.cast(obj, C.POINTER(C.POINTER(C.c_void_p))).contents
        return C.WINFUNCTYPE(result, C.c_void_p, *args)(table[index])

    def initialize(self):
        self.ok(self.ole.CoInitializeEx(None, 0))

    def uninitialize(self):
        self.ole.CoUninitialize()

    def enable_cancellation(self):
        self.ok(self.ole.CoEnableCallCancellation(None))

    def disable_cancellation(self):
        self.ok(self.ole.CoDisableCallCancellation(None))

    def cancel(self, thread_id):
        result = self.ole.CoCancelCall(thread_id, 0)
        need(
            result >= 0 or result & 0xFFFFFFFF in (0x80010117, 0x80010002, 0x80004002),
            "COM_CANCELLATION_UNAVAILABLE",
        )

    def release(self, obj):
        self.method(obj, 2, [], C.c_uint32)(obj)

    def bstr(self, text):
        pointer = self.auto.SysAllocString(text)
        need(pointer is not None, "CIM_BSTR_ALLOCATION")
        return pointer

    def free(self, pointer):
        self.auto.SysFreeString(pointer)

    def locator(self):
        cls = GUID.parse("4590f811-1d3a-11d0-891f-00aa004b2e24")
        iid = GUID.parse("dc12a687-737f-11cf-884d-00aa004b2e24")
        obj = C.c_void_p()
        self.ok(
            self.ole.CoCreateInstance(C.byref(cls), None, 1, C.byref(iid), C.byref(obj))
        )
        need(obj.value is not None, "CIM_LOCATOR")
        return obj

    def connect(self, locator, namespace):
        service = C.c_void_p()
        self.ok(
            self.method(
                locator,
                3,
                [
                    C.c_void_p,
                    C.c_void_p,
                    C.c_void_p,
                    C.c_void_p,
                    C.c_int32,
                    C.c_void_p,
                    C.c_void_p,
                    C.POINTER(C.c_void_p),
                ],
            )(locator, namespace, None, None, None, 0, None, None, C.byref(service))
        )
        try:
            self.ok(self.ole.CoSetProxyBlanket(service, 10, 0, None, 3, 3, None, 0))
        except BaseException:
            self.release(service)
            raise
        return service

    def query(self, service, language, query):
        enum = C.c_void_p()
        self.ok(
            self.method(
                service,
                20,
                [C.c_void_p, C.c_void_p, C.c_int32, C.c_void_p, C.POINTER(C.c_void_p)],
            )(service, language, query, 0x30, None, C.byref(enum))
        )
        return enum

    def next(self, enum, timeout_ms):
        rows = (C.c_void_p * 2)()
        count = C.c_uint32()
        hr = self.method(
            enum,
            4,
            [C.c_int32, C.c_uint32, C.POINTER(C.c_void_p), C.POINTER(C.c_uint32)],
        )(enum, timeout_ms, 2, rows, C.byref(count))
        # A timed-out partial enumeration is not an exact one-process result.
        if hr not in (0, 1) or count.value != 1:
            for obj in rows:
                if obj:
                    self.release(obj)
            raise ValueError("CIM_EXACT_PROCESS_ENUMERATION_UNAVAILABLE")
        return rows[0]

    def property(self, obj, name):
        value = Variant()
        try:
            self.ok(
                self.method(
                    obj,
                    4,
                    [
                        C.c_wchar_p,
                        C.c_int32,
                        C.POINTER(Variant),
                        C.c_void_p,
                        C.c_void_p,
                    ],
                )(obj, name, 0, C.byref(value), None, None)
            )
            if value.vt == 8:
                need(value.value.ptr is not None, "CIM_NULL_STRING")
                return C.wstring_at(value.value.ptr)
            if value.vt == 3:
                return int(value.value.i32)
            if value.vt == 19:
                return int(value.value.u32)
            raise ValueError("CIM_UNSUPPORTED_OR_NULL_PROPERTY")
        finally:
            self.ok(self.auto.VariantClear(C.byref(value)))


def filetime(value):
    import re

    need(
        type(value) is str and re.fullmatch(r"\d{14}\.\d{6}[+-]\d{3}", value),
        "CIM_CREATION_TIME_FORMAT",
    )
    offset = int(value[22:25]) * (1 if value[21] == "+" else -1)
    need(abs(offset) <= 14 * 60, "CIM_CREATION_TIME_OFFSET")
    date = (
        datetime.strptime(value[:21], "%Y%m%d%H%M%S.%f")
        .replace(tzinfo=timezone(timedelta(minutes=offset)))
        .astimezone(UTC)
    )
    delta = date - datetime(1601, 1, 1, tzinfo=UTC)
    return (delta.days * 86400 + delta.seconds) * 10**7 + delta.microseconds * 10


class CimProcessQuery:
    def __init__(self, *, api, allocations, clock_ns, cancellation=False):
        self.api, self.allocations, self.clock = api, allocations, clock_ns
        self.cancellation = cancellation

    def process(self, pid, *, deadline_ns):
        now = self.clock()
        need(
            integer(pid, 5) and now < deadline_ns <= now + 5 * 10**9, "CIM_QUERY_BOUND"
        )
        held = []
        initialized = False
        enabled = False

        def owned(name, create, release):
            ticket = self.allocations.reserve("cim:" + name, "handle")
            item = create()
            held.append((ticket, item, release))
            return item

        try:
            self.api.initialize()
            initialized = True
            if self.cancellation:
                self.api.enable_cancellation()
                enabled = True
            loc = owned("locator", self.api.locator, self.api.release)
            namespace = owned(
                "namespace", lambda: self.api.bstr(r"ROOT\CIMV2"), self.api.free
            )
            service = owned(
                "service", lambda: self.api.connect(loc, namespace), self.api.release
            )
            lang = owned("language", lambda: self.api.bstr("WQL"), self.api.free)
            query = owned(
                "query",
                lambda: self.api.bstr(
                    "SELECT ProcessId,ParentProcessId,CreationDate,ExecutablePath,CommandLine FROM Win32_Process WHERE ProcessId="
                    + str(pid)
                ),
                self.api.free,
            )
            enum = owned(
                "enumerator",
                lambda: self.api.query(service, lang, query),
                self.api.release,
            )
            remaining = min(2000, (deadline_ns - self.clock()) // 10**6)
            need(remaining > 0, "CIM_QUERY_DEADLINE")
            obj = owned(
                "process", lambda: self.api.next(enum, remaining), self.api.release
            )
            result = {
                target: self.api.property(obj, source)
                for source, target in (
                    ("ProcessId", "pid"),
                    ("ParentProcessId", "parent_pid"),
                    ("CreationDate", "created"),
                    ("ExecutablePath", "image"),
                    ("CommandLine", "command_line"),
                )
            }
            need(
                type(result["pid"]) is int
                and result["pid"] == pid
                and integer(result["parent_pid"], 5)
                and type(result["image"]) is str
                and result["image"]
                and type(result["command_line"]) is str
                and 0 < len(result["command_line"]) < 32767,
                "CIM_PROCESS_IDENTITY",
            )
            result["created"] = filetime(result["created"])
            result["image"] = result["image"].casefold()
            need(now <= self.clock() <= deadline_ns, "STALE_CIM_PROCESS_QUERY")
            return result
        finally:
            for ticket, obj, release in reversed(held):
                release(obj)
                self.allocations.release(ticket)
            if enabled:
                self.api.disable_cancellation()
            if initialized:
                self.api.uninitialize()


class BoundedCimQuery:
    """Cancel-enabled owned worker contains ConnectServer as well as Next."""

    def __init__(self, query, worker):
        self.query, self.worker = query, worker

    def process(self, pid, *, deadline_ns):
        need(self.query.cancellation, "CANCEL_ENABLED_CIM_REQUIRED")
        return self.worker.run(
            lambda: self.query.process(pid, deadline_ns=deadline_ns),
            deadline_ns=deadline_ns,
            cancel=self.query.api.cancel,
        )
