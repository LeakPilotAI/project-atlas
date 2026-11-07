"""Fail-closed PAPER risk guard for auto-mirrored perp setups.

This is simulation-only. It limits new PAPER exposure and never enables live trading.
"""
from __future__ import annotations

import math
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
    accounting_reliable: bool = True,
    controls_reliable: bool = True,
) -> dict[str, Any]:
    blockers: list[str] = []
    if controls_reliable is not True:
        blockers.append("paper operator controls unavailable or unreliable")
    if kill_switch:
        blockers.append("operator kill switch enabled")
    if accounting_reliable is not True:
        blockers.append("paper accounting evidence unavailable or unreliable")
    try:
        session_r = float(session_net_r)
        if isinstance(session_net_r, bool) or not math.isfinite(session_r):
            raise ValueError("invalid session R")
    except (TypeError, ValueError, OverflowError):
        session_r = None
        blockers.append("invalid paper session net R")
    if session_r is not None and session_r <= -MAX_SESSION_LOSS_R:
        blockers.append("paper session loss stop reached")
    paper_open = [
        p for p in open_positions
        if str(p.get("trade_type") or "PAPER").upper() == "PAPER"
    ]
    if len(paper_open) >= MAX_CONCURRENT_PAPER:
        blockers.append("max concurrent paper positions reached")
    try:
        risk = float(requested_risk_usd)
        if isinstance(requested_risk_usd, bool) or not math.isfinite(risk):
            raise ValueError("invalid risk")
    except (TypeError, ValueError, OverflowError):
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
