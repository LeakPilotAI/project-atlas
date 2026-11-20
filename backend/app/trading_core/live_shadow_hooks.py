from __future__ import annotations

from typing import Any, Dict

from .shadow_coordinator import v4_shadow_coordinator


def mirror_open_from_legacy(
    *,
    trade_id: str,
    symbol: str,
    side: str,
    price: float,
    stop: float,
    setup_rr: float,
    risk_usd: float,
) -> bool:
    """Best-effort mirror of an accepted legacy PAPER open into V4 shadow.

    Failure is intentionally contained so V4 can never block or alter the legacy path.
    """
    row: Dict[str, Any] = {
        "trade_id": trade_id,
        "symbol": symbol,
        "side": side,
        "signal_price": price,
        "stop_price": stop,
        "setup_rr": setup_rr,
        "risk_usd": risk_usd,
    }
    return v4_shadow_coordinator.mirror_legacy_open(row, trade_id=trade_id, price=price)


def mirror_marks_from_legacy(price_map: Dict[str, float]) -> int:
    """Best-effort live mark fan-out to V4 shadow positions."""
    return v4_shadow_coordinator.mark_prices(price_map)


def shadow_snapshot() -> Dict[str, Any]:
    return v4_shadow_coordinator.snapshot()
