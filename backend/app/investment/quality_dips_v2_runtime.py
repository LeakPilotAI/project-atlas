"""Runtime evidence enrichment for Quality Dips V2.1 operational repair.

Uses only evidence Atlas already persisted: scored components, explicit provider analyst
price targets, and stored point-in-time daily OHLCV. Missing evidence stays missing.
No brokerage actions and no invented normalization values.
"""
from __future__ import annotations

from statistics import median
from typing import Any

from app.investment.history import load_bars


def _float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        x = float(value)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _measured_value(raw: Any) -> tuple[float | None, str | None]:
    if not isinstance(raw, dict) or not bool(raw.get("availability")):
        return None, None
    value = _float(raw.get("value"))
    if value is None or value <= 0:
        return None, None
    as_of = raw.get("effective_timestamp") or raw.get("timestamp") or raw.get("retrieved_at")
    return value, None if as_of is None else str(as_of)


def _quality_score(row: dict[str, Any]) -> float | None:
    """Conservative business-quality composite from already-scored independent pillars."""
    components = dict(row.get("components") or {})
    vals = [
        _float(components.get("fundamentals")),
        _float(components.get("balance_sheet")),
        _float(components.get("cash_flow")),
        _float(components.get("thesis_integrity")),
    ]
    present = [v for v in vals if v is not None]
    if len(present) < 2:
        return None
    # Median prevents one missing/noisy subcomponent from manufacturing A+ quality,
    # while still requiring multiple independent business-quality pillars.
    return round(float(median(present)), 2)


def _valuation_sources(row: dict[str, Any]) -> list[dict[str, Any]]:
    snap = dict(row.get("input_snapshot") or {})
    valuation = dict(snap.get("valuation") or {})
    sources: list[dict[str, Any]] = []
    for key, label in (
        ("target_low_price", "analyst target low"),
        ("target_mean_price", "analyst target mean"),
        ("target_high_price", "analyst target high"),
    ):
        value, as_of = _measured_value(valuation.get(key))
        if value is not None:
            sources.append({
                "value": value,
                "provenance": "ANALYST_CONSENSUS",
                "as_of": as_of,
                "confidence": "EXTERNAL_CONSENSUS",
                "note": label + "; provider-supplied, not an Atlas guarantee",
            })
    return sources


def _trend(row: dict[str, Any]) -> dict[str, Any]:
    symbol = str(row.get("symbol") or "").upper().strip()
    if not symbol:
        return {}
    bars = load_bars(symbol)
    clean = [(b.session_date, _float(b.adjusted_close if b.adjusted_close is not None else b.close)) for b in bars]
    clean = [(d, p) for d, p in clean if d and p is not None and p > 0]
    if not clean:
        return {}
    closes = [p for _, p in clean]
    last = closes[-1]

    def ma(n: int) -> float | None:
        return None if len(closes) < n else sum(closes[-n:]) / n

    def label(n: int) -> str:
        avg = ma(n)
        if avg is None:
            return "UNKNOWN"
        band = 0.01
        if last > avg * (1 + band):
            return "UP"
        if last < avg * (1 - band):
            return "DOWN"
        return "NEUTRAL"

    momentum = None
    if len(closes) >= 64 and closes[-64] > 0:
        momentum = round((last / closes[-64] - 1.0) * 100.0, 2)
    return {
        "short_term": label(20),
        "intermediate_term": label(50),
        "long_term": label(200),
        "momentum": momentum,
        "relative_strength": None,
        "sector_regime": None,
        "market_regime": None,
        "source": "STORED_DAILY_OHLCV_MA_20_50_200",
        "as_of": clean[-1][0] + "T23:59:59+00:00",
    }


def enrich_research_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with V2-required runtime evidence when explicitly derivable."""
    out = dict(row)
    components = dict(out.get("components") or {})
    if components.get("quality") is None:
        quality = _quality_score(out)
        if quality is not None:
            components["quality"] = quality
            out["components"] = components
            out["quality_score_provenance"] = "MEDIAN_OF_SCORED_BUSINESS_PILLARS"

    if not out.get("valuation_sources") and not out.get("normalization_sources"):
        sources = _valuation_sources(out)
        if sources:
            out["valuation_sources"] = sources

    existing_trend = dict(out.get("trend") or out.get("trend_analysis") or {})
    if not existing_trend.get("as_of"):
        trend = _trend(out)
        if trend:
            out["trend"] = trend
    return out


def enrich_research_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_research_row(r) for r in rows if isinstance(r, dict)]
