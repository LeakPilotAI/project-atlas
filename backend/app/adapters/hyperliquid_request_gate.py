"""Default-deny durable logical Hyperliquid attempt gate.

No authorization is installed on import. HTTP attempts and WebSocket connections
are counted, not individual frames, messages or library-internal wire requests.
Existing ledger schema is preserved; missing/corrupt state is never reset.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class RequestGateRefused(RuntimeError):
    pass


class HyperliquidRequestGate:
    def __init__(self, ledger_path: str | Path, *, rights_approved=False, budget_approved=False, max_attempts=0):
        if rights_approved is not True or budget_approved is not True:
            raise RequestGateRefused("Provider rights and request budget require explicit approval")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 2**63 - 1:
            raise RequestGateRefused("Invalid request budget")
        self.path = Path(ledger_path).absolute()
        self.max_attempts = max_attempts
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._location()
        created = False
        try:
            # Exclusive creation; an interrupted initialization remains evidence.
            with self.path.open("xb"):
                created = True
        except FileExistsError:
            pass
        except OSError as exc:
            raise RequestGateRefused("Budget creation failed") from exc
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if created:
                db.execute("CREATE TABLE budget (id INTEGER PRIMARY KEY CHECK(id=1), max_attempts INTEGER NOT NULL, attempted INTEGER NOT NULL)")
                db.execute("INSERT INTO budget VALUES (1, ?, 0)", (max_attempts,))
            self._state(db)

    def _location(self):
        for part in (self.path, *self.path.parents):
            if part.exists() or part.is_symlink():
                stat = part.lstat()
                if part.is_symlink() or getattr(stat, "st_file_attributes", 0) & 0x400:
                    raise RequestGateRefused("Linked budget storage refused")
                if part == self.path and (not part.is_file() or stat.st_nlink != 1):
                    raise RequestGateRefused("Invalid budget file identity")

    @contextmanager
    def _connect(self):
        self._location()
        db = None
        try:
            db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=2)
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        except sqlite3.Error as exc:
            raise RequestGateRefused("Budget storage operation failed") from exc
        finally:
            if db is not None:
                db.close()

    def _state(self, db):
        rows = db.execute("SELECT id, max_attempts, attempted FROM budget").fetchall()
        if len(rows) != 1:
            raise RequestGateRefused("Budget ledger missing or contradictory")
        key, limit, attempted = rows[0]
        if (type(key) is not int or key != 1 or type(limit) is not int
                or limit != self.max_attempts or type(attempted) is not int
                or not 0 <= attempted <= limit):
            raise RequestGateRefused("Budget configuration differs or state is corrupt")
        return limit - attempted

    def remaining(self):
        with self._connect() as db:
            remaining = self._state(db)
        return remaining

    def consume_before_attempt(self, kind):
        if type(kind) is not str or kind not in ("HTTP", "WEBSOCKET_CONNECT"):
            raise RequestGateRefused("Unsupported provider operation")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            remaining = self._state(db)
            if remaining == 0:
                raise RequestGateRefused("Provider request budget exhausted")
            cursor = db.execute("UPDATE budget SET attempted=attempted+1 WHERE id=1 AND attempted < max_attempts")
            if cursor.rowcount != 1:
                raise RequestGateRefused("Budget consumption refused")
        # The connection's transaction committed and closed before acknowledgement.
        return remaining - 1
