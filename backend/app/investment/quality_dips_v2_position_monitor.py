"""Quality Dips V2 active-position research monitor.

Compares current read-only evidence against the frozen point-in-time entry snapshot.
The monitor emits research states only; it never places, modifies, or closes orders.

Price movement alone never creates thesis failure. Trend weakness can downgrade
confidence or stop additional accumulation, but thesis failure requires explicit
business/thesis evidence deterioration.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class PositionResearchState(str, Enum):
    HOLD = "HOLD"
    HOLD_WATCH = "HOLD_WATCH"
    ADD_ELIGIBLE = "ADD_ELIGIBLE"
    STOP_ADDING = "STOP_ADDING"
    THESIS_BROKEN = "THESIS_BROKEN"
    EXIT_REVIEW = "EXIT_REVIEW"


@dataclass(frozen=True)
class PositionMonitorInput:
    symbol: str
    cost_basis: float
    current_price: float
    entry_snapshot: Dict[str, Any]
    current_evidence: Dict[str, Any]


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _upper(value: Any) -> str:
    return str(value or "UNKNOWN").upper()


def _pct_change(current: float, anchor: float) -> Optional[float]:
    if anchor <= 0:
        return None
    return round(((current / anchor) - 1.0) * 100.0, 2)


def _thesis_failed(current: Dict[str, Any]) -> bool:
    thesis = _upper(current.get("thesis"))
    classification = _upper(current.get("classification"))
    flags = dict(current.get("flags") or {})
    return bool(
        thesis in {"BROKEN", "FAILED"}
        or classification == "THESIS_BROKEN"
        or flags.get("thesis_broken")
        or flags.get("fundamental_break")
    )


def _hard_stop_adding(current: Dict[str, Any]) -> bool:
    flags = dict(current.get("flags") or {})
    evidence = _upper(current.get("evidence_quality") or current.get("evidence"))
    return bool(
        current.get("value_trap")
        or current.get("trap")
        or flags.get("value_trap")
        or flags.get("falling_knife")
        or evidence in {"LOW", "INSUFFICIENT", "UNKNOWN"}
    )


def _trend_condition(current: Dict[str, Any]) -> str:
    trend = dict(current.get("trend") or current.get("trend_analysis") or {})
    values = [
        _upper(trend.get("short_term")),
        _upper(trend.get("intermediate_term")),
        _upper(trend.get("long_term")),
        _upper(trend.get("momentum")),
        _upper(trend.get("relative_strength")),
    ]
    bearish = sum(v in {"DOWN", "BEARISH", "WEAK", "DETERIORATING"} for v in values)
    bullish = sum(v in {"UP", "BULLISH", "STRONG", "IMPROVING"} for v in values)
    known = sum(v != "UNKNOWN" for v in values)
    if known == 0:
        return "UNKNOWN"
    if bearish >= 3:
        return "BEARISH"
    if bullish >= 3:
        return "BULLISH"
    return "MIXED"


def evaluate_position(inp: PositionMonitorInput) -> Dict[str, Any]:
    """Return research-only post-entry state and evidence deltas."""
    cost = _as_float(inp.cost_basis)
    price = _as_float(inp.current_price)
    if cost is None or price is None or cost <= 0 or price <= 0:
        return {
            "symbol": inp.symbol.upper(),
            "state": PositionResearchState.HOLD_WATCH.value,
            "reasons": ["invalid or missing cost basis/current price"],
            "execution": "MANUAL_ONLY",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        }

    current = dict(inp.current_evidence or {})
    entry = dict(inp.entry_snapshot or {})
    trend_condition = _trend_condition(current)
    pnl_pct = _pct_change(price, cost)
    thesis_failed = _thesis_failed(current)
    stop_adding = _hard_stop_adding(current)

    entry_quality = _as_float(entry.get("quality_score"))
    current_quality = _as_float(current.get("quality_score"))
    entry_fund = _as_float(entry.get("fundamentals_score"))
    current_fund = _as_float(current.get("fundamentals_score"))
    quality_delta = None if entry_quality is None or current_quality is None else round(current_quality - entry_quality, 2)
    fundamentals_delta = None if entry_fund is None or current_fund is None else round(current_fund - entry_fund, 2)

    reasons: list[str] = []
    if thesis_failed:
        state = PositionResearchState.THESIS_BROKEN
        reasons.append("explicit thesis/fundamental failure evidence is active")
    elif stop_adding:
        state = PositionResearchState.STOP_ADDING
        reasons.append("new accumulation blocked by current value-trap/evidence-quality gate")
    elif fundamentals_delta is not None and fundamentals_delta <= -15:
        state = PositionResearchState.EXIT_REVIEW
        reasons.append("fundamentals deteriorated materially versus frozen entry snapshot")
    elif quality_delta is not None and quality_delta <= -15:
        state = PositionResearchState.EXIT_REVIEW
        reasons.append("business quality deteriorated materially versus frozen entry snapshot")
    elif trend_condition == "BEARISH":
        state = PositionResearchState.HOLD_WATCH
        reasons.append("trend evidence is broadly bearish; thesis remains separate")
    elif bool(current.get("add_eligible")):
        state = PositionResearchState.ADD_ELIGIBLE
        reasons.append("current evidence explicitly permits additional staged accumulation")
    else:
        state = PositionResearchState.HOLD
        reasons.append("no hard thesis deterioration or accumulation block detected")

    if pnl_pct is not None:
        reasons.append(f"price vs cost basis: {pnl_pct:+.2f}%")
    if trend_condition == "BULLISH":
        reasons.append("trend evidence is broadly constructive")

    return {
        "symbol": inp.symbol.upper(),
        "state": state.value,
        "reasons": reasons,
        "cost_basis": cost,
        "current_price": price,
        "pnl_pct": pnl_pct,
        "trend_condition": trend_condition,
        "quality_delta": quality_delta,
        "fundamentals_delta": fundamentals_delta,
        "entry_level": entry.get("entry_level") or entry.get("level"),
        "entry_timestamp": entry.get("timestamp") or entry.get("entry_timestamp"),
        "price_alone_breaks_thesis": False,
        "execution": "MANUAL_ONLY",
        "read_only": True,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
