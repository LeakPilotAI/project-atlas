"""Quality Dips V2 staged patient-capital entry planner.

Research-only. Builds L1/L2/L3/L4 price zones from a complete provenance-backed
normalization window and freezes the evidence used for any planned/manual entry.
No brokerage orders are created or submitted.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.investment.quality_dips_v2 import MIN_TARGET_UPSIDE_PCT, required_entry_price

LEVEL_HURDLES = {
    "L1": 29.0,
    "L2": 35.0,
    "L3": 40.0,
    "L4": 50.0,
}


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out > 0 else None


def _scenario_target(normalization_value: Dict[str, Any], level: str) -> Optional[float]:
    """Use conservative value for all staged entries.

    The patient-capital plan intentionally does not rely on optimistic valuation to
    justify deeper levels. This keeps the 29/35/40/50% hurdles conservative.
    """
    return _as_float((normalization_value or {}).get("conservative"))


def build_entry_ladder(
    *,
    symbol: str,
    normalization_value: Dict[str, Any],
    valuation_window_complete: bool,
    current_price: Optional[float] = None,
) -> Dict[str, Any]:
    """Return a staged L1-L4 research ladder or fail closed when valuation is incomplete."""
    conservative = _scenario_target(normalization_value, "L1")
    if not valuation_window_complete or conservative is None:
        return {
            "symbol": str(symbol or "").upper(),
            "ready": False,
            "levels": [],
            "reason": "complete conservative normalization value required",
            "execution": "MANUAL_ONLY",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        }

    price = _as_float(current_price)
    levels = []
    for level, hurdle in LEVEL_HURDLES.items():
        limit_price = required_entry_price(conservative, hurdle)
        levels.append({
            "level": level,
            "required_upside_pct": hurdle,
            "normalization_target": conservative,
            "limit_price": limit_price,
            "reached": bool(price is not None and limit_price is not None and price <= limit_price),
        })

    return {
        "symbol": str(symbol or "").upper(),
        "ready": True,
        "minimum_patient_hurdle_pct": MIN_TARGET_UPSIDE_PCT,
        "levels": levels,
        "execution": "MANUAL_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def freeze_entry_snapshot(
    *,
    symbol: str,
    level: str,
    entry_price: float,
    evidence: Dict[str, Any],
    recorded_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Freeze point-in-time evidence for a planned/manual entry.

    Deep-copying prevents later in-memory mutation from rewriting the entry thesis.
    """
    lvl = str(level or "").upper()
    if lvl not in LEVEL_HURDLES:
        raise ValueError("entry level must be one of L1/L2/L3/L4")
    price = _as_float(entry_price)
    if price is None:
        raise ValueError("entry_price must be positive")
    ts = recorded_at or datetime.now(timezone.utc).isoformat()
    return {
        "symbol": str(symbol or "").upper(),
        "level": lvl,
        "entry_price": price,
        "required_upside_pct_at_level": LEVEL_HURDLES[lvl],
        "recorded_at": ts,
        "evidence_snapshot": deepcopy(evidence or {}),
        "execution": "MANUAL_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
