"""Native NTFS synthetic protected publication; not wired to production paths.

No ACL repair: new explicitly requested directories only. Existing roots must
already have exactly the protected owner/SYSTEM DACL. Holds no-delete
ancestor handles; publishes a flushed manifest using an atomic no-replace NTFS hard link.
"""
import ctypes as C
import hashlib
import json
import ntpath
import os
import re
from ctypes import wintypes as W

if os.name != "nt":
    raise ImportError("Native Windows required")

K = C.WinDLL("kernel32", use_last_error=True)
A = C.WinDLL("advapi32", use_last_error=True)
N = C.WinDLL("ntdll", use_last_error=True)
INVALID = C.c_void_p(-1).value
READ_CONTROL, DELETE, SYNC = 0x20000, 0x10000, 0x100000
READ, WRITE, ATTR = 0x80000000, 0x40000000, 0x80
DIR_FLAGS, REPARSE, WRITE_THROUGH = 0x02200000, 0x400, 0x80000000


class SA(C.Structure):
    _fields_ = [("length", W.DWORD), ("descriptor", C.c_void_p), ("inherit", W.BOOL)]


class Info(C.Structure):
    _fields_ = [("attributes", W.DWORD), ("creation", W.FILETIME), ("access", W.FILETIME),
                ("write", W.FILETIME), ("volume", W.DWORD), ("size_hi", W.DWORD),
                ("size_lo", W.DWORD), ("links", W.DWORD), ("index_hi", W.DWORD), ("index_lo", W.DWORD)]


class AclSize(C.Structure):
    _fields_ = [("count", W.DWORD), ("used", W.DWORD), ("free", W.DWORD)]


class Ace(C.Structure):
    _fields_ = [("type", C.c_ubyte), ("flags", C.c_ubyte), ("size", W.WORD), ("mask", W.DWORD), ("sid", W.DWORD)]


class SidAttr(C.Structure):
    _fields_ = [("sid", C.c_void_p), ("attributes", W.DWORD)]


class Unicode(C.Structure):
    _fields_ = [("length", W.WORD), ("maximum", W.WORD), ("buffer", W.LPWSTR)]


class ObjectAttributes(C.Structure):
    _fields_ = [("length", W.DWORD), ("root", W.HANDLE), ("name", C.POINTER(Unicode)),
                ("attributes", W.DWORD), ("security", C.c_void_p), ("qos", C.c_void_p)]


class IO(C.Structure):
    _fields_ = [("status", C.c_void_p), ("information", C.c_size_t)]


class Link(C.Structure):
    _fields_ = [("replace", W.BOOL), ("root", W.HANDLE), ("length", W.DWORD), ("name", W.WCHAR * 1)]


def bind(lib, name, args, result=W.BOOL):
    f = getattr(lib, name)
    f.argtypes, f.restype = args, result
    return f


create_file = bind(K, "CreateFileW", [W.LPCWSTR, W.DWORD, W.DWORD, C.POINTER(SA), W.DWORD, W.DWORD, W.HANDLE], W.HANDLE)
close_handle = bind(K, "CloseHandle", [W.HANDLE])
get_info = bind(K, "GetFileInformationByHandle", [W.HANDLE, C.POINTER(Info)])
flush = bind(K, "FlushFileBuffers", [W.HANDLE])
write_file = bind(K, "WriteFile", [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p])
read_file = bind(K, "ReadFile", [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p])
create_directory = bind(K, "CreateDirectoryW", [W.LPCWSTR, C.POINTER(SA)])
nt_create = bind(N, "NtCreateFile", [C.POINTER(W.HANDLE), W.DWORD, C.POINTER(ObjectAttributes), C.POINTER(IO), C.c_void_p, W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_void_p, W.DWORD], W.LONG)
nt_set = bind(N, "NtSetInformationFile", [W.HANDLE, C.POINTER(IO), C.c_void_p, W.DWORD, C.c_int], W.LONG)
nt_error = bind(N, "RtlNtStatusToDosError", [W.LONG], W.DWORD)
local_free = bind(K, "LocalFree", [C.c_void_p], C.c_void_p)
get_sd = bind(A, "GetSecurityInfo", [W.HANDLE, C.c_int, W.DWORD, C.POINTER(C.c_void_p), C.c_void_p, C.POINTER(C.c_void_p), C.c_void_p, C.POINTER(C.c_void_p)], W.DWORD)
control_sd = bind(A, "GetSecurityDescriptorControl", [C.c_void_p, C.POINTER(W.WORD), C.POINTER(W.DWORD)])
acl_info = bind(A, "GetAclInformation", [C.c_void_p, C.c_void_p, W.DWORD, C.c_int])
get_ace = bind(A, "GetAce", [C.c_void_p, W.DWORD, C.POINTER(C.c_void_p)])
sid_string = bind(A, "ConvertSidToStringSidW", [C.c_void_p, C.POINTER(C.c_void_p)])
sddl_sd = bind(A, "ConvertStringSecurityDescriptorToSecurityDescriptorW", [W.LPCWSTR, W.DWORD, C.POINTER(C.c_void_p), C.c_void_p])
open_token = bind(A, "OpenProcessToken", [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)])
process = bind(K, "GetCurrentProcess", [], W.HANDLE)
token_info = bind(A, "GetTokenInformation", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)])
volume_info = bind(K, "GetVolumeInformationByHandleW", [W.HANDLE, W.LPWSTR, W.DWORD, C.c_void_p, C.c_void_p, C.c_void_p, W.LPWSTR, W.DWORD])


