"""Fail-closed fixture capabilities and independently enrolled path/content pins.

No defaults, production paths, environment loading, subprocesses or network I/O.
Portable checks do not provide native directory-wide exclusion against an owner
or administrator racing replacements. Production integration remains prohibited.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class Refused(ValueError):
    """Preserve evidence; never initialize/reset an ambiguous runtime."""


class Action(StrEnum):
    OBSERVE = "OBSERVE"
    RESEARCH = "RESEARCH"
    HISTORY = "HISTORY"
    LIVE_ORDER = "LIVE_ORDER"
    PAPER_ORDER = "PAPER_ORDER"
    PREDICTION_OPEN = "PREDICTION_OPEN"
    PENDING_LIMIT_EXECUTE = "PENDING_LIMIT_EXECUTE"
    DISCORD_SEND = "DISCORD_SEND"
    BACKGROUND_TRADE = "BACKGROUND_TRADE"
    PAPER_MANAGE = "PAPER_MANAGE"
    PAPER_BOOTSTRAP = "PAPER_BOOTSTRAP"
    RECOVERY_CLEAR = "RECOVERY_CLEAR"
    PRODUCTION_START = "PRODUCTION_START"
    SCHEMA_MIGRATION = "SCHEMA_MIGRATION"


ALLOWED = frozenset({Action.OBSERVE, Action.RESEARCH, Action.HISTORY})


def encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def file_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_uuid(value: Any) -> None:
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise Refused("Canonical UUID required")


def identity(path: Path) -> tuple[int, int]:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise Refused("Symlink/reparse point refused")
    if not stat.S_ISDIR(info.st_mode) and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
        raise Refused("Non-regular or hard-linked file refused")
    if not info.st_ino:
        raise Refused("File identity unavailable")
    return info.st_dev, info.st_ino


def canonical(value: str) -> Path:
    if not isinstance(value, str):
        raise Refused("Explicit path required")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise Refused("Absolute non-traversing path required")
    for part in reversed((path, *path.parents)):
        identity(part)
    resolved = path.resolve(strict=True)
    if os.path.normcase(str(resolved)) != os.path.normcase(str(path)):
        raise Refused("Path substitution refused")
    return resolved


def beneath(parent: Path, child: Path) -> bool:
    return parent == child or parent in child.parents


def read_file(path: Path, expected: tuple[int, int] | None = None) -> bytes:
    """Check descriptor identity before reading bytes; bounded regular files only."""
    before = identity(path)
    if expected is not None and before != expected:
        raise Refused("Pinned file replaced")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(descriptor)
        if (info.st_dev, info.st_ino) != before or info.st_nlink != 1 or info.st_size > 2_000_000:
            raise Refused("Opened file identity/link/size mismatch")
        raw = bytearray()
        while chunk := os.read(descriptor, 65536):
            raw.extend(chunk)
            if len(raw) > 2_000_000:
                raise Refused("File read bound exceeded")
        if len(raw) != info.st_size or identity(path) != before or os.fstat(descriptor).st_nlink != 1:
            raise Refused("File changed during read")
        return bytes(raw)
    finally:
        os.close(descriptor)


def release_tree(root: Path) -> tuple[dict[str, str], tuple[tuple[str, tuple[int, int]], ...]]:
    hashes: dict[str, str] = {}
    pins: list[tuple[str, tuple[int, int]]] = []
    pending = [(root, 0)]
    total_bytes = 0
    while pending:
        path, depth = pending.pop()
        if depth > 16 or len(pins) >= 1000:
            raise Refused("Release traversal bound exceeded")
        pin = identity(path)
        pins.append((str(path), pin))
        if path.is_dir():
            pending.extend((child, depth + 1) for child in sorted(path.iterdir()))
        else:
            raw = read_file(path, pin)
            total_bytes += len(raw)
            if total_bytes > 8_000_000:
                raise Refused("Release byte bound exceeded")
            hashes[path.relative_to(root).as_posix()] = file_digest(raw)
    if not hashes:
        raise Refused("Empty release refused")
    return hashes, tuple(pins)


def require_capability(action: Action | str, allowed: tuple[str, ...]) -> Action:
    try:
        parsed = Action(action)
    except (TypeError, ValueError) as error:
        raise Refused("Unknown capability") from error
    if parsed not in ALLOWED or parsed.value not in allowed:
        raise Refused("Observation-only capability denied: " + parsed.value)
    return parsed


PATH_KEYS = frozenset({"runtime_root", "release_root", "state_root", "journal_root", "cache_root",
                       "build_root", "environment_root", "configuration_path"})
MANIFEST_KEYS = PATH_KEYS | {"schema", "scope", "profile", "release_id", "configuration_id",
                            "dependency_ids", "database_id", "volume_ids", "runtime_port",
                            "session_id", "owner", "allowed_capabilities", "data_sources", "development"}


def shape(manifest: dict, fixture_root: Path) -> dict[str, Path]:
    if type(manifest) is not dict or set(manifest) != MANIFEST_KEYS:
        raise Refused("Manifest fields missing or unexpected")
    if (type(manifest["schema"]) is not int or manifest["schema"] != 1
            or manifest["scope"] != "SYNTHETIC_ONLY" or manifest["profile"] != "OBSERVATION_ONLY"):
        raise Refused("Synthetic observation profile required")
    canonical_uuid(manifest["session_id"])
    caps = manifest["allowed_capabilities"]
    if type(caps) is not list or len(caps) != len(ALLOWED) or set(caps) != {x.value for x in ALLOWED}:
        raise Refused("Exact observation capabilities required")
    owner = manifest["owner"]
    if (type(owner) is not dict or set(owner) != {"pid", "created", "executable_id", "command_id", "run_id"}
            or type(owner["pid"]) is not int or owner["pid"] <= 0
            or type(owner["created"]) not in (int, float) or not 0 < owner["created"] < 1e12):
        raise Refused("Ambiguous runtime owner")
    canonical_uuid(owner["run_id"])
    for value in [owner["executable_id"], owner["command_id"], manifest["release_id"], manifest["configuration_id"]]:
        if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
            raise Refused("Immutable digest identity required")
    dependencies = manifest["dependency_ids"]
    if (type(dependencies) is not dict or set(dependencies) != {"postgres", "redis", "environment"}
            or any(not isinstance(v, str) or not re.fullmatch(r"[a-f0-9]{64}", v) for v in dependencies.values())
            or len(set(dependencies.values())) != 3):
        raise Refused("Exact distinct dependency identities required")
    sources = manifest["data_sources"]
    if (type(sources) is not list or not 0 < len(sources) <= 8 or len(set(sources)) != len(sources)
            or any(not isinstance(s, str) or not re.fullmatch(r"[a-z0-9_-]{1,32}", s) for s in sources)):
        raise Refused("Bounded source identities required")
    development = manifest["development"]
    if type(development) is not dict or set(development) != {"roots", "database_ids", "volume_ids", "ports"}:
        raise Refused("Development resource inventory required")
    if type(development["roots"]) is not list or not 1 <= len(development["roots"]) <= 8:
        raise Refused("Bounded development roots required")
    for values in ([manifest["database_id"]], manifest["volume_ids"], development["database_ids"], development["volume_ids"]):
        if type(values) is not list or len(values) > 8 or any(
            not isinstance(v, str) or not re.fullmatch(r"[a-z0-9_-]{1,64}", v) for v in values
        ) or len(set(values)) != len(values):
            raise Refused("Malformed resource identity")
    if len(manifest["volume_ids"]) != 2 or type(development["ports"]) is not list or len(development["ports"]) > 8:
        raise Refused("Complete bounded volume/port inventory required")
    ports = [manifest["runtime_port"], *development["ports"]]
    if any(type(p) is not int or not 0 < p < 65536 for p in ports):
        raise Refused("Malformed port inventory")
    if (manifest["database_id"] in development["database_ids"]
            or set(manifest["volume_ids"]) & set(development["volume_ids"])
            or manifest["runtime_port"] in development["ports"]):
        raise Refused("Shared test/runtime database, volume or port")
    paths = {key: canonical(manifest[key]) for key in PATH_KEYS}
    runtime = paths["runtime_root"]
    if runtime == fixture_root or not beneath(fixture_root, runtime):
        raise Refused("Runtime must be inside the explicitly enrolled fixture")
    for key, path in paths.items():
        if not beneath(runtime, path):
            raise Refused("Runtime path escapes enrolled root: " + key)
    if not beneath(paths["state_root"], paths["journal_root"]):
        raise Refused("Journal root outside explicit state")
    separate = [paths[k] for k in ("release_root", "state_root", "cache_root", "environment_root")]
    for i, path in enumerate(separate):
        if any(beneath(path, other) or beneath(other, path) for other in separate[i + 1:]):
            raise Refused("Shared mutable runtime resources")
    if not beneath(paths["release_root"], paths["build_root"]):
        raise Refused("Assets must belong to fixed release")
    for raw in development["roots"]:
        path = canonical(raw)
        if not beneath(fixture_root, path) or beneath(runtime, path) or beneath(path, runtime):
            raise Refused("Development/runtime path overlap")
    if not paths["configuration_path"].is_file() or any(
        not p.is_dir() for key, p in paths.items() if key != "configuration_path"
    ):
        raise Refused("Unexpected path kind")
    return paths


@dataclass(frozen=True)
class FixturePin:
    scope_root: str
    scope_id: str
    manifest_id: str
    path_ids: tuple[tuple[str, tuple[int, int]], ...]
    release_hashes: tuple[tuple[str, str], ...]
    environment_hashes: tuple[tuple[str, str], ...]
    marker_hash: str


def enroll_fixture(manifest: dict, scope_root: Path, scope_id: str) -> FixturePin:
    """Explicit harness enrollment, NEVER independent production trust enrollment."""
    if len(encoded(manifest)) > 65536:
        raise Refused("Manifest bound exceeded")
    canonical_uuid(scope_id)
    root = canonical(str(scope_root))
    marker = root / "synthetic-fixture.json"
    raw = read_file(marker)
    if json.loads(raw) != {"scope": "SYNTHETIC_ONLY", "scope_id": scope_id}:
        raise Refused("Explicit synthetic fixture marker missing")
    paths = shape(manifest, root)
    hashes, file_pins = release_tree(paths["release_root"])
    environment_hashes, environment_pins = release_tree(paths["environment_root"])
    if digest(hashes) != manifest["release_id"] or file_digest(read_file(paths["configuration_path"])) != manifest["configuration_id"]:
        raise Refused("Release/configuration identity inconsistent")
    if digest(environment_hashes) != manifest["dependency_ids"]["environment"]:
        raise Refused("Environment identity inconsistent")
    directory_pins = [(str(root), identity(root)), (str(marker), identity(marker))]
    directory_pins += [(str(p), identity(p)) for p in paths.values()]
    directory_pins += [(str(canonical(p)), identity(canonical(p))) for p in manifest["development"]["roots"]]
    return FixturePin(str(root), scope_id, digest(manifest), tuple(directory_pins) + file_pins + environment_pins,
                      tuple(sorted(hashes.items())), tuple(sorted(environment_hashes.items())), file_digest(raw))


class RuntimeContract:
    def __init__(self, manifest: dict, pin: FixturePin):
        if type(pin) is not FixturePin:
            raise Refused("Explicit fixture enrollment pin required")
        self._manifest = encoded(manifest)
        if len(self._manifest) > 65536:
            raise Refused("Manifest bound exceeded")
        self.pin = pin
        self.verify()

    @property
    def manifest(self) -> dict:
        return json.loads(self._manifest)

    def verify(self) -> dict[str, Path]:
        manifest = self.manifest
        if digest(manifest) != self.pin.manifest_id:
            raise Refused("Manifest differs from independently supplied fixture pin")
        # Check shallow roots before children: replacing a root must not be
        # misclassified merely because the replacement lacks a pinned child.
        for raw, expected in sorted(self.pin.path_ids, key=lambda part: len(Path(part[0]).parts)):
            if identity(Path(raw)) != expected:
                raise Refused("Pinned root, file or directory substituted")
        root = canonical(self.pin.scope_root)
        if file_digest(read_file(root / "synthetic-fixture.json")) != self.pin.marker_hash:
            raise Refused("Fixture marker changed")
        paths = shape(manifest, root)
        hashes, _ = release_tree(paths["release_root"])
        if tuple(sorted(hashes.items())) != self.pin.release_hashes:
            raise Refused("Fixed release changed")
        environment_hashes, _ = release_tree(paths["environment_root"])
        if tuple(sorted(environment_hashes.items())) != self.pin.environment_hashes:
            raise Refused("Fixed environment changed")
        if file_digest(read_file(paths["configuration_path"])) != manifest["configuration_id"]:
            raise Refused("Runtime configuration changed")
        return paths

    def read_release(self, relative: str) -> bytes:
        paths = self.verify()
        if (not isinstance(relative, str) or Path(relative).is_absolute()
                or ".." in Path(relative).parts or relative not in dict(self.pin.release_hashes)):
            raise Refused("Unknown fixed-release resource")
        target = paths["release_root"] / relative
        return read_file(target, dict(self.pin.path_ids)[str(target)])


class DevelopmentWorkspace:
    """Guarded writer, not a sandbox for arbitrary same-account Python code."""
    def __init__(self, contract: RuntimeContract):
        self.contract = contract

    def write(self, destination: Path, raw: bytes) -> None:
        self.contract.verify()
        if type(raw) is not bytes or len(raw) > 65536:
            raise Refused("Bounded development bytes required")
        parent = canonical(str(destination.parent))
        roots = [canonical(p) for p in self.contract.manifest["development"]["roots"]]
        if not any(beneath(root, parent) for root in roots):
            raise Refused("Development writer cannot access runtime state/assets")
        if destination.exists() or destination.is_symlink():
            identity(destination)
        with destination.open("wb") as handle:
            if handle.write(raw) != len(raw):
                raise OSError("Short development write")
