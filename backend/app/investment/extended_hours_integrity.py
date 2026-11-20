"""Independent, synchronous SQLite commitment for the research JSONL journal.

Call only while holding the collector's cross-process journal lock. A durable
pending intent precedes every append; interruption is quarantined, never repaired
automatically. This detects journal-only loss, not coordinated rollback of both
the journal and its witness (which requires an external trusted backup).
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path


class JournalIntegrityError(ValueError):
    """Preserve evidence and require explicit offline recovery."""


class JournalCommitment:
    def __init__(self, journal: Path) -> None:
        self.journal = journal
        self.path = journal.with_name(journal.name + ".commitment.sqlite3")

    def _content(self) -> bytes:
        return self.journal.read_bytes() if self.journal.exists() else b""

    @staticmethod
    def _digest(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _connect(self):
        # mode=rw forbids silently creating a replacement witness.
        connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw", uri=True)
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def initialize(self, *, expected_legacy_sha256: str | None = None) -> None:
        if self.path.exists():
            raise JournalIntegrityError("Commitment already exists; never replace it")
        content = self._content()
        if self.journal.exists() and expected_legacy_sha256 != self._digest(content):
            raise JournalIntegrityError("Legacy journal requires explicit verified migration")
        # Exclusive creation prevents replacing even an empty/corrupt witness.
        with self.path.open("xb"):
            pass
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("CREATE TABLE commitment (id INTEGER PRIMARY KEY CHECK(id=1), "
                       "version INTEGER NOT NULL, journal TEXT NOT NULL, size INTEGER NOT NULL, "
                       "digest TEXT NOT NULL, pending INTEGER NOT NULL CHECK(pending IN (0,1)))")
            db.execute("INSERT INTO commitment VALUES (1,1,?,?,?,0)",
                       (str(self.journal.resolve()), len(content), self._digest(content)))

    def verify(self) -> bytes:
        if not self.path.exists():
            if self.journal.exists():
                raise JournalIntegrityError("Missing commitment; explicit legacy migration required")
            self.initialize()
        try:
            with closing(self._connect()) as db:
                rows = db.execute("SELECT version,journal,size,digest,pending FROM commitment").fetchall()
            content = self._content()
            expected = (1, str(self.journal.resolve()), len(content), self._digest(content), 0)
            if rows != [expected]:
                raise JournalIntegrityError("Journal commitment mismatch or interrupted append; quarantine")
            return content
        except sqlite3.Error as exc:
            raise JournalIntegrityError("Invalid journal commitment; quarantine") from exc

    def prepare(self, content: bytes) -> None:
        with closing(self._connect()) as db, db:
            changed = db.execute(
                "UPDATE commitment SET size=?,digest=?,pending=1 WHERE id=1 AND pending=0",
                (len(content), self._digest(content)),
            ).rowcount
            if changed != 1:
                raise JournalIntegrityError("Cannot prepare journal append")

    def finish(self, content: bytes) -> None:
        if self._content() != content:
            raise JournalIntegrityError("Journal changed during append; quarantine")
        with closing(self._connect()) as db, db:
            changed = db.execute(
                "UPDATE commitment SET pending=0 WHERE id=1 AND pending=1 AND size=? AND digest=?",
                (len(content), self._digest(content)),
            ).rowcount
            if changed != 1:
                raise JournalIntegrityError("Cannot acknowledge journal append")
