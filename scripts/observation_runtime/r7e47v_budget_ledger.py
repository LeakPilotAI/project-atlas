"""Standalone synthetic-only SQLite attempt-budget prototype."""
from contextlib import closing
import os
import sqlite3
from pathlib import Path


class BudgetRefused(RuntimeError):
    pass


class DurableBudget:
    def __init__(self, path, provider, limit, *, enroll=False):
        if (
            type(provider) is not str
            or not provider
            or type(limit) is not int
            or not 1 <= limit <= 10000
            or not isinstance(path, (str, Path))
        ):
            raise BudgetRefused("Invalid synthetic budget admission")
        self.path = Path(path)
        self.provider = provider
        self.limit = limit

        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise BudgetRefused("Unsafe or missing ledger location")

        if type(enroll) is not bool:
            raise BudgetRefused("Invalid enrollment flag")
        if enroll and self.path.exists():
            raise BudgetRefused("Ledger already exists; enrollment refused")
        if not enroll and not self.path.exists():
            raise BudgetRefused("Missing ledger; explicit enrollment required")
        first_creation = enroll
        try:
            with closing(self._connect()) as connection, connection as db:
                db.execute("BEGIN IMMEDIATE")
                if first_creation:
                    db.execute(
                        "CREATE TABLE budget "
                        "(provider TEXT PRIMARY KEY, max_attempts INTEGER NOT NULL, "
                        "attempted INTEGER NOT NULL)"
                    )
                row = db.execute(
                    "SELECT max_attempts, attempted FROM budget WHERE provider=?",
                    (provider,),
                ).fetchone()
                if row is None:
                    if not first_creation:
                        raise BudgetRefused(
                            "Existing ledger missing admitted provider"
                        )
                    db.execute(
                        "INSERT INTO budget VALUES (?, ?, 0)",
                        (provider, limit),
                    )
                elif (
                    type(row[0]) is not int
                    or type(row[1]) is not int
                    or row[0] != limit
                    or not 0 <= row[1] <= limit
                ):
                    raise BudgetRefused("Stored budget mismatch or corruption")
                db.commit()
        except sqlite3.Error as error:
            raise BudgetRefused("Ledger initialization refused") from error

    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=2, isolation_level=None)
        db.execute("PRAGMA busy_timeout=2000")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA journal_mode=DELETE")
        return db

    def consume(self):
        try:
            with closing(self._connect()) as connection, connection as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT max_attempts, attempted FROM budget WHERE provider=?",
                    (self.provider,),
                ).fetchone()
                if (
                    row is None
                    or row[0] != self.limit
                    or type(row[1]) is not int
                    or not 0 <= row[1] <= self.limit
                ):
                    raise BudgetRefused("Stored budget invalid")
                if row[1] >= self.limit:
                    raise BudgetRefused("Synthetic budget exhausted")
                db.execute(
                    "UPDATE budget SET attempted=attempted+1 WHERE provider=?",
                    (self.provider,),
                )
                db.commit()
                return row[1] + 1
        except sqlite3.Error as error:
            raise BudgetRefused("Ledger consumption refused") from error

    def remaining(self):
        try:
            with closing(self._connect()) as connection, connection as db:
                row = db.execute(
                    "SELECT max_attempts, attempted FROM budget WHERE provider=?",
                    (self.provider,),
                ).fetchone()
                if (
                    row is None
                    or row[0] != self.limit
                    or type(row[1]) is not int
                    or not 0 <= row[1] <= self.limit
                ):
                    raise BudgetRefused("Stored budget invalid")
                return self.limit - row[1]
        except sqlite3.Error as error:
            raise BudgetRefused("Ledger inspection refused") from error