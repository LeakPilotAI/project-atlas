from __future__ import annotations

import re
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from app.prediction.kalshi_public import ALLOWED_STATUSES, PredictionProviderError, kalshi_public
from app.prediction.policy import policy_snapshot

router = APIRouter(prefix="/api/prediction", tags=["prediction-research"])

_TICKER_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _ticker(value: str | None, *, required: bool = False) -> str | None:
    clean = str(value or "").strip().upper()
    if not clean:
        if required:
            raise HTTPException(status_code=400, detail="ticker is required")
        return None
    if len(clean) > 160 or not _TICKER_RE.fullmatch(clean):
        raise HTTPException(status_code=400, detail="invalid ticker")
    return clean


@router.get("/status")
async def prediction_status() -> Dict[str, Any]:
    return {
        "domain": "PREDICTION_MARKETS",
        "provider": "kalshi",
        "provider_mode": "PUBLIC_MARKET_DATA_ONLY",
        "research": True,
        "paper_ledger": False,
        "executable_orderbook": True,
        "historical_pre_event_prices": True,
        "settlement_verification": False,
        "calibration": False,
        "authenticated_provider_access": False,
        "order_submission": False,
        "portfolio_access": False,
        "live_execution": False,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
        "strategy_policy": policy_snapshot(),
        "note": "Phase 1 exposes Kalshi public single-market research with executable orderbook depth and bounded candlestick history. Combos/parlays/multivariate markets are permanently blocked; no account or order endpoints are wired.",
    }


@router.get("/markets")
async def prediction_markets(
    status: str = Query("open"),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None, max_length=4096),
    series_ticker: str | None = Query(None, max_length=160),
    event_ticker: str | None = Query(None, max_length=160),
) -> Dict[str, Any]:
    clean_status = str(status or "").lower().strip()
    if clean_status and clean_status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="unsupported market status")
    series = _ticker(series_ticker)
    event = _ticker(event_ticker)
    try:
        return await kalshi_public.get_markets(
            status=clean_status,
            limit=limit,
            cursor=cursor,
            series_ticker=series,
            event_ticker=event,
        )
    except PredictionProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/markets/{ticker}")
async def prediction_market(ticker: str) -> Dict[str, Any]:
    clean = _ticker(ticker, required=True)
    assert clean is not None
    try:
        return await kalshi_public.get_market(clean)
    except PredictionProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/markets/{ticker}/orderbook")
async def prediction_market_orderbook(
    ticker: str,
    depth: int = Query(20, ge=0, le=100),
) -> Dict[str, Any]:
    clean = _ticker(ticker, required=True)
    assert clean is not None
    try:
        return await kalshi_public.get_orderbook(clean, depth=depth)
    except PredictionProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/markets/{ticker}/candlesticks")
async def prediction_market_candlesticks(
    ticker: str,
    series_ticker: str = Query(..., min_length=1, max_length=160),
    start_ts: int = Query(..., gt=0),
    end_ts: int = Query(..., gt=0),
    period_interval: int = Query(60),
    include_latest_before_start: bool = Query(False),
) -> Dict[str, Any]:
    clean = _ticker(ticker, required=True)
    series = _ticker(series_ticker, required=True)
    assert clean is not None and series is not None
    try:
        return await kalshi_public.get_candlesticks(
            series_ticker=series,
            ticker=clean,
            start_ts=start_ts,
            end_ts=end_ts,
            period_interval=period_interval,
            include_latest_before_start=include_latest_before_start,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PredictionProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
