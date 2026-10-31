"""Quality Dips V3 point-in-time DEVELOPMENT/HOLDOUT validation helpers.

Research-only. Consumes already-recorded PIT rows; never fetches future data, sorts
away timestamp violations, retunes thresholds on HOLDOUT, or enables live capital.
"""
from __future__ import annotations

from typing import Any, Iterable

DEVELOPMENT_START = "2024-01-01T00:00:00"
DEVELOPMENT_END = "2025-06-30T23:59:59"
HOLDOUT_START = "2025-07-01T00:00:00"
HOLDOUT_END = "2025-12-31T23:59:59"
ALLOWED_STATES = {"WATCH", "ACCUMULATION", "DEEP_VALUE", "GENERATIONAL"}


def _window(ts: str) -> str | None:
    t = str(ts or "")
    if DEVELOPMENT_START <= t <= DEVELOPMENT_END:
        return "DEVELOPMENT"
    if HOLDOUT_START <= t <= HOLDOUT_END:
        return "HOLDOUT"
    return None


def validate_v3_pit_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    last: dict[str, str] = {}
    violations: list[dict[str, str]] = []
    counts = {"DEVELOPMENT": 0, "HOLDOUT": 0, "OUTSIDE": 0}
    states = {w: {s: 0 for s in sorted(ALLOWED_STATES)} for w in ("DEVELOPMENT", "HOLDOUT")}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("symbol") or "").upper().strip()
        ts = str(row.get("timestamp") or "")
        if not sym or not ts:
            violations.append({"symbol": sym, "timestamp": ts, "reason": "missing symbol/timestamp"})
            continue
        prev = last.get(sym)
        if prev is not None and ts < prev:
            violations.append({"symbol": sym, "timestamp": ts, "reason": "timestamp moved backward"})
        last[sym] = ts
        w = _window(ts)
        if w is None:
            counts["OUTSIDE"] += 1
            continue
        counts[w] += 1
        state = str(row.get("patient_state") or "WATCH").upper()
        if state not in ALLOWED_STATES:
            violations.append({"symbol": sym, "timestamp": ts, "reason": f"unknown patient_state {state}"})
        else:
            states[w][state] += 1
    return {
        "valid": not violations,
        "violations": violations,
        "windows": counts,
        "state_counts": states,
        "development_frozen": True,
        "holdout_retuning_allowed": False,
        "lookahead_allowed": False,
        "execution": "MANUAL_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
