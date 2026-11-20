"""Quality Dips V2 patient-capital research policy.

This module is intentionally NOT wired into the production Quality Dips board yet.
It defines the next isolated research cycle without rewriting the closed Atlas evidence
record or enabling brokerage execution.

The upside hurdle is a screening requirement, never a promised return. A candidate
must still pass quality, valuation, thesis-integrity, evidence and value-trap gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


MIN_TARGET_UPSIDE_PCT = 29.0
PREFERRED_TARGET_UPSIDE_PCT = 50.0


class PatientCapitalState(str, Enum):
    WATCH = "WATCH"
    ACCUMULATION = "ACCUMULATION"
    DEEP_VALUE = "DEEP_VALUE"
    GENERATIONAL = "GENERATIONAL"
    THESIS_BROKEN = "THESIS_BROKEN"


@dataclass(frozen=True)
class UpsideWindow:
    entry_price: float
    conservative_value: Optional[float]
    base_value: Optional[float]
    optimistic_value: Optional[float]


def upside_pct(entry_price: float, target_price: Optional[float]) -> Optional[float]:
    """Arithmetic upside from entry to a valuation target; not an expected return."""
    try:
        entry = float(entry_price)
        target = None if target_price is None else float(target_price)
    except (TypeError, ValueError):
        return None
    if entry <= 0 or target is None or target <= 0:
        return None
    return round(((target / entry) - 1.0) * 100.0, 2)


def required_entry_price(target_price: float, required_upside_pct: float = MIN_TARGET_UPSIDE_PCT) -> Optional[float]:
    """Highest entry price that mathematically leaves the requested upside to target."""
    try:
        target = float(target_price)
        hurdle = float(required_upside_pct)
    except (TypeError, ValueError):
        return None
    if target <= 0 or hurdle <= -100:
        return None
    return round(target / (1.0 + hurdle / 100.0), 2)


def valuation_window(window: UpsideWindow) -> dict[str, Optional[float]]:
    return {
        "conservative_upside_pct": upside_pct(window.entry_price, window.conservative_value),
        "base_upside_pct": upside_pct(window.entry_price, window.base_value),
        "optimistic_upside_pct": upside_pct(window.entry_price, window.optimistic_value),
    }


def patient_state(
    *,
    thesis_intact: bool,
    value_trap: bool,
    quality_score: float,
    valuation_score: float,
    fundamentals_score: float,
    drawdown_percentile: Optional[float],
    conservative_upside_pct: Optional[float],
    base_upside_pct: Optional[float],
    evidence_quality: str,
) -> tuple[PatientCapitalState, list[str]]:
    """Research-only V2 classification contract.

    GENERATIONAL is deliberately rare and requires extreme drawdown plus exceptional
    quality/fundamentals/valuation and >=50% conservative normalization upside.
    """
    reasons: list[str] = []
    evidence = str(evidence_quality or "UNKNOWN").upper()

    if not thesis_intact:
        return PatientCapitalState.THESIS_BROKEN, ["thesis integrity failed"]
    if value_trap:
        return PatientCapitalState.WATCH, ["value-trap/falling-knife gate active"]
    if evidence not in {"HIGH", "MEDIUM"}:
        return PatientCapitalState.WATCH, ["evidence below MEDIUM"]
    if min(float(quality_score), float(fundamentals_score)) < 70:
        return PatientCapitalState.WATCH, ["business quality/fundamentals below V2 floor"]
    if float(valuation_score) < 70:
        return PatientCapitalState.WATCH, ["valuation margin of safety below V2 floor"]
    if conservative_upside_pct is None or conservative_upside_pct < MIN_TARGET_UPSIDE_PCT:
        return PatientCapitalState.WATCH, [f"conservative upside below {MIN_TARGET_UPSIDE_PCT:.0f}% patience hurdle"]

    ddp = None if drawdown_percentile is None else float(drawdown_percentile)
    if (
        conservative_upside_pct >= PREFERRED_TARGET_UPSIDE_PCT
        and float(quality_score) >= 90
        and float(fundamentals_score) >= 90
        and float(valuation_score) >= 90
        and ddp is not None
        and ddp >= 95
        and evidence == "HIGH"
    ):
        return PatientCapitalState.GENERATIONAL, ["rare V2 generational evidence stack satisfied"]

    if (
        conservative_upside_pct >= 40
        and float(quality_score) >= 80
        and float(fundamentals_score) >= 80
        and float(valuation_score) >= 80
        and ddp is not None
        and ddp >= 85
    ):
        return PatientCapitalState.DEEP_VALUE, ["deep-value evidence stack satisfied"]

    if base_upside_pct is not None and base_upside_pct >= MIN_TARGET_UPSIDE_PCT:
        return PatientCapitalState.ACCUMULATION, ["patient accumulation hurdle satisfied"]

    reasons.append("wait for a larger margin of safety")
    return PatientCapitalState.WATCH, reasons


POLICY_METADATA = {
    "cycle": "QUALITY_DIPS_V2_PATIENT_CAPITAL",
    "wired_to_production": False,
    "execution": "MANUAL_ONLY",
    "live_capital_allowed": False,
    "automatic_real_money_execution": False,
    "minimum_upside_hurdle_pct": MIN_TARGET_UPSIDE_PCT,
    "preferred_generational_upside_hurdle_pct": PREFERRED_TARGET_UPSIDE_PCT,
    "guaranteed_return": False,
}
