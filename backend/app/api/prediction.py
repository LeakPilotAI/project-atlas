from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from app.prediction.kalshi_public import ALLOWED_STATUSES, PredictionProviderError, kalshi_public
from app.prediction.policy import policy_snapshot
from app.prediction.prediction_paper_automation import prediction_paper_automation
from app.prediction.paper_engine import (
    PAPER_ENGINE_VERSION,
    PredictionPaperError,
    evaluate_pre_event_repricing,
    prediction_paper_journal,
)

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
        "paper_ledger": True,
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
        "note": "Atlas exposes Kalshi public single-market research plus an isolated PAPER-only pre-event repricing ledger. Combos/parlays/multivariate markets are permanently blocked; no authenticated account or live order endpoints are wired.",
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
    series_ticker: str | None = Query(None, min_length=1, max_length=160),
    start_ts: int = Query(..., gt=0),
    end_ts: int = Query(..., gt=0),
    period_interval: int = Query(60),
    include_latest_before_start: bool = Query(False),
) -> Dict[str, Any]:
    clean = _ticker(ticker, required=True)
    series = _ticker(series_ticker)
    assert clean is not None
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


def _paper_quantity(value: float) -> Decimal:
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="invalid PAPER quantity") from exc
    if quantity <= 0 or quantity > Decimal("10000"):
        raise HTTPException(status_code=400, detail="PAPER quantity must be > 0 and <= 10000")
    return quantity


async def _build_prediction_paper_evaluation(
    *,
    ticker: str,
    side: str,
    quantity: Decimal,
    depth: int,
    history_minutes: int,
) -> Dict[str, Any]:
    clean_side = str(side or "").upper().strip()
    if clean_side not in {"YES", "NO"}:
        raise HTTPException(status_code=400, detail="side must be YES or NO")

    market_payload = await kalshi_public.get_market(ticker)
    market = market_payload["market"]
    orderbook_payload = await kalshi_public.get_orderbook(ticker, depth=depth)

    now = datetime.now(timezone.utc)
    end_ts = int(now.timestamp())
    start_ts = end_ts - (max(5, min(int(history_minutes), 1000)) * 60)
    candle_payload = await kalshi_public.get_candlesticks(
        ticker=ticker,
        start_ts=start_ts,
        end_ts=end_ts,
        period_interval=1,
        include_latest_before_start=True,
    )

    return evaluate_pre_event_repricing(
        market=market,
        orderbook=orderbook_payload["orderbook"],
        candles=candle_payload["candlesticks"],
        side=clean_side,
        quantity=quantity,
        now=now,
    )


@router.get("/paper/status")
async def prediction_paper_status(
    limit: int = Query(100, ge=1, le=1000),
) -> Dict[str, Any]:
    payload = prediction_paper_journal.snapshot(limit=limit)
    payload["automation"] = prediction_paper_automation.status()
    return payload


@router.get("/paper/automation/status")
async def prediction_paper_automation_status() -> Dict[str, Any]:
    return prediction_paper_automation.status()


@router.post("/paper/evaluate/{ticker}")
async def prediction_paper_evaluate(
    ticker: str,
    side: str = Query("YES"),
    quantity: float = Query(10.0, gt=0, le=10000),
    depth: int = Query(20, ge=1, le=100),
    history_minutes: int = Query(180, ge=5, le=1000),
) -> Dict[str, Any]:
    clean = _ticker(ticker, required=True)
    assert clean is not None
    try:
        evaluation = await _build_prediction_paper_evaluation(
            ticker=clean,
            side=side,
            quantity=_paper_quantity(quantity),
            depth=depth,
            history_minutes=history_minutes,
        )
        candidate = prediction_paper_journal.log_candidate(evaluation)
        return {
            "execution": "PAPER_ONLY",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "candidate": candidate,
        }
    except PredictionPaperError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PredictionProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/paper/open/{ticker}")
async def prediction_paper_open(
    ticker: str,
    side: str = Query("YES"),
    quantity: float = Query(10.0, gt=0, le=10000),
    depth: int = Query(20, ge=1, le=100),
    history_minutes: int = Query(180, ge=5, le=1000),
) -> Dict[str, Any]:
    clean = _ticker(ticker, required=True)
    assert clean is not None
    try:
        evaluation = await _build_prediction_paper_evaluation(
            ticker=clean,
            side=side,
            quantity=_paper_quantity(quantity),
            depth=depth,
            history_minutes=history_minutes,
        )
        candidate = prediction_paper_journal.log_candidate(evaluation)
        if not evaluation.get("eligible"):
            return {
                "execution": "PAPER_ONLY",
                "live_capital_allowed": False,
                "automatic_real_money_execution": False,
                "opened": False,
                "candidate": candidate,
                "rejection_reasons": evaluation.get("rejection_reasons") or [],
            }
        opened = prediction_paper_journal.open_from_evaluation(evaluation)
        return {
            "execution": "PAPER_ONLY",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "opened": True,
            "candidate": candidate,
            "trade": opened,
        }
    except PredictionPaperError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PredictionProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/paper/close")
async def prediction_paper_close(
    reason: str = Query("MANUAL_PAPER_EXIT", min_length=1, max_length=80),
    depth: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    opened = prediction_paper_journal.open_trade()
    if not opened:
        raise HTTPException(status_code=409, detail="no open prediction PAPER position")
    ticker = str(opened.get("ticker") or "")
    if not ticker:
        raise HTTPException(status_code=409, detail="open prediction PAPER ticker missing")
    try:
        orderbook_payload = await kalshi_public.get_orderbook(ticker, depth=depth)
        closed = prediction_paper_journal.close_from_orderbook(
            orderbook=orderbook_payload["orderbook"],
            exit_reason=reason,
        )
        return {
            "execution": "PAPER_ONLY",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "closed": True,
            "trade": closed,
        }
    except PredictionPaperError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PredictionProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
