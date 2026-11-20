"""Read-only Quality Dips V2 evidence adapter.

Maps existing investment research rows into the isolated V2 patient-capital policy.
It never mutates legacy scoring, plans, positions, or brokerage state.

The adapter is deliberately tolerant of partial evidence. Missing normalization-value
inputs remain UNKNOWN rather than being fabricated. Trend fields are surfaced for the
future active-position monitor but do not yet create sell/hold instructions.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.investment.quality_dips_v2 import UpsideWindow, patient_state, valuation_window


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _component(row: Dict[str, Any], name: str) -> Optional[float]:
    components = dict(row.get("components") or {})
    return _as_float(components.get(name))


def _drawdown_percentile(row: Dict[str, Any]) -> Optional[float]:
    drawdown = dict(row.get("drawdown") or {})
    return _as_float(drawdown.get("percentile") or drawdown.get("historical_percentile"))


def _normalization_values(row: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Read normalization values if present; never infer or fabricate them."""
    value = dict(row.get("normalization_value") or row.get("valuation_window") or {})
    return {
        "conservative": _as_float(value.get("conservative") or value.get("conservative_value")),
        "base": _as_float(value.get("base") or value.get("base_value")),
        "optimistic": _as_float(value.get("optimistic") or value.get("optimistic_value")),
    }


def _thesis_intact(row: Dict[str, Any]) -> bool:
    thesis = str(row.get("thesis") or "UNKNOWN").upper()
    classification = str(row.get("classification") or "").upper()
    return thesis in {"STRONG", "INTACT"} and classification != "THESIS_BROKEN"


def _value_trap(row: Dict[str, Any]) -> bool:
    flags = dict(row.get("flags") or {})
    return bool(
        row.get("value_trap")
        or row.get("trap")
        or flags.get("value_trap")
        or flags.get("falling_knife")
    )


def _trend_snapshot(row: Dict[str, Any]) -> Dict[str, Any]:
    """Surface existing trend evidence without manufacturing signals.

    Phase 2 only transports evidence. A later active-position monitor will interpret
    these fields against a frozen entry snapshot and cost basis.
    """
    trend = dict(row.get("trend") or row.get("trend_analysis") or {})
    return {
        "short_term": trend.get("short_term"),
        "intermediate_term": trend.get("intermediate_term"),
        "long_term": trend.get("long_term"),
        "momentum": trend.get("momentum"),
        "relative_strength": trend.get("relative_strength"),
        "sector_regime": trend.get("sector_regime"),
        "market_regime": trend.get("market_regime"),
        "source": trend.get("source"),
        "as_of": trend.get("as_of"),
    }


def adapt_research_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Project one existing investment research row into the V2 research contract."""
    price = _as_float(row.get("quote_trigger_price") or row.get("quote_price") or row.get("price"))
    values = _normalization_values(row)
    upside = {
        "conservative_upside_pct": None,
        "base_upside_pct": None,
        "optimistic_upside_pct": None,
    }
    if price is not None and price > 0:
        upside = valuation_window(
            UpsideWindow(
                entry_price=price,
                conservative_value=values["conservative"],
                base_value=values["base"],
                optimistic_value=values["optimistic"],
            )
        )

    quality = _component(row, "quality")
    if quality is None:
        quality = _component(row, "business_quality")
    if quality is None:
        quality = _as_float(row.get("quality_score"))

    fundamentals = _component(row, "fundamentals")
    valuation = _component(row, "valuation")
    evidence = str(row.get("evidence_quality") or row.get("evidence") or "UNKNOWN").upper()

    required_missing = []
    for name, value in (
        ("price", price),
        ("quality", quality),
        ("fundamentals", fundamentals),
        ("valuation", valuation),
        ("conservative_normalization_value", values["conservative"]),
        ("base_normalization_value", values["base"]),
    ):
        if value is None:
            required_missing.append(name)

    state = "WATCH"
    state_reasons = ["V2 evidence incomplete"]
    if not required_missing:
        classified, state_reasons = patient_state(
            thesis_intact=_thesis_intact(row),
            value_trap=_value_trap(row),
            quality_score=float(quality),
            valuation_score=float(valuation),
            fundamentals_score=float(fundamentals),
            drawdown_percentile=_drawdown_percentile(row),
            conservative_upside_pct=upside["conservative_upside_pct"],
            base_upside_pct=upside["base_upside_pct"],
            evidence_quality=evidence,
        )
        state = classified.value

    return {
        "symbol": str(row.get("symbol") or "").upper(),
        "timestamp": row.get("timestamp"),
        "price": price,
        "research_price": row.get("research_price", row.get("price")),
        "evidence_quality": evidence,
        "thesis": str(row.get("thesis") or "UNKNOWN").upper(),
        "thesis_intact": _thesis_intact(row),
        "value_trap": _value_trap(row),
        "quality_score": quality,
        "fundamentals_score": fundamentals,
        "valuation_score": valuation,
        "drawdown_percentile": _drawdown_percentile(row),
        "normalization_value": values,
        **upside,
        "patient_state": state,
        "state_reasons": state_reasons,
        "missing_v2_evidence": required_missing,
        "trend": _trend_snapshot(row),
        "legacy_classification": row.get("classification"),
        "legacy_opportunity_score": row.get("opportunity_score"),
        "execution": "MANUAL_ONLY",
        "read_only": True,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def adapt_research_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [adapt_research_row(row) for row in rows if isinstance(row, dict)]
