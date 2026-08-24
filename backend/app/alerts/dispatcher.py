"""Alert dispatcher — routes decisions to Discord (and future channels)."""

from __future__ import annotations

from typing import Any, Optional

from app.alerts.discord import send_discord_alert
from app.core.logging import get_logger

logger = get_logger("dispatcher")


async def dispatch_alert(
    *args: Any,
    symbol: str = "",
    decision: Any = None,
    price: Optional[float] = None,
    ticker: Any = None,
    candles: Any = None,
    **kwargs: Any,
) -> None:
    """
    Flexible entry used by scanner / trackers.

    Supports:
      await dispatch_alert(decision)
      await dispatch_alert(symbol=..., decision=..., price=...)
    """
    if args:
        first = args[0]
        if decision is None and not isinstance(first, (str, bytes, int, float)):
            decision = first
        elif not symbol and isinstance(first, str):
            symbol = first

    if decision is not None:
        symbol = symbol or str(getattr(decision, "symbol", "") or "")
        if price is None:
            try:
                price = float(getattr(decision, "price", None) or 0) or None
            except (TypeError, ValueError):
                price = None
        if price is None and ticker is not None:
            try:
                price = float(getattr(ticker, "price", 0) or 0) or None
            except (TypeError, ValueError):
                price = None

    try:
        await send_discord_alert(
            decision=decision,
            symbol=symbol,
            price=price,
            **{k: v for k, v in kwargs.items() if k in ("title", "description", "severity", "embed")},
        )
    except Exception as e:
        logger.warning("dispatch_alert failed", symbol=symbol, error=str(e))
        # Last resort positional embed/decision
        try:
            if decision is not None:
                await send_discord_alert(decision)
        except Exception as e2:
            logger.error("dispatch_alert fallback failed", error=str(e2))