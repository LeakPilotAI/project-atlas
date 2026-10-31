"""Hard Quality Dips V2 evidence gate.

Research-only. This gate sits between the read-only evidence adapter and later V2
classification/entry planning. It fails closed on stale/weak/broken evidence and never
places brokerage orders or mutates legacy scoring.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

MIN_EVIDENCE_QUALITY = {"MEDIUM", "HIGH"}
MAX_RESEARCH_AGE_DAYS = 45.0
MAX_TREND_AGE_DAYS = 14.0


def _parse_dt(value: Any) -> Optional[datetime]:
    if value in {None, ""}:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _age_days(value: Any, *, now: Optional[datetime] = None) -> Optional[float]:
    dt = _parse_dt(value)
    if dt is None:
        return None
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    return max(0.0, (ref.astimezone(timezone.utc) - dt).total_seconds() / 86400.0)


def evaluate_v2_gate(evidence: Dict[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Fail-closed decision gate for Quality Dips V2 research evidence."""
    blockers: list[str] = []
    cautions: list[str] = []

    thesis = str(evidence.get("thesis") or "UNKNOWN").upper()
    thesis_intact = bool(evidence.get("thesis_intact"))
    value_trap = bool(evidence.get("value_trap"))
    evidence_quality = str(evidence.get("evidence_quality") or "UNKNOWN").upper()
    missing = list(evidence.get("missing_v2_evidence") or [])

    if thesis in {"BROKEN", "FAILED"} or not thesis_intact:
        blockers.append("thesis integrity failed")
    if value_trap:
        blockers.append("value-trap/falling-knife gate active")
    if evidence_quality not in MIN_EVIDENCE_QUALITY:
        blockers.append("evidence quality below MEDIUM")
    if missing:
        blockers.append("required V2 evidence missing: " + ", ".join(sorted(str(x) for x in missing)))

    research_age = _age_days(evidence.get("timestamp"), now=now)
    if research_age is None:
        blockers.append("research timestamp unavailable")
    elif research_age > MAX_RESEARCH_AGE_DAYS:
        blockers.append(f"research evidence stale beyond {MAX_RESEARCH_AGE_DAYS:.0f} days")

    trend = dict(evidence.get("trend") or {})
    trend_as_of = trend.get("as_of")
    trend_age = _age_days(trend_as_of, now=now)
    if trend_as_of in {None, ""}:
        cautions.append("trend timestamp unavailable")
    elif trend_age is not None and trend_age > MAX_TREND_AGE_DAYS:
        cautions.append(f"trend evidence older than {MAX_TREND_AGE_DAYS:.0f} days")

    # Trend is deliberately not a thesis breaker by itself. Weak trend can block
    # additional buying later, but cannot convert an intact business thesis to broken.
    trend_values = {
        str(trend.get("short_term") or "UNKNOWN").upper(),
        str(trend.get("intermediate_term") or "UNKNOWN").upper(),
        str(trend.get("long_term") or "UNKNOWN").upper(),
    }
    if trend_values & {"DOWN", "BEARISH", "WEAK"}:
        cautions.append("weak/bearish price trend requires patience; trend alone is not thesis failure")

    passed = not blockers
    return {
        "gate_passed": passed,
        "status": "ELIGIBLE_FOR_V2_CLASSIFICATION" if passed else "BLOCKED",
        "blockers": blockers,
        "cautions": cautions,
        "research_age_days": None if research_age is None else round(research_age, 2),
        "trend_age_days": None if trend_age is None else round(trend_age, 2),
        "execution": "MANUAL_ONLY",
        "read_only": True,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
