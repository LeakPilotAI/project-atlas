"""Isolated mocked execution contracts. No Docker, subprocess or production integration.

SQLite serialization fences cooperating callers only. Windows ACL enforcement and
production startup integration deliberately remain unavailable.
"""
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import stat
import time
from contextlib import contextmanager
from pathlib import Path

STATES = {"NOT_AUTHORIZED", "PRECONDITIONS_VERIFIED", "IN_PROGRESS", "COMPLETE", "FAILED", "UNCERTAIN"}
BLOCKING = {"PRECONDITIONS_VERIFIED", "IN_PROGRESS", "UNCERTAIN"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class Fence:
    """One-operation durable fence; no implicit expiration, clearing or replacement."""

    def __init__(self, path, *, create=False):
        self.path = Path(path).resolve()
        if create:
            # Explicit initialization only; never reconstruct a missing fence.
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            with self.connect() as db:
                db.execute("CREATE TABLE fence (id INTEGER PRIMARY KEY CHECK(id=1), record TEXT NOT NULL)")
                db.execute("CREATE TABLE audit (id INTEGER PRIMARY KEY, record TEXT NOT NULL)")
                db.execute("INSERT INTO fence VALUES (1, ?)", (json.dumps({"state": "NOT_AUTHORIZED"}),))
        else:
            self.read()  # Missing/corrupt/partial initialization is not repaired.

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=1)
        try:
            db.execute("PRAGMA synchronous=FULL")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @contextmanager
    def startup_guard(self):
        """Cooperating startup holds this transaction through lifecycle admission.

        Not wired into any launcher; no guarantee about external writers.
        """
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT record FROM fence WHERE id=1").fetchone()
            if self.decode(row[0])["state"] in BLOCKING:
                raise ValueError("Inspection prohibits startup")
            yield

    @staticmethod
    def decode(raw):
        x = json.loads(raw)
        if not isinstance(x, dict) or x.get("state") not in STATES:
            raise ValueError("Malformed fence")
        if x["state"] == "NOT_AUTHORIZED":
            if set(x) != {"state"}:
                raise ValueError("Contradictory unauthorized state")
        else:
            if not all(k in x for k in ("operation", "approval", "helper")) or not isinstance(x["approval"], dict):
                raise ValueError("Incomplete fence")
            if x["operation"] != x["approval"].get("operation"):
                raise ValueError("Contradictory authorization")
            if x["helper"] is not None and (not isinstance(x["helper"], str) or not re.fullmatch(r"[a-f0-9]{64}", x["helper"])):
                raise ValueError("Malformed helper identity")
            if x["state"] in {"IN_PROGRESS", "COMPLETE", "FAILED"} and x["helper"] is None:
                raise ValueError("Missing helper identity")
            if x["state"] == "COMPLETE" and not re.fullmatch(r"[a-f0-9]{64}", x.get("digest", "")):
                raise ValueError("Missing evidence commitment")
        return x

    def read(self):
        with self.connect() as db:
            return self.decode(db.execute("SELECT record FROM fence WHERE id=1").fetchone()[0])

    def startup_allowed(self):
        try:
            return self.read()["state"] in {"NOT_AUTHORIZED", "COMPLETE", "FAILED"}
        except (ValueError, TypeError, KeyError, IndexError, sqlite3.Error):
            return False

    def transition(self, expected, record):
        self.decode(json.dumps(record))
        allowed = {"NOT_AUTHORIZED": {"PRECONDITIONS_VERIFIED"},
                   "PRECONDITIONS_VERIFIED": {"UNCERTAIN"},
                   "UNCERTAIN": {"UNCERTAIN", "IN_PROGRESS", "FAILED"},
                   "IN_PROGRESS": {"COMPLETE", "UNCERTAIN"}, "FAILED": set(), "COMPLETE": set()}
        if record["state"] not in allowed[expected["state"]]:
            raise ValueError("Forbidden fence transition")
        if expected["state"] != "NOT_AUTHORIZED" and any(record[k] != expected[k] for k in ("operation", "approval")):
            raise ValueError("Authorization replacement")
        if expected.get("helper") is not None and record["helper"] != expected["helper"]:
            raise ValueError("Helper replacement")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = self.decode(db.execute("SELECT record FROM fence WHERE id=1").fetchone()[0])
            if old != expected:
                raise ValueError("Concurrent or replaced fence")
            db.execute("UPDATE fence SET record=? WHERE id=1", (canonical(record).decode(),))
            db.execute("INSERT INTO audit(record) VALUES (?)", (canonical(record).decode(),))
        return record

    def authorize(self, approval, now):
        if (set(approval) != {"operation", "image", "source", "volume", "expires", "exclusive_window"}
                or not re.fullmatch(r"[a-z0-9-]{8,64}", approval["operation"])
                or not re.fullmatch(r"sha256:[a-f0-9]{64}", approval["image"])
                or not re.fullmatch(r"[a-f0-9]{64}", approval["source"])
                or type(approval["expires"]) not in (int, float)
                or not now < approval["expires"] <= now + 300
                or approval["exclusive_window"] is not True):
            raise ValueError("Explicit bounded approval required")
        old = self.read()
        if old["state"] != "NOT_AUTHORIZED":
            raise ValueError("One-time authorization already consumed")
        return self.transition(old, {"state": "PRECONDITIONS_VERIFIED", "operation": approval["operation"],
                                     "approval": approval, "helper": None})


