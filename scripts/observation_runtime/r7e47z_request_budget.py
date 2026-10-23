"""Durable offline request-attempt budget for a future isolated collector.

This module does not authorize or perform network requests.
"""

import sqlite3
from contextlib import closing
from pathlib import Path


class RequestBudgetRefused(RuntimeError):
    pass


class RequestBudget:
    def __init__(self, path, *, enroll=False):
        self.path = Path(path)

        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise RequestBudgetRefused("Unsafe ledger location")

        if enroll and self.path.exists():
            raise RequestBudgetRefused("Ledger already exists")

        if not enroll and not self.path.exists():
            raise RequestBudgetRefused("Explicit enrollment required")

        try:
            with closing(self._connect()) as db:
                db.execute("BEGIN IMMEDIATE")

                if enroll:
                    db.execute(
                        "CREATE TABLE budget ("
                        "id INTEGER PRIMARY KEY CHECK(id=1), "
                        "max_attempts INTEGER NOT NULL CHECK(max_attempts=1), "
                        "attempted INTEGER NOT NULL "
                        "CHECK(attempted BETWEEN 0 AND 1))"
                    )
                    db.execute(
                        "INSERT INTO budget VALUES (1, 1, 0)"
                    )

                row = db.execute(
                    "SELECT max_attempts, attempted "
                    "FROM budget WHERE id=1"
                ).fetchone()

                if row is None or row[0] != 1 or row[1] not in (0, 1):
                    raise RequestBudgetRefused("Invalid ledger")

                db.commit()
        except sqlite3.Error as error:
            raise RequestBudgetRefused("Ledger initialization failed") from error

    def _connect(self):
        db = sqlite3.connect(
            str(self.path),
            timeout=2,
            isolation_level=None,
        )
        db.execute("PRAGMA busy_timeout=2000")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA journal_mode=DELETE")
        return db

    def consume_before_attempt(self):
        try:
            with closing(self._connect()) as db:
                db.execute("BEGIN IMMEDIATE")
                cursor = db.execute(
                    "UPDATE budget SET attempted=1 "
                    "WHERE id=1 AND max_attempts=1 AND attempted=0"
                )

                if cursor.rowcount != 1:
                    raise RequestBudgetRefused(
                        "Request budget exhausted or invalid"
                    )

                db.commit()
        except sqlite3.Error as error:
            raise RequestBudgetRefused("Budget transaction failed") from error

    def remaining(self):
        try:
            with closing(self._connect()) as db:
                row = db.execute(
                    "SELECT max_attempts, attempted "
                    "FROM budget WHERE id=1"
                ).fetchone()

                if row is None or row[0] != 1 or row[1] not in (0, 1):
                    raise RequestBudgetRefused("Invalid ledger")

                return 1 - row[1]
        except sqlite3.Error as error:
            raise RequestBudgetRefused("Ledger inspection failed") from error
