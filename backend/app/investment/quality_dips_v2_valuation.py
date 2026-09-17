"""Quality Dips V2 normalization-value model.

Research-only, read-only valuation normalizer for the patient-capital cycle.
It consumes explicit valuation evidence with provenance and never invents fair value.
All outputs remain decision-support only; brokerage execution is manual.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional


ALLOWED_PROVENANCE = {
    "HISTORICAL_MULTIPLE",
    "SECTOR_RELATIVE",
    "DCF",
    "ANALYST_CONSENSUS",
    "OWNER_EARNINGS",
    "MANUAL_RESEARCH",
}


@dataclass(frozen=True)
class ValueEstimate:
    value: float
    provenance: str
    as_of: Optional[str] = None
    confidence: Optional[str] = None
    note: Optional[str] = None


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out > 0 else None


def _normalize_source(raw: dict[str, Any]) -> Optional[ValueEstimate]:
    value = _as_float(raw.get("value") or raw.get("target") or raw.get("fair_value"))
    provenance = str(raw.get("provenance") or raw.get("method") or "").upper().strip()
    if value is None or provenance not in ALLOWED_PROVENANCE:
        return None
    return ValueEstimate(
        value=value,
        provenance=provenance,
        as_of=raw.get("as_of"),
        confidence=(str(raw.get("confidence")).upper() if raw.get("confidence") is not None else None),
        note=raw.get("note"),
    )


def normalize_sources(sources: Iterable[dict[str, Any]]) -> list[ValueEstimate]:
    out: list[ValueEstimate] = []
    for raw in sources:
        if not isinstance(raw, dict):
            continue
        est = _normalize_source(raw)
        if est is not None:
            out.append(est)
    return out


def build_normalization_window(sources: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build conservative/base/optimistic values from explicit source estimates only.

    With fewer than 3 valid source estimates, the window is incomplete and does not
    fabricate missing scenarios. With 3+ estimates, sorted order defines the low,
    median, and high scenarios. Provenance is returned alongside every value.
    """
    estimates = sorted(normalize_sources(sources), key=lambda e: e.value)
    if not estimates:
        return {
            "complete": False,
            "conservative": None,
            "base": None,
            "optimistic": None,
            "source_count": 0,
            "provenance": [],
            "execution": "MANUAL_ONLY",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        }

    base_idx = len(estimates) // 2
    conservative = estimates[0]
    optimistic = estimates[-1]
    base = estimates[base_idx]

    complete = len(estimates) >= 3
    return {
        "complete": complete,
        "conservative": conservative.value if complete else None,
        "base": base.value if complete else None,
        "optimistic": optimistic.value if complete else None,
        "source_count": len(estimates),
        "provenance": [
            {
                "value": e.value,
                "provenance": e.provenance,
                "as_of": e.as_of,
                "confidence": e.confidence,
                "note": e.note,
            }
            for e in estimates
        ],
        "method": "LOW_MEDIAN_HIGH_EXPLICIT_ESTIMATES" if complete else "INSUFFICIENT_EXPLICIT_ESTIMATES",
        "execution": "MANUAL_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def from_research_row(row: dict[str, Any]) -> dict[str, Any]:
    """Extract explicit valuation-source evidence from a research row."""
    sources = row.get("valuation_sources") or row.get("normalization_sources") or []
    if not isinstance(sources, list):
        sources = []
    window = build_normalization_window(sources)
    return {
        "symbol": str(row.get("symbol") or "").upper(),
        "timestamp": row.get("timestamp"),
        "normalization_value": {
            "conservative": window.get("conservative"),
            "base": window.get("base"),
            "optimistic": window.get("optimistic"),
        },
        "valuation_provenance": window.get("provenance") or [],
        "valuation_window_complete": bool(window.get("complete")),
        "valuation_source_count": int(window.get("source_count") or 0),
        "valuation_method": window.get("method"),
        "execution": "MANUAL_ONLY",
        "read_only": True,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