class ProtectedOutput:
    """POSIX private-directory evidence. Windows fails closed, no ACL edits.

    Directory must be exclusively owned and not writable by other actors. The
    reviewed Windows DACL/handle implementation is a separate production gate.
    """

    def __init__(self, root):
        self.root = Path(root)
        if os.name != "posix":
            raise PermissionError("Windows DACL acceptance not implemented")
        if not self.root.is_absolute() or self.root.is_symlink() or self.root.resolve() != self.root:
            raise PermissionError("Unsafe destination")
        s = self.root.stat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or stat.S_IMODE(s.st_mode) != 0o700:
            raise PermissionError("Private owned directory required")
        self.identity = (s.st_dev, s.st_ino)

    def publish(self, name, value):
        if not re.fullmatch(r"[a-z0-9-]{1,64}\.json", name):
            raise ValueError("Unsafe evidence name")
        current = self.root.stat()
        if (self.root.is_symlink() or self.root.resolve() != self.root
                or (current.st_dev, current.st_ino) != self.identity
                or current.st_uid != os.getuid() or stat.S_IMODE(current.st_mode) != 0o700):
            raise PermissionError("Output directory changed")
        data = canonical(safe_metadata(canonical(value)))
        if len(data) > 65536:
            raise ValueError("Evidence too large")
        # Unique final file with O_EXCL retains partial failure evidence. A
        # separate commit file is the atomic publication boundary for readers.
        path = self.root / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        digest = hashlib.sha256(data).hexdigest()
        marker = self.root / (name + ".commit")
        pending = self.root / (name + ".commit.pending")
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(digest.encode())
            f.flush()
            os.fsync(f.fileno())
        # Hard-link publication is atomic and refuses an existing commit name.
        # Pending files are intentionally retained, including on failure.
        os.link(pending, marker, follow_symlinks=False)
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return digest


def safe_metadata(raw):
    """Deliberately narrow scalar acceptance; never persist raw stdout/stderr."""
    if not isinstance(raw, bytes) or len(raw) > 65536:
        raise ValueError("Output limit or type")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate output key")
            result[key] = value
        return result
    x = json.loads(raw, object_pairs_hook=unique)
    keys = {"schema", "service", "status", "files", "directories", "logical_file_bytes",
            "effective_configuration", "payloads_read"}
    helper_extra = {"entries", "allocated_file_bytes", "tree_allocated_bytes", "allocation_known",
                    "layout", "artifacts", "links", "anomalies"}
    if not isinstance(x, dict) or set(x) not in (keys, keys | helper_extra):
        raise ValueError("Unknown output fields")
    if type(x["schema"]) is not int or x["schema"] != 1 or x["service"] not in {"postgres", "redis"} or x["status"] != "METADATA_COMPLETE_COVERAGE_UNPROVEN":
        raise ValueError("Incomplete output")
    if x["effective_configuration"] != "NOT_ESTABLISHED" or x["payloads_read"] is not False:
        raise ValueError("Forbidden content claim")
    if any(type(x[k]) is not int or not 0 <= x[k] <= 2**63-1 for k in ("files", "directories", "logical_file_bytes")):
        raise ValueError("Malformed totals")
    if "links" in x:
        if x["anomalies"] != [] or not isinstance(x["links"], list) or len(x["links"]) > 64:
            raise ValueError("Incomplete traversal")
        for link in x["links"]:
            if not isinstance(link, dict) or link.get("scope") != "internal_unfollowed":
                raise ValueError("External or malformed link")
    # Discard all filenames/link tokens/layout strings, even from pinned helper.
    return {k: x[k] for k in keys}


class MockDocker:
    """Fixture transport only; no real API implementation or callable injection."""
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def request(self, method, timeout, limit):
        self.calls.append((method, timeout, limit))
        result = self.responses[method]
        if isinstance(result, BaseException):
            raise result
        encoded = result if isinstance(result, bytes) else canonical(result)
        if len(encoded) > limit:
            raise ValueError("Mock transport output limit")
        return json.loads(encoded) if not isinstance(result, bytes) else result


