"""Fail-closed PAPER risk guard for auto-mirrored perp setups.

This is simulation-only. It limits new PAPER exposure and never enables live trading.
"""
from __future__ import annotations

from typing import Any

MAX_CONCURRENT_PAPER = 3
MAX_RISK_USD_PER_TRADE = 25.0
MAX_SESSION_LOSS_R = 3.0


def check_paper_risk(
    *,
    open_positions: list[dict[str, Any]],
    requested_risk_usd: float,
    session_net_r: float = 0.0,
    kill_switch: bool = False,
) -> dict[str, Any]:
    blockers: list[str] = []
    if kill_switch:
        blockers.append("operator kill switch enabled")
    try:
        session_r = float(session_net_r)
    except (TypeError, ValueError):
        session_r = 0.0
    if session_r <= -MAX_SESSION_LOSS_R:
        blockers.append("paper session loss stop reached")
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
        "max_session_loss_r": MAX_SESSION_LOSS_R,
        "session_net_r": session_r,
        "kill_switch": bool(kill_switch),
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
