from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .models import MarketQuote, PaperExecutionConfig, PaperPosition, Side, TradeIntent
from .paper_engine import EngineStep, PaperEngine


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass(frozen=True)
class LegacySignalAdapter:
    """Translate the current Atlas signal shape into an immutable V4 TradeIntent.

    This adapter deliberately does not perform networking, persistence, or strategy
    decisions. It is a compatibility boundary while the legacy coach still runs.
    """

    strategy_version: str = "atlas-v4-shadow-adapter-1"

    def to_intent(self, signal: Dict[str, Any]) -> TradeIntent:
        side = Side(str(signal.get("side") or "").upper())
        symbol = str(signal.get("symbol") or signal.get("coin") or "").upper()
        signal_price = float(signal.get("signal_price") or signal.get("entry") or signal.get("price"))
        stop_price = float(signal.get("stop_price") or signal.get("stop"))
        target_r = float(signal.get("target_r") or signal.get("setup_rr") or signal.get("rr") or 1.8)
        risk_usd = float(signal.get("risk_usd") or signal.get("risk_dollars") or 1.0)
        trade_id = str(signal.get("trade_id") or signal.get("candidate_id") or "").strip()
        if not trade_id:
            raise ValueError("legacy signal requires trade_id or candidate_id")
        ts = _parse_ts(signal.get("signal_timestamp") or signal.get("timestamp") or datetime.now(timezone.utc))
        return TradeIntent(
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            signal_price=signal_price,
            stop_price=stop_price,
            target_r=target_r,
            risk_usd=risk_usd,
            signal_timestamp=ts,
            strategy_version=self.strategy_version,
        )


class V4ShadowRuntime:
    """In-memory shadow runtime around the pure deterministic paper engine.

    No journal writes and no production side effects. This exists to compare V4
    behavior with the legacy paper path before any cutover.
    """

    def __init__(self, config: Optional[PaperExecutionConfig] = None) -> None:
        self.engine = PaperEngine(config)
        self.positions: Dict[str, PaperPosition] = {}

    def open_from_legacy(self, signal: Dict[str, Any], quote_price: float, quote_timestamp: Any) -> PaperPosition:
        intent = LegacySignalAdapter().to_intent(signal)
        if intent.trade_id in self.positions and self.positions[intent.trade_id].is_open:
            return self.positions[intent.trade_id]
        quote = MarketQuote(symbol=intent.symbol, price=float(quote_price), timestamp=_parse_ts(quote_timestamp))
        pos = self.engine.open(intent, quote)
        self.positions[pos.trade_id] = pos
        return pos

    def mark(self, trade_id: str, price: float, timestamp: Any) -> EngineStep:
        pos = self.positions[trade_id]
        quote = MarketQuote(symbol=pos.symbol, price=float(price), timestamp=_parse_ts(timestamp))
        step = self.engine.mark(pos, quote)
        self.positions[trade_id] = step.position
        return step

    def get(self, trade_id: str) -> Optional[PaperPosition]:
        return self.positions.get(trade_id)
