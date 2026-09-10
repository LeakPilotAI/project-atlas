from __future__ import annotations

from typing import Any, Iterable

from app.trading_core.perp_order_sanity import classify_limit_behavior


_TIER_ORDER = {"PRIME": 0, "QUALIFIED": 1, "WATCH": 2}
_STATE_ORDER = {"L3_ACTIVE": 0, "L2_ACTIVE": 1, "L1_ACTIVE": 2, "PREPARE": 3, "WAIT": 4, "TP1_HIT": 5, "TP2_HIT": 6, "INVALIDATED": 7}


def _limit_sanity(side: str, mark: float, value: Any) -> dict[str, Any] | None:
    try:
        if value is None:
            return None
        return classify_limit_behavior(side=side, mark=mark, limit_price=float(value))
    except (TypeError, ValueError):
        return None


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
        sanity = {
            "l1": _limit_sanity(side, mark, l1),
            "l2": _limit_sanity(side, mark, l2),
            "l3": _limit_sanity(side, mark, l3),
        } if mark > 0 else {"l1": None, "l2": None, "l3": None}
        board.append({
            "setup_key": str(row.get("setup_key") or f"{symbol}:{side}"),
            "symbol": symbol,
            "side": side,
            "tier": str(row.get("tier") or "WATCH").upper(),
            "state": str(row.get("state") or "WAIT").upper(),
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
            "limit_sanity": sanity,
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
