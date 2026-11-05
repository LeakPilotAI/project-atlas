"""Guarded boundary used by the real AIP-06 native fixture entry points.

No default ports, launcher, approval, provider or installed runtime. Native
callbacks are reached only after the shared source guards admit the effect.
Offline tests inject native interfaces; they never receive native acceptance.
"""

import contextlib
import contextvars
import hashlib
import json
import ntpath
import os
import re
import sys
import threading
from subprocess import list2cmdline
from urllib.parse import parse_qs, unquote, urlsplit

from app.services.paper_financial_replay import body, digest

from scripts.observation_runtime.aip06_harness import (
    LIMITS,
    ROOTS,
    SCOPE_HASH,
    FixturePaths,
    SharedResources,
    StopVerification,
    WorkerOwnership,
    bounded_line,
    need,
    path_for,
)

_active = None
_gate = threading.RLock()
_internal = contextvars.ContextVar("aip06_internal_effect", default=None)
_audit_installed = False


class OwnedNativeHandle(int):
    """Retain the allocation token when Windows reuses an integer handle."""

    def __new__(cls, value, token):
        raw = value.value if hasattr(value, "value") else value
        need(
            type(raw) is int and raw > 0 and raw not in (2**32 - 1, 2**64 - 1),
            "NATIVE_CREATION_HANDLE_REQUIRED",
        )
        result = int.__new__(cls, raw)
        result.token = token
        return result


class CreateNewJournal:
    """Concrete append/CAS/readback algorithm over an explicit durable IO port.

    The caller supplies a retained, already-reserved E/journal directory. The
    port cannot select paths: every immutable record name is constructed here.
    flush_close must verify a durable closed handle, not merely return write().
    """

    def __init__(self, io, directory_identity):
        self.io, self.identity = io, directory_identity
        self.lock = threading.RLock()
        self.last = None

    def read(self):
        with self.lock:
            self.io.verify_directory(path_for("E", "journal"), self.identity)
            names = self.io.names()
            need(
                type(names) is list
                and len(names) <= LIMITS["entries"]
                and names == [f"record-{i:08d}.json" for i in range(1, len(names) + 1)],
                "COMPLETE_CONTIGUOUS_JOURNAL_NAMESPACE_REQUIRED",
            )
            rows = []
            size = 0
            for name in names:
                raw = self.io.read_exact(
                    path_for("E", "journal", name), maximum_bytes=1024**2
                )
                need(
                    type(raw) is bytes and len(raw) <= 1024**2,
                    "BOUNDED_JOURNAL_RECORD_REQUIRED",
                )
                size += len(raw)
                need(size <= LIMITS["bytes"], "JOURNAL_STORAGE_CAPACITY")
                row = json.loads(raw)
                need(
                    body(row).encode() == raw
                    and row["parent"] == (digest(rows[-1]) if rows else SCOPE_HASH)
                    and row["sequence"] == len(rows) + 1
                    and row["scope"] == SCOPE_HASH,
                    "JOURNAL_NATIVE_READBACK_CHAIN",
                )
                rows.append(row)
            return rows

    def append(self, head, event):
        with self.lock:
            rows = self.read()
            need(
                head == (digest(rows[-1]) if rows else SCOPE_HASH)
                and event["parent"] == head
                and event["sequence"] == len(rows) + 1
                and event["scope"] == SCOPE_HASH,
                "JOURNAL_COMPARE_AND_APPEND",
            )
            raw = body(event).encode()
            need(
                len(rows) < LIMITS["entries"] and len(raw) <= 1024**2,
                "JOURNAL_RECORD_CAPACITY",
            )
            path = path_for("E", "journal", f"record-{len(rows) + 1:08d}.json")
            self.last = None  # Interrupted append cannot reuse an earlier ACK.
            handle = self.io.create_new(path, self.identity)
            self.io.write_exact(handle, raw)
            proof = self.io.flush_close(handle)
            need(
                type(proof) is dict
                and set(proof) == {"closed", "flushed", "path", "sha256"}
                and proof["closed"] is True
                and proof["flushed"] is True
                and proof["path"] == path
                and proof["sha256"] == hashlib.sha256(raw).hexdigest(),
                "DURABLE_JOURNAL_CLOSE_REQUIRED",
            )
            need(self.read() == rows + [event], "JOURNAL_POST_APPEND_READBACK")
            self.last = {
                "head": digest(event),
                "owner": event["state"]["controller"],
                "closed": True,
            }

    def receipt(self):
        need(self.last is not None, "NO_COMPLETED_JOURNAL_ACK")
        need(
            self.read()[-1] and digest(self.read()[-1]) == self.last["head"],
            "JOURNAL_RECEIPT_CONFLICT",
        )
        return dict(self.last)


def current():
    return _active


def require_fixture(label):
    need(type(label) is str and label, "NAMED_FIXTURE_REQUIRED")
    guard = current()
    need(
        type(guard) is FixtureGuard and not guard.failed,
        "AIP06_GUARDED_SESSION_REQUIRED:" + label,
    )
    guard.check()
    guard.entries.append(label)
    return guard