def check(ok):
    if not ok:
        # No OS path/error text is emitted to metadata/audit.
        raise C.WinError(C.get_last_error(), "Native protected operation refused")


def sid_text(sid):
    out = C.c_void_p()
    check(sid_string(sid, C.byref(out)))
    try:
        return C.wstring_at(out)
    finally:
        local_free(out)


def current_sid():
    token = W.HANDLE()
    check(open_token(process(), 8, C.byref(token)))
    try:
        size = W.DWORD()
        token_info(token, 1, None, 0, C.byref(size))
        buf = C.create_string_buffer(size.value)
        check(token_info(token, 1, buf, size, C.byref(size)))
        return sid_text(C.cast(buf, C.POINTER(SidAttr)).contents.sid)
    finally:
        close_handle(token)


def descriptor(sid):
    out = C.c_void_p()
    check(sddl_sd(f"O:{sid}D:P(A;OICI;FA;;;{sid})(A;OICI;FA;;;SY)", 1, C.byref(out), None))
    return out


def validate_acl(handle, sid):
    owner, dacl, sd = C.c_void_p(), C.c_void_p(), C.c_void_p()
    error = get_sd(handle, 1, 5, C.byref(owner), None, C.byref(dacl), None, C.byref(sd))
    if error:
        raise PermissionError(error, "Security descriptor unavailable")
    try:
        ctrl, rev = W.WORD(), W.DWORD()
        check(control_sd(sd, C.byref(ctrl), C.byref(rev)))
        if sid_text(owner) != sid or not ctrl.value & 0x1000 or not dacl:
            raise PermissionError("Protected owner DACL required")
        size = AclSize()
        check(acl_info(dacl, C.byref(size), C.sizeof(size), 2))
        found = set()
        for i in range(size.count):
            ptr = C.c_void_p()
            check(get_ace(dacl, i, C.byref(ptr)))
            ace = C.cast(ptr, C.POINTER(Ace)).contents
            principal = sid_text(ptr.value + Ace.sid.offset)
            if ace.type != 0 or ace.flags not in (0, 3) or ace.mask != 0x1F01FF or principal not in {sid, "S-1-5-18"}:
                raise PermissionError("Broad, inherited or unexpected ACE")
            found.add(principal)
        if size.count != 2 or found != {sid, "S-1-5-18"}:
            raise PermissionError("Exact owner/SYSTEM DACL required")
    finally:
        local_free(sd)


