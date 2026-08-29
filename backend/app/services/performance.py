"""Performance HTTP endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter
from sqlalchemy import select

from app.db.session import async_session
from app.models.opportunity import Opportunity
from app.services.performance_service import get_performance_report

router = APIRouter(prefix="/api", tags=["performance"])


def _dashboard_perf(payload: dict[str, Any]) -> dict[str, Any]:
    overall = payload.get("overall") if isinstance(payload.get("overall"), dict) else {}
    payload["total_closed"] = int(payload.get("total_trades") or 0)
    payload["win_rate"] = float(overall.get("win_rate") or 0)
    payload["avg_pnl"] = float(overall.get("avg_pnl_pct") or 0)
    payload["best_trade"] = float(overall.get("max_win_pct") or 0)
    payload["worst_trade"] = float(overall.get("max_loss_pct") or 0)
    return payload


@router.get("/performance")
async def performance():
    payload = await get_performance_report()
    return _dashboard_perf(payload)


@router.get("/opportunities")
async def opportunities() -> list[dict[str, Any]]:
    rows: list[Any] = []
    try:
        async with async_session() as session:
            q = select(Opportunity).order_by(Opportunity.opened_at.desc()).limit(50)
            result = await session.execute(q)
            rows = list(result.scalars().all())
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for r in rows:
        fired: Optional[str] = None
        opened = getattr(r, "opened_at", None)
        if isinstance(opened, datetime):
            fired = opened.isoformat()
        elif opened:
            fired = str(opened)
        out.append(
            {
                "symbol": r.symbol,
                "status": r.status,
                "recommendation": r.bias,
                "confidence": r.confidence,
                "entry_price": r.entry_price if r.entry_price is not None else 0,
                "fired_at": fired,
            }
        )
    return out
