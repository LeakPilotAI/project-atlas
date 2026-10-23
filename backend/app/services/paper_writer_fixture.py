"""Durable cooperative fixture writer roster; no production authority or adapters."""
import hashlib
import sqlite3
import time
from pathlib import Path


def _validated_operations(db):
    """Corrupt acknowledgements cannot prove cooperative fixture quiescence."""
    rows = db.execute("SELECT id,writer,incarnation,acked,payload FROM writer_operations ORDER BY id").fetchall()
    for operation, writer, incarnation, acked, payload in rows:
        if (any(type(value) is not str or not value for value in (operation, writer, incarnation))
                or type(acked) is not int or acked not in (0, 1)
                or type(payload) is not str or len(payload) != 64
                or any(char not in "0123456789abcdef" for char in payload)):
            raise ValueError("Malformed fixture writer operation evidence")
        owner = db.execute("SELECT incarnation,uncertain FROM writer_roster WHERE id=?", (writer,)).fetchone()
        if owner != (incarnation, 0):
            raise ValueError("Unverified fixture writer operation ownership")
    return rows


def provision_fixture_writers(path, roster):
    if type(roster) is not dict or not roster or any(type(k) is not str or not k or type(v) is not str or not v for k, v in roster.items()):
        raise ValueError("Exact writer identity/incarnation roster required")
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rw", uri=True) as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE writer_roster(id TEXT PRIMARY KEY, incarnation TEXT NOT NULL, uncertain INTEGER NOT NULL)")
        db.executemany("INSERT INTO writer_roster VALUES(?,?,0)", sorted(roster.items()))
        db.execute("CREATE TABLE writer_operations(id TEXT PRIMARY KEY,writer TEXT,incarnation TEXT,acked INTEGER,payload TEXT NOT NULL)")


def fixture_writer_operation(path, *, writer, incarnation, operation, payload, acknowledge=False):
    if type(operation) is not str or not operation:
        raise ValueError("Stable operation identity required")
    if type(payload) is not str or len(payload) != 64 or any(c not in '0123456789abcdef' for c in payload):
        raise ValueError("Explicit payload SHA256 required")
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rw", uri=True, timeout=1) as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        _validated_operations(db)
        row = db.execute("SELECT incarnation,uncertain FROM writer_roster WHERE id=?", (writer,)).fetchone()
        if row != (incarnation, 0):
            raise ValueError("Unknown, restarted or uncertain writer")
        old = db.execute("SELECT writer,incarnation,acked,payload FROM writer_operations WHERE id=?", (operation,)).fetchone()
        if old and (old[:2] != (writer, incarnation) or old[3] != payload):
            raise ValueError("Conflicting operation identity")
        if acknowledge:
            if not old:
                raise ValueError("No admitted operation")
            db.execute("UPDATE writer_operations SET acked=1 WHERE id=?", (operation,))
        elif not old:
            if db.execute("SELECT stopped FROM control").fetchall() != [(0,)]:
                raise ValueError("Writer admission closed or ambiguous")
            db.execute("INSERT INTO writer_operations VALUES(?,?,?,0,?)", (operation, writer, incarnation, payload))
        return "ACKNOWLEDGED" if acknowledge or old and old[2] == 1 else "UNCERTAIN" if old else "ADMITTED"


def run_fixture_writer(path, *, writer, incarnation, operation, payload, mutation, fault=lambda phase: None):
    """Wrap a supplied fixture save/append callback; ambiguous retries never reapply."""
    args = {"writer": writer, "incarnation": incarnation, "operation": operation, "payload": payload}
    fault("before_admission")
    state = fixture_writer_operation(path, **args)
    if state == "ACKNOWLEDGED":
        return
    if state != "ADMITTED":
        raise ValueError("Unacknowledged mutation requires reconciliation")
    fault("after_admission")
    mutation()
    fault("after_mutation")
    fixture_writer_operation(path, **args, acknowledge=True)
    fault("after_ack")


def close_fixture_writers(path, expected, *, fault=lambda phase: None):
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rw", uri=True, timeout=1) as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT stopped FROM control").fetchall() not in ([(0,)], [(1,)]):
            raise ValueError("Ambiguous fixture admission")
        rows = db.execute("SELECT id,incarnation,uncertain FROM writer_roster ORDER BY id").fetchall()
        if rows != [(key, value, 0) for key, value in sorted(expected.items())] or not rows:
            raise ValueError("Incomplete or uncertain writer inventory")
        operations = _validated_operations(db)
        db.execute("UPDATE control SET stopped=1")
        pending = [row[0] for row in operations if row[3] == 0]
        fault("before_close_commit")
        db.commit()
        fault("after_close_commit")
        return {"status": "INCOMPLETE" if pending else "DRAINED_FIXTURE_ONLY",
                "pending": pending, "production_authorized": False}


def reconcile_external_fixture(path, *, root, relative_file, writer, incarnation, operation, payload):
    """Verify an explicitly supplied disposable external file before ack.

    Cooperative fixture namespace only; not protected production verification.
    Does not execute/retry the mutation or clear writer uncertainty.
    """
    root = Path(root).resolve(strict=True)
    relative = Path(relative_file)
    if relative.is_absolute() or not relative.parts or any(part in ("..", ".") for part in relative.parts):
        raise ValueError("Explicit confined fixture path required")
    candidate = root
    for part in relative.parts:
        candidate /= part
        if candidate.is_symlink() or candidate.is_junction():
            raise ValueError("Fixture path substitution refused")
    if candidate.resolve(strict=True).parent != root or not candidate.is_file():
        raise ValueError("Direct fixture file required")
    with candidate.open("rb") as handle:
        original = handle.read(1048577)
        if len(original) > 1048576 or hashlib.sha256(original).hexdigest() != payload:
            raise ValueError("External fixture commitment mismatch")
        handle.seek(0)
        if handle.read(1048577) != original:
            raise ValueError("External fixture changed during verification")
        fixture_writer_operation(path, writer=writer, incarnation=incarnation, operation=operation,
                                 payload=payload, acknowledge=True)


def drain_fixture_writers(path, expected, *, timeout):
    """Bounded cooperative observation; no cancellation, recovery or forced ack."""
    if type(timeout) not in (int, float) or not 0 <= timeout <= 5:
        raise ValueError("Explicit bounded fixture drain timeout required")
    deadline = time.monotonic() + timeout
    while True:
        result = close_fixture_writers(path, expected)
        if result["status"] == "DRAINED_FIXTURE_ONLY":
            return result
        if time.monotonic() >= deadline:
            return {**result, "status": "TIMED_OUT", "recovery_required": True}
        time.sleep(min(0.01, max(0, deadline - time.monotonic())))
