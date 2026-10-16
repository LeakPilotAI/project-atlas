"""Fail-closed, recipient-scoped outbox contract for gated Discord lifecycle events.

This module is intentionally not wired to production producers. Its sender must
address exactly one recipient and return True only after confirmed DM delivery.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import secrets
import sqlite3
from collections.abc import Awaitable, Callable, Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LIFECYCLE_EVENT_TYPES = frozenset(
    {
        "SIGNAL_CREATED",
        "SIGNAL_INVALIDATED",
        "PAPER_ENTRY",
        "PAPER_MARK",
        "PAPER_CLOSE",
        "PAPER_INTERRUPTED",
        "PAPER_RISK_STOP",
    }
)
_MAX_ID_LENGTH = 256
_MAX_PAYLOAD_BYTES = 16_384
_MAX_RECIPIENTS = 500
_MAX_ATTEMPTS = 3
_RETRY_DELAYS_SECONDS = (5, 30)
_LEASE_SECONDS = 120
_SCHEMA_VERSION = 1
_TOKEN = re.compile(r"^[A-Za-z0-9_.:-]+$")
LifecycleSender = Callable[..., Awaitable[bool]]


class LifecycleContractError(ValueError):
    """The event or persisted delivery state violates the lifecycle contract."""


@dataclass(frozen=True)
class LifecycleEvent:
    event_id: str
    event_type: str
    source: str
    entity_id: str
    source_event_id: str
    source_sequence: int
    occurred_at: str
    payload_json: str

    @property
    def payload(self) -> dict[str, Any]:
        return json.loads(self.payload_json)


def _required_id(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise LifecycleContractError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized or len(normalized) > _MAX_ID_LENGTH:
        raise LifecycleContractError(f"{name} must contain 1 to {_MAX_ID_LENGTH} characters")
    if any(ord(char) < 32 for char in normalized):
        raise LifecycleContractError(f"{name} cannot contain control characters")
    return normalized


def _timestamp(value: datetime) -> tuple[str, float]:
    if not isinstance(value, datetime):
        raise LifecycleContractError("occurred_at must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise LifecycleContractError("occurred_at must be timezone-aware")
    utc_value = value.astimezone(UTC)
    return utc_value.isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    ), utc_value.timestamp()


def make_lifecycle_event(
    *,
    event_type: str,
    source: str,
    entity_id: str,
    source_event_id: str,
    source_sequence: int,
    occurred_at: datetime,
    payload: Mapping[str, Any],
) -> LifecycleEvent:
    """Build a deterministic event; producers supply their durable source key and sequence."""
    normalized_type = _required_id(event_type, "event_type").upper()
    if normalized_type not in LIFECYCLE_EVENT_TYPES:
        raise LifecycleContractError("unsupported Discord lifecycle event type")
    normalized_source = _required_id(source, "source")
    if not _TOKEN.fullmatch(normalized_source):
        raise LifecycleContractError("source contains unsupported characters")
    normalized_entity = _required_id(entity_id, "entity_id")
    normalized_source_event = _required_id(source_event_id, "source_event_id")
    if (
        isinstance(source_sequence, bool)
        or not isinstance(source_sequence, int)
        or not 1 <= source_sequence < (1 << 63)
    ):
        raise LifecycleContractError("source_sequence must be a positive signed 64-bit integer")
    if not isinstance(payload, Mapping):
        raise LifecycleContractError("payload must be an object with string keys")
    _validate_json_value(payload, 0)
    try:
        payload_json = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise LifecycleContractError(f"payload is not canonical JSON: {exc}") from exc
    if len(payload_json.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
        raise LifecycleContractError("payload exceeds 16 KiB")
    occurred, _ = _timestamp(occurred_at)
    identity = json.dumps(
        [normalized_type, normalized_source, normalized_entity, normalized_source_event],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    event_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return LifecycleEvent(
        event_id=event_id,
        event_type=normalized_type,
        source=normalized_source,
        entity_id=normalized_entity,
        source_event_id=normalized_source_event,
        source_sequence=source_sequence,
        occurred_at=occurred,
        payload_json=payload_json,
    )


def _validate_json_value(value: Any, depth: int) -> None:
    if depth > 24:
        raise LifecycleContractError("payload nesting exceeds 24 levels")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise LifecycleContractError("payload numbers must be finite")
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_json_value(item, depth + 1)
        return
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise LifecycleContractError("payload objects must have string keys")
        for item in value.values():
            _validate_json_value(item, depth + 1)
        return
    raise LifecycleContractError("payload must contain only JSON values")


def _epoch(value: datetime | None) -> float:
    instant = value or datetime.now(UTC)
    if not isinstance(instant, datetime):
        raise LifecycleContractError("delivery time must be a datetime")
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise LifecycleContractError("delivery time must be timezone-aware")
    return instant.astimezone(UTC).timestamp()


class DiscordLifecycleOutbox:
    """SQLite-backed durable ordering, deduplication, and recipient receipts."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            if version == 0 and not tables:
                connection.executescript(
                    """
                    BEGIN IMMEDIATE;
                    CREATE TABLE lifecycle_events (
                        event_id TEXT PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        source TEXT NOT NULL,
                        entity_id TEXT NOT NULL,
                        source_event_id TEXT NOT NULL,
                        source_sequence INTEGER NOT NULL,
                        occurred_at TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        UNIQUE(source, entity_id, source_sequence),
                        UNIQUE(source, entity_id, event_type, source_event_id)
                    );
                    CREATE TABLE lifecycle_deliveries (
                        event_id TEXT NOT NULL REFERENCES lifecycle_events(event_id),
                        recipient_id TEXT NOT NULL,
                        status TEXT NOT NULL CHECK (
                            status IN ('pending','inflight','retry','delivered','uncertain','dead')
                        ),
                        attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0 AND attempts <= 3),
                        next_attempt_at REAL NOT NULL DEFAULT 0,
                        lease_token TEXT,
                        lease_until REAL,
                        last_error TEXT,
                        PRIMARY KEY(event_id, recipient_id)
                    );
                    CREATE INDEX lifecycle_delivery_due
                        ON lifecycle_deliveries(status, next_attempt_at, lease_until);
                    PRAGMA user_version=1;
                    COMMIT;
                    """
                )
            elif version != _SCHEMA_VERSION or tables != {
                "lifecycle_events",
                "lifecycle_deliveries",
            }:
                raise LifecycleContractError(
                    "unrecognized lifecycle outbox schema; refusing to modify it"
                )
            expected_columns = {
                "lifecycle_events": {
                    "event_id",
                    "event_type",
                    "source",
                    "entity_id",
                    "source_event_id",
                    "source_sequence",
                    "occurred_at",
                    "payload_json",
                    "created_at",
                },
                "lifecycle_deliveries": {
                    "event_id",
                    "recipient_id",
                    "status",
                    "attempts",
                    "next_attempt_at",
                    "lease_token",
                    "lease_until",
                    "last_error",
                },
            }
            for table, columns in expected_columns.items():
                actual = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
                if actual != columns:
                    raise LifecycleContractError(
                        "lifecycle outbox columns do not match schema version"
                    )
            check = connection.execute("PRAGMA quick_check").fetchone()[0]
            if check != "ok":
                raise LifecycleContractError("lifecycle outbox integrity check failed")

    @staticmethod
    def _validated_recipients(recipients: set[int] | list[int] | tuple[int, ...]) -> list[str]:
        values = list(recipients)
        if len(values) > _MAX_RECIPIENTS:
            raise LifecycleContractError("recipient snapshot exceeds 500 users")
        if any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value <= 0
            or value > (1 << 64) - 1
            for value in values
        ):
            raise LifecycleContractError("recipient IDs must be positive unsigned 64-bit integers")
        return sorted({str(value) for value in values}, key=int)

    def enqueue(
        self, event: LifecycleEvent, recipients: set[int] | list[int] | tuple[int, ...]
    ) -> bool:
        """Persist once with an immutable recipient snapshot; return True only for a new event."""
        verified_event = make_lifecycle_event(
            event_type=event.event_type,
            source=event.source,
            entity_id=event.entity_id,
            source_event_id=event.source_event_id,
            source_sequence=event.source_sequence,
            occurred_at=datetime.fromisoformat(event.occurred_at),
            payload=event.payload,
        )
        if verified_event != event:
            raise LifecycleContractError("event identity or canonical payload is invalid")
        recipient_ids = self._validated_recipients(recipients)
        _, created_at = _timestamp(datetime.now(UTC))
        expected = (
            event.event_type,
            event.source,
            event.entity_id,
            event.source_event_id,
            event.source_sequence,
            event.occurred_at,
            event.payload_json,
        )
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = connection.execute(
                    """
                    SELECT event_type, source, entity_id, source_event_id, source_sequence,
                           occurred_at, payload_json
                    FROM lifecycle_events WHERE event_id=?
                    """,
                    (event.event_id,),
                ).fetchone()
                if existing is not None:
                    if tuple(existing) != expected:
                        raise LifecycleContractError(
                            "event identity was reused with conflicting content"
                        )
                    connection.execute("COMMIT")
                    return False

                latest = connection.execute(
                    "SELECT MAX(source_sequence) FROM lifecycle_events WHERE source=? AND entity_id=?",
                    (event.source, event.entity_id),
                ).fetchone()[0]
                expected_sequence = 1 if latest is None else latest + 1
                if event.source_sequence != expected_sequence:
                    raise LifecycleContractError(
                        f"out-of-order source sequence: expected {expected_sequence}"
                    )
                connection.execute(
                    """
                    INSERT INTO lifecycle_events (
                        event_id, event_type, source, entity_id, source_event_id,
                        source_sequence, occurred_at, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        *expected,
                        created_at,
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO lifecycle_deliveries(event_id, recipient_id, status)
                    VALUES (?, ?, 'pending')
                    """,
                    [(event.event_id, recipient_id) for recipient_id in recipient_ids],
                )
                connection.execute("COMMIT")
                return True
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def _claim_due(
        self, now: float, batch_size: int
    ) -> tuple[list[tuple[LifecycleEvent, str, str, int]], int]:
        claimed: list[tuple[LifecycleEvent, str, str, int]] = []
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                recovered = connection.execute(
                    """
                    UPDATE lifecycle_deliveries
                    SET status='uncertain', lease_token=NULL, lease_until=NULL,
                        last_error='delivery lease expired; outcome requires operator review'
                    WHERE status='inflight' AND lease_until <= ?
                    """,
                    (now,),
                ).rowcount
                rows = connection.execute(
                    """
                    SELECT e.*, d.recipient_id, d.attempts
                    FROM lifecycle_deliveries AS d
                    JOIN lifecycle_events AS e ON e.event_id=d.event_id
                    WHERE d.status IN ('pending','retry') AND d.next_attempt_at <= ?
                      AND NOT EXISTS (
                        SELECT 1
                        FROM lifecycle_events AS earlier
                        JOIN lifecycle_deliveries AS prior
                          ON prior.event_id=earlier.event_id
                        WHERE earlier.source=e.source
                          AND earlier.entity_id=e.entity_id
                          AND earlier.source_sequence < e.source_sequence
                          AND prior.status != 'delivered'
                      )
                    ORDER BY e.created_at, e.source_sequence, d.recipient_id
                    LIMIT ?
                    """,
                    (now, batch_size),
                ).fetchall()
                for row in rows:
                    token = secrets.token_hex(16)
                    updated = connection.execute(
                        """
                        UPDATE lifecycle_deliveries
                        SET status='inflight', attempts=attempts+1,
                            lease_token=?, lease_until=?
                        WHERE event_id=? AND recipient_id=? AND status IN ('pending','retry')
                        """,
                        (token, now + _LEASE_SECONDS, row["event_id"], row["recipient_id"]),
                    ).rowcount
                    if updated:
                        event = LifecycleEvent(
                            event_id=row["event_id"],
                            event_type=row["event_type"],
                            source=row["source"],
                            entity_id=row["entity_id"],
                            source_event_id=row["source_event_id"],
                            source_sequence=row["source_sequence"],
                            occurred_at=row["occurred_at"],
                            payload_json=row["payload_json"],
                        )
                        claimed.append((event, row["recipient_id"], token, row["attempts"] + 1))
                connection.execute("COMMIT")
                return claimed, recovered
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def _finish(
        self,
        event_id: str,
        recipient_id: str,
        token: str,
        *,
        outcome: str,
        now: float,
        error: str | None = None,
    ) -> str:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """
                    SELECT attempts FROM lifecycle_deliveries
                    WHERE event_id=? AND recipient_id=? AND status='inflight' AND lease_token=?
                    """,
                    (event_id, recipient_id, token),
                ).fetchone()
                if row is None:
                    connection.execute("COMMIT")
                    return "uncertain"

                if outcome == "delivered":
                    status, next_attempt = "delivered", 0
                elif outcome == "uncertain":
                    status, next_attempt = "uncertain", 0
                elif row["attempts"] >= _MAX_ATTEMPTS:
                    status, next_attempt = "dead", 0
                else:
                    status = "retry"
                    delay = _RETRY_DELAYS_SECONDS[
                        min(row["attempts"] - 1, len(_RETRY_DELAYS_SECONDS) - 1)
                    ]
                    next_attempt = now + delay
                connection.execute(
                    """
                    UPDATE lifecycle_deliveries
                    SET status=?, next_attempt_at=?, lease_token=NULL, lease_until=NULL, last_error=?
                    WHERE event_id=? AND recipient_id=? AND lease_token=?
                    """,
                    (
                        status,
                        next_attempt,
                        (error or "")[:300] or None,
                        event_id,
                        recipient_id,
                        token,
                    ),
                )
                connection.execute("COMMIT")
                return status
            except Exception:
                connection.execute("ROLLBACK")
                raise

    async def dispatch_due(
        self,
        *,
        sender: LifecycleSender,
        now: datetime | None = None,
        batch_size: int = 50,
    ) -> dict[str, Any]:
        """Send due recipients independently; ambiguous outcomes are quarantined, never retried."""
        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or not 1 <= batch_size <= _MAX_RECIPIENTS
        ):
            raise LifecycleContractError("batch_size must be between 1 and 500")
        instant = now or datetime.now(UTC)
        now_epoch = _epoch(instant)
        claimed, recovered = await asyncio.to_thread(self._claim_due, now_epoch, batch_size)
        results: list[dict[str, Any]] = []
        for event, recipient, token, attempt in claimed:
            try:
                confirmed = await sender(recipient_id=int(recipient), event=event)
            except Exception as exc:  # noqa: BLE001
                # A transport exception cannot prove whether Discord accepted the DM.
                outcome = "uncertain"
                error = f"{type(exc).__name__}: {str(exc)[:240]}"
            else:
                if confirmed is True:
                    outcome, error = "delivered", None
                elif confirmed is False:
                    outcome, error = "not_delivered", "sender confirmed non-delivery"
                else:
                    outcome, error = "uncertain", "sender returned a non-boolean acknowledgement"
            status = await asyncio.to_thread(
                self._finish,
                event.event_id,
                recipient,
                token,
                outcome=outcome,
                now=now_epoch,
                error=error,
            )
            results.append(
                {
                    "event_id": event.event_id,
                    "recipient_id": int(recipient),
                    "status": status,
                    "attempt": attempt,
                }
            )
        return {
            "attempted": len(results),
            "delivered": sum(result["status"] == "delivered" for result in results),
            "retry": sum(result["status"] == "retry" for result in results),
            "uncertain": sum(result["status"] == "uncertain" for result in results),
            "dead": sum(result["status"] == "dead" for result in results),
            "recovered_expired_leases": recovered,
            "results": results,
            "delivery_guarantee": "recipient-scoped at-least-once only for confirmed non-delivery; ambiguous outcomes require review",
            "execution_authority": False,
            "paper_entry_authority": False,
            "live_capital_allowed": False,
        }

    def delivery_states(self, event_id: str) -> dict[int, dict[str, Any]]:
        """Read-only recipient status; payload and message text are never exposed."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT recipient_id, status, attempts, next_attempt_at, last_error
                FROM lifecycle_deliveries WHERE event_id=? ORDER BY CAST(recipient_id AS INTEGER)
                """,
                (event_id,),
            ).fetchall()
        return {
            int(row["recipient_id"]): {
                "status": row["status"],
                "attempts": row["attempts"],
                "next_attempt_at": row["next_attempt_at"],
                "last_error": row["last_error"],
            }
            for row in rows
        }
