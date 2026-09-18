"""Quality Dips V3 research alerts and frozen-entry snapshots.

This module converts durable V3 state changes into explicit research notifications
and freezes the evidence used when an entry level is first reached. It never places
or modifies brokerage orders.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


def freeze_v3_entry_snapshot(*, symbol: str, event: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    level = str(event.get("level") or "").upper()
    if level not in {"L1", "L2", "L3", "L4"}:
        raise ValueError("V3 snapshot requires L1-L4 entry event")
    price = float(event.get("limit_price") or 0.0)
    if price <= 0:
        raise ValueError("V3 entry snapshot requires positive limit price")
    return {
        "symbol": str(symbol or "").upper(),
        "level": level,
        "entry_limit_price": price,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "v3_plan_snapshot": deepcopy(plan or {}),
        "execution": "MANUAL_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def format_v3_alert(event: dict[str, Any], plan: dict[str, Any]) -> str:
    sym = str(event.get("symbol") or plan.get("symbol") or "").upper()
    state = str(plan.get("patient_state") or "WATCH").upper()
    fair = plan.get("fair_value_anchor")
    discount = plan.get("discount_to_fair_value_pct")
    et = str(event.get("event_type") or "V3_EVENT").upper()
    lines = [
        f"QUALITY DIPS V3 · {et}",
        sym,
        "",
        f"Patient state: {state}",
        f"Robust fair-value anchor: {fair}",
        f"Discount to fair value: {discount}%",
    ]
    if event.get("level"):
        lines.append(f"Entry level reached: {event.get('level')} at {event.get('limit_price')}")
    lines += [
        "",
        "MANUAL RESEARCH ONLY:",
        "Review the evidence and place any Robinhood order yourself.",
        "No brokerage order was placed. This is not a guaranteed bargain or return.",
    ]
    return "\n".join(lines)
