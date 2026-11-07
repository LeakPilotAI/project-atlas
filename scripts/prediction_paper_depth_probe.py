"""Read-only Kalshi public-depth entry/exit feasibility diagnostic.

No position is opened; no journal or broker operation is performed. Both
hypothetical fills use ONE snapshot and do not prove future exit liquidity.
"""
from __future__ import annotations

import asyncio
import json
from decimal import Decimal

from app.prediction.kalshi_public import kalshi_public
from app.prediction.paper_engine import walk_executable_depth


async def probe(*, limit: int = 5, quantity: Decimal = Decimal("1")) -> dict:
    if not 1 <= limit <= 5 or not Decimal("0") < quantity <= Decimal("10"):
        raise ValueError("bounded read-only probe requires 1..5 markets and 0..10 contracts")
    markets = await kalshi_public.get_markets(status="open", limit=limit)
    results = []
    for market in markets.get("markets", []):
        ticker = str(market.get("ticker") or "")
        if not ticker:
            continue
        try:
            book = (await kalshi_public.get_orderbook(ticker, depth=20))["orderbook"]
            sides = {}
            for side in ("YES", "NO"):
                entry = walk_executable_depth(book, side=side, action="BUY", quantity=quantity)
                exit_ = walk_executable_depth(book, side=side, action="SELL", quantity=quantity)
                sides[side] = {
                    "entry_fillable": entry["fillable"],
                    "exit_fillable": exit_["fillable"],
                    "entry_reason": entry.get("reason"),
                    "exit_reason": exit_.get("reason"),
                    "entry_vwap": entry.get("vwap_dollars"),
                    "exit_vwap": exit_.get("vwap_dollars"),
                }
            results.append({"ticker": ticker, "sides": sides})
        except Exception as exc:
            results.append({"ticker": ticker, "error_type": type(exc).__name__})
    return {
        "mode": "READ_ONLY_ONE_SNAPSHOT_DEPTH_DIAGNOSTIC",
        "paper_positions_opened": 0,
        "broker_orders": 0,
        "unattended_paper_authorized": False,
        "future_exit_liquidity_proven": False,
        "requested_contracts": str(quantity),
        "markets_returned": len(markets.get("markets", [])),
        "books_checked": len(results),
        "markets": results,
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(probe()), sort_keys=True, indent=2))

