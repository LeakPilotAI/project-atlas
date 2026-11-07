from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional

from .event_store import JsonlEventStore
from .events import TradingEventType, position_to_payload
from .models import MarketQuote, PaperExecutionConfig, PaperPosition, TradeIntent
from .paper_engine import PaperEngine
from .position_book import PositionBook


class PersistentPaperRuntime:
    """Durable V4 paper runtime backed only by append-only trading events."""

    def __init__(self, path: Path, config: PaperExecutionConfig | None = None) -> None:
        self.store = JsonlEventStore(path)
        self.engine = PaperEngine(config)
        self.book = PositionBook.from_events(self.store.load())

    def recover(self) -> int:
        self.book = PositionBook.from_events(self.store.load())
        return len(self.book.list_open())

    def open(self, intent: TradeIntent, quote: MarketQuote) -> PaperPosition:
        if self.book.get_open(intent.trade_id) is not None:
            return self.book.get_open(intent.trade_id)  # type: ignore[return-value]
        if self.book.get_closed(intent.trade_id) is not None:
            raise ValueError("trade_id is already closed")
        position = self.engine.open(intent, quote)
        event = self.store.append(
            event_type=TradingEventType.POSITION_OPENED,
            trade_id=position.trade_id,
            symbol=position.symbol,
            timestamp=quote.timestamp.isoformat(),
            payload={"position": position_to_payload(position)},
        )
        self.book.apply(event)
        return position

    def mark(self, trade_id: str, quote: MarketQuote) -> PaperPosition:
        current = self.book.get_open(trade_id)
        if current is None:
            if self.book.get_closed(trade_id) is not None:
                return self.book.get_closed(trade_id)  # type: ignore[return-value]
            raise KeyError(f"unknown open trade {trade_id}")
        before_stop = current.working_stop
        step = self.engine.mark(current, quote)
        updated = step.position
        if updated.status.value == "CLOSED":
            event_type = TradingEventType.POSITION_CLOSED
        elif abs(updated.working_stop - before_stop) > 1e-15:
            event_type = TradingEventType.STOP_MOVED
        else:
            event_type = TradingEventType.POSITION_MARKED
        event = self.store.append(
            event_type=event_type,
            trade_id=updated.trade_id,
            symbol=updated.symbol,
            timestamp=quote.timestamp.isoformat(),
            payload={"position": position_to_payload(updated), "engine_event": step.event},
        )
        self.book.apply(event)
        return updated

    def mark_many(self, quotes: Dict[str, MarketQuote]) -> Dict[str, PaperPosition]:
        out: Dict[str, PaperPosition] = {}
        for position in list(self.book.list_open()):
            quote = quotes.get(position.symbol)
            if quote is None:
                continue
            out[position.trade_id] = self.mark(position.trade_id, quote)
        return out
