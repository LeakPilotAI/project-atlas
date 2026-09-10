from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .events import TradingEvent, TradingEventType, position_from_payload
from .models import PaperPosition, PositionStatus


@dataclass(frozen=True)
class BookSnapshot:
    open_positions: Dict[str, PaperPosition]
    closed_positions: Dict[str, PaperPosition]
    last_sequence: Dict[str, int]


class PositionBook:
    """Pure event projection. No I/O and no hidden mutable source of truth."""

    def __init__(self) -> None:
        self._open: Dict[str, PaperPosition] = {}
        self._closed: Dict[str, PaperPosition] = {}
        self._last_sequence: Dict[str, int] = {}

    def apply(self, event: TradingEvent) -> None:
        expected = self._last_sequence.get(event.trade_id, 0) + 1
        if event.sequence != expected:
            raise ValueError(
                f"sequence mismatch for {event.trade_id}: expected {expected}, got {event.sequence}"
            )

        if event.event_type in {
            TradingEventType.POSITION_OPENED,
            TradingEventType.POSITION_MARKED,
            TradingEventType.STOP_MOVED,
            TradingEventType.RECOVERY_RESTORED,
        }:
            pos = position_from_payload(event.payload["position"])
            if pos.status is PositionStatus.CLOSED:
                raise ValueError("non-close event cannot project a CLOSED position")
            self._open[event.trade_id] = pos
            self._closed.pop(event.trade_id, None)

        elif event.event_type is TradingEventType.POSITION_CLOSED:
            pos = position_from_payload(event.payload["position"])
            if pos.status is not PositionStatus.CLOSED:
                raise ValueError("POSITION_CLOSED requires CLOSED position payload")
            self._open.pop(event.trade_id, None)
            self._closed[event.trade_id] = pos

        elif event.event_type in {
            TradingEventType.SIGNAL_CREATED,
            TradingEventType.INTENT_APPROVED,
            TradingEventType.DATA_STALE,
            TradingEventType.EXECUTION_REJECTED,
        }:
            pass
        else:
            raise ValueError(f"unsupported event type {event.event_type}")

        self._last_sequence[event.trade_id] = event.sequence

    def replay(self, events: Iterable[TradingEvent]) -> "PositionBook":
        for event in events:
            self.apply(event)
        return self

    def get_open(self, trade_id: str) -> Optional[PaperPosition]:
        return self._open.get(trade_id)

    def get_closed(self, trade_id: str) -> Optional[PaperPosition]:
        return self._closed.get(trade_id)

    def list_open(self) -> List[PaperPosition]:
        return list(self._open.values())

    def list_closed(self) -> List[PaperPosition]:
        return list(self._closed.values())

    def snapshot(self) -> BookSnapshot:
        return BookSnapshot(
            open_positions=dict(self._open),
            closed_positions=dict(self._closed),
            last_sequence=dict(self._last_sequence),
        )

    @classmethod
    def from_events(cls, events: Iterable[TradingEvent]) -> "PositionBook":
        return cls().replay(events)
