"""Explicit disposable ports. Never accepted by the operational native factory."""

import hashlib
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import ClassVar

from scripts.release_selection import encoded, strict, validate_spec


def check_path(path):
    for p in (path, *path.parents):
        s = p.lstat()
        if (
            getattr(s, "st_file_attributes", 0) & 0x400
            or p.is_symlink()
            or p.is_junction()
        ):
            raise ValueError("FIXTURE_REPARSE_REFUSED")


class DisposableStore:
    domain = "DISPOSABLE"
    locks: ClassVar[dict] = {}

    def __init__(self, root):
        self.root = root
        root.mkdir(exist_ok=True)
        check_path(root)
        s = root.stat()
        self.identity = s.st_dev, s.st_ino
        self.lock = self.locks.setdefault(str(root), threading.Lock())
        self.fault = None

    @contextmanager
    def locked(self):
        if not self.lock.acquire(timeout=0.3):
            raise ValueError("FIXTURE_SELECTION_BUSY")
        try:
            check_path(self.root)
            s = self.root.stat()
            if (s.st_dev, s.st_ino) != self.identity:
                raise ValueError("FIXTURE_ROOT_SUBSTITUTION")
            yield
        finally:
            self.lock.release()

    def records(self):
        names = {p.name for p in self.root.iterdir()}
        count = len(names) // 2
        if names != {
            f"r{i:04d}.{s}" for i in range(1, count + 1) for s in ("pending", "json")
        }:
            raise ValueError("FIXTURE_INTERRUPTED_OR_FOREIGN_TAIL")
        rows = []
        for i in range(1, count + 1):
            pending, published = [
                self.root / f"r{i:04d}.{s}" for s in ("pending", "json")
            ]
            check_path(pending)
            check_path(published)
            a, b = pending.stat(), published.stat()
            if (
                (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino)
                or a.st_nlink != 2
                or b.st_nlink != 2
            ):
                raise ValueError("FIXTURE_PUBLICATION_SUBSTITUTION")
            raw = published.read_bytes()
            envelope = strict(raw)
            if (
                encoded(envelope) != raw
                or set(envelope) != {"record", "native_id"}
                or envelope["native_id"] != [b.st_dev, b.st_ino]
            ):
                raise ValueError("FIXTURE_RECORD_IDENTITY_OR_ENCODING")
            rows.append(envelope["record"])
        return rows

    def publish(self, row):
        if self.fault == "before_stage":
            raise OSError("SYNTHETIC_PRE_EFFECT_FAILURE")
        name = f"r{row['revision']:04d}"
        pending, public = self.root / (name + ".pending"), self.root / (name + ".json")
        with pending.open("xb") as stream:
            info = os.fstat(stream.fileno())
            raw = encoded({"record": row, "native_id": [info.st_dev, info.st_ino]})
            if self.fault == "partial_stage":
                stream.write(raw[:10])
                stream.flush()
                os.fsync(stream.fileno())
                raise OSError("SYNTHETIC_INTERRUPTED_WRITE")
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if self.fault == "after_stage":
            raise OSError("SYNTHETIC_BEFORE_ATOMIC_LINK")
        os.link(pending, public)
        if self.fault == "after_publish":
            raise OSError("SYNTHETIC_COMMITTED_BEFORE_CALLER_ACK")


class FixtureVerifier:
    domain = "DISPOSABLE"

    def __init__(self, base):
        self.base = base

    @contextmanager
    def open(self, reference):
        spec = validate_spec(reference, self.domain)
        root = Path(spec["root"])
        if root.parent != self.base or root.name != spec["release"]:
            raise ValueError("FIXTURE_RELEASE_PATH_BINDING")
        path = Path(spec["receipt"])
        check_path(path)
        check_path(root)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != spec["receipt_sha256"]:
            raise ValueError("FIXTURE_RECEIPT_HASH")
        receipt = strict(raw)
        if (
            receipt["schema"] != "DISPOSABLE_INSTALLED_RELEASE_V1"
            or receipt["release"] != spec["release"]
            or receipt["root"] != str(root)
            or hashlib.sha256(encoded(receipt["files"])).hexdigest()
            != spec["artifact_digest"]
        ):
            raise ValueError("FIXTURE_RECEIPT_BINDING")

        def verify():
            names = {
                p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
            }
            if names != {r["path"] for r in receipt["files"]}:
                raise ValueError("FIXTURE_RELEASE_NAMESPACE")
            for r in receipt["files"]:
                p = root / r["path"]
                check_path(p)
                s = p.stat()
                if (
                    s.st_nlink != 1
                    or [s.st_dev, s.st_ino] != r["id"]
                    or s.st_size != r["bytes"]
                    or hashlib.sha256(p.read_bytes()).hexdigest() != r["sha256"]
                ):
                    raise ValueError("FIXTURE_RELEASE_FILE_IDENTITY")

        verify()
        yield receipt
        verify()


def make_release(base, name):
    root = base / name
    root.mkdir()
    for relative in (
        "python/python.exe",
        "python/python312.dll",
        "python/Lib/os.py",
        "backend/app/static/dashboard_hub.html",
        "scripts/observation_runtime/desktop_observation.py",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(("DISPOSABLE_NOT_EXECUTABLE_" + relative).encode())
    files = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        s = path.stat()
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": s.st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "id": [s.st_dev, s.st_ino],
            }
        )
    receipt = {
        "schema": "DISPOSABLE_INSTALLED_RELEASE_V1",
        "release": name,
        "root": str(root),
        "files": files,
    }
    path = base / (name + ".receipt.json")
    path.write_bytes(encoded(receipt))
    return {
        "schema": "QD_INSTALLED_RELEASE_REFERENCE_V1",
        "domain": "DISPOSABLE",
        "release": name,
        "root": str(root),
        "receipt": str(path),
        "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "artifact_digest": hashlib.sha256(encoded(files)).hexdigest(),
    }