def audit(event, args):
    """Raw Python writes/launches cannot fall through while a fixture is active."""
    guard = current()
    if guard is None:
        return
    mode = _internal.get()
    if event == "open":
        flags = args[2]
        writing = type(flags) is int and flags & (
            os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        )
        if not writing:
            return
        if mode == "journal":
            guard.journal_path(args[0])
            return
        need(mode == "effect", "UNATTRIBUTED_PYTHON_WRITE")
    elif event in {
        "os.mkdir",
        "os.remove",
        "os.rmdir",
        "os.rename",
        "os.link",
        "os.symlink",
        "os.chmod",
        "os.truncate",
    }:
        need(mode == "effect", "UNATTRIBUTED_FILESYSTEM_MUTATION:" + event)
    elif event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.spawn", "_winapi.CreateProcess"}:
        need(mode == "process", "UNOWNED_PROCESS_LAUNCH")
    elif event in {'socket.bind','socket.connect'}:
        raise ValueError('AIP06_NATIVE_FIXTURE_NO_NETWORK_TRANSPORT')
    elif event == "sqlite3.connect":
        need(args[0] == ":memory:" or mode == "sqlite", "UNRESERVED_SQLITE_DATABASE")


class FixtureGuard:
    """Connect shared accounting to the actual native/Python/process interfaces.

    io supplies handle-backed paths/identity observations and owned create-new
    ordinary IO. processes supplies suspended creation, exact retained binding,
    bounded IPC, independent complete Job/usage/exit/closed-handle observations.
    Native ports must be reviewed/pinned for a separate authorized execution;
    constructor arguments or scope hashes are never operational permission.
    """

    def __init__(self, *, resources, paths, ownership, owner, io, processes, clock_ns):
        from scripts.observation_runtime.aip06_ipc import RemoteResources

        need(
            type(resources) in (SharedResources, RemoteResources)
            and type(paths) is FixturePaths
            and type(ownership) is WorkerOwnership
            and ownership.resources is resources,
            "EXACT_SHARED_GUARDS_REQUIRED",
        )
        need(
            owner in resources.state["owners"]
            and io is not None
            and processes is not None
            and callable(clock_ns),
            "OWNED_NATIVE_INTERFACES_REQUIRED",
        )
        self.resources, self.paths, self.ownership = resources, paths, ownership
        self.owner, self.io, self.processes, self.clock = owner, io, processes, clock_ns
        self.failed, self.entries, self.calls = False, [], []
        self.handles, self.closed_keys = {}, set()
        self.databases = {}
        self.counter, self.stop = len(resources.state["resources"]), None
        self.owned_files = set()
        self.file_identities = {}
        self.case_results = []
        self.launch_nonces = set()
        self.query_active = False
        if hasattr(io, "bind_guard"):
            io.bind_guard(self)

    @contextlib.contextmanager
    def installed(self):
        global _active, _audit_installed
        with _gate:
            need(_active is None, "ONE_FIXTURE_SESSION_ONLY")
            if not _audit_installed:
                sys.addaudithook(audit)
                _audit_installed = True
            _active = self
        try:
            yield self
        except BaseException:
            self.failed = True
            raise
        finally:
            with _gate:
                _active = None

    @contextlib.contextmanager
    def internal(self, mode):
        token = _internal.set(mode)
        try:
            yield
        finally:
            _internal.reset(token)

    def ledger(self, method, *args, **kwargs):
        with self.internal("journal"):
            return getattr(self.resources, method)(*args, **kwargs)

    def journal_path(self, path):
        need(isinstance(path, (str, os.PathLike)), "JOURNAL_PATH_REQUIRED")
        value = os.fspath(path)
        need(
            ntpath.dirname(value) == path_for("E", "journal")
            and re.fullmatch(r"record-\d{8}\.json", ntpath.basename(value)) is not None,
            "UNRESERVED_JOURNAL_PATH",
        )

    def check(self):
        need(not self.failed, "FIXTURE_FAILURE_LATCHED")
        need(self.stop is None or self.stop.failure is None,'STOP_FAILURE_LATCHED')
        need(
            not any(
                os.environ.get(k)
                for k in (
                    "ATLAS_PERSONAL_NATIVE_TEST_APPROVAL",
                    "ATLAS_SYNTHETIC_INSTALL_SCOPE",
                    "ATLAS_SYNTHETIC_INSTALL_SCOPE_SHA256",
                )
            ),
            "NO_LEGACY_GRANT_OR_INSTALLED_SCOPE_REUSE",
        )
        self.ledger("read")
        if hasattr(self.processes, 'verify_budget'):
            with self.internal('journal'):
                self.processes.verify_budget()

    def locate(self, path):
        value = os.fspath(path)
        need(
            type(value) is str
            and ntpath.normpath(value) == value
            and value.startswith("D:\\"),
            "EXACT_NATIVE_DISPOSABLE_PATH_REQUIRED",
        )
        for alias, root in ROOTS.items():
            if value == root:
                return alias, ()
            if value.startswith(root + "\\"):
                parts = tuple(value[len(root) + 1 :].split("\\"))
                need(path_for(alias, *parts) == value, "CANONICAL_DESCENDANT_REQUIRED")
                return alias, parts
        raise ValueError("OUTSIDE_AIP06_ROOTS")

    def key(self, kind):
        self.counter += 1
        return "fixture:" + self.owner + ':' + kind + ":" + str(self.counter)

    def cleanup(self):
        return self.resources.state["mode"] == "STOP" or any(
            r["state"] == "PENDING" for r in self.resources.state["stops"].values()
        )

    def reserve(self, key, kind, *, size=0, entries=0):
        self.check()
        result = self.ledger(
            "reserve",
            self.owner,
            key,
            kind,
            entries=entries,
            size=size,
            cleanup=self.cleanup(),
        )
        if hasattr(self.io, "begin"):
            self.io.begin(self.owner, key, kind, None)
        return result

    def effect_path(self, key, path):
        if hasattr(self.io, "bind_path"):
            self.io.bind_path(key, os.fspath(path))

    def validate_path(self, path, *, create=False):
        alias, parts = self.locate(path)
        if not parts and alias not in self.paths.bound:
            need(create, "UNBOUND_FIXTURE_ROOT")
            return self.paths.prepare(alias)
        existing = self.paths.port.inspect(os.fspath(path))
        if create:
            need(existing is None, "NO_EXISTING_ARTIFACT_ADOPTION")
        else:
            need(existing is not None, "MISSING_FIXTURE_ARTIFACT")
            prior = self.file_identities.get(os.fspath(path))
            need(prior is None or existing["id"] == prior, "OWNED_ARTIFACT_REPLACED")
        self.paths.verify(
            alias, *parts, existing_id=None if existing is None else existing["id"]
        )
        return None

    def mkdir(self, path):
        intent = self.validate_path(path, create=True)
        key = self.key("directory")
        self.reserve(key, "directory", entries=1)
        self.effect_path(key, path)
        with self.internal("effect"):
            self.io.mkdir(os.fspath(path))
        if intent is not None:
            self.paths.bind_created(intent)
        self.validate_path(path)
        self.owned_files.add(os.fspath(path))
        self.file_identities[os.fspath(path)] = self.paths.port.inspect(
            os.fspath(path)
        )["id"]
        self.release(key)

    def write(self, path, data):
        need(
            type(data) is bytes and len(data) <= 1024**2,
            "BOUNDED_IMMUTABLE_PAYLOAD_REQUIRED",
        )
        self.validate_path(path, create=True)
        key = self.key("file")
        self.reserve(key, "file", entries=1, size=len(data))
        self.effect_path(key, path)
        with self.internal("effect"):
            self.io.write_new(os.fspath(path), data)
        row = self.io.readback(os.fspath(path))
        need(
            row == {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
            "ORDINARY_WRITE_READBACK_REQUIRED",
        )
        self.validate_path(path)
        self.owned_files.add(os.fspath(path))
        self.file_identities[os.fspath(path)] = self.paths.port.inspect(
            os.fspath(path)
        )["id"]
        self.release(key)

    def rewrite(self, path, data):
        """Explicit fixture fault/CAS replacement; never overwrite an adopted file."""
        need(os.fspath(path) in self.owned_files, "OWNED_REWRITE_ONLY")
        temporary = os.fspath(path) + ".guard-" + self.key("rewrite").replace(":", "-")
        self.write(temporary, data)
        self.replace(temporary, path)

    def replace(self, source, target):
        left, _ = self.locate(source)
        right, _ = self.locate(target)
        need(left == right, "CROSS_ACCOUNT_RENAME_REFUSED")
        need(
            os.fspath(source) in self.owned_files
            and os.fspath(target) in self.owned_files,
            "OWNED_REPLACEMENT_ONLY",
        )
        self.validate_path(source)
        self.validate_path(target)
        row = self.io.readback(os.fspath(source))
        key = self.key("replacement")
        self.reserve(key, "file", entries=1, size=row["bytes"])
        self.effect_path(key, target)
        with self.internal("effect"):
            self.io.replace_owned(os.fspath(source), os.fspath(target))
        need(
            self.io.readback(os.fspath(target)) == row, "REPLACEMENT_READBACK_REQUIRED"
        )
        self.owned_files.discard(os.fspath(source))
        self.owned_files.add(os.fspath(target))
        self.file_identities[os.fspath(target)] = self.file_identities.pop(
            os.fspath(source)
        )
        self.release(key)

    def release(self, key):
        need(
            self.io.closed(self.owner, key) is True,
            "NATIVE_RESOURCE_RELEASE_UNVERIFIED",
        )
        self.ledger("close", self.owner, key, observer=self.io)
        self.closed_keys.add(key)

    def native(self, event, invoke, values, *, module):
        """Called by real WindowsOutput functions BEFORE their native callbacks."""
        need(_internal.get() != "journal", "NATIVE_JOURNAL_MUST_USE_ITS_PINNED_PORT")
        if event != "close":
            self.check()
        if event == "token":
            key = self.key("token")
            self.reserve(key, "handle")
            result = OwnedNativeHandle(invoke(*values), key)
            self.handles[key] = {
                "path": "current-process-token",
                "key": key,
                "kind": "token",
                "module": module,
                "handle": result,
            }
            self.io.verify_token(result, self.resources.state["owners"][self.owner])
            return result
        if event == "image_open":
            path = values[0]
            pin = self.processes.pinned_images.get(ntpath.normcase(path))
            need(
                type(pin) is dict and set(pin) == {"file_id", "sha256"},
                "REVIEWED_IMAGE_PIN_REQUIRED",
            )
            key = self.key("image-lease")
            self.reserve(key, "image")
            result = OwnedNativeHandle(invoke(*values), key)
            self.handles[key] = {
                "path": path,
                "key": key,
                "kind": "image",
                "module": module,
                "handle": result,
            }
            self.io.verify_image(result, path, pin)
            return result
        if event == "absolute_open":
            path, access, _, _, disposition, *_ = values
            need(
                disposition == 3 and not access & (module.WRITE | module.DELETE),
                "ANCESTRY_OPEN_READ_ONLY",
            )
            need(path in self.io.ancestors(), "UNDECLARED_ABSOLUTE_NATIVE_OPEN")
            key = self.key("ancestor")
            self.reserve(key, "handle")
            result = OwnedNativeHandle(invoke(*values), key)
            self.handles[key] = {
                "path": path,
                "key": key,
                "kind": "handle",
                "module": module,
                "handle": result,
            }
            self.io.verify_handle(result, path, module)
            return result
        if event == "relative_open":
            parent, leaf, _, directory = values[:4]
            create = values[4] if len(values) > 4 else False
            access = (
                values[5] if len(values) > 5 else module.READ_CONTROL | module.ATTR | 1
            )
            need(
                type(parent) is OwnedNativeHandle and parent.token in self.handles,
                "UNRETAINED_NATIVE_PARENT",
            )
            path = ntpath.join(self.handles[parent.token]["path"], leaf)
            if path in self.io.ancestors():
                need(
                    not create and directory and not access & module.WRITE,
                    "READ_ONLY_ANCESTOR_REQUIRED",
                )
                intent = None
            else:
                intent = self.validate_path(path, create=create)
            need(
                not access & module.WRITE or create, "NO_EXISTING_NATIVE_WRITE_ADOPTION"
            )
            key = self.key("native")
            kind = ("directory" if directory else "file") if create else "handle"
            self.reserve(key, kind, entries=int(create))
            result = OwnedNativeHandle(invoke(*values), key)
            need(
                not any(int(r["handle"]) == int(result) for r in self.handles.values()),
                "NATIVE_HANDLE_REUSE_WHILE_LIVE",
            )
            self.handles[key] = {
                "path": path,
                "key": key,
                "kind": kind,
                "module": module,
                "handle": result,
            }
            self.io.verify_handle(result, path, module)
            if intent is not None:
                self.paths.bind_created(intent)
            if create:
                self.owned_files.add(path)
                self.file_identities[path] = self.paths.port.inspect(path)["id"]
            return result
        if event == "write":
            handle, data, count, *_ = values
            need(
                type(handle) is OwnedNativeHandle
                and handle.token in self.handles
                and self.handles[handle.token]["kind"] == "file"
                and type(data) is bytes
                and type(count) is int
                and count == len(data),
                "BOUND_NATIVE_FILE_WRITE_REQUIRED",
            )
            item = self.handles[handle.token]
            self.io.verify_handle(handle, item["path"], module)
            self.ledger(
                "charge_write",
                self.owner,
                item["key"],
                size=count,
                cleanup=self.cleanup(),
            )
            return invoke(*values)
        if event == "close":
            (handle,) = values
            need(
                type(handle) is OwnedNativeHandle
                and handle.token in self.handles
                and self.handles[handle.token]["handle"] is handle,
                "NO_FOREIGN_OR_STALE_HANDLE_CLOSE",
            )
            item = self.handles[handle.token]
            result = invoke(*values)
            need(bool(result), "NATIVE_CLOSE_FAILED")
            self.io.note_closed(self.owner, item["key"], handle)
            del self.handles[
                handle.token
            ]  # Never close a reused integer on ACK failure.
            self.release(item["key"])
            return result
        if event == "mutex":
            name = values[2]
            need(
                type(name) is str and name.startswith("Global\\Atlas-Isolated-Fence-"),
                "DECLARED_FIXTURE_MUTEX_REQUIRED",
            )
            key = self.key("mutex")
            self.reserve(key, "handle")
            result = OwnedNativeHandle(invoke(*values), key)
            self.handles[key] = {
                "path": name,
                "key": key,
                "kind": "mutex",
                "module": module,
                "handle": result,
            }
            self.io.verify_mutex(result, name, module)
            return result
        raise ValueError("UNSUPPORTED_NATIVE_MUTATION:" + event)

    def spawn(self, argv, **options):
        try:
            return self._spawn(argv, **options)
        except BaseException:
            self.failed=True
            if hasattr(self.processes,'refuse_current_launch'):
                self.processes.refuse_current_launch()
            raise

    def _spawn(self, argv, **options):
        """The process port uses suspended creation; never ordinary Popen fallback."""
        self.check()
        need(
            type(argv) in (list, tuple) and argv and all(type(x) is str for x in argv),
            "EXPLICIT_CHILD_COMMAND_REQUIRED",
        )
        need(
            type(self.processes.executable) is str
            and self.processes.executable.startswith("D:\\"),
            "D_RESIDENT_FIXTURE_INTERPRETER_REQUIRED",
        )
        plan = self.processes.plan(tuple(argv), options)
        required = {
            "name",
            "request",
            "parent_owner",
            "api",
            "parent_handle",
            "job_limits",
            "resource_kinds",
        }
        need(
            type(plan) is dict and set(plan) == required,
            "EXACT_PRELAUNCH_PLAN_REQUIRED",
        )
        need(plan["request"].nonce not in self.launch_nonces, "LAUNCH_NONCE_REPLAY")
        if plan["name"] == "query" and "query" in self.ownership.finished:
            old = self.ownership.prepared["query"]
            need(
                all(
                    self.resources.state["resources"][k]["closed"] for k in old["slots"]
                ),
                "PRIOR_QUERY_NOT_RELEASED",
            )
            del self.ownership.bindings["query"]
            del self.ownership.prepared["query"]
            self.ownership.finished.remove("query")
        need(
            body(plan["job_limits"])
            == body(
                {
                    "processes": LIMITS["processes"],
                    "private_bytes": LIMITS["private_bytes"],
                    "child_private_bytes": LIMITS["child_private_bytes"],
                    "cpu_ns": LIMITS["cpu_ns"],
                    "kill_on_close": True,
                }
            ),
            "FINITE_NATIVE_JOB_LIMITS_REQUIRED",
        )
        need(
            plan["request"].launch_command == (
                self.processes.command_line(tuple(argv), options)
                if hasattr(self.processes, "command_line")
                else list2cmdline(list(argv))
            )
            and type(plan["resource_kinds"]) is tuple
            and 1 <= len(plan["resource_kinds"]) <= 64
            and {"job", "thread", "image", "pipe"} <= set(plan["resource_kinds"])
            and set(plan["resource_kinds"])
            <= {"job", "thread", "image", "pipe", "handle"},
            "EXACT_COMMAND_AND_NATIVE_RESOURCES_REQUIRED",
        )
        with self.internal("journal"):
            permit = self.ownership.prepare(
                plan["name"], plan["request"], parent_owner=plan["parent_owner"]
            )
        self.launch_nonces.add(plan["request"].nonce)
        keys = []
        for kind in plan["resource_kinds"]:
            key = self.key(kind)
            self.reserve(key, kind)
            keys.append(key)
        if hasattr(self.processes, "preallocate"):
            self.processes.preallocate(plan, keys)
        with self.internal("process"):
            child = self.processes.create_suspended(plan, permit, tuple(argv), options)
        job = self.processes.verify_suspended_job(child, plan)
        need(
            type(job) is dict
            and set(job) == {"limits", "members", "suspended", "handle"}
            and body(job["limits"]) == body(plan["job_limits"])
            and job["members"] == sorted(plan["api"].members())
            and len(job["members"]) == 1
            and job["suspended"] is True
            and type(job["handle"]) is int
            and job["handle"] > 0,
            "OBSERVED_SUSPENDED_JOB_LIMITS_REQUIRED",
        )
        with self.internal("process"):
            self.processes.resume(child)
        ready = self.processes.ready(child, timeout=8, maximum_bytes=65536)
        with self.internal("journal"):
            self.ownership.bind(
                plan["name"],
                api=plan["api"],
                request=plan["request"],
                parent_handle=plan["parent_handle"],
                launch_handle=child.launch_handle,
                runtime_handle=child.runtime_handle,
                ready=ready,
            )
        binding_head = self.resources.head
        self.processes.attach_guards(child, self, plan["name"], keys)
        allocated = self.processes.allocations(child)
        need(
            type(allocated) is dict
            and set(allocated) == set(keys)
            and all(
                type(v) is dict
                and set(v) == {"kind", "handle"}
                and v["kind"] == self.resources.state["resources"][k]["kind"]
                and type(v["handle"]) is int
                and v["handle"] > 0
                for k, v in allocated.items()
            )
            and len({v["handle"] for v in allocated.values()}) == len(keys),
            "EXACT_RESERVED_NATIVE_ALLOCATIONS_REQUIRED",
        )
        need(
            [v["handle"] for v in allocated.values() if v["kind"] == "job"]
            == [job["handle"]],
            "JOB_ALLOCATION_OBSERVATION_CONFLICT",
        )
        receipt = self.processes.guard_receipt(child)
        need(
            type(receipt) is dict
            and receipt
            == {
                "scope": SCOPE_HASH,
                "nonce": plan["request"].nonce,
                "owner": digest(self.ownership.bindings[plan["name"]].runtime),
                "reservation_head": binding_head,
                "guarded": True,
            },
            "CHILD_SHARED_GUARD_BINDING_REQUIRED",
        )
        self.processes.release_target(child)  # Bootstrap stays fenced until binding.
        return GuardedProcess(self, child, plan, keys + permit["slots"], tuple(argv))

    def query(self, argv, **options):
        need(not self.query_active, "RECURSIVE_PROCESS_OBSERVER_REFUSED")
        timeout = options.pop('timeout', 6)
        need(type(timeout) in (int, float) and 0 < timeout <= 6, 'BOUNDED_QUERY_DEADLINE_REQUIRED')
        self.query_active = True
        child = None
        try:
            child = self.spawn(argv, **options)
            need(child.plan["name"] == "query", "EXACT_QUERY_ROLE_REQUIRED")
            return self.processes.query_result(
                child, timeout=timeout, maximum_bytes=65536
            )
        finally:
            try:
                if child is not None:
                    child.close()
            finally:
                self.query_active = False

    def sample_root(self, sample):
        intent = self.paths.stop_slot(sample)
        return intent["path"], ntpath.basename(intent["path"])[-32:]

    def read_input(self, *, maximum_bytes, timeout, line=False):
        need(
            type(timeout) in (int, float)
            and 0 < timeout <= 30
            and type(maximum_bytes) is int
            and 0 < maximum_bytes <= 65536,
            "BOUNDED_FIXTURE_INPUT_REQUIRED",
        )
        self.check()
        started = self.clock()
        deadline = started + int(timeout * 10**9)
        if line:
            return bounded_line(
                self.processes,
                deadline_ns=deadline,
                clock_ns=self.clock,
                maximum_bytes=maximum_bytes,
            )
        data = self.processes.read_input(timeout=timeout, maximum_bytes=maximum_bytes)
        need(
            started <= self.clock() <= deadline
            and type(data) is bytes
            and 0 < len(data) <= maximum_bytes
            and b"\x00" not in data,
            "FIXTURE_INPUT_MISSING_OR_LATE",
        )
        return data

    @contextlib.contextmanager
    def watchdog(self, *, seconds, exit_code):
        need(
            type(seconds) is int and 0 < seconds <= 120 and exit_code in (70, 71),
            "DECLARED_WATCHDOG_REQUIRED",
        )
        keys = [self.key("watchdog-thread"), self.key("watchdog-handle")]
        self.reserve(keys[0], "thread")
        self.reserve(keys[1], "handle")
        timer = self.processes.start_watchdog(
            seconds=seconds, exit_code=exit_code, owner=self.owner, keys=tuple(keys)
        )
        need(
            type(timer) is dict
            and set(timer) == {"owner", "thread", "handle", "created"}
            and timer["owner"] == self.owner
            and all(
                type(timer[k]) is int and timer[k] > 0
                for k in ("thread", "handle", "created")
            ),
            "RETAINED_OWNED_WATCHDOG_REQUIRED",
        )
        try:
            yield
        finally:
            self.processes.cancel_watchdog(timer)
            for key in keys:
                self.ledger("close", self.owner, key, observer=self.processes)

    def verify_received_stop(self, command, nonce, identity):
        """Worker-side binding to the controller's already durable Stop request."""
        need(
            type(command) is dict
            and set(command) == {"scope", "nonce", "worker", "operation_id"}
            and command["scope"] == SCOPE_HASH
            and command["nonce"] == nonce,
            "EXACT_RECEIVED_STOP_REQUIRED",
        )
        self.check()
        owner = self.resources.state["owners"][self.owner]
        record = self.resources.state["stops"].get(command["operation_id"])
        need(
            type(record) is dict
            and record["state"] == "PENDING"
            and digest(command) == record["request"]
            and body(command["worker"]) == body(owner)
            and type(identity) is dict
            and set(identity) == {"pid", "creation_filetime", "image"}
            and identity["pid"] == owner["pid"]
            and identity["creation_filetime"] == owner["created"]
            and type(identity["image"]) is str
            and ntpath.normcase(identity["image"]) == ntpath.normcase(owner["image"]),
            "STOP_CONTROLLER_WORKER_BINDING_CONFLICT",
        )
        return command

    def begin_stop(self, *, reader, expected_accounts, nonce, worker, operation_id):
        need(self.stop is None, "ONE_STOP_PER_FIXTURE_LIFETIME")
        self.stop = StopVerification(
            self.resources,
            self.ownership,
            clock_ns=self.clock,
            financial_reader=reader,
            expected_accounts=expected_accounts,
        )
        with self.internal("journal"):
            return self.stop.begin(
                nonce=nonce, worker=worker, operation_id=operation_id
            )

    def finish_stop(self, **evidence):
        need(self.stop is not None, "MATCHED_STOP_REQUEST_REQUIRED")
        with self.internal("journal"):
            return self.stop.finish(**evidence)

    def run_owned_stop_sample(self, sample, repo):
        """Real timing test calls this path, instead of its old raw Popen loop."""
        if self.stop is not None:
            need(
                self.stop.result is not None
                and not self.failed
                and not self.handles
                and self.ownership.finished == set(self.ownership.bindings),
                "PRIOR_SAMPLE_CLEANUP_REQUIRED",
            )
            self.case_results.append(self.stop.result)
            self.ownership = WorkerOwnership(
                self.resources, all_members=self.ownership.all_members
            )
            self.stop = None  # New lifetime; counters/history/paths are never reset.
        root, nonce = self.sample_root(sample)
        spec = self.processes.owned_stop_spec(sample, root, nonce, os.fspath(repo))
        need(
            set(spec)
            == {"argv", "options", "expected_accounts", "reader", "operation_id"}
            and set(spec["expected_accounts"]) == {"QUALITY_DIPS"},
            "PINNED_QD_TIMING_SCOPE_REQUIRED",
        )
        child = self.spawn(spec["argv"], **spec["options"])
        self.processes.financial_ready(child, timeout=40)
        worker = self.ownership.bindings["financial_worker"].runtime
        request = self.begin_stop(
            reader=spec["reader"],
            expected_accounts=spec["expected_accounts"],
            nonce=nonce,
            worker=worker,
            operation_id=spec["operation_id"],
        )
        self.processes.send_stop(child, request)
        # collect_stop must use the same guarded launch/query/write interfaces
        # for the cold reader and evidence, and return raw verified evidence.
        evidence = self.processes.collect_stop(
            child, self, request, deadline_ns=self.stop.started + 8 * 10**9
        )
        result = self.finish_stop(**evidence)
        need(
            result["cuts"]["QUALITY_DIPS"]["revision"] == 3
            and result["cash_by_lane"]["QUALITY_DIPS"] == "1015.9136",
            "EXACT_QD_NATIVE_FINANCIAL_RESULT_REQUIRED",
        )
        self.write(
            path_for("T", f"sample-{sample}.json"),
            json.dumps(result, sort_keys=True).encode(),
        )
        return result

    def sqlite(self, *args, **kwargs):
        import sqlite3

        need(args, "EXPLICIT_SQLITE_PATH_REQUIRED")
        value = os.fspath(args[0])
        readonly = False
        if value.startswith("file:"):
            need(kwargs.get("uri") is True, "EXPLICIT_SQLITE_URI_REQUIRED")
            parsed = urlsplit(value)
            query = parse_qs(parsed.query)
            need(
                not parsed.netloc
                and set(query) == {"mode"}
                and query["mode"] in (["ro"], ["rw"]),
                "SCOPED_SQLITE_URI_REQUIRED",
            )
            path = unquote(parsed.path).lstrip("/").replace("/", "\\")
            readonly = query["mode"] == ["ro"]
        else:
            path = value
        self.locate(path)
        existing = self.paths.port.inspect(path)
        self.validate_path(path, create=existing is None)
        if path not in self.databases:
            need(
                not readonly and (existing is None or path in self.owned_files),
                "NO_UNOWNED_DATABASE_ADOPTION",
            )
            capacity = self.key("sqlite-capacity")
            self.reserve(
                capacity, "file", entries=int(existing is None), size=256 * 1024
            )
            if hasattr(self.io,'capacity'):
                self.io.capacity(self.owner,capacity,path,256*1024)
            self.databases[path] = {"capacity": capacity, "connections": 0}
            # This is an allocation, not an open database handle. Its charge
            # survives closure; connection handles below have separate lives.
            self.io.note_closed(self.owner, capacity, None)
            self.release(capacity)
        key = self.key("sqlite-connection")
        self.reserve(key, "handle")
        with self.internal("sqlite"):
            db = self.io.sqlite_open(*args, **kwargs)
        try:
            if not readonly:
                page = db.execute("PRAGMA page_size").fetchone()[0]
                need(type(page) is int and 512 <= page <= 65536, "SQLITE_PAGE_SIZE")
                need(
                    db.execute("PRAGMA journal_mode=DELETE").fetchone()[0].lower()
                    == "delete",
                    "SQLITE_BOUNDED_JOURNAL_MODE_REQUIRED",
                )
                db.execute("PRAGMA temp_store=MEMORY")
                need(
                    db.execute("PRAGMA temp_store").fetchone()[0] == 2,
                    "SQLITE_MEMORY_TEMP_REQUIRED",
                )
                need(
                    db.execute(
                        "PRAGMA max_page_count=" + str(256 * 1024 // page)
                    ).fetchone()[0]
                    == 256 * 1024 // page,
                    "SQLITE_PAGE_QUOTA_READBACK_REQUIRED",
                )
            self.validate_path(path)
            self.owned_files.add(path)
            self.file_identities[path] = self.paths.port.inspect(path)["id"]

            def authorize(action, first, second, *_):
                if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
                    return sqlite3.SQLITE_DENY
                if (
                    action == sqlite3.SQLITE_FUNCTION
                    and (second or "").lower() == "load_extension"
                ):
                    return sqlite3.SQLITE_DENY
                if action == sqlite3.SQLITE_PRAGMA and second is not None:
                    allowed = {
                        "synchronous": {"FULL", "2"},
                        "foreign_keys": {"ON", "1"},
                        "query_only": {"ON", "1"},
                    }
                    if (
                        first not in allowed
                        or str(second).upper() not in allowed[first]
                    ):
                        return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK

            db.set_authorizer(authorize)
        except BaseException:
            db.close()
            self.io.note_closed(self.owner, key, db)
            self.release(key)
            raise
        self.databases[path]["connections"] += 1
        return OwnedSqlite(self, db, key, path, readonly)


class OwnedSqlite:
    def __init__(self, guard, db, key, path, readonly):
        self.guard, self.db, self.key, self.closed = guard, db, key, False
        self.path, self.readonly, self.journals = path, readonly, []

    def __getattr__(self, name):
        need(
            name in {"in_transaction", "total_changes", "isolation_level"},
            "UNGUARDED_SQLITE_INTERFACE",
        )
        return getattr(self.db, name)

    def execute(self, sql, params=()):
        need(type(sql) is str, "EXPLICIT_SQL_REQUIRED")
        verb = sql.lstrip().split(None, 1)[0].upper()
        read_transaction = sql.strip().upper() in {
            "BEGIN",
            "BEGIN DEFERRED",
            "BEGIN TRANSACTION",
        }
        if (
            verb not in {"SELECT", "PRAGMA", "COMMIT", "ROLLBACK"}
            and not read_transaction
            and not self.journals
        ):
            need(not self.readonly, "READONLY_SQLITE")
            key = self.guard.key("sqlite-journal")
            self.guard.reserve(key, "file", entries=1, size=1024**2)
            self.journals.append(key)
        try:
            return OwnedCursor(self, self.db.execute(sql, params))
        finally:
            if not self.db.in_transaction:
                self._journal_closed()

    def executemany(self, sql, rows):
        cursor = None
        for params in rows:
            cursor = self.execute(sql, params)
        return cursor

    def cursor(self):
        return OwnedCursor(self, None)

    def commit(self):
        self.db.commit()
        self._journal_closed()

    def rollback(self):
        self.db.rollback()
        self._journal_closed()

    def _journal_closed(self):
        need(
            self.guard.paths.port.inspect(self.path + "-journal") is None,
            "SQLITE_JOURNAL_NOT_DRAINED",
        )
        for key in self.journals:
            self.guard.io.note_closed(self.guard.owner, key, self.db)
            self.guard.release(key)
        self.journals.clear()

    def __enter__(self):
        self.db.__enter__()
        return self

    def __exit__(self, *exc):
        try:
            return self.db.__exit__(*exc)
        finally:
            self.close()

    def close(self):
        if not self.closed:
            self.db.close()
            self._journal_closed()
            self.closed = True
            self.guard.databases[self.path]["connections"] -= 1
            self.guard.io.note_closed(self.guard.owner, self.key, self.db)
            self.guard.release(self.key)


class OwnedCursor:
    def __init__(self, connection, cursor):
        self.connection, self._cursor = connection, cursor

    def execute(self, sql, params=()):
        result = self.connection.execute(sql, params)
        self._cursor = result._cursor
        return self

    def executemany(self, sql, rows):
        result = self.connection.executemany(sql, rows)
        self._cursor = result._cursor
        return self

    def __iter__(self):
        return iter(self._cursor)

    def __getattr__(self, name):
        need(
            name
            in {
                "fetchone",
                "fetchall",
                "fetchmany",
                "rowcount",
                "lastrowid",
                "description",
                "close",
            },
            "UNGUARDED_SQLITE_CURSOR",
        )
        return getattr(self._cursor, name)


class GuardedProcess:
    def __init__(self, guard, child, plan, keys, argv):
        self.guard, self.child, self.plan, self.keys = guard, child, plan, keys
        self.argv = argv
        self.closed = False

    def identity(self):
        bound = self.guard.ownership.bindings[self.plan["name"]]
        bound.verify()
        return dict(bound.runtime)

    @property
    def pid(self):
        return self.guard.ownership.bindings[self.plan["name"]].runtime["pid"]

    @property
    def returncode(self):
        return self.guard.processes.returncode(self.child)

    def communicate(self, input=None, timeout=12):
        need(
            type(timeout) in (int, float) and 0 < timeout <= 35,
            "BOUNDED_CHILD_WAIT_REQUIRED",
        )
        result = self.guard.processes.communicate(
            self.child, input, timeout=timeout, maximum_bytes=1024**2
        )
        self.close()
        return result

    def wait(self, timeout=12):
        need(
            type(timeout) in (int, float) and 0 < timeout <= 35,
            "BOUNDED_CHILD_WAIT_REQUIRED",
        )
        return self.guard.processes.wait(self.child, timeout=timeout)

    def poll(self):
        return self.guard.processes.returncode(self.child)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self.closed:
            need(
                self.guard.processes.resources_closed(self.child, self.keys),
                "REPEATED_CHILD_CLEANUP_CONFLICT",
            )
            return
        with self.guard.internal("journal"):
            roster, name = self.guard.ownership, self.plan["name"]
            bound = roster.bindings[name]
            if self.returncode == 0:
                roster.exit(name)
            else:
                # Explicit self-exit fault probes only; no generic nonzero exit
                # allowance and no change to normal RetainedLaunchBinding exits.
                need(
                    self.returncode == 71
                    and name in {"race_one", "race_two", "financial_worker"}
                    and len(self.argv) == 7
                    and self.argv[1] == "-B"
                    and ntpath.basename(self.argv[2]) == "perp_order_crash_child.py"
                    and self.argv[3] == "--config"
                    and self.argv[5] == "--phase"
                    and self.argv[6]
                    in {
                        "before_publication",
                        "after_record_before_pin",
                        "after_pin",
                        "financial-after-ack",
                    },
                    "UNDECLARED_ABRUPT_EXIT",
                )
                need(
                    not bound.refused
                    and not bound.finished
                    and bound.api.observe(bound.parent_handle) == bound.parent,
                    "CRASH_PARENT_OWNERSHIP_LOST",
                )
                pairs = [
                    (bound.launch_handle, bound.launch),
                    (bound.runtime_handle, bound.runtime),
                ]
                for handle, row in pairs:
                    need(
                        bound.api.lifecycle(handle)
                        == {
                            "pid": row["pid"],
                            "created": row["created"],
                            "exited": True,
                            "exit_code": 71,
                        },
                        "EXACT_CRASH_LIFETIME_REQUIRED",
                    )
                need(bound.api.members() == set(), "CRASH_JOB_NOT_DRAINED")
                bound.finished = True
                roster.finished.add(name)
                roster.verify()
            self.guard.processes.close_owned_handles(self.child, self.keys)
            for key in self.keys:
                resource = self.guard.resources.state["resources"][key]
                self.guard.resources.close(
                    resource["owner"], key, observer=self.guard.processes
                )
        self.closed = True


def native_call(event, invoke, values, module):
    guard = current()
    return (
        invoke(*values)
        if guard is None
        else guard.native(event, invoke, values, module=module)
    )


def image_open(api, path):
    return native_call(
        "image_open",
        api.k.CreateFileW,
        (path, 0x80000000, 1, None, 3, 0x80, None),
        None,
    )


def image_close(api, handle):
    return native_call("close", api.k.CloseHandle, (handle,), None)


def mkdir(path):
    return require_fixture("mkdir").mkdir(path)


def write_bytes(path, data):
    return require_fixture("write").write(path, data)


def write_text(path, data):
    need(type(data) is str, "EXPLICIT_TEXT_REQUIRED")
    return write_bytes(path, data.encode("utf8"))


def rewrite_text(path, data):
    need(type(data) is str, "EXPLICIT_TEXT_REQUIRED")
    return require_fixture("owned-fault-replacement").rewrite(path, data.encode("utf8"))


def read_bytes(path):
    guard = require_fixture("read-owned-artifact")
    guard.validate_path(path)
    return guard.io.read_bytes(os.fspath(path))


def replace(source, target):
    return require_fixture("replace").replace(source, target)


def popen(argv, **options):
    return require_fixture("child-launch").spawn(argv, **options)


def query(argv, **options):
    return require_fixture("process-query").query(argv, **options)


def watchdog(**options):
    return require_fixture("child-watchdog").watchdog(**options)


def sqlite_connect(*args, **kwargs):
    guard = current()
    if guard is None:
        import sqlite3

        return sqlite3.connect(*args, **kwargs)
    if args and args[0] == ":memory:":
        import sqlite3

        return sqlite3.connect(*args, **kwargs)
    return guard.sqlite(*args, **kwargs)
