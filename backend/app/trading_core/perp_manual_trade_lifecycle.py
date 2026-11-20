from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .models import Side
from .perp_setup_state import classify_setup_state


class ManualTradeStatus(str, Enum):
    ENTERED = "ENTERED"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class ManualEntry:
    setup_key: str
    symbol: str
    side: Side
    fill_price: float
    entered_at: str


def _utc_iso(now: datetime | None = None) -> str:
    dt = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _positive(name: str, value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be positive") from exc
    if out <= 0:
        raise ValueError(f"{name} must be positive")
    return out


def enter_setup(
    setup: dict[str, Any],
    *,
    fill_price: float | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Convert one discovered Hyperliquid setup into an explicitly entered manual plan.

    This function never infers entry from market movement. The caller must invoke it
    after the user confirms a real/manual fill.
    """
    row = dict(setup)
    symbol = str(row.get("symbol") or "").upper()
    side_raw = str(row.get("side") or "").upper()
    setup_key = str(row.get("setup_key") or "")
    levels = dict(row.get("levels") or {})
    if not symbol or side_raw not in {"LONG", "SHORT"} or not setup_key:
        raise ValueError("invalid manual perp setup")

    try:
        side = Side[side_raw]
    except KeyError as exc:
        raise ValueError("side must be LONG or SHORT") from exc

    l1 = _positive("l1", levels.get("l1"))
    l2 = _positive("l2", levels.get("l2"))
    l3 = _positive("l3", levels.get("l3"))
    stop = _positive("stop", levels.get("stop"))
    tp1 = _positive("tp1", levels.get("tp1"))
    tp2 = _positive("tp2", levels.get("tp2"))
    mark = _positive("mark", row.get("price") or row.get("mark"))
    actual_fill = _positive("fill_price", fill_price if fill_price is not None else mark)

    state = classify_setup_state(
        side=side,
        mark=mark,
        l1=l1,
        l2=l2,
        l3=l3,
        stop=stop,
        tp1=tp1,
        tp2=tp2,
        entered=True,
    )

    return {
        "setup_key": setup_key,
        "symbol": symbol,
        "side": side.value,
        "source": "hyperliquid",
        "mode": "MANUAL_ONLY",
        "status": ManualTradeStatus.ENTERED.value,
        "entered": True,
        "entered_at": _utc_iso(now),
        "entry_price": actual_fill,
        "mark": mark,
        "state": state.state.value,
        "next_action": state.next_action,
        "distance_to_l1_pct": round(float(state.distance_to_l1_pct), 4),
        "l1": l1,
        "l2": l2,
        "l3": l3,
        "stop": stop,
        "tp1": tp1,
        "tp2": tp2,
        "target_rr": levels.get("target_rr"),
        "score_at_entry": float(row.get("score") or 0.0),
        "tier_at_entry": str(row.get("tier") or "WATCH").upper(),
        "closed_at": None,
        "exit_price": None,
        "close_reason": None,
        "note": "User-confirmed manual Hyperliquid entry. Atlas did not place an order.",
    }


def close_plan(
    plan: dict[str, Any],
    *,
    exit_price: float,
    reason: str = "MANUAL_EXIT",
    now: datetime | None = None,
) -> dict[str, Any]:
    row = dict(plan)
    if str(row.get("status") or "").upper() != ManualTradeStatus.ENTERED.value:
        raise ValueError("manual perp plan is not entered")
    row["status"] = ManualTradeStatus.CLOSED.value
    row["entered"] = False
    row["closed_at"] = _utc_iso(now)
    row["exit_price"] = _positive("exit_price", exit_price)
    row["close_reason"] = str(reason or "MANUAL_EXIT")[:120]
    row["next_action"] = "Manual position closed; no further active management."
    return row