def canonical_path(value):
    path = os.fspath(value)
    if not re.match(r"^[A-Za-z]:\\", path) or path.startswith("\\\\"):
        raise ValueError("Local absolute drive path required")
    parts = path[3:].split("\\")
    if any(not p or p in {".", ".."} or p[-1:] in {".", " "} or ":" in p or "/" in p or re.match(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", p) for p in parts):
        raise ValueError("Noncanonical destination")
    if ntpath.normpath(path) != path:
        raise ValueError("Path normalization refused")
    return path


def info(handle):
    data = Info()
    check(get_info(handle, C.byref(data)))
    if data.attributes & REPARSE:
        raise PermissionError("Reparse traversal refused")
    return data


def filtered(raw):
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path
    loader = spec_from_file_location("isolated_filter", Path(__file__).with_name("isolated_adapter.py"))
    module = module_from_spec(loader)
    loader.loader.exec_module(module)
    return module.safe_metadata(raw)


def nt_check(status):
    if status < 0:
        raise C.WinError(nt_error(status), "Native relative operation refused")


def relative_open(parent, leaf, sid, directory, create=False, access=READ_CONTROL | ATTR | 1):
    if not leaf or leaf in {".", ".."} or any(x in leaf for x in ("/", "\\", ":")):
        raise ValueError("One relative component required")
    text = C.create_unicode_buffer(leaf)
    name = Unicode(len(leaf.encode("utf-16-le")), C.sizeof(text), C.cast(text, W.LPWSTR))
    sd = descriptor(sid) if create else None
    try:
        attributes = ObjectAttributes(C.sizeof(ObjectAttributes), parent, C.pointer(name), 0x40 | 0x1000, sd, None)
        handle = W.HANDLE()
        options = 0x200000 | 0x20 | (1 if directory else 0x40) | (2 if create and not directory else 0)
        nt_check(nt_create(C.byref(handle), access | SYNC, C.byref(attributes), C.byref(IO()), None, 0,
                           3 if directory else 1, 2 if create else 1, options, None, 0))
        try:
            data = info(handle)
            if bool(data.attributes & 0x10) != directory:
                raise PermissionError("Unexpected object type")
        except BaseException:
            close_handle(handle)
            raise
        return handle
    finally:
        if sd:
            local_free(sd)


class WindowsOutput:
    """Native private NTFS bundle. Explicit close; no deletion or ACL repair."""
    def __init__(self, root):
        self.root = canonical_path(root)
        self.sid = current_sid()
        self.handles = []
        try:
            h = create_file(self.root[:3], READ_CONTROL | ATTR | 1, 3, None, 3, DIR_FLAGS, None)
            if h == INVALID:
                check(False)
            self.handles.append(h)
            info(h)
            # Every subsequent lookup is relative to an already verified handle.
            # No path is re-resolved through a mutable ancestor.
            for part in self.root[3:].split("\\"):
                self.handles.append(relative_open(self.handles[-1], part, self.sid, True))
            self.root_handle = self.handles[-1]
            validate_acl(self.root_handle, self.sid)
            fs = C.create_unicode_buffer(32)
            check(volume_info(self.root_handle, None, 0, None, None, None, fs, 32))
            if fs.value != "NTFS":
                raise PermissionError("Only locally tested NTFS supported")
        except BaseException:
            self.close()
            raise

    @classmethod
    def create_root(cls, root):
        root = canonical_path(root)
        sid = current_sid()
        handles = []
        try:
            h = create_file(root[:3], READ_CONTROL | ATTR | 1, 3, None, 3, DIR_FLAGS, None)
            if h == INVALID:
                check(False)
            handles.append(h)
            info(h)
            parts = root[3:].split("\\")
            for part in parts[:-1]:
                handles.append(relative_open(handles[-1], part, sid, True))
            handles.append(relative_open(handles[-1], parts[-1], sid, True, create=True))
            # Validate the exact newly created root through its already pinned
            # handles, instead of reopening an absolute path.
            out = cls.__new__(cls)
            out.root, out.sid, out.handles = root, sid, handles
            out.root_handle = handles[-1]
            out._verify()
            fs = C.create_unicode_buffer(32)
            check(volume_info(out.root_handle, None, 0, None, None, None, fs, 32))
            if fs.value != "NTFS":
                raise PermissionError("Only locally tested NTFS supported")
            handles = []
            return out
        finally:
            for h in reversed(handles):
                close_handle(h)

    def close(self):
        for handle in reversed(self.handles):
            close_handle(handle)
        self.handles = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _verify(self):
        if not self.handles:
            raise PermissionError("Output handles closed")
        for h in self.handles:
            info(h)
        validate_acl(self.root_handle, self.sid)

    def _write(self, directory, name, data):
        self._write_bound(directory, name, data)

    def write_bound(self, name, data):
        """Return identity from the exclusive creation handle, never a reopen."""
        self._verify()
        return self._write_bound(self.root_handle, name, data)

    def _write_bound(self, directory, name, data):
        if len(data) > 65536:
            raise ValueError("Output bound")
        h = relative_open(directory, name, self.sid, False, create=True, access=READ | WRITE | READ_CONTROL)
        try:
            validate_acl(h, self.sid)
            before = info(h)
            identity = [before.volume, before.index_hi, before.index_lo]
            if before.links != 1:
                raise PermissionError("Linked file refused")
            count = W.DWORD()
            check(write_file(h, data, len(data), C.byref(count), None))
            if count.value != len(data):
                raise OSError("Partial output retained")
            check(flush(h))
            after = info(h)
            if ([after.volume, after.index_hi, after.index_lo] != identity or after.links != 1
                    or (after.size_hi << 32) | after.size_lo != len(data)):
                raise OSError("Creation handle changed during publication")
            return {"id": identity, "sha256": hashlib.sha256(data).hexdigest()}
        finally:
            close_handle(h)

    def publish(self, name, value):
        data = json.dumps(filtered(json.dumps(value, allow_nan=False).encode()), sort_keys=True, separators=(",", ":")).encode()
        if not re.fullmatch(r"[a-z0-9-]{1,48}\.json", name):
            raise ValueError("Opaque operation filename required")
        self._verify()
        staging = relative_open(self.root_handle, name + ".pending", self.sid, True, create=True)
        try:
            digest = hashlib.sha256(data).hexdigest()
            audit = json.dumps({"schema": 1, "event": "METADATA_STAGED", "bytes": len(data), "sha256": digest}, sort_keys=True).encode()
            self._write(staging, "metadata.json", data)
            self._write(staging, "audit.json", audit)
            self._write(staging, "commit.json", json.dumps({"schema": 1, "metadata_sha256": digest, "audit_sha256": hashlib.sha256(audit).hexdigest()}, sort_keys=True).encode())
            self._verify()
            commit = relative_open(staging, "commit.json", self.sid, False, access=DELETE | READ_CONTROL | ATTR)
            try:
                validate_acl(commit, self.sid)
                if info(commit).links != 1:
                    raise PermissionError("Linked commitment refused")
                target = (name + ".commit").encode("utf-16-le")
                buf = C.create_string_buffer(max(C.sizeof(Link), Link.name.offset + len(target) + 2))
                link = C.cast(buf, C.POINTER(Link)).contents
                link.replace, link.root, link.length = False, self.root_handle, len(target)
                C.memmove(C.addressof(buf) + Link.name.offset, target, len(target))
                nt_check(nt_set(commit, C.byref(IO()), buf, len(buf), 11))
            finally:
                close_handle(commit)
            return digest
        finally:
            close_handle(staging)

    def read(self, name, expected_digest=None):
        if not re.fullmatch(r"[a-z0-9-]{1,48}\.json", name):
            raise ValueError("Opaque operation filename required")
        self._verify()
        published = relative_open(self.root_handle, name + ".commit", self.sid, False, access=READ | READ_CONTROL)
        staging = None
        try:
            published_info = info(published)
            validate_acl(published, self.sid)
            if published_info.links != 2:
                raise PermissionError("Unexpected commit link identity")
            staging = relative_open(self.root_handle, name + ".pending", self.sid, True)
            validate_acl(staging, self.sid)
            values = {}
            for file in ("metadata.json", "audit.json", "commit.json"):
                f = relative_open(staging, file, self.sid, False, access=READ | READ_CONTROL)
                try:
                    validate_acl(f, self.sid)
                    fi = info(f)
                    if fi.links != (2 if file == "commit.json" else 1):
                        raise PermissionError("Linked evidence refused")
                    if file == "commit.json" and (fi.volume, fi.index_hi, fi.index_lo) != (published_info.volume, published_info.index_hi, published_info.index_lo):
                        raise PermissionError("Commitment replaced")
                    buf, count = C.create_string_buffer(65537), W.DWORD()
                    check(read_file(f, buf, 65537, C.byref(count), None))
                    if count.value > 65536:
                        raise ValueError("Oversize evidence")
                    values[file] = buf.raw[:count.value]
                finally:
                    close_handle(f)
            commit = json.loads(values["commit.json"])
            digest = hashlib.sha256(values["metadata.json"]).hexdigest()
            if commit != {"schema": 1, "metadata_sha256": digest, "audit_sha256": hashlib.sha256(values["audit.json"]).hexdigest()}:
                raise ValueError("Integrity mismatch")
            if expected_digest is not None and expected_digest != digest:
                raise ValueError("Independent commitment mismatch")
            if json.loads(values["audit.json"]) != {"schema": 1, "event": "METADATA_STAGED", "bytes": len(values["metadata.json"]), "sha256": digest}:
                raise ValueError("Audit mismatch")
            return filtered(values["metadata.json"])
        finally:
            if staging:
                close_handle(staging)
            close_handle(published)
