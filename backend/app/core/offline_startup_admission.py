"""Isolated admission foundation. No production authority, enrollment or startup hook.

The caller supplies a trusted issued-evidence binding and fresh identity reader.
SQLite consumption assumes a trusted, non-rollback storage directory. This is not
the native protected storage/VFS acceptance required for production integration.
"""
import json
import sqlite3
from pathlib import Path
from uuid import UUID


class AdmissionRefused(RuntimeError):
    pass


def initialize_fixture_store(path: Path):
    """Explicit isolated fixture provisioning only; never resets existing state."""
    with path.open("xb"):
        pass
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE consumed (token TEXT PRIMARY KEY, evidence TEXT NOT NULL)")


def consume_offline_admission(path, evidence, *, issued, run_id, now, read_identity):
    """Return an offline receipt only after durable, exclusive consumption."""
    try:
        if type(evidence) is not dict or evidence != issued:
            raise ValueError("Missing or untrusted issued evidence")
        if set(evidence) != {"token", "run_id", "profile", "issued_at", "expires_at", "process"}:
            raise ValueError("Malformed evidence")
        UUID(evidence["token"])
        UUID(run_id)
        if evidence["run_id"] != run_id or evidence["profile"] != "DAILY_PAPER_OFFLINE":
            raise ValueError("Admission identity mismatch")
        start, end = evidence["issued_at"], evidence["expires_at"]
        if any(type(v) is not int for v in (start, end, now)) or not 0 < end - start <= 60 or not start <= now < end:
            raise ValueError("Expired or unbounded evidence")
        identity = evidence["process"]
        if (type(identity) is not dict or set(identity) != {"pid", "created_at", "executable", "command"}
                or type(identity["pid"]) is not int or identity["pid"] <= 4
                or any(type(identity[k]) is not str or not identity[k] for k in ("created_at", "executable", "command"))):
            raise ValueError("Malformed process identity")
        # mode=rw forbids silent creation of missing consumption state.
        with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rw", uri=True, timeout=1) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            if read_identity() != identity:
                raise ValueError("Fresh process identity mismatch")
            db.execute("INSERT INTO consumed VALUES (?, ?)",
                       (evidence["token"], json.dumps(evidence, sort_keys=True)))
            db.commit()
        return {"scope": "OFFLINE_ONLY", "run_id": run_id, "production_authorized": False}
    except Exception as error:
        raise AdmissionRefused("Offline admission refused") from error
