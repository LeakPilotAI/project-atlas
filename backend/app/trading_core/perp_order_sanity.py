from __future__ import annotations

from typing import Any, Dict


def classify_limit_behavior(*, side: str, mark: float, limit_price: float) -> Dict[str, Any]:
    """Classify whether a manual limit is resting or marketable.

    LONG buy limits at/above the current mark are marketable and may fill immediately.
    SHORT sell limits at/below the current mark are marketable and may fill immediately.
    Leverage is intentionally not part of this calculation; leverage changes exposure,
    margin, and liquidation distance, not whether the limit crosses the market.
    """
    s = str(side or "").strip().upper()
    m = float(mark)
    p = float(limit_price)
    if s not in {"LONG", "SHORT"}:
        raise ValueError("side must be LONG or SHORT")
    if m <= 0 or p <= 0:
        raise ValueError("mark and limit_price must be positive")

    marketable = p >= m if s == "LONG" else p <= m
    distance_pct = ((p / m) - 1.0) * 100.0
    if marketable:
        message = (
            "MARKETABLE: buy limit is at/above current mark and may fill immediately."
            if s == "LONG"
            else "MARKETABLE: sell limit is at/below current mark and may fill immediately."
        )
    else:
        message = (
            "RESTING: buy limit is below current mark and should wait for price to fall to it."
            if s == "LONG"
            else "RESTING: sell limit is above current mark and should wait for price to rise to it."
        )
    return {
        "behavior": "MARKETABLE" if marketable else "RESTING",
        "marketable": marketable,
        "distance_from_mark_pct": round(distance_pct, 4),
        "message": message,
    }
