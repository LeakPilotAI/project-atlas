from __future__ import annotations

from typing import Dict

import structlog

from app.trading_core.live_shadow_hooks import mirror_marks_from_legacy, mirror_open_from_legacy

log = structlog.get_logger(__name__)


def on_paper_open(*, trade_id: str, symbol: str, side: str, entry: float, stop: float, setup_rr: float, risk_usd: float) -> None:
    try:
        mirror_open_from_legacy(
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            price=float(entry),
            stop=float(stop),
            setup_rr=float(setup_rr),
            risk_usd=float(risk_usd),
        )
    except Exception as e:
        log.debug("v4 shadow open observer failed", trade_id=trade_id, error=str(e)[:160])


def on_paper_mark(*, symbol: str, mark: float) -> None:
    try:
        mirror_marks_from_legacy({str(symbol).upper(): float(mark)})
    except Exception as e:
        log.debug("v4 shadow mark observer failed", symbol=symbol, error=str(e)[:160])
