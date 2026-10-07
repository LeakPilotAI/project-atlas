from __future__ import annotations

from typing import Any, Iterable

from app.trading_core.perp_order_sanity import classify_limit_behavior


_TIER_ORDER = {"PRIME": 0, "QUALIFIED": 1, "WATCH": 2}
_STATE_ORDER = {"L3_ACTIVE": 0, "L2_ACTIVE": 1, "L1_ACTIVE": 2, "PREPARE": 3, "WAIT": 4, "TP1_HIT": 5, "TP2_HIT": 6, "INVALIDATED": 7}
_ACTIONABLE_STATES = {"PREPARE", "L1_ACTIVE", "L2_ACTIVE", "L3_ACTIVE"}


def _limit_sanity(side: str, mark: float, value: Any) -> dict[str, Any] | None:
    try:
        if value is None:
            return None
        return classify_limit_behavior(side=side, mark=mark, limit_price=float(value))
    except (TypeError, ValueError):
        return None


def _manual_instruction(row: dict[str, Any], *, side: str, state: str, mark: float, l1: Any, sanity: dict[str, Any] | None) -> dict[str, Any]:
    """Return one beginner-safe instruction for manual execution.

    This is presentation guidance only. It never places an order. A setup must be
    currently scanner-confirmed, actionable, not already entered, and have a
    resting L1 relative to the current mark before Atlas tells the user to place it.
    """
    if bool(row.get("discovery_stale", False)):
        return {
            "action": "NO_NEW_ORDER",
            "can_mark_entered": False,
            "headline": "NO NEW ORDER — STALE SETUP",
            "instruction": "Scanner confirmation is temporarily absent. Keep any existing resting order unchanged, but do not place, move, or chase a new order until this setup is rediscovered.",
        }
    if str(row.get("trade_status") or "").upper() == "ENTERED":
        return {
            "action": "MANAGE_EXISTING",
            "can_mark_entered": False,
            "headline": "POSITION ALREADY ENTERED",
            "instruction": "Do not create another entry from this card. Manage the existing recorded position using its frozen stop and targets.",
        }
    if state not in _ACTIONABLE_STATES:
        return {
            "action": "WAIT",
            "can_mark_entered": False,
            "headline": "WAIT — DO NOT PLACE ORDER",
            "instruction": "This setup is not currently actionable. Wait for Atlas to show a scanner-confirmed actionable setup.",
        }
    if mark <= 0 or l1 is None or sanity is None:
        return {
            "action": "WAIT",
            "can_mark_entered": False,
            "headline": "WAIT — PRICE CHECK UNAVAILABLE",
            "instruction": "Atlas cannot verify that L1 is a resting limit against the current mark. Do not place a new order.",
        }
    if bool(sanity.get("marketable", False)):
        direction = "below" if side == "LONG" else "above"
        return {
            "action": "NO_NEW_ORDER",
            "can_mark_entered": False,
            "headline": "NO NEW ORDER — L1 WOULD FILL NOW",
            "instruction": f"Do not place L1 at {float(l1):g}. For a resting {side} limit, the entry must be {direction} the current market. Wait for Atlas to issue a valid resting setup instead of chasing price.",
        }
    direction = "below" if side == "LONG" else "above"
    return {
        "action": "PLACE_RESTING_L1",
        "can_mark_entered": True,
        "headline": f"PLACE {side} LIMIT AT L1",
        "order_type": "LIMIT",
        "limit_price": float(l1),
        "instruction": f"Use a {side} LIMIT at L1 {float(l1):g}. L1 is currently {direction} the market, so it is classified as RESTING by Atlas. Do not move the order toward price if the market runs away.",
    }


def build_perp_board(setups: Iterable[dict[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    """Project discovery/lifecycle rows into a compact manual trading board.

    This is presentation-only: it never changes ranking, lifecycle state, or orders.
    """
    board: list[dict[str, Any]] = []
    for raw in setups:
        row = dict(raw)
        levels = dict(row.get("levels") or {})
        symbol = str(row.get("symbol") or "").upper()
        side = str(row.get("side") or "").upper()
        if not symbol or side not in {"LONG", "SHORT"}:
            continue
        mark = float(row.get("price") or row.get("mark") or 0.0)
        l1 = levels.get("l1")
        l2 = levels.get("l2")
        l3 = levels.get("l3")
        state = str(row.get("state") or "WAIT").upper()
        sanity = {
            "l1": _limit_sanity(side, mark, l1),
            "l2": _limit_sanity(side, mark, l2),
            "l3": _limit_sanity(side, mark, l3),
        } if mark > 0 else {"l1": None, "l2": None, "l3": None}
        instruction = _manual_instruction(row, side=side, state=state, mark=mark, l1=l1, sanity=sanity["l1"])
        board.append({
            "setup_key": str(row.get("setup_key") or f"{symbol}:{side}"),
            "symbol": symbol,
            "side": side,
            "tier": str(row.get("tier") or "WATCH").upper(),
            "state": state,
            "trade_status": str(row.get("trade_status") or "NOT_ENTERED").upper(),
            "entry_price": row.get("entry_price"),
            "entered_at": row.get("entered_at"),
            "score": round(float(row.get("score") or 0.0), 2),
            "mark": mark,
            "l1": l1,
            "l2": l2,
            "l3": l3,
            "stop": levels.get("stop"),
            "tp1": levels.get("tp1"),
            "tp2": levels.get("tp2"),
            "levels_frozen": bool(row.get("levels_frozen", False)),
            "discovery_stale": bool(row.get("discovery_stale", False)),
            "limit_sanity": sanity,
            "manual_instruction": instruction,
            "leverage_note": "Leverage affects exposure/margin/liquidation, not whether a limit order crosses the current market.",
            "next_action": str(row.get("next_action") or "Wait for a qualified setup."),
            "alert_eligible": bool(row.get("alert_eligible", False)),
            "alert_reason": row.get("alert_reason"),
            "distance_to_l1_pct": row.get("distance_to_l1_pct"),
            "momentum_pct": row.get("momentum_pct"),
            "trend_pct": row.get("trend_pct"),
            "volatility_pct": row.get("volatility_pct"),
        })

    board.sort(key=lambda r: (
        _TIER_ORDER.get(str(r["tier"]), 9),
        _STATE_ORDER.get(str(r["state"]), 9),
        -float(r["score"]),
        str(r["symbol"]),
    ))
    return board[: max(1, int(limit))]
