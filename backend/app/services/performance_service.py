"""Load paper trades from DB and build performance reports."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select

from app.analytics.performance import format_report_text, report_to_dict, summarize_trades
from app.core.logging import get_logger
from app.db.session import async_session

logger = get_logger("performance_service")


async def _load_paper_trades(limit: int = 2000) -> list[dict[str, Any]]:
    """Best-effort load from PaperTrade model if present."""
    trades: list[dict[str, Any]] = []
    try:
        from app.models.paper_trade import PaperTrade
    except Exception:
        logger.warning("PaperTrade model not importable")
        return trades

    try:
        async with async_session() as session:
            q = select(PaperTrade).order_by(PaperTrade.id.desc()).limit(limit)
            result = await session.execute(q)
            rows = result.scalars().all()
            for r in rows:
                # Prefer closed / resolved only
                status = str(getattr(r, "status", "") or getattr(r, "state", "") or "").lower()
                pnl = getattr(r, "pnl_pct", None)
                if pnl is None:
                    pnl = getattr(r, "pnl_percent", None)
                if pnl is None and hasattr(r, "pnl"):
                    pnl = getattr(r, "pnl")
                if status and status not in ("closed", "resolved", "done", "complete", "tp", "sl", "stopped"):
                    # still include if pnl is set
                    if pnl is None:
                        continue
                lane = getattr(r, "lane", None) or getattr(r, "source", None) or "unknown"
                trades.append(
                    {
                        "symbol": getattr(r, "symbol", None) or getattr(r, "market_symbol", "?"),
                        "pnl_pct": pnl if pnl is not None else 0.0,
                        "lane": lane,
                        "status": status,
                    }
                )
    except Exception as e:
        logger.warning("Failed loading paper trades", error=str(e))
    return trades


async def get_performance_report() -> dict[str, Any]:
    trades = await _load_paper_trades()
    report = summarize_trades(trades)
    payload = report_to_dict(report)
    payload["text"] = format_report_text(report)
    return payload