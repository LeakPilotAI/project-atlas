"""Quality Dips V2 normalization-value model.

Research-only, read-only valuation normalizer for the patient-capital cycle.
It consumes explicit valuation evidence with provenance and never invents fair value.
All outputs remain decision-support only; brokerage execution is manual.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from typing import Any

from app.investment.freshness import VALUATION_TTL_SECONDS

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
    as_of: str | None = None
    confidence: str | None = None
    note: str | None = None


def _as_float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        out = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return out if isfinite(out) and out > 0 else None


def _fresh_as_of(value: Any, now: datetime) -> bool:
    """Recheck original estimate time; collection time cannot renew a target."""
    if not isinstance(value, str):
        return False
    try:
        stamp = datetime.fromisoformat(value)
        # An explicitly dated disclosure has day precision, conservatively UTC
        # midnight. An undated/naive time is not authenticated by this helper.
        if stamp.tzinfo is None:
            if len(value) != 10:
                return False
            stamp = stamp.replace(tzinfo=UTC)
        return 0 <= (now - stamp).total_seconds() <= VALUATION_TTL_SECONDS
    except (ValueError, TypeError, OverflowError):
        return False


def _normalize_source(raw: dict[str, Any]) -> ValueEstimate | None:
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


def normalize_sources(sources: Iterable[dict[str, Any]], *, now: datetime | None = None) -> list[ValueEstimate]:
    if now is not None and (not isinstance(now, datetime) or now.utcoffset() is None):
        raise ValueError("AWARE_VALUATION_EVALUATION_TIME_REQUIRED")
    out: list[ValueEstimate] = []
    for raw in sources:
        if not isinstance(raw, dict):
            continue
        if now is not None and (raw.get("availability", True) is not True
                                or raw.get("quality", "FRESH") != "FRESH"):
            continue
        est = _normalize_source(raw)
        if est is not None and (now is None or _fresh_as_of(est.as_of, now)):
            out.append(est)
    return out


def build_normalization_window(sources: Iterable[dict[str, Any]], *, now: datetime | None = None) -> dict[str, Any]:
    """Build conservative/base/optimistic values from explicit source estimates only.

    With fewer than 3 valid source estimates, the window is incomplete and does not
    fabricate missing scenarios. With 3+ estimates, sorted order defines the low,
    median, and high scenarios. Provenance is returned alongside every value.
    """
    # Historical display remains supported when no evaluation time is supplied.
    # Current explicit-source readers must supply now; this is freshness, NOT
    # issuer authentication or financial command admission.
    estimates = sorted(normalize_sources(sources, now=now), key=lambda e: e.value)
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


def from_research_row(row: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Extract explicit valuation-source evidence from a research row."""
    sources = row.get("valuation_sources") or row.get("normalization_sources") or []
    if not isinstance(sources, list):
        sources = []
    window = build_normalization_window(sources, now=now)
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
