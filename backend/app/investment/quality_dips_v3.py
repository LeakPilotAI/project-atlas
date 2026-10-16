"""Quality Dips V3 evidence-weighted margin-of-safety entry policy.

This opens a NEW research cycle. V2/V2.1 and their historical evidence stay immutable.

V3 fixes V2's double-conservatism: the low analyst target is no longer divided by
another 29/35/40/50 percent. Instead Atlas builds a robust evidence-backed fair-value
anchor from the complete normalization distribution, then applies explicit margins
of safety. Classification still fails closed on weak quality, fundamentals, thesis,
evidence, or incomplete valuation.

Research only. No brokerage orders are created or submitted.
"""
from __future__ import annotations

from statistics import median
from typing import Any, Dict, Optional

LEVEL_MARGINS = {"L1": 0.15, "L2": 0.20, "L3": 0.25, "L4": 0.30}


def _f(v: Any) -> Optional[float]:
    try:
        x = float(v)
        return x if x > 0 and x == x else None
    except (TypeError, ValueError):
        return None


def robust_fair_value(normalization: Dict[str, Any]) -> Optional[float]:
    """Conservative blend: median of low, mean/base, high; requires all 3."""
    vals = [_f(normalization.get(k)) for k in ("conservative", "base", "optimistic")]
    if any(v is None for v in vals):
        return None
    return round(float(median(vals)), 2)


def build_v3_entry_plan(
    *,
    symbol: str,
    current_price: Any,
    normalization: Dict[str, Any],
    quality_score: Any,
    fundamentals_score: Any,
    valuation_score: Any,
    drawdown_percentile: Any,
    evidence_quality: str,
    thesis_intact: bool,
    value_trap: bool,
) -> Dict[str, Any]:
    sym = str(symbol or "").upper().strip()
    price, quality, fundamentals, valuation, drawdown = map(
        _f, (current_price, quality_score, fundamentals_score, valuation_score, drawdown_percentile)
    )
    evidence = str(evidence_quality or "UNKNOWN").upper()
    fair = robust_fair_value(normalization)
    blockers: list[str] = []
    if not thesis_intact: blockers.append("thesis integrity failed")
    if value_trap: blockers.append("value-trap/falling-knife gate active")
    if evidence not in {"MEDIUM", "HIGH"}: blockers.append("evidence below MEDIUM")
    if quality is None or quality < 75: blockers.append("business quality below 75")
    if fundamentals is None or fundamentals < 70: blockers.append("fundamentals below 70")
    if valuation is None or valuation < 50: blockers.append("valuation evidence below 50")
    if fair is None: blockers.append("complete normalization distribution required")

    levels = []
    if fair is not None:
        for name, margin in LEVEL_MARGINS.items():
            lp = round(fair * (1.0 - margin), 2)
            levels.append({
                "level": name,
                "margin_of_safety_pct": round(margin * 100, 1),
                "limit_price": lp,
                "reached": bool(price is not None and price <= lp),
            })

    discount = None if price is None or fair is None else round((1.0 - price / fair) * 100.0, 2)
    state = "WATCH"
    if not blockers and discount is not None:
        if discount >= 30 and evidence == "HIGH" and quality >= 90 and fundamentals >= 85 and valuation >= 80 and drawdown is not None and drawdown >= 90:
            state = "GENERATIONAL"
        elif discount >= 25 and quality >= 85 and fundamentals >= 80 and valuation >= 70 and drawdown is not None and drawdown >= 75:
            state = "DEEP_VALUE"
        elif discount >= 15:
            state = "ACCUMULATION"

    return {
        "cycle": "QUALITY_DIPS_V3_MARGIN_OF_SAFETY",
        "symbol": sym,
        "patient_state": state,
        "fair_value_anchor": fair,
        "discount_to_fair_value_pct": discount,
        "blockers": blockers,
        "entry_ladder": {"ready": not blockers and fair is not None, "levels": levels},
        "policy": {
            "method": "ROBUST_NORMALIZATION_MEDIAN_PLUS_MARGIN_OF_SAFETY",
            "level_margins_pct": {"L1": 15.0, "L2": 20.0, "L3": 25.0, "L4": 30.0},
            "guaranteed_undervaluation": False,
            "guaranteed_return": False,
            "price_alone_breaks_thesis": False,
        },
        "execution": "MANUAL_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
