"""Metadata-only Linux inspector. No database/configuration file is opened."""

import hashlib
import json
import os
import posixpath
import re
import signal
import stat
import sys
import time

ROOT = "/inspection"
MAX_ENTRIES = 100000
MAX_DEPTH = 32
MAX_OUTPUT = 65536
SECONDS = 30
KNOWN = {"PG_VERSION", "base", "global", "pg_wal", "pg_tblspc", "pg_xact",
         "postgresql.conf", "postgresql.auto.conf", "pg_hba.conf", "pg_ident.conf",
         "dump.rdb", "appendonlydir", "appendonly.aof", "redis.conf"}


def token(value):
    return hashlib.sha256(os.fsencode(value)).hexdigest()


def public_path(path):
    safe = all(p in KNOWN or re.fullmatch(r"appendonly\.aof\.\d+\.(base|incr)\.(rdb|aof)", p) for p in path.split("/"))
    return path if safe else "sha256:" + token(path)


def link_metadata(path, target, service):
    original = "/var/lib/postgresql/data" if service == "postgres" else "/data"
    joined = posixpath.normpath(target if target.startswith("/") else posixpath.join(original, posixpath.dirname(path), target))
    internal = joined == original or joined.startswith(original + "/")
    # Unknown target strings may themselves contain confidential names. Never
    # print them; the hash permits correlation without dereferencing them.
    return {"path": public_path(path), "target_sha256": token(target),
            "scope": "internal_unfollowed" if internal else "external_unfollowed"}


class PosixTree:
    """Directory-fd traversal; O_NOFOLLOW on EVERY directory, no file reads."""

    def __init__(self, root=ROOT):
        if sys.platform != "linux":
            raise RuntimeError("Linux descriptor backend required")
        self.root = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.device = os.fstat(self.root).st_dev

    def close(self):
        os.close(self.root)

    def root_stat(self):
        return os.fstat(self.root)

    def visit(self, parent, name, expected=None):
        fd = os.dup(self.root) if parent is None else os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        s = os.fstat(fd)
        if s.st_dev != self.device or (expected is not None and (s.st_dev, s.st_ino) != (expected.st_dev, expected.st_ino)):
            os.close(fd)
            raise RuntimeError("Unexpected nested filesystem")
        return fd

    def entries(self, fd):
        # scandir is consumed incrementally: never materialize an enormous tree.
        return os.scandir(fd)

    def metadata(self, entry):
        return entry.name, entry.stat(follow_symlinks=False)

    def readlink(self, fd, name):
        return os.readlink(name, dir_fd=fd)

    def release(self, fd):
        os.close(fd)


