from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from app.adapters.registry import registry

from app.services.perp_alert_delivery import perp_alert_delivery_service
from app.services.perp_manual_service import perp_manual_service
from app.services.perp_paper_observability import build_paper_observability
from app.services.perp_setup_paper_mirror import perp_setup_paper_mirror
from app.services.paper_risk_controls import paper_risk_controls
from app.services.paper_risk_window import utc_day_risk_snapshot
from app.services.paper_journal import paper_journal
from app.trading_core.perp_board import build_perp_board

router = APIRouter(prefix="/api/perps", tags=["manual-perps"])


@router.get("/paper-risk")
async def paper_risk_status() -> Dict[str, Any]:
    try:
        risk_window = await asyncio.to_thread(utc_day_risk_snapshot)
        session_net_r = float(risk_window.get("net_r") or 0.0)
    except Exception:
        risk_window = {
            "net_r": float(paper_risk_controls.session_net_r or 0.0),
            "window": "DURABLE_CONTROL_FALLBACK",
            "source": "PAPER_RISK_CONTROL_STORE",
        }
        session_net_r = float(risk_window["net_r"])
    return {
        **paper_risk_controls.snapshot(),
        "session_net_r": session_net_r,
        "session_net_r_source": str(risk_window.get("source") or "UNKNOWN"),
        "risk_window": risk_window,
        "mode": "PAPER_ONLY",
        "live_execution": False,
    }


@router.post("/paper-risk/kill-switch")
async def set_paper_kill_switch(enabled: bool = Query(...)) -> Dict[str, Any]:
    paper_risk_controls.kill_switch = bool(enabled)
    paper_risk_controls.save()
    return {
        "ok": True,
        **paper_risk_controls.snapshot(),
        "note": "PAPER only. Does not enable or disable real-money execution.",
    }


@router.get("/manual")
async def manual_perps() -> Dict[str, Any]:
    snapshot = perp_manual_service.snapshot()
    snapshot["alert_delivery"] = {
        "running": perp_alert_delivery_service.running,
        "last_result": dict(perp_alert_delivery_service.last_result),
        "last_error": perp_alert_delivery_service.last_error,
    }
    snapshot["auto_paper"] = {
        **(await asyncio.to_thread(perp_setup_paper_mirror.status)),
        "last_pass": dict(perp_alert_delivery_service.last_paper_result),
        "mode": "RESTING_L1_LIMIT_TOUCH",
        "live_execution": False,
        "observability": await asyncio.to_thread(build_paper_observability, snapshot.get("setups") or []),
    }
    return snapshot


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
        "entered_count": sum(1 for row in board if str(row.get("trade_status")) == "ENTERED"),
        "alert_delivery_running": perp_alert_delivery_service.running,
        "auto_paper": {
            **(await asyncio.to_thread(perp_setup_paper_mirror.status)),
            "observability": await asyncio.to_thread(build_paper_observability, setups),
        },
        "note": "Real Hyperliquid execution is manual-only. Each verified manual resting-L1 instruction is mirrored as a PAPER limit and fills only on an L1 touch/cross.",
    }


@router.get("/candles")
async def perp_candles(
    symbol: str = Query(..., min_length=1, max_length=32),
    interval: str = Query("5m"),
    lookback: int = Query(96, ge=24, le=240),
) -> Dict[str, Any]:
    """Read-only Hyperliquid OHLC history for the Perp cockpit chart."""
    allowed_intervals = {"1m", "5m", "15m", "1h", "4h"}
    interval = str(interval).strip()
    if interval not in allowed_intervals:
        raise HTTPException(status_code=400, detail="unsupported candle interval")

    clean_symbol = str(symbol).strip().upper()
    if not clean_symbol or not clean_symbol.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="invalid symbol")

    adapter = registry.get("hyperliquid")
    if adapter is None or not hasattr(adapter, "get_candles"):
        raise HTTPException(status_code=503, detail="Hyperliquid candle history unavailable")

    try:
        candles = await adapter.get_candles(
            clean_symbol,
            interval=interval,
            lookback=lookback,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Hyperliquid candle history request failed") from exc

    cleaned = [
        {
            "time": int(row.get("time") or 0),
            "open": float(row.get("open") or 0.0),
            "high": float(row.get("high") or 0.0),
            "low": float(row.get("low") or 0.0),
            "close": float(row.get("close") or 0.0),
            "volume": float(row.get("volume") or 0.0),
        }
        for row in (candles or [])
        if isinstance(row, dict)
        and int(row.get("time") or 0) > 0
        and float(row.get("high") or 0.0) > 0
        and float(row.get("low") or 0.0) > 0
    ]
    return {
        "source": "hyperliquid",
        "symbol": clean_symbol,
        "interval": interval,
        "count": len(cleaned),
        "candles": cleaned,
        "live_execution": False,
    }


@router.post("/manual/alerts/{setup_key}/ack")
async def acknowledge_manual_perp_alert(setup_key: str) -> Dict[str, Any]:
    if not perp_manual_service.acknowledge_alert(setup_key):
        raise HTTPException(status_code=404, detail="setup alert not found")
    return {"ok": True, "setup_key": setup_key, "status": "COOLDOWN_ACTIVE"}


@router.post("/manual/setups/{setup_key}/enter")
async def enter_manual_perp_setup(
    setup_key: str,
    fill_price: float | None = Query(None, gt=0),
) -> Dict[str, Any]:
    try:
        plan = perp_manual_service.enter_discovered_setup(setup_key, fill_price=fill_price)
        return {
            "ok": True,
            "setup_key": setup_key,
            "status": plan.get("status"),
            "plan": plan,
            "note": "Recorded a user-confirmed manual fill. Atlas did not place an order.",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/manual/plans/{setup_key}/close")
async def close_manual_perp_plan(
    setup_key: str,
    exit_price: float = Query(..., gt=0),
    reason: str = Query("MANUAL_EXIT", min_length=1, max_length=120),
) -> Dict[str, Any]:
    try:
        plan = perp_manual_service.close_entered_plan(
            setup_key,
            exit_price=exit_price,
            reason=reason,
        )
        return {
            "ok": True,
            "setup_key": setup_key,
            "status": plan.get("status"),
            "plan": plan,
            "note": "Recorded a user-confirmed manual close. Atlas did not place an order.",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


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
