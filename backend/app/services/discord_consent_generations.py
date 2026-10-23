"""Isolated durable consent-generation contract. No production wiring."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from app.alerts.subscriptions import validate_discord_user_id


class ConsentStateError(RuntimeError):
    """Consent evidence is missing, invalid, or unreliable."""


class DiscordConsentGenerations:
    """SQLite-backed monotonic consent revisions per recipient."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.parent.is_dir():
            raise ConsentStateError("consent database directory must already exist")
        if not self.path.is_file():
            raise ConsentStateError("consent database must be explicitly provisioned")
        self._validate()
        self._database_id = self.database_id

    @classmethod
    def create(cls, path: Path) -> DiscordConsentGenerations:
        """Explicitly provision a new consent ledger."""
        path = Path(path)
        if not path.parent.is_dir():
            raise ConsentStateError("consent database directory must already exist")
        if path.exists():
            raise ConsentStateError("consent database already exists")

        instance = cls.__new__(cls)
        instance.path = path
        instance._initialize()
        return cls(path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path.resolve().as_uri() + "?mode=rw",
            timeout=5,
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(sqlite3.connect(str(self.path), timeout=5)) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    """
                    CREATE TABLE consent_generations (
                        recipient_id TEXT PRIMARY KEY,
                        generation INTEGER NOT NULL CHECK (generation > 0),
                        subscribed INTEGER NOT NULL CHECK (subscribed IN (0, 1))
                    )
                    """
                )
                db.execute(
                    "CREATE TABLE consent_metadata "
                    "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
                )
                db.execute(
                    "INSERT INTO consent_metadata (key, value) VALUES (?, ?)",
                    ("database_id", uuid.uuid4().hex),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise

    def _validate(self) -> None:
        try:
            with closing(self._connect()) as db:
                row = db.execute(
                    "SELECT value FROM consent_metadata WHERE key='database_id'"
                ).fetchone()
                if row is None or not isinstance(row["value"], str):
                    raise ConsentStateError("missing consent database identity")
                if len(row["value"]) != 32:
                    raise ConsentStateError("invalid consent database identity")
                uuid.UUID(hex=row["value"])
                db.execute("SELECT recipient_id FROM consent_generations LIMIT 1")
        except (sqlite3.Error, OSError, ValueError) as exc:
            raise ConsentStateError("invalid consent database") from exc

    def _assert_identity(self, db: sqlite3.Connection) -> None:
        row = db.execute(
            "SELECT value FROM consent_metadata WHERE key='database_id'"
        ).fetchone()
        if row is None or row["value"] != self._database_id:
            raise ConsentStateError("consent database identity changed")

    @property
    def database_id(self) -> str:
        """Identity to bind to future outbox consent evidence."""
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT value FROM consent_metadata WHERE key='database_id'"
            ).fetchone()
        if row is None:
            raise ConsentStateError("missing consent database identity")
        return str(row["value"])

    @staticmethod
    def _recipient(recipient_id: int) -> str:
        return str(validate_discord_user_id(recipient_id))

    def set_subscription(self, recipient_id: int, subscribed: bool) -> int:
        """Change consent, incrementing generation on every real transition."""
        recipient = self._recipient(recipient_id)
        if type(subscribed) is not bool:
            raise ValueError("subscribed must be a boolean")

        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._assert_identity(db)
                row = db.execute(
                    "SELECT generation, subscribed FROM consent_generations "
                    "WHERE recipient_id=?",
                    (recipient,),
                ).fetchone()

                if row is None:
                    generation = 1
                    db.execute(
                        "INSERT INTO consent_generations VALUES (?, ?, ?)",
                        (recipient, generation, int(subscribed)),
                    )
                else:
                    generation = row["generation"]
                    if type(generation) is not int or generation < 1:
                        raise ConsentStateError("invalid consent generation")
                    if row["subscribed"] not in (0, 1):
                        raise ConsentStateError("invalid consent status")
                    if bool(row["subscribed"]) != subscribed:
                        if generation >= 9223372036854775807:
                            raise ConsentStateError("consent generation exhausted")
                        generation += 1
                        db.execute(
                            "UPDATE consent_generations "
                            "SET generation=?, subscribed=? WHERE recipient_id=?",
                            (generation, int(subscribed), recipient),
                        )

                db.commit()
                return generation
            except Exception:
                db.rollback()
                raise

    def authorized(self, recipient_id: int, generation: int) -> bool:
        """Only the current subscribed generation is authorized."""
        recipient = self._recipient(recipient_id)
        if type(generation) is not int or generation < 1:
            return False

        try:
            with closing(self._connect()) as db:
                self._assert_identity(db)
                row = db.execute(
                    "SELECT generation, subscribed FROM consent_generations "
                    "WHERE recipient_id=?",
                    (recipient,),
                ).fetchone()

            if row is None:
                return False
            if type(row["generation"]) is not int or row["generation"] < 1:
                return False
            if row["subscribed"] not in (0, 1):
                return False

            return row["subscribed"] == 1 and row["generation"] == generation
        except (sqlite3.Error, OSError, ConsentStateError):
            return False
