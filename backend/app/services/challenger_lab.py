"""Atlas V6 Challenger Lab — isolated, research-only hypotheses.

This module never changes production gates, execution, sizing, or live-capital state.
It evaluates pre-declared slices of the existing PAPER population so Atlas can decide
which hypotheses deserve prospective validation. PAPER and SHADOW remain separate.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Sequence

from app.analytics.regime import normalize_regime
from app.services.paper_validation import metrics, uncertainty

LAB_VERSION = "v6"
PRODUCTION_GATES = {"rsi_long": 28.0, "rsi_short": 72.0, "extension_pct": 1.4, "min_rr": 1.8}
MIN_RESEARCH_N = 40


def _features(row: Dict[str, Any]) -> Dict[str, Any]:
    return row.get("features") if isinstance(row.get("features"), dict) else {}


def _num(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _regime(row: Dict[str, Any]) -> str:
    return normalize_regime(row.get("regime_normalized") or row.get("regime"))


def _extension(row: Dict[str, Any]) -> Optional[float]:
    f = _features(row)
    return _num(f.get("ext_pct") if f.get("ext_pct") is not None else row.get("extension_pct"))


def _quality(row: Dict[str, Any]) -> Optional[float]:
    f = _features(row)
    raw = f.get("qscore") if f.get("qscore") is not None else row.get("signal_score")
    return _num(raw)


def _slice(rows: Sequence[Dict[str, Any]], predicate: Callable[[Dict[str, Any]], bool]) -> Dict[str, Any]:
    selected = [r for r in rows if predicate(r)]
    m = metrics(selected)
    return {
        **m,
        "uncertainty": uncertainty(selected),
        "research_sample_sufficient": len(selected) >= MIN_RESEARCH_N,
        "prospective_validated": False,
        "promoted": False,
    }


def challenger_report(*, paper: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if paper is None:
        from app.services.edge_diagnostics import load_paper_closes_safe
        rows, malformed, counts = load_paper_closes_safe()
    else:
        rows = list(paper)
        malformed, counts = [], {"closed": len(rows)}

    trend = lambda r: _regime(r) in {"TREND_UP", "TREND_DOWN"}
    ext3 = lambda r: (_extension(r) is not None and _extension(r) >= 3.0)
    q85 = lambda r: (_quality(r) is not None and _quality(r) >= 85.0)

    challengers = {
        "trend_regime": {
            "hypothesis": "TREND_UP/TREND_DOWN may be more stable than RANGE/LOW_VOLATILITY.",
            "selection": "regime in TREND_UP,TREND_DOWN",
            "metrics": _slice(rows, trend),
        },
        "extension_3pct": {
            "hypothesis": "Larger dislocations may improve entry quality.",
            "selection": "extension >= 3.0%",
            "metrics": _slice(rows, ext3),
        },
        "quality_85": {
            "hypothesis": "Higher setup quality may reduce weak entries.",
            "selection": "quality score >= 85",
            "metrics": _slice(rows, q85),
        },
        "trend_extension_quality": {
            "hypothesis": "Trend regime + >=3% extension + >=85 quality may identify a stronger interaction.",
            "selection": "trend regime AND extension >= 3.0% AND quality >= 85",
            "metrics": _slice(rows, lambda r: trend(r) and ext3(r) and q85(r)),
        },
    }

    return {
        "ok": True,
        "title": "ATLAS V6 CHALLENGER LAB",
        "version": LAB_VERSION,
        "mode": "RESEARCH_ONLY",
        "production_gates": {**PRODUCTION_GATES, "unchanged": True},
        "production_strategy_modified": False,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
        "paper_n": len(rows),
        "journal_counts": counts,
        "malformed_count": len(malformed),
        "baseline": {**metrics(rows), "uncertainty": uncertainty(rows)},
        "challengers": challengers,
        "promotion_policy": {
            "automatic_promotion": False,
            "requires_prospective_forward_sample": True,
            "requires_positive_expectancy_after_costs": True,
            "requires_risk_review": True,
            "note": "Historical superiority only nominates a hypothesis. It never changes production gates.",
        },
        "exit_challenger": {
            "status": "DIAGNOSTIC_ONLY",
            "next": "Build point-in-time mark-event replay before simulating alternate exits.",
            "reason": "MFE/MAE summaries alone cannot prove a realizable alternate exit without path-aware replay.",
        },
        "shadow_discovery": {
            "status": "SEPARATE_POPULATION",
            "combined_with_paper": False,
            "next": "Analyze feature interactions without averaging SHADOW and PAPER performance.",
        },
        "disclaimer": "Research only. No profitability claim and no permission for live capital.",
    }
