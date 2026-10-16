from __future__ import annotations

import json
import os
import uuid
import threading
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
        self._append_lock = threading.RLock()
        self._indexed_stamp = None
        self._by_id = {}
        self._sequences = {}

    def _stamp(self):
        try:
            stat = self.path.stat()
            return (stat.st_size, stat.st_mtime_ns, stat.st_ino)
        except FileNotFoundError:
            return None

    def _index(self, events):
        self._by_id = {event.event_id: event for event in events}
        self._sequences = {}
        for event in events:
            self._sequences[event.trade_id] = event.sequence
        self._indexed_stamp = self._stamp()

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
        with self._append_lock:
            events = [TradingEvent.from_dict(r) for r in self._read_rows()]
            self._validate_sequences(events)
            self._index(events)
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
        with self._append_lock:
            # Revalidate if another writer changed/replaced the file. Our own durable
            # appends update the index, avoiding a full history replay for every mark.
            if self._indexed_stamp != self._stamp() or not self._by_id:
                self.load()
            eid = event_id or uuid.uuid4().hex
            if eid in self._by_id:
                return self._by_id[eid]
            sequence = self._sequences.get(trade_id, 0) + 1
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
            self._by_id[event.event_id] = event
            self._sequences[trade_id] = sequence
            self._indexed_stamp = self._stamp()
            return event
