from __future__ import annotations

from typing import Dict

from app.trading_core.live_shadow_hooks import mirror_marks_from_legacy, mirror_open_from_legacy


def mirror_price_map(price_map: Dict[str, float]) -> None:
    try:
        mirror_marks_from_legacy(price_map)
    except Exception:
        pass


def mirror_legacy_trade(
    *,
    trade_id: str,
    symbol: str,
    side: str,
    price: float,
    stop: float,
    setup_rr: float,
    risk_usd: float,
) -> None:
    try:
        mirror_open_from_legacy(
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            price=price,
            stop=stop,
            setup_rr=setup_rr,
            risk_usd=risk_usd,
        )
    except Exception:
        pass
