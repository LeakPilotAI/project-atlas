from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .events import TradingEvent, TradingEventType, utc_now_iso


class EventStoreCorruption(RuntimeError):
    pass


class JsonlEventStore:
    """Crash-safe append-only event store for Atlas V4 paper execution."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_rows(self) -> List[dict]:
        rows: List[dict] = []
        if not self.path.exists():
            return rows
        with self.path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError as exc:
                    if line_no == sum(1 for _ in self.path.open("r", encoding="utf-8")):
                        break
                    raise EventStoreCorruption(f"malformed event line {line_no}") from exc
                if not isinstance(parsed, dict):
                    raise EventStoreCorruption(f"non-object event line {line_no}")
                rows.append(parsed)
        return rows

    def load(self) -> List[TradingEvent]:
        events = [TradingEvent.from_dict(r) for r in self._read_rows()]
        self._validate_sequences(events)
        return events

    @staticmethod
    def _validate_sequences(events: Iterable[TradingEvent]) -> None:
        last: Dict[str, int] = {}
        seen_ids = set()
        for event in events:
            if event.event_id in seen_ids:
                raise EventStoreCorruption(f"duplicate event_id {event.event_id}")
            seen_ids.add(event.event_id)
            expected = last.get(event.trade_id, 0) + 1
            if event.sequence != expected:
                raise EventStoreCorruption(
                    f"sequence gap for {event.trade_id}: expected {expected}, got {event.sequence}"
                )
            last[event.trade_id] = event.sequence

    def events_for_trade(self, trade_id: str) -> List[TradingEvent]:
        return [e for e in self.load() if e.trade_id == trade_id]

    def next_sequence(self, trade_id: str) -> int:
        seq = 0
        for event in self.load():
            if event.trade_id == trade_id:
                seq = event.sequence
        return seq + 1

    def append(
        self,
        *,
        event_type: TradingEventType,
        trade_id: str,
        symbol: str,
        payload: dict,
        timestamp: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> TradingEvent:
        existing = self.load()
        eid = event_id or uuid.uuid4().hex
        if any(e.event_id == eid for e in existing):
            return next(e for e in existing if e.event_id == eid)
        sequence = 1 + max((e.sequence for e in existing if e.trade_id == trade_id), default=0)
        event = TradingEvent(
            event_id=eid,
            event_type=event_type,
            trade_id=trade_id,
            symbol=symbol.upper(),
            timestamp=timestamp or utc_now_iso(),
            sequence=sequence,
            payload=dict(payload),
        )
        line = json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        return event
