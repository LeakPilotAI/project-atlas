"""Read-only stable lifecycle identities derived from the append-only PAPER journal.

The adapter does not modify journal records. It fails closed when the byte stream
cannot prove complete ordering, and is intentionally not connected to delivery.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.discord_lifecycle_outbox import (
    LifecycleContractError,
    LifecycleEvent,
    make_lifecycle_event,
)

_LIFECYCLE_FIELDS = (
    "event",
    "trade_id",
    "trade_type",
    "symbol",
    "side",
    "timestamp",
    "signal_timestamp",
    "entry_timestamp",
    "exit_timestamp",
    "status",
    "result",
    "exit_reason",
    "interrupted",
    "actual_entry_price",
    "actual_exit_price",
    "mark",
    "unrealized_r",
    "mfe_r",
    "mae_r",
    "working_stop",
    "working_target",
)


@dataclass(frozen=True)
class PaperJournalIdentityBatch:
    events: tuple[LifecycleEvent, ...]
    reliable: bool
    malformed_lines: int
    invalid_lifecycle_rows: int
    has_partial_tail: bool
    source_fingerprint: str | None
    error: str | None = None


def _event_timestamp(row: dict[str, Any]) -> datetime:
    event = str(row.get("event") or "").lower()
    candidates = (
        ("entry_timestamp", "signal_timestamp", "timestamp")
        if event == "open"
        else ("exit_timestamp", "timestamp", "entry_timestamp")
        if event == "close"
        else ("timestamp",)
    )
    for key in candidates:
        raw = row.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            parsed = datetime.fromisoformat(raw.strip())
        except ValueError:
            continue
        if parsed.tzinfo is not None and parsed.utcoffset() is not None:
            return parsed.astimezone(UTC)
    raise LifecycleContractError("lifecycle journal row has no valid timezone-aware timestamp")


def _lifecycle_type(row: dict[str, Any]) -> str | None:
    event = str(row.get("event") or "").lower()
    if event == "open":
        return "PAPER_ENTRY"
    if event == "mark":
        return "PAPER_MARK"
    if event != "close":
        return None
    if row.get("interrupted") is True or str(row.get("result") or "").upper() == "INTERRUPTED":
        return "PAPER_INTERRUPTED"
    reason = str(row.get("exit_reason") or "").upper()
    result = str(row.get("result") or "").upper()
    if result == "STOP" or reason == "STOP" or reason.endswith("_STOP"):
        return "PAPER_RISK_STOP"
    return "PAPER_CLOSE"


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row[key]
        for key in _LIFECYCLE_FIELDS
        if key in row and isinstance(row[key], (str, int, float, bool, type(None)))
    }


def read_paper_journal_identities(path: Path) -> PaperJournalIdentityBatch:
    """Derive event identities and contiguous per-trade sequences from complete JSONL rows.

    A source-event ID combines the hash of the immutable first complete record with
    that record's byte offset. This distinguishes identical repeated rows while
    remaining stable across rescans and process restarts. The source journal must
    remain append-only; rewrite/rotation changes ordering assumptions and is not
    automatically reconciled with an existing outbox.
    """
    journal_path = Path(path)
    if not journal_path.exists():
        return PaperJournalIdentityBatch((), True, 0, 0, False, None)

    events: list[LifecycleEvent] = []
    sequence_by_trade: dict[str, int] = {}
    malformed_lines = 0
    invalid_lifecycle_rows = 0
    has_partial_tail = False
    first_record_digest: str | None = None
    offset = 0
    failure: str | None = None

    try:
        with journal_path.open("rb") as handle:
            while raw_line := handle.readline():
                line_offset = offset
                offset += len(raw_line)
                if not raw_line.endswith(b"\n"):
                    has_partial_tail = True
                    break
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    decoded = json.loads(stripped.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    malformed_lines += 1
                    continue
                if not isinstance(decoded, dict):
                    malformed_lines += 1
                    continue

                if first_record_digest is None:
                    first_record_digest = hashlib.sha256(stripped).hexdigest()[:24]
                lifecycle_type = _lifecycle_type(decoded)
                if lifecycle_type is None:
                    continue
                if str(decoded.get("trade_type") or "PAPER").upper() == "TEST":
                    continue
                trade_id = decoded.get("trade_id")
                if not isinstance(trade_id, str) or not trade_id.strip():
                    invalid_lifecycle_rows += 1
                    continue
                try:
                    occurred_at = _event_timestamp(decoded)
                    sequence = sequence_by_trade.get(trade_id, 0) + 1
                    source_event_id = f"paper-journal:{first_record_digest}:{line_offset}"
                    public_payload = _payload(decoded)
                    lifecycle_event = make_lifecycle_event(
                        event_type=lifecycle_type,
                        source="paper_journal",
                        entity_id=trade_id,
                        source_event_id=source_event_id,
                        source_sequence=sequence,
                        occurred_at=occurred_at,
                        payload=public_payload,
                    )
                except (LifecycleContractError, TypeError, ValueError) as exc:
                    invalid_lifecycle_rows += 1
                    failure = f"{type(exc).__name__}: {str(exc)[:180]}"
                    continue
                sequence_by_trade[trade_id] = sequence
                events.append(lifecycle_event)
    except OSError as exc:
        return PaperJournalIdentityBatch(
            (),
            False,
            malformed_lines,
            invalid_lifecycle_rows,
            has_partial_tail,
            first_record_digest,
            f"{type(exc).__name__}: {str(exc)[:180]}",
        )

    reliable = not (malformed_lines or invalid_lifecycle_rows or has_partial_tail)
    return PaperJournalIdentityBatch(
        tuple(events) if reliable else (),
        reliable,
        malformed_lines,
        invalid_lifecycle_rows,
        has_partial_tail,
        first_record_digest,
        failure or ("journal contains malformed or incomplete data" if not reliable else None),
    )
