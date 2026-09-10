from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from app.services.perp_manual_service import perp_manual_service

router = APIRouter(prefix="/api/perps", tags=["manual-perps"])


@router.get("/manual")
async def manual_perps() -> Dict[str, Any]:
    return perp_manual_service.snapshot()


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
