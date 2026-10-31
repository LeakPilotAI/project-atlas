"""Native append-only atomic selection publication. No root creation or defaults."""

import ctypes as C
import re
from contextlib import contextmanager
from pathlib import Path
from threading import get_ident

from scripts.release_selection import MAX_RECORDS, encoded, strict


class NativeSelectionStore:
    domain = "WINDOWS_LOCAL"

    def __init__(self, *, root=None, native_root=None):
        if root != "D:\\AtlasRuntime\\selection":
            raise ValueError("EXACT_ACCEPTED_SELECTION_RESOURCE_REQUIRED")
        self._open(root, native_root, "WINDOWS_LOCAL")

    @classmethod
    def disposable(cls, *, root, native_root):
        """Explicit native fixture domain; never operational selector authority."""
        path = Path(root).absolute()
        repo = Path(__file__).resolve().parents[1]
        relative = path.relative_to(repo / "logs/diagnostics")
        if (
            not relative.parts[0].startswith("qd-selector-v1-native-")
            or len(relative.parts) != 3
            or relative.parts[-1] != "selection"
            or str(path).casefold().startswith("d:\\atlasruntime")
        ):
            raise ValueError("EXACT_NATIVE_SELECTION_FIXTURE_REQUIRED")
        value = cls.__new__(cls)
        value._open(str(path), native_root, "DISPOSABLE")
        return value

    def _open(self, root, native_root, domain):
        if (
            type(native_root) is not list
            or len(native_root) != 3
            or any(type(n) is not int or not 0 <= n <= 0xFFFFFFFF for n in native_root)
        ):
            raise ValueError("EXACT_ACCEPTED_SELECTION_RESOURCE_REQUIRED")
        from scripts.observation_runtime.personal_paper_inception import (
            native_primitives,
        )

        self.native = native_primitives()
        self.output = self.native.w.WindowsOutput(root)
        self.domain = domain
        self.root, self.native_root = root, list(native_root)
        self.poisoned = False
        self.mutex = None
        self.owner = None
        self.file_handles = []
        self._binding = self.output, root, tuple(native_root), domain
        try:
            self._verify()
            self.coordinator = self.native.native.Registry.__new__(
                self.native.native.Registry
            )
            self.coordinator.output, self.coordinator.root_id = (
                self.output,
                list(native_root),
            )
            self.coordinator._create_mutex()
            self.mutex = self.coordinator.mutex
        except BaseException:
            self.close()
            raise

    def _verify(self):
        if self.poisoned:
            raise ValueError("SELECTION_CLOSED_OR_UNKNOWN")
        if (
            self.output,
            self.root,
            tuple(self.native_root),
            self.domain,
        ) != self._binding:
            raise ValueError("SELECTION_RESOURCE_BINDING_CHANGED")
        self.output._verify()
        if (
            self.native.native.file_identity(self.output.root_handle)
            != self.native_root
        ):
            raise ValueError("SELECTION_ROOT_SUBSTITUTION")
        if hasattr(self, "coordinator"):
            # Existing read-only absolute/handle equality check also catches
            # a drive-letter/volume remap while original handles remain alive.
            self.coordinator._binding()

    @contextmanager
    def locked(self):
        if not self.mutex:
            raise ValueError("SELECTION_STORE_CLOSED")
        if self.owner == get_ident():
            raise ValueError("SELECTION_REENTRANT_OWNER_REFUSED")
        status = self.coordinator.wait(self.mutex, 3000)
        if status != 0:
            if status == 0x80:
                self.poisoned = True
                self.coordinator.release(self.mutex)
            raise ValueError("SELECTION_BUSY_OR_ABANDONED")
        try:
            if self.owner is not None:
                raise ValueError("SELECTION_REENTRANT_OWNER_REFUSED")
            self.owner = get_ident()
            self._verify()
            yield
        finally:
            self.owner = None
            if not self.coordinator.release(self.mutex):
                self.poisoned = True
                raise OSError("SELECTION_MUTEX_RELEASE_UNCONFIRMED")

    def _read_pair(self, revision):
        w = self.native.w
        names = [f"r{revision:04d}.{suffix}" for suffix in ("pending", "json")]
        handles = []
        try:
            for name in names:
                h = w.relative_open(
                    self.output.root_handle,
                    name,
                    self.output.sid,
                    False,
                    access=w.READ | w.READ_CONTROL,
                )
                handles.append(h)
                self.file_handles.append(h)
                w.validate_acl(h, self.output.sid)
            infos = [w.info(h) for h in handles]
            ids = [[i.volume, i.index_hi, i.index_lo] for i in infos]
            if ids[0] != ids[1] or any(
                i.links != 2 or (i.size_hi << 32 | i.size_lo) > 65536 for i in infos
            ):
                raise ValueError("SELECTION_PUBLICATION_IDENTITY")
            buffer, count = C.create_string_buffer(65537), w.W.DWORD()
            w.check(w.read_file(handles[1], buffer, 65537, C.byref(count), None))
            raw = buffer.raw[: count.value]
            envelope = strict(raw)
            if (
                len(raw) > 65536
                or encoded(envelope) != raw
                or set(envelope) != {"record", "native_id"}
                or envelope["native_id"] != ids[0]
            ):
                raise ValueError("SELECTION_RECORD_ENCODING")
            return envelope["record"]
        finally:
            failed = False
            for handle in handles:
                if not w.close_handle(handle):
                    self.poisoned = True
                    failed = True
                else:
                    self.file_handles.remove(handle)
            if failed:
                raise OSError("SELECTION_READ_CLOSE_UNCONFIRMED")

    def records(self):
        if self.owner != get_ident():
            raise ValueError("SELECTION_LOCK_OWNERSHIP_REQUIRED")
        self._verify()
        names = {p.name for p in Path(self.root).iterdir()}
        if len(names) > MAX_RECORDS * 2 or any(
            not re.fullmatch(r"r[0-9]{4}\.(json|pending)", n) for n in names
        ):
            raise ValueError("SELECTION_NAMESPACE_OR_CAPACITY")
        if len(names) % 2:
            raise ValueError("SELECTION_INTERRUPTED_TAIL_NO_REPAIR")
        revisions = len(names) // 2
        expected = {
            f"r{i:04d}.{suffix}"
            for i in range(1, revisions + 1)
            for suffix in ("pending", "json")
        }
        if names != expected:
            raise ValueError("SELECTION_INCOMPLETE_OR_FOREIGN_TAIL")
        return [self._read_pair(i) for i in range(1, revisions + 1)]

    def publish(self, row):
        if self.owner != get_ident():
            raise ValueError("SELECTION_LOCK_OWNERSHIP_REQUIRED")
        self._verify()
        revision = row["revision"]
        if not 1 <= revision <= MAX_RECORDS or len(encoded(row)) > 65536:
            raise ValueError("SELECTION_RECORD_CAPACITY")
        w = self.native.w
        name = f"r{revision:04d}"
        try:
            handle = w.relative_open(
                self.output.root_handle,
                name + ".pending",
                self.output.sid,
                False,
                create=True,
                access=w.READ | w.WRITE | w.DELETE | w.READ_CONTROL,
            )
            self.file_handles.append(handle)
            try:
                w.validate_acl(handle, self.output.sid)
                identity = self.native.native.file_identity(handle)
                data = encoded({"record": row, "native_id": identity})
                if len(data) > 65536 or w.info(handle).links != 1:
                    raise ValueError("SELECTION_STAGE_SUBSTITUTION")
                count = w.W.DWORD()
                w.check(w.write_file(handle, data, len(data), C.byref(count), None))
                if count.value != len(data):
                    raise OSError("SELECTION_PARTIAL_WRITE_PRESERVED")
                w.check(w.flush(handle))
                info = w.info(handle)
                if (
                    self.native.native.file_identity(handle) != identity
                    or info.links != 1
                    or (info.size_hi << 32 | info.size_lo) != len(data)
                ):
                    raise ValueError("SELECTION_STAGE_SUBSTITUTION")
                target = (name + ".json").encode("utf-16-le")
                buffer = C.create_string_buffer(
                    max(C.sizeof(w.Link), w.Link.name.offset + len(target) + 2)
                )
                link = C.cast(buffer, C.POINTER(w.Link)).contents
                link.replace, link.root, link.length = (
                    False,
                    self.output.root_handle,
                    len(target),
                )
                C.memmove(C.addressof(buffer) + w.Link.name.offset, target, len(target))
                # Existing NTFS atomic no-replace hardlink primitive. This single
                # published record is the durable selected reference AND receipt.
                w.nt_check(w.nt_set(handle, C.byref(w.IO()), buffer, len(buffer), 11))
                w.check(w.flush(handle))
            finally:
                if not w.close_handle(handle):
                    raise OSError("SELECTION_PUBLICATION_CLOSE_UNCONFIRMED")
                self.file_handles.remove(handle)
            if self._read_pair(revision) != row:
                raise ValueError("SELECTION_POST_COMMIT_UNKNOWN")
        except BaseException:
            self.poisoned = True  # Preserve staged/committed evidence; never retry.
            raise

    def close(self):
        if self.owner is not None:
            raise ValueError("SELECTION_CLOSE_WHILE_LEASED")
        self.poisoned = True
        failed = False
        for handle in list(self.file_handles):
            if not self.native.w.close_handle(handle):
                failed = True
            else:
                self.file_handles.remove(handle)
        if self.mutex:
            if not self.native.w.close_handle(self.mutex):
                failed = True
            else:
                self.mutex = None
        for handle in list(reversed(self.output.handles)):
            if not self.native.w.close_handle(handle):
                failed = True
            else:
                self.output.handles.remove(handle)
        if failed:
            raise OSError("SELECTION_CLOSE_UNCONFIRMED_HANDLES_RETAINED")
