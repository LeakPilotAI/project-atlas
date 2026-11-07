"""Synthetic append-only session history; never a recovery/admission authority.

Reuses the existing research journal commitment, only on explicitly created
fixture files. SQLite is path-based: this is not security-critical VFS acceptance.
No existing journal migration, uncertainty clearing or production initialization.
"""
from __future__ import annotations

import json
import math
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from app.core.durable_io import sync_parent, write_flushed
from app.investment.extended_hours_integrity import JournalCommitment

from .contracts import (
    Refused,
    RuntimeContract,
    canonical_uuid,
    digest,
    encoded,
    file_digest,
    identity,
)

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GATE = threading.Lock()
EVENTS = frozenset({"SESSION_START", "DATA_SOURCE", "HEALTH", "GRACEFUL_SHUTDOWN",
                    "INTERRUPTED", "RECOVERY_REQUIRED"})


@dataclass(frozen=True)
class HistoryPin:
    files: tuple[tuple[str, tuple[int, int]], ...]


class SessionHistory:
    def __init__(self, contract: RuntimeContract, pin: HistoryPin):
        self.contract = contract
        self.path = contract.verify()["journal_root"] / "sessions.jsonl"
        self.commitment = JournalCommitment(self.path)
        self.lock_path = self.path.with_suffix(".lock")
        if type(pin) is not HistoryPin or {p for p, _ in pin.files} != {
            str(self.path), str(self.commitment.path), str(self.lock_path)
        }:
            raise Refused("Exact independently retained fixture history pin required")
        self.pin = pin
        self.failure: BaseException | None = None
        with _LOCKS_GATE:
            self._thread_lock = _LOCKS.setdefault(os.path.normcase(str(self.path)), threading.Lock())
        self.verify()

    @classmethod
    def create_fixture(cls, contract: RuntimeContract) -> SessionHistory:
        """Explicit fixture-only creation; partial artifacts never overwritten."""
        path = contract.verify()["journal_root"] / "sessions.jsonl"
        commitment = JournalCommitment(path)
        lock = path.with_suffix(".lock")
        if any(p.exists() for p in (path, commitment.path, lock)):
            raise Refused("History already exists or initialization was interrupted")
        with lock.open("x", encoding="utf-8") as handle:
            write_flushed(handle, "1")
        with path.open("x", encoding="utf-8") as handle:
            write_flushed(handle, "")
        commitment.initialize(expected_legacy_sha256=file_digest(b""))
        sync_parent(path)
        pin = HistoryPin(tuple((str(p), identity(p)) for p in (path, commitment.path, lock)))
        return cls(contract, pin)

    @contextmanager
    def _locked(self):
        if self.failure is not None:
            raise self.failure
        if not self._thread_lock.acquire(blocking=False):
            raise Refused("Concurrent history operation refused")
        try:
            self.contract.verify()
            for path, expected in self.pin.files:
                if identity(Path(path)) != expected:
                    raise Refused("History/witness/lock identity changed")
            with self.lock_path.open("r+b") as handle:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    yield
                finally:
                    handle.seek(0)
                    if os.name == "nt":
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._thread_lock.release()

    def _read(self) -> list[dict]:
        if self.path.stat().st_size > 2_000_000:
            raise Refused("History read bound exceeded; evidence retained")
        raw = self.commitment.verify()
        rows = []
        previous = "0" * 64
        ids = set()
        for line in raw.splitlines():
            row = json.loads(line)
            if (type(row) is not dict or set(row) != {"event_id", "session_id", "event", "payload", "observed_at", "previous", "digest"}
                    or row["event"] not in EVENTS or row["previous"] != previous):
                raise Refused("Malformed or reordered history")
            if (type(row["observed_at"]) not in (int, float) or not math.isfinite(row["observed_at"])
                    or row["observed_at"] < 0 or (rows and row["observed_at"] < rows[-1]["observed_at"])):
                raise Refused("Malformed or out-of-order history timestamp")
            canonical_uuid(row["event_id"])
            canonical_uuid(row["session_id"])
            if row["event_id"] in ids or digest({k: v for k, v in row.items() if k != "digest"}) != row["digest"]:
                raise Refused("History digest/duplicate mismatch")
            ids.add(row["event_id"])
            previous = row["digest"]
            rows.append(row)
            if len(rows) > 2048:
                raise Refused("History entry bound exceeded")
        return rows

    def verify(self) -> list[dict]:
        with self._locked():
            return self._read()

    @staticmethod
    def _state(rows: list[dict]) -> tuple[str | None, bool, set[str]]:
        active = None
        uncertain = False
        seen: set[str] = set()
        for row in rows:
            if row["event"] == "SESSION_START":
                if active is not None or row["session_id"] in seen:
                    raise Refused("Overlapping or reused session identity")
                active = row["session_id"]
                seen.add(active)
            elif row["event"] in {"INTERRUPTED", "RECOVERY_REQUIRED"}:
                uncertain = True
            elif row["event"] == "GRACEFUL_SHUTDOWN":
                if uncertain or active != row["session_id"]:
                    raise Refused("Uncertain session cannot become complete")
                active = None
        return active, uncertain, seen

    def admission(self, *, continuing: bool = False) -> None:
        active, uncertain, seen = self._state(self.verify())
        session = self.contract.manifest["session_id"]
        if uncertain or (continuing and active != session) or (not continuing and (active or session in seen)):
            raise Refused("Session interrupted, active, replayed or recovery required")

    def append(self, event: str, payload: dict, event_id: str, *, observed_at: float,
               session_id: str | None = None) -> dict:
        canonical_uuid(event_id)
        manifest = self.contract.manifest
        session = session_id or manifest["session_id"]
        canonical_uuid(session)
        if type(observed_at) not in (int, float) or not math.isfinite(observed_at) or observed_at < 0:
            raise Refused("Explicit finite observation time required")
        if event not in EVENTS or type(payload) is not dict or len(encoded(payload)) > 4096:
            raise Refused("Bounded session event required")
        expected_keys = {"SESSION_START": {"release_id", "profile", "configuration_id"},
                         "DATA_SOURCE": {"source_id"}, "HEALTH": {"state"},
                         "GRACEFUL_SHUTDOWN": {"outcome"}, "INTERRUPTED": {"reason"},
                         "RECOVERY_REQUIRED": {"reason"}}[event]
        if set(payload) != expected_keys:
            raise Refused("Unknown session payload fields")
        if event == "SESSION_START" and payload != {k: manifest[k] for k in expected_keys}:
            raise Refused("Session release/profile/configuration mismatch")
        if event == "DATA_SOURCE" and payload["source_id"] not in manifest["data_sources"]:
            raise Refused("Unapproved source identity")
        if event == "HEALTH" and payload["state"] not in {"READY", "DEGRADED", "UNAVAILABLE"}:
            raise Refused("Unknown health state")
        if event == "GRACEFUL_SHUTDOWN" and payload["outcome"] != "COMPLETE":
            raise Refused("Non-complete shutdown requires interrupted evidence")
        if event in {"INTERRUPTED", "RECOVERY_REQUIRED"} and payload["reason"] not in {
            "PROCESS_INTERRUPTED", "UNKNOWN_EXIT", "PUBLICATION_FAILED", "EVIDENCE_EXPIRED"
        }:
            raise Refused("Unknown non-clearing reason")
        with self._locked():
            rows = self._read()
            for old in rows:
                if old["event_id"] == event_id:
                    if (old["event"], old["session_id"], old["payload"]) != (event, session, payload):
                        raise Refused("Conflicting replay refused")
                    return old
            active, uncertain, seen = self._state(rows)
            if rows and observed_at < rows[-1]["observed_at"]:
                raise Refused("Backdated session evidence refused")
            if event == "SESSION_START":
                if active or uncertain or session in seen or session != manifest["session_id"]:
                    raise Refused("New session requires reconciled history")
            elif active != session or (uncertain and event not in {"INTERRUPTED", "RECOVERY_REQUIRED"}):
                raise Refused("No active reconciled session for event")
            row = {"event_id": event_id, "session_id": session, "event": event, "payload": payload, "observed_at": observed_at,
                   "previous": rows[-1]["digest"] if rows else "0" * 64}
            row["digest"] = digest(row)
            raw = self.path.read_bytes()
            target = raw + encoded(row) + b"\n"
            if len(target) > 2_000_000:
                raise Refused("History capacity exhausted")
            try:
                self.commitment.prepare(target)
                with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                    write_flushed(handle, encoded(row).decode() + "\n")
                self.commitment.finish(target)
            except BaseException as error:
                self.failure = error
                raise
            return row
