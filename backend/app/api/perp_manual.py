from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from app.services.perp_manual_service import perp_manual_service
from app.trading_core.perp_board import build_perp_board

router = APIRouter(prefix="/api/perps", tags=["manual-perps"])


@router.get("/manual")
async def manual_perps() -> Dict[str, Any]:
    return perp_manual_service.snapshot()


@router.get("/manual/board")
async def manual_perp_board(limit: int = Query(8, ge=1, le=25)) -> Dict[str, Any]:
    snapshot = perp_manual_service.snapshot()
    setups = list(snapshot.get("setups") or [])
    board = build_perp_board(setups, limit=limit)
    return {
        "source": "hyperliquid",
        "mode": "MANUAL_ONLY",
        "updated_at": snapshot.get("updated_at"),
        "board": board,
        "count": len(board),
        "alert_count": sum(1 for row in board if bool(row.get("alert_eligible"))),
        "note": "Manual guidance only. Atlas does not place Hyperliquid orders.",
    }


@router.post("/manual/alerts/{setup_key}/ack")
async def acknowledge_manual_perp_alert(setup_key: str) -> Dict[str, Any]:
    if not perp_manual_service.acknowledge_alert(setup_key):
        raise HTTPException(status_code=404, detail="setup alert not found")
    return {"ok": True, "setup_key": setup_key, "status": "COOLDOWN_ACTIVE"}


@router.post("/manual/plan")
async def create_manual_plan(
    symbol: str = Query(..., min_length=1),
    side: str = Query(..., pattern="^(?i:long|short)$"),
    reference_price: float = Query(..., gt=0),
    risk_pct: float = Query(1.0, gt=0, le=10),
    layer_spacing_pct: float = Query(0.35, gt=0, le=5),
    tp1_r: float = Query(1.5, gt=0, le=10),
    tp2_r: float = Query(2.5, gt=0, le=20),
) -> Dict[str, Any]:
    try:
        return perp_manual_service.create_plan(
            symbol=symbol,
            side=side,
            reference_price=reference_price,
            risk_pct=risk_pct,
            layer_spacing_pct=layer_spacing_pct,
            tp1_r=tp1_r,
            tp2_r=tp2_r,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
