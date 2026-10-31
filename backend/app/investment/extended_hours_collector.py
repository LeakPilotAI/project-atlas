"""Isolated, research-only extended-hours quote collector."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time as clock_time
from contextlib import contextmanager
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.investment.extended_hours_integrity import JournalCommitment, JournalIntegrityError
from app.investment.market_hours import session_bounds

ET = ZoneInfo("America/New_York")
VALID_SESSIONS = frozenset({"PRE_MARKET", "POST_MARKET"})


def extended_session(now: datetime) -> str | None:
    if now.tzinfo is None:
        return None
    local = now.astimezone(ET)
    bounds = session_bounds(now)
    if bounds is None:
        return None

    opening, closing = bounds
    current = now.astimezone(UTC)
    clock = local.time()

    if time(4, 0) <= clock and current < opening:
        return "PRE_MARKET"

    if closing <= current and clock < time(20, 0):
        return "POST_MARKET"

    return None


def validated_observation(
    symbol: str,
    quote: dict[str, Any],
    now: datetime,
    *,
    max_age_seconds: float = 900.0,
) -> dict[str, Any] | None:
    session = extended_session(now)
    if session is None or now.tzinfo is None:
        return None

    try:
        raw_ts = quote.get("effective_timestamp")
        ts = datetime.fromisoformat(str(raw_ts))
        if ts.tzinfo is None:
            return None
        ts = ts.astimezone(UTC)

        price = float(quote.get("price"))
        age = (now.astimezone(UTC) - ts).total_seconds()

        if not (0 <= age <= max_age_seconds):
            return None
        if isinstance(quote.get("price"), bool) or not (0 < price < float("inf")):
            return None
        if not str(quote.get("source") or "").strip():
            return None
        if extended_session(ts) != session:
            return None
        if quote.get("quality") not in {"LIVE", "FRESH"}:
            return None

        return {
            "symbol": symbol.upper(),
            "price": price,
            "source": str(quote.get("source") or "UNKNOWN"),
            "session": session,
            "effective_timestamp": ts.isoformat(),
            "retrieved_at": now.astimezone(UTC).isoformat(),
            "age_sec": round(age, 3),
            "research_only": True,
        }
    except (TypeError, ValueError, OverflowError):
        return None


@contextmanager
def _exclusive_history_lock(path: Path, timeout_seconds: float = 3.0):
    """Bounded Windows cross-process lock; fail closed on contention."""
    if sys.platform != "win32":
        raise RuntimeError("Extended-hours locking requires Windows")

    import msvcrt

    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    deadline = clock_time.monotonic() + timeout_seconds

    with lock_path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)

        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()

        while True:
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError as exc:
                if clock_time.monotonic() >= deadline:
                    raise TimeoutError(
                        "Extended-hours history lock timed out"
                    ) from exc
                clock_time.sleep(0.05)

        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

class ExtendedHoursCollector:
    """No startup hooks, trading actions, or notification side effects."""

    def __init__(self, quote_service: Any, output_path: Path) -> None:
        self.quote_service = quote_service
        self.output_path = Path(output_path)
        self._lock = asyncio.Lock()
        self._closing = False
        self._collections: set[asyncio.Task] = set()
        self._seen: set[tuple[str, str]] = set()

    def _read_committed_keys(self) -> set[tuple[str, str]]:
        if not self.output_path.exists():
            return set()

        keys: set[tuple[str, str]] = set()
        with self.output_path.open("r", encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    raise ValueError(f"Empty history record at line {number}")
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Malformed history record at line {number}"
                    ) from exc

                if not isinstance(record, dict):
                    raise ValueError(f"Invalid history record at line {number}")  # noqa: TRY004 - stable corruption contract

                symbol = record.get("symbol")
                timestamp = record.get("effective_timestamp")
                if not isinstance(symbol, str) or not isinstance(timestamp, str):
                    raise ValueError(f"Incomplete history record at line {number}")  # noqa: TRY004 - stable corruption contract

                try:
                    parsed = datetime.fromisoformat(timestamp)
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid history timestamp at line {number}"
                    ) from exc

                if parsed.tzinfo is None:
                    raise ValueError(
                        f"Naive history timestamp at line {number}"
                    )
                try:
                    retrieved = datetime.fromisoformat(str(record.get("retrieved_at")))
                except ValueError as exc:
                    raise ValueError(f"Invalid history retrieval time at line {number}") from exc
                validated = validated_observation(
                    symbol, {**record, "quality": "FRESH"}, retrieved
                )
                if (not symbol or symbol != symbol.strip().upper()
                        or record.get("research_only") is not True
                        or validated is None or validated["session"] != record.get("session")):
                    raise ValueError(f"Invalid research history contract at line {number}")
                key = (symbol, parsed.astimezone(UTC).isoformat())
                if key in keys:
                    raise ValueError(f"Duplicate history identity at line {number}")
                keys.add(key)

        return keys

    def reopen(self) -> None:
        if self._collections:
            raise RuntimeError("Collector still owns unfinished work")
        self._closing = False

    async def shutdown(self, timeout: float = 20.0) -> None:
        self._closing = True
        tasks = list(self._collections)
        for task in tasks:
            task.cancel()
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=max(0.0, timeout))
            if pending:
                raise TimeoutError("Research commit/collection still owned; shutdown incomplete")

    async def collect_once(self, symbols: list[str], *, now: datetime | None = None):
        if self._closing:
            raise RuntimeError("Collector closed")
        task = asyncio.current_task()
        self._collections.add(task)
        try:
            return await self._collect_once(symbols, now=now)
        finally:
            self._collections.discard(task)

    async def _collect_once(
        self, symbols: list[str], *, now: datetime | None = None
    ) -> list[dict[str, Any]]:
        if extended_session(now or datetime.now(UTC)) is None:
            return []

        clean = sorted({
            str(symbol).strip().upper()
            for symbol in symbols
            if str(symbol).strip()
        })
        if not clean:
            return []

        quotes = await self.quote_service.get_many(clean)
        observed_now = now or datetime.now(UTC)

        async with self._lock:
            if self._closing:
                raise RuntimeError("Collector closed before commit")
            # File locking/replay/fsync must not block the API event loop. Drain
            # an in-flight commit on cancellation so graceful Stop cannot return
            # while this collector still has a writer touching the journal.
            commit = asyncio.create_task(asyncio.to_thread(
                self._commit_with_lock, clean, quotes, observed_now
            ))
            cancelled = False
            while not commit.done():
                try:
                    await asyncio.shield(commit)
                except asyncio.CancelledError:
                    cancelled = True
            result = commit.result()
            if cancelled:
                raise asyncio.CancelledError
            return result

    def _commit_with_lock(self, clean, quotes, now):
        with _exclusive_history_lock(self.output_path):
            return self._collect_committed(clean, quotes, now)

    def adopt_legacy_journal(self, *, expected_sha256: str) -> None:
        """Explicit offline migration only; caller must authorize and back up evidence.

        Never invoked by startup/collection. A hash attests only the operator's
        reviewed current file, not completeness before migration.
        """
        with _exclusive_history_lock(self.output_path):
            self._read_committed_keys()  # Validate schema before trusting legacy bytes.
            content = self.output_path.read_bytes()
            if content and not content.endswith(b"\n"):
                raise JournalIntegrityError("Legacy journal requires a complete line boundary")
            JournalCommitment(self.output_path).initialize(
                expected_legacy_sha256=expected_sha256
            )

    def _collect_committed(
        self, clean: list[str], quotes: dict[str, Any], now: datetime
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        witness = JournalCommitment(self.output_path)
        original = witness.verify()
        committed = self._read_committed_keys()
        prior = {
            (row["symbol"], datetime.fromisoformat(row["effective_timestamp"]).astimezone(UTC).isoformat()): row
            for row in (json.loads(line) for line in original.decode("utf-8").splitlines())
        }

        for symbol in clean:
            quote = quotes.get(symbol)
            if not isinstance(quote, dict):
                continue

            record = validated_observation(symbol, quote, now)
            if record is None:
                continue

            key = (symbol, record["effective_timestamp"])
            if key in committed:
                if any(prior[key].get(field) != record[field] for field in ("price", "source", "session")):
                    raise JournalIntegrityError("Conflicting observation identity; preserve original")
                continue

            records.append(record)

        if records:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            # Independent durable intent MUST precede the JSONL write. A crash
            # between files quarantines the pair rather than blessing tail loss.
            payload = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
            # Text append uses the Windows newline translation below.
            target = original + payload.replace("\n", os.linesep).encode("utf-8")
            witness.prepare(target)
            with self.output_path.open("a", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            witness.finish(target)

            self._seen.update(
                (record["symbol"], record["effective_timestamp"])
                for record in records
            )

        return records
