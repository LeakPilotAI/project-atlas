"""Isolated E136 consent rollback witness. Not connected to production."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from app.alerts.subscriptions import validate_discord_user_id


class ConsentWitnessError(RuntimeError):
    """Witness state is missing, conflicting, or unreliable."""


class DiscordConsentWitness:
    """Independent monotonic witness for consent generation observations."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise ConsentWitnessError("witness must be explicitly provisioned")
        self._database_id = self._validate()

    @classmethod
    def create(cls, path: Path) -> DiscordConsentWitness:
        path = Path(path)
        if not path.parent.is_dir():
            raise ConsentWitnessError("witness parent directory missing")
        if path.exists():
            raise ConsentWitnessError("witness already exists")
        with closing(sqlite3.connect(path, timeout=5)) as db:
            db.execute(
                "CREATE TABLE witness_metadata "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            db.execute(
                "INSERT INTO witness_metadata (key, value) VALUES (?, ?)",
                ("witness_id", uuid.uuid4().hex),
            )
            db.execute(
                "CREATE TABLE witness ("
                "recipient_id TEXT PRIMARY KEY, "
                "database_id TEXT NOT NULL, "
                "generation INTEGER NOT NULL CHECK(generation > 0), "
                "subscribed INTEGER NOT NULL CHECK(subscribed IN (0,1)))"
            )
            db.commit()
        return cls(path)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(
            self.path.resolve().as_uri() + "?mode=rw",
            uri=True,
            timeout=5,
        )
        db.row_factory = sqlite3.Row
        return db

    def _validate(self) -> str:
        try:
            with closing(self._connect()) as db:
                columns = {
                    row["name"]
                    for row in db.execute("PRAGMA table_info(witness)")
                }
                if columns != {
                    "recipient_id",
                    "database_id",
                    "generation",
                    "subscribed",
                }:
                    raise ConsentWitnessError("invalid witness schema")
                row = db.execute(
                    "SELECT value FROM witness_metadata WHERE key='witness_id'"
                ).fetchone()
                if row is None or not isinstance(row["value"], str):
                    raise ConsentWitnessError("missing witness identity")
                try:
                    witness_id = uuid.UUID(hex=row["value"]).hex
                except (ValueError, AttributeError) as exc:
                    raise ConsentWitnessError("invalid witness identity") from exc
                if len(row["value"]) != 32 or witness_id != row["value"]:
                    raise ConsentWitnessError("invalid witness identity")
                if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise ConsentWitnessError("invalid witness integrity")
                return witness_id
        except (sqlite3.Error, OSError) as exc:
            raise ConsentWitnessError("unreliable witness database") from exc

    def _assert_identity(self, db: sqlite3.Connection) -> None:
        row = db.execute(
            "SELECT value FROM witness_metadata WHERE key='witness_id'"
        ).fetchone()
        if row is None or row["value"] != self._database_id:
            raise ConsentWitnessError("witness database identity changed")

    @property
    def witness_id(self) -> str:
        return self._database_id

    def observe(
        self,
        recipient_id: int,
        database_id: str,
        generation: int,
        subscribed: bool,
    ) -> None:
        recipient = str(validate_discord_user_id(recipient_id))
        if not isinstance(database_id, str) or len(database_id) != 32:
            raise ValueError("invalid consent database identity")
        if type(generation) is not int or not 1 <= generation < (1 << 63):
            raise ValueError("invalid consent generation")
        if type(subscribed) is not bool:
            raise ValueError("subscribed must be boolean")

        try:
            with closing(self._connect()) as db:
                db.execute("BEGIN IMMEDIATE")
                self._assert_identity(db)
                row = db.execute(
                    "SELECT database_id, generation, subscribed "
                    "FROM witness WHERE recipient_id=?",
                    (recipient,),
                ).fetchone()

                if row is not None:
                    if row["database_id"] != database_id:
                        raise ConsentWitnessError("database identity changed")
                    if generation < row["generation"]:
                        raise ConsentWitnessError("consent generation rollback")
                    if generation == row["generation"]:
                        if row["subscribed"] != int(subscribed):
                            raise ConsentWitnessError("conflicting consent evidence")
                        db.commit()
                        return

                db.execute(
                    "INSERT INTO witness VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(recipient_id) DO UPDATE SET "
                    "database_id=excluded.database_id, "
                    "generation=excluded.generation, "
                    "subscribed=excluded.subscribed",
                    (recipient, database_id, generation, int(subscribed)),
                )
                db.commit()
        except (sqlite3.Error, OSError) as exc:
            raise ConsentWitnessError("witness update failed") from exc

    def matches(
        self,
        recipient_id: int,
        database_id: str,
        generation: int,
        subscribed: bool,
    ) -> bool:
        recipient = str(validate_discord_user_id(recipient_id))
        if type(generation) is not int or type(subscribed) is not bool:
            return False
        try:
            with closing(self._connect()) as db:
                self._assert_identity(db)
                row = db.execute(
                    "SELECT database_id, generation, subscribed "
                    "FROM witness WHERE recipient_id=?",
                    (recipient,),
                ).fetchone()
            return (
                row is not None
                and row["database_id"] == database_id
                and row["generation"] == generation
                and row["subscribed"] == int(subscribed)
            )
        except (sqlite3.Error, OSError, ConsentWitnessError):
            return False
