"""Evaluation status is not the same as investment classification."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from app.investment.enums import DataQuality, EvaluationStatus, EvidenceQuality, InvestmentAlertState
from app.investment.research_models import ResearchRecord
from app.investment.snapshot import InvestmentSnapshot

RATE_CODES = {"RATE_LIMIT"}
PROVIDER_CODES = {
    "TIMEOUT",
    "HTTP_401",
    "PROVIDER_ERROR",
    "PROVIDER_FAIL",
    "PRICE_FAIL",
    "FUND_FAIL",
    "VAL_FAIL",
    "HISTORY_FAIL",
    "SCAN_EXCEPTION",
    "DEPENDENCY",
}


def _codes(failures: Iterable[dict]) -> List[str]:
    out: List[str] = []
    for f in failures or []:
        if isinstance(f, dict) and f.get("code"):
            out.append(str(f["code"]))
    return out


def _has_conflict(snap: InvestmentSnapshot) -> bool:
    items = [snap.price, *snap.fundamentals.values(), *snap.valuation.values()]
    return any(getattr(mv, "quality", None) is DataQuality.CONFLICTING for mv in items)


def classify_evaluation(
    snap: InvestmentSnapshot,
    rec: ResearchRecord,
    *,
    failures: Optional[List[dict]] = None,
) -> Tuple[EvaluationStatus, str]:
    """Map provider/data state onto EvaluationStatus. Does not change classification."""
    fails = list(failures if failures is not None else snap.failures)
    codes = _codes(fails)
    usable_price = snap.price.is_usable()

    if any(c in RATE_CODES for c in codes) and not usable_price:
        return EvaluationStatus.RATE_LIMITED, "rate limited; no usable price substitute"
    if any(c in PROVIDER_CODES for c in codes) and not usable_price:
        why = next((f.get("message") or f.get("code") for f in fails if f.get("code") in PROVIDER_CODES), "provider unavailable")
        return EvaluationStatus.PROVIDER_ERROR, f"fundamental/price provider unavailable ({why})"
    if _has_conflict(snap):
        return EvaluationStatus.CONFLICTING_DATA, "conflicting values present — not repaired"
    if rec.evidence_quality in (EvidenceQuality.INSUFFICIENT, EvidenceQuality.UNKNOWN) or not usable_price:
        missing = ", ".join(rec.missing_critical[:6]) or "critical fields missing"
        return EvaluationStatus.INSUFFICIENT_DATA, missing
    if snap.price.quality is DataQuality.STALE:
        return EvaluationStatus.STALE_DATA, "price is STALE versus freshness policy"
    if rec.classification is InvestmentAlertState.NO_ACTION:
        reason = (rec.generational_blockers[0] if rec.generational_blockers else None) or "valuation not attractive / no setup"
        return EvaluationStatus.VALID_NO_ACTION, reason
    return EvaluationStatus.VALID, f"classified {rec.classification.value} on sufficient data"


def is_valid_evaluation(status: EvaluationStatus) -> bool:
    return status in (EvaluationStatus.VALID, EvaluationStatus.VALID_NO_ACTION)