def inspect(tree, service, clock=time.monotonic, limit=MAX_ENTRIES, deadline=SECONDS):
    if service not in {"postgres", "redis"}:
        raise ValueError("Unknown service")
    started = clock()
    out = {"schema": 1, "status": "INCOMPLETE", "service": service, "entries": 0,
           "files": 0, "directories": 0, "logical_file_bytes": 0,
           "allocated_file_bytes": 0, "allocation_known": True,
           "tree_allocated_bytes": 0,
           "links": [], "artifacts": [], "layout": [], "anomalies": [],
           "payloads_read": False, "effective_configuration": "NOT_ESTABLISHED"}
    seen = set()
    seen_entries = set()

    def allocation(s):
        key = (s.st_dev, s.st_ino)
        if key not in seen_entries:
            seen_entries.add(key)
            blocks = getattr(s, "st_blocks", None)
            if blocks is None:
                out["allocation_known"] = False
            else:
                out["tree_allocated_bytes"] += blocks * 512

    def walk(parent=None, name=None, path="", depth=0, expected=None):
        if depth > MAX_DEPTH:
            raise RuntimeError("DEPTH_LIMIT")
        fd = tree.visit(parent, name, expected)
        try:
            with tree.entries(fd) as entries:
                for entry in entries:
                    if clock() - started >= deadline:
                        raise TimeoutError("DEADLINE")
                    out["entries"] += 1
                    if out["entries"] > limit:
                        raise RuntimeError("ENTRY_LIMIT")
                    leaf, s = tree.metadata(entry)
                    if leaf in {".", ".."} or "/" in leaf or "\\" in leaf:
                        raise RuntimeError("INVALID_NAME")
                    rel = posixpath.join(path, leaf)
                    allocation(s)
                    if stat.S_ISLNK(s.st_mode):
                        if len(out["links"]) >= 64:
                            raise RuntimeError("LINK_OUTPUT_LIMIT")
                        out["links"].append(link_metadata(rel, tree.readlink(fd, leaf), service))
                    elif stat.S_ISDIR(s.st_mode):
                        out["directories"] += 1
                        if depth == 0 and leaf in KNOWN:
                            out["layout"].append(leaf)
                        walk(fd, leaf, rel, depth + 1, s)
                    elif stat.S_ISREG(s.st_mode):
                        out["files"] += 1
                        identity = (s.st_dev, s.st_ino)
                        if identity not in seen:
                            seen.add(identity)
                            out["logical_file_bytes"] += s.st_size
                            blocks = getattr(s, "st_blocks", None)
                            if blocks is None:
                                out["allocation_known"] = False
                            else:
                                out["allocated_file_bytes"] += blocks * 512
                        if leaf in KNOWN or (service == "redis" and leaf.endswith((".rdb", ".aof", ".manifest"))):
                            if len(out["artifacts"]) >= 128:
                                raise RuntimeError("ARTIFACT_OUTPUT_LIMIT")
                            out["artifacts"].append({"path": public_path(rel), "bytes": s.st_size})
                    else:
                        raise RuntimeError("SPECIAL_FILE")
        finally:
            tree.release(fd)

    try:
        allocation(tree.root_stat())
        walk()
        out["status"] = "METADATA_COMPLETE_COVERAGE_UNPROVEN"
    except Exception as exc:  # noqa: BLE001 - bounded report must redact all OS/path failures.
        # Never print exceptions/OS paths which may contain confidential names.
        out["anomalies"] = [type(exc).__name__]
    if any(x["scope"].startswith("external") for x in out["links"]):
        out["status"] = "BLOCKED_EXTERNAL_REFERENCE"
    if not out["allocation_known"]:
        out["allocated_file_bytes"] = None
        out["tree_allocated_bytes"] = None
    return out


def bounded_json(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    if len(raw) > MAX_OUTPUT:
        return b'{"status":"INCOMPLETE","reason":"OUTPUT_LIMIT","payloads_read":false}'
    return raw


def verify_mountinfo(text):
    matches = []
    for line in text.splitlines():
        left = line.split(" - ", 1)[0].split()
        if len(left) >= 6 and left[4] == ROOT:
            matches.append(left)
        elif len(left) >= 6 and left[4].startswith(ROOT + "/"):
            raise RuntimeError("Nested mount refused")
    if len(matches) != 1 or "ro" not in matches[0][5].split(","):
        raise RuntimeError("Exact read-only inspection mount required")


def main():
    tree = None
    try:
        if sys.argv[1:] not in (["postgres"], ["redis"]):
            raise RuntimeError("Exact service argument required")
        if sys.platform != "linux":
            raise RuntimeError("Linux required")
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        # Read kernel mount metadata only. No source file is opened.
        with open("/proc/self/mountinfo", encoding="utf-8") as stream:
            mountinfo = stream.read(262145)
        if len(mountinfo) > 262144:
            raise RuntimeError("Mount metadata too large")
        verify_mountinfo(mountinfo)
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError()))
        signal.alarm(SECONDS)
        tree = PosixTree()
        result = inspect(tree, sys.argv[1])
    except BaseException:  # noqa: BLE001 - no traceback or sensitive paths on the helper boundary.
        result = {"status": "INCOMPLETE", "reason": "PREFLIGHT_OR_DEADLINE", "payloads_read": False}
    finally:
        if tree is not None:
            try:
                tree.close()
            except OSError:
                result = {"status": "INCOMPLETE", "reason": "CLOSE_FAILURE", "payloads_read": False}
    sys.stdout.buffer.write(bounded_json(result) + b"\n")
    return 0 if result["status"] == "METADATA_COMPLETE_COVERAGE_UNPROVEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