class Adapter:
    def __init__(self, fence, docker, output, clock=time.time, monotonic=time.monotonic):
        if type(docker) is not MockDocker:
            raise TypeError("Synthetic transport only")
        self.fence, self.docker, self.output, self.clock = fence, docker, output, clock
        self.monotonic = monotonic

    def call(self, method):
        remaining = self.deadline - self.monotonic()
        if self.clock() >= self.expires:
            raise TimeoutError("Approval expired")
        if remaining <= 0:
            raise TimeoutError("Observer deadline")
        x = self.docker.request(method, min(5, remaining), 65536)
        if self.monotonic() >= self.deadline or self.clock() >= self.expires:
            raise TimeoutError("Late result")
        return x

    def run(self, approval, spec, before, after):
        try:
            return self._run(approval, spec, before, after)
        except BaseException:
            with self.fence.connect() as db:
                db.execute("INSERT INTO audit(record) VALUES (?)", ('{"event":"ATTEMPT_FAILED_REVIEW_REQUIRED"}',))
            raise

    def _run(self, approval, spec, before, after):
        loader = importlib.util.spec_from_file_location("inspection_policy", Path(__file__).with_name("policy.py"))
        policy = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(policy)
        verified_plan = policy.plan(spec["service"], before, after, approval["image"], now=self.clock())
        verified_plan.update(pid_mode="private", ipc_mode="private", seccomp="default",
                             env=[], devices=[], binds=[], synthetic_only=True)
        cid, volume, _, _ = policy.EXPECTED[spec["service"]]
        if approval["source"] != cid or approval["volume"] != volume:
            raise ValueError("Approval identity mismatch")
        # Strict entire-spec equality includes namespaces/seccomp/env/deadlines;
        # caller's trusted plan must come from the pinned policy plus extension.
        if canonical(spec) != canonical(verified_plan) or spec.get("image") != approval["image"]:
            raise ValueError("Launch specification mismatch")
        required = {"pid_mode": "private", "ipc_mode": "private", "seccomp": "default",
                    "env": [], "devices": [], "binds": [], "synthetic_only": True}
        if any(spec.get(k) != v for k, v in required.items()):
            raise ValueError("Unsafe complete launch controls")
        state = self.fence.authorize(approval, self.clock())
        self.deadline = self.monotonic() + 40
        self.expires = approval["expires"]
        try:
            # Persist uncertainty BEFORE any mock create: crash can never imply
            # no remote side effect. Recovery needs operation-label discovery.
            state = self.fence.transition(state, {**state, "state": "UNCERTAIN"})
            pre = self.call("preflight")
            if policy.plan(spec["service"], before, pre, approval["image"], now=self.clock()) != {k: v for k, v in verified_plan.items() if k not in required}:
                raise ValueError("Ownership changed")
            helper = self.call("create")
            if not isinstance(helper, str) or not re.fullmatch(r"[a-f0-9]{64}", helper):
                raise ValueError("Malformed helper ID")
            state = self.fence.transition(state, {**state, "helper": helper})
            actual = self.call("inspect_created")
            if canonical(actual) != canonical({"id": helper, "operation": approval["operation"], "spec": spec, "state": "created"}):
                raise ValueError("Created controls mismatch")
            if self.call("preflight_after_create") != pre:
                raise ValueError("Source replacement")
            state = self.fence.transition(state, {**state, "state": "IN_PROGRESS"})
            if canonical(self.call("start")) != canonical({"id": helper, "started": True}):
                raise ValueError("Invalid start acknowledgement")
            raw = self.call("output")
            exit_proof = self.call("exit")
            if canonical(exit_proof) != canonical({"id": helper, "operation": approval["operation"], "state": "exited", "pid": 0, "exit": 0}):
                raise ValueError("Unproven helper exit")
            if self.call("postflight") != pre:
                raise ValueError("Postflight changed")
            metadata = safe_metadata(raw)
            if metadata["service"] != spec["service"]:
                raise ValueError("Output service mismatch")
            digest = self.output.publish(approval["operation"] + ".json", metadata)
            self.fence.transition(state, {**state, "state": "COMPLETE", "digest": digest})
            return metadata
        except BaseException:
            # Persist no exception message: third-party errors can contain secrets.
            latest = self.fence.read()
            if latest["state"] in BLOCKING:
                self.fence.transition(latest, {**latest, "state": "UNCERTAIN", "failure": "REVIEW_REQUIRED"})
            raise

    def recover(self, proof, now, operator_approved=False):
        old = self.fence.read()
        if not operator_approved or old["state"] not in {"UNCERTAIN", "IN_PROGRESS"} or old["helper"] is None:
            raise ValueError("Independent exact-helper recovery required")
        expected = {"id": old["helper"], "operation": old["operation"], "state": "exited", "pid": 0}
        if (not isinstance(proof, dict) or set(proof) != set(expected) | {"observed"}
                or any(type(proof[k]) is not type(v) or proof[k] != v for k, v in expected.items())
                or type(proof["observed"]) not in (int, float) or not 0 <= now-proof["observed"] <= 5):
            raise ValueError("Fresh independent exit proof required")
        # Failure, never success or retry. Unknown create-ID remains fenced.
        return self.fence.transition(old, {**old, "state": "FAILED", "recovery": "INDEPENDENT_EXIT_PROVEN"})
