"""Fail-closed PAPER risk guard for auto-mirrored perp setups.

This is simulation-only. It limits new PAPER exposure and never enables live trading.
"""
from __future__ import annotations

from typing import Any

MAX_CONCURRENT_PAPER = 3
MAX_RISK_USD_PER_TRADE = 25.0


def check_paper_risk(*, open_positions: list[dict[str, Any]], requested_risk_usd: float) -> dict[str, Any]:
    blockers: list[str] = []
    paper_open = [
        p for p in open_positions
        if str(p.get("trade_type") or "PAPER").upper() == "PAPER"
    ]
    if len(paper_open) >= MAX_CONCURRENT_PAPER:
        blockers.append("max concurrent paper positions reached")
    try:
        risk = float(requested_risk_usd)
    except (TypeError, ValueError):
        risk = -1.0
    if risk <= 0:
        blockers.append("invalid requested paper risk")
    elif risk > MAX_RISK_USD_PER_TRADE:
        blockers.append("per-trade paper risk ceiling exceeded")
    return {
        "allowed": not blockers,
        "blockers": blockers,
        "max_concurrent_paper": MAX_CONCURRENT_PAPER,
        "max_risk_usd_per_trade": MAX_RISK_USD_PER_TRADE,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
