"""Why a name is not GENERATIONAL. Recorded on every evaluation, including rejects."""

from __future__ import annotations

from typing import List, Tuple

from app.investment.enums import EvidenceQuality, InvestmentAlertState, ThesisState
from app.investment.research_models import ResearchRecord

QUALIFIED_STATES = {
    InvestmentAlertState.ACCUMULATION,
    InvestmentAlertState.DEEP_VALUE,
    InvestmentAlertState.GENERATIONAL_OPPORTUNITY,
}


def is_qualified(rec: ResearchRecord) -> bool:
    return rec.classification in QUALIFIED_STATES


def blocking_factors(rec: ResearchRecord) -> List[str]:
    """All relevant reasons this is not a generational opportunity (and extra rejects)."""
    factors: List[str] = []
    if rec.classification is InvestmentAlertState.THESIS_BROKEN or rec.thesis is ThesisState.BROKEN:
        factors.append("Thesis BROKEN")
    if rec.thesis is ThesisState.UNDER_PRESSURE:
        factors.append("Thesis UNDER_PRESSURE")
    if rec.thesis is ThesisState.DAMAGED:
        factors.append("Thesis DAMAGED")
    if rec.thesis is ThesisState.UNKNOWN:
        factors.append("Thesis UNKNOWN")
    if rec.evidence_quality in (EvidenceQuality.INSUFFICIENT, EvidenceQuality.UNKNOWN):
        factors.append(f"Evidence quality {rec.evidence_quality.value}")
    elif rec.evidence_quality is EvidenceQuality.LOW:
        factors.append("Evidence quality LOW")
    elif rec.evidence_quality is EvidenceQuality.MEDIUM:
        # not automatically a hard fail, but recorded for later FN/FP research
        factors.append("Evidence quality MEDIUM")
    if rec.components.valuation is None:
        factors.append("Valuation missing")
    elif rec.components.valuation < 70:
        factors.append("Valuation insufficient")
    if rec.components.fundamentals is None:
        factors.append("Fundamentals missing")
    elif rec.components.fundamentals < 70:
        factors.append("Fundamentals insufficient")
    if rec.components.risk is not None and rec.components.risk < 50:
        factors.append("Risk not acceptable")
    for b in rec.generational_blockers:
        if b not in factors:
            factors.append(b)
    # de-dupe, keep order
    seen = set()
    out: List[str] = []
    for f in factors:
        if f in seen:
            continue
        seen.add(f)
        out.append(f)
    return out


def first_blocker(rec: ResearchRecord) -> str:
    if rec.classification is InvestmentAlertState.GENERATIONAL_OPPORTUNITY:
        return ""
    fac = blocking_factors(rec)
    if fac:
        return fac[0]
    return f"classified {rec.classification.value} — not generational"


def blocker_bucket(text: str) -> str:
    t = (text or "").lower()
    if "valuation" in t:
        return "Valuation"
    if "fundamental" in t:
        return "Fundamentals"
    if "evidence" in t:
        return "Evidence"
    if "thesis" in t:
        return "Thesis"
    if "risk" in t:
        return "Risk"
    if "drawdown" in t or "dislocation" in t:
        return "Drawdown"
    if "coverage" in t or "252" in t or "history" in t or "bars" in t:
        return "History"
    return "Other"


def blocking_pair(rec: ResearchRecord) -> Tuple[str, List[str]]:
    fac = blocking_factors(rec)
    first = first_blocker(rec)
    return first, fac
