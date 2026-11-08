"""Isolated durable consent-generation contract. No production wiring."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import closing
from itertools import islice
from pathlib import Path

from app.alerts.subscriptions import validate_discord_user_id


class ConsentStateError(RuntimeError):
    """Consent evidence is missing, invalid, or unreliable."""


class _ConsentCheckpoint:
    """Local append-only high-water outside restorable SQLite files.

    Not a remote issuer or protection against rollback of the complete directory.
    Provisioned only by explicit create; missing/torn history never self-repairs.
    """

    def __init__(self, path, database_id):
        self.path = Path(str(path) + "." + database_id + ".checkpoint")
        self.database_id = database_id

    @staticmethod
    def _body(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

    def create(self):
        self.path.mkdir(exist_ok=False)
        self._write(
            "scope.json",
            {"schema": "ISOLATED_CONSENT_CHECKPOINT_V1", "database_id": self.database_id},
        )

    def _write(self, name, value):
        raw = self._body(value)
        with (self.path / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())

    def read(self):
        if not self.path.is_dir() or any(
            p.is_symlink() or p.is_junction() for p in (self.path, *self.path.parents)
        ):
            raise ConsentStateError("consent checkpoint unavailable or escaped")
        files = list(islice(self.path.iterdir(), 4098))
        if len(files) > 4097:
            raise ConsentStateError("consent checkpoint capacity")
        names = {p.name for p in files}
        count = len(files) - 1
        if names != {"scope.json", *(f"{i:04d}.json" for i in range(1, count + 1))}:
            raise ConsentStateError("incomplete consent checkpoint")

        def read(name):
            file = self.path / name
            if (
                file.is_symlink()
                or not file.is_file()
                or file.stat().st_nlink != 1
                or file.stat().st_size > 2048
            ):
                raise ConsentStateError("checkpoint identity or size conflict")
            raw = file.read_bytes()
            value = json.loads(raw)
            if self._body(value) != raw:
                raise ConsentStateError("noncanonical checkpoint")
            return value

        scope = {"schema": "ISOLATED_CONSENT_CHECKPOINT_V1", "database_id": self.database_id}
        if read("scope.json") != scope:
            raise ConsentStateError("checkpoint database identity conflict")
        head = hashlib.sha256(self._body(scope)).hexdigest()
        states = {}
        for index in range(1, count + 1):
            row = read(f"{index:04d}.json")
            if (
                set(row) != {"index", "parent", "recipient", "generation", "subscribed"}
                or type(row["index"]) is not int
                or row["index"] != index
                or row["parent"] != head
                or type(row["subscribed"]) is not bool
                or type(row["generation"]) is not int
                or type(row["recipient"]) is not str
            ):
                raise ConsentStateError("checkpoint chain conflict")
            validate_discord_user_id(int(row["recipient"]))
            previous = states.get(row["recipient"])
            if (
                row["generation"] != (previous[0] + 1 if previous else 1)
                or previous is not None
                and previous[1] == row["subscribed"]
            ):
                raise ConsentStateError("checkpoint generation conflict")
            states[row["recipient"]] = (row["generation"], row["subscribed"])
            head = hashlib.sha256(self._body(row)).hexdigest()
        return states, count, head

    def advance(self, recipient, generation, subscribed):
        states, count, head = self.read()
        old = states.get(recipient)
        if old == (generation, subscribed):
            return
        if (
            count >= 4096
            or generation != (old[0] + 1 if old else 1)
            or old is not None
            and old[1] == subscribed
        ):
            raise ConsentStateError("checkpoint exhausted or conflicting transition")
        self._write(
            f"{count + 1:04d}.json",
            {
                "index": count + 1,
                "parent": head,
                "recipient": recipient,
                "generation": generation,
                "subscribed": subscribed,
            },
        )


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
        self.checkpoint = _ConsentCheckpoint(self.path, self._database_id)

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
        created = cls(path)
        created.checkpoint.create()
        return created

    def _assert_checkpoint(self, db):
        states, _, _ = self.checkpoint.read()
        rows = db.execute(
            "SELECT recipient_id,generation,subscribed FROM consent_generations"
        ).fetchall()
        current = {r["recipient_id"]: (r["generation"], bool(r["subscribed"])) for r in rows}
        if current != states or any(
            type(r["generation"]) is not int or r["subscribed"] not in (0, 1) for r in rows
        ):
            raise ConsentStateError("consent rollback or incomplete checkpoint publication")

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
                    "CREATE TABLE consent_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
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
        row = db.execute("SELECT value FROM consent_metadata WHERE key='database_id'").fetchone()
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
                self._assert_checkpoint(db)
                row = db.execute(
                    "SELECT generation, subscribed FROM consent_generations WHERE recipient_id=?",
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

                self.checkpoint.advance(recipient, generation, subscribed)
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
                self._assert_checkpoint(db)
                row = db.execute(
                    "SELECT generation, subscribed FROM consent_generations WHERE recipient_id=?",
                    (recipient,),
                ).fetchone()

            if row is None:
                return False
            if type(row["generation"]) is not int or row["generation"] < 1:
                return False
            if row["subscribed"] not in (0, 1):
                return False

            return row["subscribed"] == 1 and row["generation"] == generation
        except (sqlite3.Error, OSError, ValueError, ConsentStateError):
            return False
