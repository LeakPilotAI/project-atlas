"""Read-only Archive APIs for investment research/PAPER history.

This surface never places broker orders and never rewrites investment or trading
journals. Investment history is intentionally honest about the current book:
Atlas records accumulation fills/open positions, but does not currently record
closed long-horizon investment exits suitable for realized win-rate/P&L claims.
"""
from __future__ import annotations

import asyncio
import json
from collections import deque
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Query

from app.investment.daily_research_plan import PLAN_PATH
from app.investment.history import load_bars
from app.investment.paper_book import PaperBook
from app.investment.storage import LEDGER_PATH, PAPER_STATE_PATH

router = APIRouter(prefix="/api/archive", tags=["archive"])


def _tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: deque[dict[str, Any]] = deque(maxlen=max(1, int(limit)))
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except Exception:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        return []
    return list(rows)


def _event_row(row: dict[str, Any]) -> dict[str, Any]:
    kind = str(row.get("kind") or "UNKNOWN").upper()
    price = row.get("price")
    if price is None:
        price = row.get("limit")
    shares = row.get("shares")
    usd = row.get("usd")
    if usd is None and isinstance(price, (int, float)) and isinstance(shares, (int, float)):
        usd = float(price) * float(shares)
    status = {
        "RESEARCH_BUY": "PAPER_FILLED",
        "FILL": "PAPER_FILLED",
        "ORDER": "OPEN_LIMIT",
        "CANCEL": "CANCELLED",
    }.get(kind, kind)
    return {
        "at": row.get("at"),
        "symbol": row.get("symbol"),
        "event": kind,
        "status": status,
        "price": price,
        "shares": shares,
        "usd": usd,
        "reason": row.get("reason"),
        "session": row.get("session"),
        "order_id": row.get("order_id"),
        # The current investment paper book does not implement closed long-horizon
        # exits, so realized exit/return fields must stay unavailable.
        "exit_price": None,
        "realized_return_pct": None,
        "realized_pnl": None,
        "hold_time": None,
    }


def _build_investment_history(limit: int) -> Dict[str, Any]:
    book = PaperBook.load(PAPER_STATE_PATH)
    snapshot = book.snapshot()
    ledger = _tail_jsonl(LEDGER_PATH, limit)
    plans = _tail_jsonl(PLAN_PATH, min(limit, 120))

    positions = []
    for symbol, row in (snapshot.get("positions") or {}).items():
        shares = float(row.get("shares") or 0.0)
        avg_cost = float(row.get("avg_cost") or 0.0)
        market_price = float(row.get("market_price") or 0.0)
        market_value = float(row.get("value") or 0.0)
        cost_basis = shares * avg_cost
        unrealized = market_value - cost_basis
        return_pct = ((market_price / avg_cost) - 1.0) * 100.0 if avg_cost > 0 and market_price > 0 else None
        positions.append(
            {
                "symbol": str(symbol),
                "shares": shares,
                "avg_cost": avg_cost,
                "market_price": market_price,
                "market_value": market_value,
                "cost_basis": cost_basis,
                "unrealized_pnl": unrealized,
                "unrealized_return_pct": return_pct,
                "status": "OPEN_PAPER_INVESTMENT",
            }
        )
    positions.sort(key=lambda row: abs(float(row.get("market_value") or 0.0)), reverse=True)

    events = [_event_row(row) for row in reversed(ledger)]
    fill_count = sum(1 for row in ledger if str(row.get("kind") or "").lower() in {"fill", "research_buy"})
    open_orders = int(snapshot.get("open_orders") or 0)
    latest_plan = plans[-1] if plans else None

    return {
        "domain": "INVESTMENT_ARCHIVE",
        "execution": "PAPER_RESEARCH_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
        "summary": {
            "open_positions": len(positions),
            "paper_fills": fill_count,
            "ledger_events": len(ledger),
            "portfolio_value": snapshot.get("portfolio_value"),
            "cash": snapshot.get("cash"),
            "invested": snapshot.get("invested"),
            "unrealized_pnl": snapshot.get("unrealized_pnl"),
            "realized_pnl": snapshot.get("realized_pnl"),
            "drawdown": snapshot.get("drawdown"),
            "open_orders": open_orders,
            "closed_investment_positions": None,
            "win_rate": None,
            "average_realized_return": None,
            "realized_performance_supported": False,
        },
        "positions": positions,
        "events": events,
        "daily_plan_history": list(reversed(plans)),
        "latest_daily_plan": latest_plan,
        "capabilities": {
            "paper_accumulation_fills": True,
            "open_position_marking": True,
            "closed_long_horizon_investment_exits": False,
            "realized_investment_win_rate": False,
            "realized_investment_return_series": False,
            "broker_history": False,
        },
        "note": (
            "Investment Archive is read-only. Atlas currently records simulated "
            "accumulation fills/open positions and daily research plans, but not "
            "closed long-horizon investment exits. Realized win rate, realized "
            "returns and closed-position charts therefore remain unavailable."
        ),
    }


@router.get("/investment-history")
async def investment_history(limit: int = Query(300, ge=25, le=1000)) -> Dict[str, Any]:
    return await asyncio.to_thread(_build_investment_history, limit)


@router.get("/investment-history/{symbol}/bars")
async def investment_history_bars(
    symbol: str,
    limit: int = Query(120, ge=20, le=400),
) -> Dict[str, Any]:
    safe = "".join(ch for ch in str(symbol).upper() if ch.isalnum() or ch in ".-^")[:20]
    if not safe:
        return {
            "symbol": "",
            "bars": [],
            "source": "investment_daily_history",
            "execution": "READ_ONLY",
        }
    bars = await asyncio.to_thread(load_bars, safe)
    selected = bars[-limit:]
    return {
        "symbol": safe,
        "bars": [
            {
                "date": bar.session_date,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "quality": bar.quality,
                "issues": list(bar.issues or []),
            }
            for bar in selected
        ],
        "source": "investment_daily_history",
        "execution": "READ_ONLY",
        "live_capital_allowed": False,
    }
