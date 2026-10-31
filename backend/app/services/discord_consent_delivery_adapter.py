"""Isolated fail-closed consent-bound dispatch prototype.

This prototype is intentionally not connected to the production lifecycle send path
or production outbox schema. It enforces immutable consent-generation and database
identity binding before a delivery can be admitted to the transport queue.
"""

from __future__ import annotations

import secrets
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from app.alerts.subscriptions import validate_discord_user_id
from app.services.discord_consent_coordinator import DiscordConsentCoordinator


class ConsentDeliveryAdapterError(RuntimeError):
    """Consent-bound delivery evidence is missing, stale, or invalid."""


class DiscordConsentDeliveryAdapter:
    """Fail-closed delivery guard for isolated consent-bound dispatch.

    Queue admission requires: the recipient is currently authorized for the specific
    consent generation, the consent ledger identity matches the database ID recorded
    at the time the queue record was created, and the witness still matches. This
    adapter never grants authority based on recovery diagnostics alone.
    """

    def __init__(self, coordinator: DiscordConsentCoordinator, path: Path) -> None:
        self.coordinator = coordinator
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5.0)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self) -> None:
        with closing(self._connect()) as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS delivery_queue (
                    event_id TEXT PRIMARY KEY,
                    recipient_id TEXT NOT NULL,
                    consent_generation INTEGER NOT NULL CHECK(consent_generation > 0),
                    consent_database_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('queued', 'dispatching', 'sent', 'denied', 'uncertain')),
                    lease_token TEXT,
                    lease_expires_at REAL,
                    updated_at REAL NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            columns = {row[1] for row in db.execute("PRAGMA table_info(delivery_queue)")}
            if "lease_token" not in columns:
                db.execute("ALTER TABLE delivery_queue ADD COLUMN lease_token TEXT")
            if "lease_expires_at" not in columns:
                db.execute("ALTER TABLE delivery_queue ADD COLUMN lease_expires_at REAL")
            db.commit()

    def _current_binding(
        self,
        recipient_id: int,
        generation: int,
        database_id: str,
    ) -> bool:
        if type(recipient_id) is not int:
            return False
        if type(generation) is not int or generation < 1:
            return False
        if not isinstance(database_id, str) or len(database_id) != 32:
            return False
        try:
            validate_discord_user_id(recipient_id)
        except ValueError:
            return False

        try:
            if database_id != self.coordinator.consent.database_id:
                return False
            if not self.coordinator.authorized(recipient_id, generation):
                return False
            return self.coordinator.witness.matches(
                recipient_id,
                database_id,
                generation,
                True,
            )
        except (
            sqlite3.Error,
            OSError,
            ValueError,
            TypeError,
            ConsentDeliveryAdapterError,
        ):
            return False

    def authorize_for_delivery(
        self,
        recipient_id: int,
        generation: int | None,
        database_id: str | None,
    ) -> bool:
        """Return False if consent evidence is absent, stale, or untrusted."""
        if generation is None or database_id is None:
            return False
        return self._current_binding(recipient_id, generation, database_id)

    def enqueue(
        self,
        event_id: str,
        recipient_id: int,
        *,
        generation: int | None,
        database_id: str | None,
    ) -> bool:
        if not isinstance(event_id, str) or not event_id.strip():
            return False
        if not self.authorize_for_delivery(recipient_id, generation, database_id):
            return False

        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    """
                    INSERT INTO delivery_queue (
                        event_id,
                        recipient_id,
                        consent_generation,
                        consent_database_id,
                        status,
                        lease_token,
                        lease_expires_at,
                        updated_at,
                        created_at
                    ) VALUES (?, ?, ?, ?, 'queued', NULL, NULL, strftime('%s','now'), strftime('%s','now'))
                    ON CONFLICT(event_id) DO UPDATE SET
                        recipient_id=excluded.recipient_id,
                        consent_generation=excluded.consent_generation,
                        consent_database_id=excluded.consent_database_id,
                        status='queued',
                        lease_token=NULL,
                        lease_expires_at=NULL,
                        updated_at=strftime('%s','now')
                    """,
                    (
                        event_id,
                        str(validate_discord_user_id(recipient_id)),
                        generation,
                        database_id,
                    ),
                )
                db.commit()
                return True
            except Exception:
                db.rollback()
                raise

    def _claim_dispatch(self, event_id: str) -> bool:
        now = time.time()
        lease_expires_at = now + 30.0
        lease_token = secrets.token_hex(16)

        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT status, lease_expires_at FROM delivery_queue WHERE event_id=?",
                    (event_id,),
                ).fetchone()
                if row is None:
                    db.rollback()
                    return False
                status = row["status"]
                existing_expiry = row["lease_expires_at"]
                if status in {"sent", "denied", "uncertain"}:
                    db.rollback()
                    return False
                if status == "dispatching" and existing_expiry is not None and float(existing_expiry) > now:
                    db.rollback()
                    return False

                changed = db.execute(
                    "UPDATE delivery_queue "
                    "SET status='dispatching', lease_token=?, lease_expires_at=?, updated_at=strftime('%s','now') "
                    "WHERE event_id=? AND (status='queued' OR (status='dispatching' AND (lease_expires_at IS NULL OR lease_expires_at <= ?)))",
                    (lease_token, lease_expires_at, event_id, now),
                ).rowcount
                db.commit()
                return changed == 1
            except Exception:
                db.rollback()
                raise

    def dispatch_due(
        self,
        event_id: str,
        recipient_id: int,
        sender: Callable[[], bool],
    ) -> bool:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT recipient_id, consent_generation, consent_database_id, status, lease_expires_at "
                "FROM delivery_queue WHERE event_id=?",
                (event_id,),
            ).fetchone()

        if row is None:
            return False

        status = row["status"]
        if status in {"sent", "denied", "uncertain"}:
            return False
        if status == "dispatching":
            expiry = row["lease_expires_at"]
            if expiry is not None and float(expiry) > time.time():
                return False

        stored_recipient = str(row["recipient_id"])
        stored_generation = row["consent_generation"]
        stored_database_id = row["consent_database_id"]
        try:
            expected_recipient = int(validate_discord_user_id(recipient_id))
        except ValueError:
            self._set_status(event_id, "denied")
            return False
        if int(stored_recipient) != expected_recipient:
            self._set_status(event_id, "denied")
            return False
        if not self.authorize_for_delivery(
            int(stored_recipient),
            stored_generation,
            stored_database_id,
        ):
            self._set_status(event_id, "denied")
            return False
        if not self._claim_dispatch(event_id):
            return False
        if not self.authorize_for_delivery(
            int(stored_recipient),
            stored_generation,
            stored_database_id,
        ):
            self._set_status(event_id, "denied")
            return False

        try:
            accepted = bool(sender())
        except Exception:  # noqa: BLE001 - fail closed on any sender failure
            self._set_status(event_id, "uncertain")
            return False

        if not accepted:
            self._set_status(event_id, "denied")
            return False

        self._set_status(event_id, "sent")
        return True

    def _set_status(self, event_id: str, status: str) -> None:
        valid = {"queued", "dispatching", "sent", "denied", "uncertain"}
        if status not in valid:
            raise ConsentDeliveryAdapterError("unsupported delivery status")
        with closing(self._connect()) as db:
            db.execute(
                "UPDATE delivery_queue SET status=?, lease_token=NULL, lease_expires_at=NULL, updated_at=strftime('%s','now') WHERE event_id=?",
                (status, event_id),
            )
            db.commit()
