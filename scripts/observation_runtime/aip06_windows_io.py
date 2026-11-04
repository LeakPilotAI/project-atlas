"""Concrete, lazy Windows IO for the disposable AIP06 guard.

Importing this module performs no Windows calls. WindowsFileCalls is the only
raw filesystem boundary; NativeIO requires an accounting owner and fixed paths.
The same implementation is exercised offline with injected Win32 responses.
"""

import contextlib
import ctypes as C
import hashlib
import ntpath
import threading
from ctypes import wintypes as W


from scripts.observation_runtime.aip06_harness import (
    BASE,
    LIMITS,
    ROOTS,
    need,
    path_for,
)


class NativeOpenFailed(OSError):
    """The create/open syscall returned no handle, before any post-open check."""

    def __init__(self, code):
        super().__init__(code, "Native open refused")
        self.winerror = code


class WindowsFileCalls:
    """Use the existing no-reparse/relative-open/protected-ACL primitives.

    load() is explicit and is NEVER called by offline tests. Raw handles are
    private to the IO adapter; no path or executable is selected by this class.
    """

    def __init__(self, primitives):
        self.w = primitives

    @classmethod
    def load(cls):
        from scripts.volume_inspector import windows_output

        return cls(windows_output)

    def open_drive(self):
        w = self.w
        h = w._raw_create_file(
            "D:\\", w.READ_CONTROL | w.ATTR | 1, 3, None, 3, w.DIR_FLAGS, None
        )
        if h in (None, w.INVALID):
            raise NativeOpenFailed(C.get_last_error())
        return h

    def open_image(self, path):
        need(
            type(path) is str
            and path.startswith("D:\\")
            and ntpath.normpath(path) == path,
            "D_READ_ONLY_IMAGE_PATH",
        )
        w = self.w
        h = w._raw_create_file(
            path, w.READ | w.READ_CONTROL | w.ATTR, 1, None, 3, 0x200000 | 0x80, None
        )
        if h in (None, w.INVALID):
            raise NativeOpenFailed(C.get_last_error())
        return h

    def open_current_token(self):
        return self.w._current_token()

    def relative(
        self,
        parent,
        leaf,
        *,
        directory=None,
        create=False,
        write=False,
        delete=False,
        sid=None,
    ):
        w = self.w
        need(
            type(leaf) is str
            and leaf not in ("", ".", "..")
            and not any(c in leaf for c in "\\/:\x00"),
            "ONE_NATIVE_COMPONENT",
        )
        access = w.READ | w.READ_CONTROL | w.ATTR
        if write:
            access |= w.WRITE
        if delete:
            access |= w.DELETE
        need(
            directory is not None or not create and not write and not delete,
            "UNKNOWN_TYPE_READ_ONLY",
        )
        text = C.create_unicode_buffer(leaf)
        name = w.Unicode(
            len(leaf.encode("utf-16-le")), C.sizeof(text), C.cast(text, W.LPWSTR)
        )
        sd = w.descriptor(sid) if create else None
        attrs = w.ObjectAttributes(
            C.sizeof(w.ObjectAttributes),
            parent,
            C.pointer(name),
            0x40 | 0x1000,
            sd,
            None,
        )
        h = W.HANDLE()
        options = (
            0x200000
            | 0x20
            | (1 if directory is True else 0x40 if directory is False else 0)
        )
        try:
            status = w.nt_create(
                C.byref(h),
                access | w.SYNC,
                C.byref(attrs),
                C.byref(w.IO()),
                None,
                0,
                3 if directory else 1,
                2 if create else 1,
                options,
                None,
                0,
            )
            if status < 0:
                raise NativeOpenFailed(w.nt_error(status))
        finally:
            if sd:
                w.local_free(sd)
        return h

    def describe(self, handle):
        i = self.w.info(handle)
        return {
            "id": [i.volume, i.index_hi, i.index_lo],
            "kind": "directory" if i.attributes & 16 else "file",
            "reparse": bool(i.attributes & 0x400),
            "links": i.links,
            "bytes": (i.size_hi << 32) | i.size_lo,
        }

    def final_path(self, handle):
        f = self.w.bind(
            self.w.K,
            "GetFinalPathNameByHandleW",
            [W.HANDLE, W.LPWSTR, W.DWORD, W.DWORD],
            W.DWORD,
        )
        buf = C.create_unicode_buffer(32768)
        count = f(handle, buf, len(buf), 0)
        need(0 < count < len(buf), "NATIVE_FINAL_PATH_UNAVAILABLE")
        path = buf.value
        need(
            path.startswith("\\\\?\\") and not path.startswith("\\\\?\\UNC\\"),
            "NATIVE_LOCAL_PATH_REQUIRED",
        )
        return path[4:]

    def acl(self, handle, sid):
        self.w.validate_acl(handle, sid)

    def token_identity(self, handle):
        w = self.w
        size = W.DWORD()
        w.token_info(handle, 1, None, 0, C.byref(size))
        need(0 < size.value <= 65536, "TOKEN_INFORMATION_CAPACITY")
        buf = C.create_string_buffer(size.value)
        w.check(w.token_info(handle, 1, buf, size, C.byref(size)))
        sid = w.sid_text(C.cast(buf, C.POINTER(w.SidAttr)).contents.sid)
        kind = W.DWORD()
        w.check(w.token_info(handle, 8, C.byref(kind), C.sizeof(kind), C.byref(size)))
        return {"sid": sid, "type": kind.value}

    def current_process_native(self):
        get_pid = self.w.bind(self.w.K, "GetProcessId", [W.HANDLE], W.DWORD)
        times = self.w.bind(
            self.w.K, "GetProcessTimes", [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4
        )
        values = [W.FILETIME() for _ in range(4)]
        h = self.w.process()
        self.w.check(times(h, *(C.byref(v) for v in values)))
        return {
            "pid": get_pid(h),
            "created": (values[0].dwHighDateTime << 32) | values[0].dwLowDateTime,
        }

    def close(self, handle):
        self.w.check(self.w._raw_close_handle(handle))

    def closed(self, handle):
        flags = W.DWORD()
        f = self.w.bind(
            self.w.K, "GetHandleInformation", [W.HANDLE, C.POINTER(W.DWORD)]
        )
        if f(handle, C.byref(flags)):
            return False
        error = C.get_last_error()
        need(error == 6, "HANDLE_CLOSE_OBSERVATION_UNAVAILABLE")
        return True

    def read(self, handle, limit):
        w = self.w
        seek = w.bind(
            w.K, "SetFilePointerEx", [W.HANDLE, C.c_longlong, C.c_void_p, W.DWORD]
        )
        w.check(seek(handle, 0, None, 0))
        result = bytearray()
        while len(result) <= limit:
            block = min(65536, limit + 1 - len(result))
            buf, count = C.create_string_buffer(block), W.DWORD()
            w.check(w.read_file(handle, buf, block, C.byref(count), None))
            if not count.value:
                break
            result.extend(buf.raw[: count.value])
        need(len(result) <= limit, "NATIVE_READ_CAPACITY")
        return bytes(result)

    def write(self, handle, raw):
        need(type(raw) is bytes, "IMMUTABLE_NATIVE_WRITE")
        offset = 0
        while offset < len(raw):
            count = W.DWORD()
            block = raw[offset : offset + 65536]
            self.w.check(
                self.w._raw_write_file(handle, block, len(block), C.byref(count), None)
            )
            need(0 < count.value <= len(block), "NATIVE_WRITE_PROGRESS")
            offset += count.value

    def flush(self, handle):
        self.w.check(self.w.flush(handle))

    def rename(self, source, parent, leaf):
        w = self.w

        class Rename(C.Structure):
            _fields_ = [
                ("replace", W.BOOL),
                ("root", W.HANDLE),
                ("length", W.DWORD),
                ("name", W.WCHAR * 1),
            ]

        raw = leaf.encode("utf-16-le")
        buf = C.create_string_buffer(Rename.name.offset + len(raw))
        value = C.cast(buf, C.POINTER(Rename)).contents
        value.replace, value.root, value.length = True, parent, len(raw)
        C.memmove(C.addressof(buf) + Rename.name.offset, raw, len(raw))
        w.nt_check(w.nt_set(source, C.byref(w.IO()), buf, len(buf), 10))

    def names(self, handle, maximum):
        # Enumerate the retained directory handle, never a pathname glob.
        class Entry(C.Structure):
            _fields_ = [
                ("next", W.DWORD),
                ("index", W.DWORD),
                ("name_bytes", W.DWORD),
                ("name", W.WCHAR * 1),
            ]

        f = self.w.bind(
            self.w.K,
            "GetFileInformationByHandleEx",
            [W.HANDLE, C.c_int, C.c_void_p, W.DWORD],
        )
        buf = C.create_string_buffer(65536)
        names = []
        # FileNamesInfo is not supported by this API; FileIdBothDirectoryInfo
        # uses a fixed documented layout. Refuse a malformed/truncated page.
        info_class, restart = 10, True
        while True:
            if not f(handle, 11 if restart else info_class, buf, len(buf)):
                need(C.get_last_error() == 18, "NATIVE_DIRECTORY_ENUMERATION_FAILED")
                break
            restart = False
            offset = 0
            while True:
                need(offset + 104 <= len(buf), "NATIVE_DIRECTORY_RECORD_TRUNCATED")
                next_offset = int.from_bytes(buf.raw[offset : offset + 4], "little")
                length = int.from_bytes(buf.raw[offset + 60 : offset + 64], "little")
                need(
                    length % 2 == 0 and 104 + length <= len(buf) - offset,
                    "NATIVE_DIRECTORY_NAME_TRUNCATED",
                )
                name = buf.raw[offset + 104 : offset + 104 + length].decode("utf-16-le")
                if name not in (".", ".."):
                    names.append(name)
                need(len(names) <= maximum, "NATIVE_DIRECTORY_CAPACITY")
                if not next_offset:
                    break
                need(
                    next_offset >= 104 + length and offset + next_offset < len(buf),
                    "NATIVE_DIRECTORY_OFFSET",
                )
                offset += next_offset
        return sorted(names)


class AllocationBook:
    """Prospective native handle lifetimes; no PID lookup or foreign close.

    The journal's own transient handles use a separate bounded closed batch.
    Their storage/metadata reservation is the SharedResources commit itself;
    creating another reservation from journal.read would recursively append.
    No ordinary effect may use that internal journal batch.
    """

    def __init__(self, resources, owner, calls, clock_ns):
        self.resources, self.owner, self.calls, self.clock = (
            resources,
            owner,
            calls,
            clock_ns,
        )
        self.live, self.released, self.serial = {}, set(), 0
        self.lock = threading.RLock()
        self.journal_live = {}
        self.journal_batch = False

    def fresh(self, deadline=None):
        self.resources.read()
        if deadline is not None:
            need(self.clock() <= deadline, "WINDOWS_IO_DEADLINE")

    def open(self, callback, *, journal=False):
        with self.lock:
            need(not journal or self.journal_batch, "NO_AMBIENT_JOURNAL_CAPABILITY")
            self.serial += 1
            key = f"winio:{self.serial}"
            if journal:
                need(len(self.journal_live) < 16, "JOURNAL_TRANSIENT_HANDLE_CAPACITY")
            else:
                self.fresh()
                self.resources.reserve(
                    self.owner,
                    key,
                    "handle",
                    cleanup=self.resources.state["mode"] == "STOP"
                    or any(
                        r["state"] == "PENDING"
                        for r in self.resources.state["stops"].values()
                    ),
                )
            try:
                h = callback()
            except NativeOpenFailed:
                self.released.add(key)
                if not journal:
                    self.resources.close(self.owner, key, observer=self)
                raise
            raw = h.value if hasattr(h, "value") else h
            need(type(raw) is int and 0 < raw < 2**64 - 1, "NATIVE_HANDLE_REQUIRED")
            target = self.journal_live if journal else self.live
            need(
                raw
                not in {
                    r["handle"]
                    for r in (*self.live.values(), *self.journal_live.values())
                },
                "LIVE_HANDLE_REUSE",
            )
            target[key] = {"handle": raw}
            if not journal and hasattr(self.resources, "bind_native_handle"):
                self.resources.bind_native_handle(key, raw)
            return key, raw

    def close(self, key, handle, *, journal=False):
        target = self.journal_live if journal else self.live
        need(target.get(key) == {"handle": handle}, "EXACT_OWNED_IO_LIFETIME_REQUIRED")
        self.calls.close(handle)
        need(self.calls.closed(handle), "IO_HANDLE_RELEASE_UNVERIFIED")
        del target[key]
        self.released.add(key)
        if not journal:
            self.resources.close(self.owner, key, observer=self)

    def closed(self, owner, key):
        return owner == self.owner and key in self.released

    @contextlib.contextmanager
    def journal(self):
        need(
            not self.journal_batch and not self.journal_live, "ONE_CLOSED_JOURNAL_BATCH"
        )
        self.journal_batch = True
        try:
            yield
        finally:
            self.journal_batch = False
            need(not self.journal_live, "JOURNAL_NATIVE_HANDLES_NOT_CLOSED")


class NativeIO:
    """Guard's concrete IO and metadata port. All raw effects are below here."""

    def __init__(self, *, calls, book, sid, clock_ns):
        self.calls, self.book, self.sid, self.clock = calls, book, sid, clock_ns
        self.guard = None
        self.operations, self.completed, self.callback_handles = {}, set(), {}
        self.cache = {}
        self.lock = threading.RLock()

    def bind_guard(self, guard):
        need(
            self.guard is None
            and guard.resources is self.book.resources
            and guard.owner == self.book.owner,
            "EXACT_IO_GUARD_BINDING",
        )
        self.guard = guard

    def begin(self, owner, key, kind, path):
        need(
            owner == self.book.owner
            and key not in self.operations
            and self.book.resources.state["resources"].get(key)
            == {"owner": owner, "kind": kind, "closed": False},
            "IO_RESERVATION_REQUIRED",
        )
        self.operations[key] = {"kind": kind, "path": path}

    def bind_path(self, key, path):
        need(
            key in self.operations and self.operations[key]["path"] is None,
            "ONE_RESERVED_IO_PATH",
        )
        self.allowed(path)
        self.operations[key]["path"] = path

    def ancestors(self):
        p = "D:\\"
        result = {p}
        for component in BASE[3:].split("\\"):
            p = ntpath.join(p, component)
            result.add(p)
        return result

    def allowed(self, path):
        need(type(path) is str and ntpath.normpath(path) == path, "EXACT_NATIVE_PATH")
        if path in self.ancestors():
            return
        for alias, root in ROOTS.items():
            if path == root:
                return
            if path.startswith(root + "\\"):
                need(
                    path_for(alias, *path[len(root) + 1 :].split("\\")) == path,
                    "CANONICAL_IO_DESCENDANT",
                )
                return
        raise ValueError("OUTSIDE_NATIVE_IO_SCOPE")

    @contextlib.contextmanager
    def opened(
        self,
        path,
        *,
        create=False,
        directory=None,
        write=False,
        delete=False,
        journal=False,
    ):
        self.allowed(path)
        handles = []
        deadline = self.clock() + 5 * 10**9
        if not journal:
            if path == "D:\\":
                yield self._directory(path)
                need(self.clock() <= deadline, "WINDOWS_IO_DEADLINE")
                return
            parent = self._directory(ntpath.dirname(path))
            if not create and not write and not delete and path in self.cache:
                yield self._directory(path)
                need(self.clock() <= deadline, "WINDOWS_IO_DEADLINE")
                return
            key, h = self.book.open(
                lambda: self.calls.relative(
                    parent,
                    ntpath.basename(path),
                    directory=directory,
                    create=create,
                    write=write,
                    delete=delete,
                    sid=self.sid,
                )
            )
            retain = False
            try:
                row = self.calls.describe(h)
                need(
                    not row["reparse"]
                    and row["links"] == 1
                    and (
                        directory is None or (row["kind"] == "directory") == directory
                    ),
                    "NATIVE_PATH_KIND_OR_LINK",
                )
                if path not in self.ancestors():
                    self.calls.acl(h, self.sid)
                if not create and row["kind"] == "directory":
                    self.cache[path] = (key, h, row["id"])
                    retain = True
                need(self.clock() <= deadline, "WINDOWS_IO_DEADLINE")
                yield h
                need(self.clock() <= deadline, "WINDOWS_IO_DEADLINE")
            finally:
                if not retain:
                    self.book.close(key, h)
            return
        try:
            key, h = self.book.open(self.calls.open_drive, journal=journal)
            handles.append((key, h))
            parts = path[3:].split("\\") if path != "D:\\" else []
            for index, leaf in enumerate(parts):
                final = index == len(parts) - 1
                key, h = self.book.open(
                    lambda parent=h, leaf=leaf: self.calls.relative(
                        parent,
                        leaf,
                        directory=directory if final else True,
                        create=create and final,
                        write=write and final,
                        delete=delete and final,
                        sid=self.sid,
                    ),
                    journal=journal,
                )
                handles.append((key, h))
                row = self.calls.describe(h)
                need(
                    row["reparse"] is False and row["links"] == 1, "NATIVE_LINK_REFUSED"
                )
                if final and path not in self.ancestors():
                    self.calls.acl(h, self.sid)
                need(self.clock() <= deadline, "WINDOWS_IO_DEADLINE")
            yield h
            need(self.clock() <= deadline, "WINDOWS_IO_DEADLINE")
        finally:
            for key, h in reversed(handles):
                self.book.close(key, h, journal=journal)

    def _directory(self, path):
        self.allowed(path)
        if path not in self.cache:
            if path == "D:\\":
                key, h = self.book.open(self.calls.open_drive)
            else:
                parent = self._directory(ntpath.dirname(path))
                key, h = self.book.open(
                    lambda: self.calls.relative(
                        parent, ntpath.basename(path), directory=True, sid=self.sid
                    )
                )
            try:
                row = self.calls.describe(h)
                need(
                    row["kind"] == "directory"
                    and not row["reparse"]
                    and row["links"] == 1,
                    "PINNED_DIRECTORY_REQUIRED",
                )
                if path not in self.ancestors():
                    self.calls.acl(h, self.sid)
                self.cache[path] = (key, h, row["id"])
            except BaseException:
                self.book.close(key, h)
                raise
        _, h, identity = self.cache[path]
        row = self.calls.describe(h)
        need(
            row["id"] == identity and not row["reparse"] and row["links"] == 1,
            "RETAINED_DIRECTORY_CHANGED",
        )
        return h

    def close_cache(self):
        for path in sorted(self.cache, key=len, reverse=True):
            key, h, _ = self.cache[path]
            self.book.close(key, h)
            del self.cache[path]

    def names(self, path, maximum):
        with self.opened(path, directory=True) as h:
            return self.calls.names(h, maximum)

    def chain(self, path):
        need(path == BASE, "EXACT_BASE_CHAIN")
        result = []
        parent = None
        for p in sorted(self.ancestors(), key=len):
            with self.opened(p, directory=True) as h:
                r = self.calls.describe(h)
                result.append(
                    {k: r[k] for k in ("id", "kind", "reparse", "links")}
                    | {"path": p, "parent_id": parent}
                )
                parent = r["id"]
        return result

    def inspect(self, path):
        self.allowed(path)
        try:
            callbacks = [
                h
                for key, h in self.callback_handles.items()
                if key not in self.completed and self.operations[key]["path"] == path
            ]
            if callbacks:
                need(len(callbacks) == 1, "AMBIGUOUS_NATIVE_PATH_HANDLES")
                h = callbacks[0]
                r = self.calls.describe(h)
                need(
                    ntpath.normcase(self.calls.final_path(h)) == ntpath.normcase(path),
                    "NATIVE_CALLBACK_PATH_CHANGED",
                )
                parent = None
                if path != "D:\\":
                    with self.opened(ntpath.dirname(path), directory=True) as hp:
                        parent = self.calls.describe(hp)["id"]
                return {k: r[k] for k in ("id", "kind", "reparse", "links")} | {
                    "path": path,
                    "parent_id": parent,
                }
            with self.opened(path) as h:
                r = self.calls.describe(h)
                parent = None
                if path != "D:\\":
                    with self.opened(ntpath.dirname(path), directory=True) as hp:
                        parent = self.calls.describe(hp)["id"]
                return {k: r[k] for k in ("id", "kind", "reparse", "links")} | {
                    "path": path,
                    "parent_id": parent,
                }
        except OSError as exc:
            if getattr(exc, "winerror", None) in (2, 3):
                return None
            raise

    def operation(self, path):
        keys = [
            k
            for k, v in self.operations.items()
            if v["path"] == path and k not in self.completed
        ]
        need(len(keys) == 1, "ONE_RESERVED_IO_OPERATION")
        return keys[0]

    def mkdir(self, path):
        key = self.operation(path)
        with self.opened(path, create=True, directory=True):
            pass
        self.completed.add(key)

    def write_new(self, path, raw):
        key = self.operation(path)
        with self.opened(path, create=True, directory=False, write=True) as h:
            self.calls.write(h, raw)
            self.calls.flush(h)
            need(self.calls.read(h, len(raw)) == raw, "CREATE_HANDLE_WRITE_READBACK")
        self.completed.add(key)

    def read_bytes(self, path, maximum_bytes=1024**2):
        with self.opened(path, directory=False) as h:
            return self.calls.read(h, maximum_bytes)

    def readback(self, path):
        raw = self.read_bytes(path)
        return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

    def replace_owned(self, source, target):
        key = self.operation(target)
        need(
            self.guard is not None
            and source in self.guard.owned_files
            and target in self.guard.owned_files,
            "OWNED_REPLACE_ONLY",
        )
        self.guard.validate_path(source)
        self.guard.validate_path(target)
        with self.opened(ntpath.dirname(target), directory=True) as parent:
            with self.opened(source, directory=False, delete=True) as h:
                expected = self.calls.describe(h)["id"]
                self.calls.rename(h, parent, ntpath.basename(target))
                self.calls.flush(h)
        need(self.inspect(target)["id"] == expected, "RENAMED_NATIVE_IDENTITY")
        self.completed.add(key)

    def verify_handle(self, handle, path, module):
        need(
            self.guard is not None and handle.token in self.operations,
            "NATIVE_CALLBACK_RESERVATION",
        )
        row = self.calls.describe(int(handle))
        need(
            ntpath.normcase(self.calls.final_path(int(handle))) == ntpath.normcase(path)
            and row["reparse"] is False
            and row["links"] == 1,
            "NATIVE_CALLBACK_IDENTITY",
        )
        prior = self.guard.file_identities.get(path)
        need(prior is None or row["id"] == prior, "NATIVE_CALLBACK_FILE_SUBSTITUTION")
        self.operations[handle.token]["path"] = path
        self.callback_handles[handle.token] = int(handle)
        if hasattr(self.book.resources, "bind_native_handle"):
            self.book.resources.bind_native_handle(handle.token, int(handle))

    def verify_mutex(self, handle, name, module):
        need(
            self.guard is not None
            and name.startswith("Global\\Atlas-Isolated-Fence-")
            and not self.calls.closed(int(handle)),
            "OWNED_MUTEX_HANDLE_REQUIRED",
        )
        self.callback_handles[handle.token] = int(handle)

    def verify_token(self, handle, owner):
        current = self.calls.current_process_native()
        need(
            self.guard is not None
            and owner == self.book.resources.state["owners"][self.book.owner]
            and current == {"pid": owner["pid"], "created": owner["created"]}
            and self.calls.token_identity(int(handle)) == {"sid": self.sid, "type": 1},
            "OWNED_TOKEN_IDENTITY",
        )
        self.callback_handles[handle.token] = int(handle)

    def verify_image(self, handle, path, pin):
        row = self.calls.describe(int(handle))
        raw = self.calls.read(int(handle), 32 * 1024**2)
        need(
            row["id"] == list(pin["file_id"])
            and hashlib.sha256(raw).hexdigest() == pin["sha256"],
            "PINNED_NATIVE_IMAGE",
        )
        self.callback_handles[handle.token] = int(handle)

    def note_closed(self, owner, key, handle):
        need(owner == self.book.owner, "IO_CLOSE_OWNER")
        if key in self.callback_handles:
            need(
                self.calls.closed(self.callback_handles[key]),
                "NATIVE_CALLBACK_NOT_CLOSED",
            )
        else:
            need(key in self.operations, "UNDECLARED_IO_CLOSE")
            # SQLite driver handle is private; prove its own closed state.
            if self.operations[key]["kind"] == "handle" and handle is not None:
                try:
                    handle.execute("SELECT 1")
                except Exception as exc:
                    import sqlite3

                    need(
                        isinstance(exc, sqlite3.ProgrammingError)
                        and str(exc) == "Cannot operate on a closed database.",
                        "SQLITE_CLOSE_UNVERIFIED",
                    )
                else:
                    raise ValueError("SQLITE_CONNECTION_STILL_OPEN")
        self.completed.add(key)

    def closed(self, owner, key):
        return owner == self.book.owner and key in self.completed

    def sqlite_open(self, *args, **kwargs):
        import sqlite3

        return sqlite3.connect(*args, **kwargs)


class NativeJournalIO:
    """Closed, fixed E/journal batches used solely by CreateNewJournal."""

    def __init__(self, io, directory_identity):
        self.io, self.identity = io, directory_identity
        self.open_files = {}

    def verify_directory(self, path, identity):
        need(
            path == path_for("E", "journal") and identity == self.identity,
            "EXACT_JOURNAL_DIRECTORY",
        )
        with (
            self.io.book.journal(),
            self.io.opened(path, directory=True, journal=True) as h,
        ):
            need(
                self.io.calls.describe(h)["id"] == identity,
                "JOURNAL_DIRECTORY_REPLACED",
            )

    def names(self):
        with (
            self.io.book.journal(),
            self.io.opened(path_for("E", "journal"), directory=True, journal=True) as h,
        ):
            return self.io.calls.names(h, LIMITS["entries"])

    def read_exact(self, path, maximum_bytes):
        self._path(path)
        with (
            self.io.book.journal(),
            self.io.opened(path, directory=False, journal=True) as h,
        ):
            return self.io.calls.read(h, maximum_bytes)

    def _path(self, path):
        import re

        need(
            ntpath.dirname(path) == path_for("E", "journal")
            and re.fullmatch(r"record-\d{8}\.json", ntpath.basename(path)),
            "JOURNAL_RECORD_PATH",
        )

    def create_new(self, path, parent):
        self._path(path)
        need(
            parent == self.identity and not self.open_files,
            "JOURNAL_CREATE_NEW_IDENTITY",
        )
        batch = self.io.book.journal()
        batch.__enter__()
        opened = self.io.opened(
            path, create=True, directory=False, write=True, journal=True
        )
        try:
            h = opened.__enter__()
        except BaseException:
            batch.__exit__(*__import__("sys").exc_info())
            raise
        self.open_files[int(h)] = {
            "path": path,
            "opened": opened,
            "batch": batch,
            "raw": None,
        }
        return int(h)

    def write_exact(self, handle, raw):
        need(
            handle in self.open_files and self.open_files[handle]["raw"] is None,
            "ONE_JOURNAL_WRITE",
        )
        try:
            self.io.calls.write(handle, raw)
            self.open_files[handle]["raw"] = raw
        except BaseException:
            item = self.open_files[handle]
            self._close(item)
            del self.open_files[handle]
            raise

    @staticmethod
    def _close(item):
        try:
            item["opened"].__exit__(None, None, None)
        finally:
            item["batch"].__exit__(None, None, None)

    def flush_close(self, handle):
        need(handle in self.open_files, "OWNED_JOURNAL_HANDLE")
        item = self.open_files[handle]
        try:
            self.io.calls.flush(handle)
            need(
                item["raw"] is not None
                and self.io.calls.read(handle, len(item["raw"])) == item["raw"],
                "JOURNAL_CREATION_HANDLE_READBACK",
            )
        finally:
            self._close(item)
            del self.open_files[handle]
        return {
            "closed": not self.io.book.journal_live,
            "flushed": True,
            "path": item["path"],
            "sha256": hashlib.sha256(item["raw"]).hexdigest(),
        }
