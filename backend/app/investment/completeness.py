"""Data completeness diagnostic. Not an investment-confidence score."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.investment.enums import DataQuality, EvidenceQuality
from app.investment.models import MeasuredValue
from app.investment.snapshot import InvestmentSnapshot

# Twelve fields used only as a coverage diagnostic.
COMPLETENESS_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("price", "price"),
    ("revenue", "fundamentals"),
    ("earnings", "fundamentals"),
    ("eps", "fundamentals"),
    ("free_cash_flow", "fundamentals"),
    ("operating_cash_flow", "fundamentals"),
    ("cash", "fundamentals"),
    ("total_debt", "fundamentals"),
    ("market_cap", "fundamentals"),
    ("pe", "valuation"),
    ("ps", "valuation"),
    ("fcf_yield", "valuation"),
)

REQUIRED_N = len(COMPLETENESS_FIELDS)


def _usable(mv: Optional[MeasuredValue]) -> bool:
    return bool(mv is not None and mv.is_usable())


def _get(snap: InvestmentSnapshot, group: str, name: str) -> Optional[MeasuredValue]:
    if group == "price":
        return snap.price
    if group == "fundamentals":
        return snap.fundamentals.get(name)
    if group == "valuation":
        return snap.valuation.get(name)
    return None


def completeness_report(
    snap: InvestmentSnapshot,
    *,
    evidence: Optional[EvidenceQuality] = None,
) -> Dict[str, Any]:
    present: List[str] = []
    missing: List[str] = []
    qualities: Dict[str, str] = {}
    for name, group in COMPLETENESS_FIELDS:
        mv = _get(snap, group, name)
        q = DataQuality.MISSING.value
        if mv is not None:
            q = mv.quality.value if isinstance(mv.quality, DataQuality) else str(mv.quality)
        qualities[name] = q
        if _usable(mv):
            present.append(name)
        else:
            missing.append(name)
    n = len(present)
    return {
        "present": n,
        "required": REQUIRED_N,
        "label": f"{n} / {REQUIRED_N}",
        "missing": missing,
        "qualities": qualities,
        "evidence_quality": evidence.value if evidence is not None else None,
        "note": "Completeness is a diagnostic, not investment confidence.",
    }


def format_completeness(report: Dict[str, Any]) -> str:
    ev = report.get("evidence_quality") or "UNKNOWN"
    return f"Evidence Quality:\n{ev}\nRequired fields:\n{report.get('label')}"
