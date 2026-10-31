"""Point-in-time validation helpers for Quality Dips V2.

Research-only. This module evaluates already-recorded PIT observations and post-entry
state transitions without lookahead. It never fetches future data, mutates closed
historical evidence, places orders, or retunes thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional


HURDLES = (29.0, 40.0, 50.0)


@dataclass(frozen=True)
class PitObservation:
    symbol: str
    timestamp: str
    price: float
    conservative_value: Optional[float]
    patient_state: str
    position_state: Optional[str] = None
    entry_timestamp: Optional[str] = None
    entry_price: Optional[float] = None


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out > 0 else None


def conservative_upside_pct(price: Any, conservative_value: Any) -> Optional[float]:
    p = _as_float(price)
    target = _as_float(conservative_value)
    if p is None or target is None:
        return None
    return round(((target / p) - 1.0) * 100.0, 4)


def hurdle_flags(price: Any, conservative_value: Any) -> dict[str, bool]:
    upside = conservative_upside_pct(price, conservative_value)
    return {f"gte_{int(h)}": bool(upside is not None and upside >= h) for h in HURDLES}


def validate_pit_order(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Require each symbol's observations to be nondecreasing by timestamp.

    This does not sort input because sorting could conceal an upstream PIT violation.
    """
    last: dict[str, str] = {}
    violations: list[dict[str, str]] = []
    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        count += 1
        symbol = str(row.get("symbol") or "").upper().strip()
        timestamp = str(row.get("timestamp") or "")
        if not symbol or not timestamp:
            violations.append({"symbol": symbol, "timestamp": timestamp, "reason": "missing symbol/timestamp"})
            continue
        prev = last.get(symbol)
        if prev is not None and timestamp < prev:
            violations.append({"symbol": symbol, "timestamp": timestamp, "reason": "timestamp moved backward"})
        last[symbol] = timestamp
    return {
        "valid": not violations,
        "observation_count": count,
        "violations": violations,
        "lookahead_allowed": False,
        "same_window_retuning_allowed": False,
    }


def evaluate_hurdle_observations(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Summarize PIT hurdle occurrence without making return claims."""
    rows = [r for r in rows if isinstance(r, dict)]
    order = validate_pit_order(rows)
    counts = {f"gte_{int(h)}": 0 for h in HURDLES}
    evaluable = 0
    for row in rows:
        upside = conservative_upside_pct(row.get("price"), row.get("conservative_value"))
        if upside is None:
            continue
        evaluable += 1
        for key, hit in hurdle_flags(row.get("price"), row.get("conservative_value")).items():
            if hit:
                counts[key] += 1
    return {
        "pit_order_valid": bool(order["valid"]),
        "pit_violations": order["violations"],
        "evaluable_observations": evaluable,
        "hurdle_counts": counts,
        "hurdles_pct": list(HURDLES),
        "interpretation": "screening opportunity frequency only; not realized return or forecast",
        "execution": "MANUAL_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def evaluate_position_states(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Count recorded post-entry research states using only timestamped observations."""
    allowed = {"HOLD", "HOLD_WATCH", "ADD_ELIGIBLE", "STOP_ADDING", "THESIS_BROKEN", "EXIT_REVIEW"}
    counts = {state: 0 for state in sorted(allowed)}
    unknown = 0
    entry_time_violations: list[dict[str, str]] = []
    rows = [r for r in rows if isinstance(r, dict)]
    order = validate_pit_order(rows)
    for row in rows:
        state = str(row.get("position_state") or "").upper()
        if state in counts:
            counts[state] += 1
        elif state:
            unknown += 1
        entry_ts = str(row.get("entry_timestamp") or "")
        ts = str(row.get("timestamp") or "")
        if entry_ts and ts and ts < entry_ts:
            entry_time_violations.append({
                "symbol": str(row.get("symbol") or "").upper(),
                "timestamp": ts,
                "entry_timestamp": entry_ts,
            })
    return {
        "pit_order_valid": bool(order["valid"]),
        "pit_violations": order["violations"],
        "entry_time_valid": not entry_time_violations,
        "entry_time_violations": entry_time_violations,
        "state_counts": counts,
        "unknown_state_count": unknown,
        "lookahead_allowed": False,
        "same_window_retuning_allowed": False,
        "execution": "MANUAL_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
