"""High-conviction Quality Dips gate.

Research-only. The 25% figure is a minimum recovery-runway hurdle back to the
prior high, not a profit forecast or guarantee. Atlas never places Robinhood orders.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

MIN_RECOVERY_RUNWAY_PCT = 25.0
MIN_QUALITY_SCORE = 65
MAX_BOTTOM_RISK = 40
MIN_OPPORTUNITY_SCORE = 75
MIN_VALUATION_SCORE = 70
MIN_FUNDAMENTALS_SCORE = 70


def recovery_runway_pct(drawdown: Optional[float]) -> Optional[float]:
    """Return % upside from current price back to the prior high.

    Example: -20% drawdown => 25% recovery runway. This is arithmetic, not
    expected return and not evidence the prior high will be revisited.
    """
    if drawdown is None:
        return None
    try:
        dd = float(drawdown)
    except (TypeError, ValueError):
        return None
    off = abs(dd)
    if off <= 0 or off >= 1:
        return None
    return round((off / (1.0 - off)) * 100.0, 1)


def from_quality_tape(row: Dict[str, Any], prep: Dict[str, Any]) -> Dict[str, Any]:
    """Gate DM alerts from the live Quality Dips tape."""
    dd = row.get("drawdown")
    if dd is None and row.get("pct_from_high") is not None:
        try:
            dd = -abs(float(row["pct_from_high"])) / 100.0
        except (TypeError, ValueError):
            dd = None
    runway = recovery_runway_pct(dd)
    thesis = str(row.get("thesis") or "UNKNOWN").upper()
    evidence = str(row.get("evidence") or "UNKNOWN").upper()
    action = str(prep.get("action") or "").upper()
    quality = int(prep.get("quality_score") or 0)
    falling = int(prep.get("bottom_risk") or 100)
    trap = bool(prep.get("trap"))

    reasons = []
    if action != "ACCUMULATE": reasons.append("not in ACCUMULATE state")
    if thesis != "STRONG": reasons.append("thesis is not STRONG")
    if evidence not in {"HIGH", "MEDIUM"}: reasons.append("evidence below MEDIUM")
    if quality < MIN_QUALITY_SCORE: reasons.append(f"quality score below {MIN_QUALITY_SCORE}")
    if falling > MAX_BOTTOM_RISK: reasons.append(f"still-falling risk above {MAX_BOTTOM_RISK}")
    if trap: reasons.append("trap/falling-knife flag active")
    if runway is None or runway < MIN_RECOVERY_RUNWAY_PCT:
        reasons.append(f"recovery runway below {MIN_RECOVERY_RUNWAY_PCT:.0f}%")

    eligible = not reasons
    return {
        "high_conviction": eligible,
        "dm_notify": eligible,
        "recovery_runway_pct": runway,
        "target_hurdle_pct": MIN_RECOVERY_RUNWAY_PCT,
        "label": "A+ QUALITY DIP" if eligible else "NOT A+ YET",
        "gate_reasons": reasons,
        "ladder": prep.get("ladder") or [],
        "note": "25% is a screening hurdle based on recovery to the prior high, not a promised return.",
    }


def from_research_board(row: Dict[str, Any], *, stance: str) -> Dict[str, Any]:
    """Gate the persisted investment board using stronger quality evidence."""
    drawdown = dict(row.get("drawdown") or {})
    dd = drawdown.get("current_drawdown")
    runway = recovery_runway_pct(dd)
    components = dict(row.get("components") or {})
    thesis = str(row.get("thesis") or "UNKNOWN").upper()
    evidence = str(row.get("evidence_quality") or "UNKNOWN").upper()
    asset_type = str(row.get("asset_type") or "UNKNOWN").upper()
    opp = float(row.get("opportunity_score") or 0)
    valuation = float(components.get("valuation") or 0)
    fundamentals = float(components.get("fundamentals") or 0)

    reasons = []
    if asset_type != "STOCK": reasons.append("A+ company alerts are stock-only")
    if stance != "ACCUMULATE": reasons.append("readiness gate is not ACCUMULATE")
    if thesis not in {"STRONG", "INTACT"}: reasons.append("thesis is not intact")
    if evidence not in {"HIGH", "MEDIUM"}: reasons.append("evidence below MEDIUM")
    if opp < MIN_OPPORTUNITY_SCORE: reasons.append(f"opportunity score below {MIN_OPPORTUNITY_SCORE}")
    if valuation < MIN_VALUATION_SCORE: reasons.append(f"valuation score below {MIN_VALUATION_SCORE}")
    if fundamentals < MIN_FUNDAMENTALS_SCORE: reasons.append(f"fundamentals score below {MIN_FUNDAMENTALS_SCORE}")
    if runway is None or runway < MIN_RECOVERY_RUNWAY_PCT:
        reasons.append(f"recovery runway below {MIN_RECOVERY_RUNWAY_PCT:.0f}%")

    eligible = not reasons
    return {
        "high_conviction": eligible,
        "recovery_runway_pct": runway,
        "target_hurdle_pct": MIN_RECOVERY_RUNWAY_PCT,
        "label": "A+ QUALITY DIP" if eligible else "NOT A+ YET",
        "gate_reasons": reasons,
        "note": "A+ means Atlas' quality/value/readiness gates passed; it does not guarantee a 25% gain.",
    }
