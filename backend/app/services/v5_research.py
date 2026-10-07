"""Descriptive V5 research diagnostics for the frozen perp strategy.

This module does not optimize thresholds, generate orders, or unlock live capital.
It summarizes where the existing paper strategy is losing so future challenger
research can be evaluated out-of-sample instead of tuned to the same sample.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Iterable


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0, "expectancy_r": None, "winrate": None, "profit_factor": None, "zero_mfe_loss_rate": None}
    pnl = [_f(r.get("net_pnl_r")) for r in rows]
    wins = [x for x in pnl if x > 0]
    losses = [x for x in pnl if x < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    losing_rows = [r for r in rows if _f(r.get("net_pnl_r")) < 0]
    zero_mfe_losses = [r for r in losing_rows if _f(r.get("mfe_r")) <= 0]
    return {
        "n": len(rows),
        "expectancy_r": round(mean(pnl), 4),
        "winrate": round(len(wins) / len(rows), 4),
        "profit_factor": round(gross_win / gross_loss, 4) if gross_loss > 0 else None,
        "avg_mfe_r": round(mean([_f(r.get("mfe_r")) for r in rows]), 4),
        "avg_mae_r": round(mean([_f(r.get("mae_r")) for r in rows]), 4),
        "zero_mfe_loss_rate": round(len(zero_mfe_losses) / len(losing_rows), 4) if losing_rows else 0.0,
    }


def build_v5_research_report(closed_rows: Iterable[dict[str, Any]], *, recent_n: int = 30) -> dict[str, Any]:
    rows = [dict(r) for r in closed_rows if isinstance(r, dict)]
    side_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    regime_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    score_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        side_groups[str(row.get("side") or "UNKNOWN").upper()].append(row)
        regime = str(row.get("regime_normalized") or row.get("regime") or "UNKNOWN").upper()
        regime_groups[regime].append(row)
        score = _f(row.get("signal_score"), -1.0)
        if score < 0:
            bucket = "UNKNOWN"
        elif score < 60:
            bucket = "LT60"
        elif score < 70:
            bucket = "60_69"
        elif score < 80:
            bucket = "70_79"
        else:
            bucket = "80_PLUS"
        score_groups[bucket].append(row)

    recent = rows[-max(1, int(recent_n)) :] if rows else []
    prior = rows[: max(0, len(rows) - len(recent))]
    recent_summary = _summary(recent)
    prior_summary = _summary(prior)
    deterioration = None
    if recent_summary["expectancy_r"] is not None and prior_summary["expectancy_r"] is not None:
        deterioration = round(float(recent_summary["expectancy_r"]) - float(prior_summary["expectancy_r"]), 4)

    return {
        "domain": "HYPERLIQUID_PERPS",
        "mode": "RESEARCH_DIAGNOSTICS_ONLY",
        "strategy_frozen": True,
        "closed_trades": len(rows),
        "overall": _summary(rows),
        "recent": recent_summary,
        "prior": prior_summary,
        "recent_minus_prior_expectancy_r": deterioration,
        "by_side": {k: _summary(v) for k, v in sorted(side_groups.items())},
        "by_regime": {k: _summary(v) for k, v in sorted(regime_groups.items())},
        "by_score_bucket": {k: _summary(v) for k, v in sorted(score_groups.items())},
        "research_questions": [
            "Do losing trades show zero favorable excursion immediately after entry?",
            "Does performance deteriorate outside directional trend regimes?",
            "Do higher signal-score buckets actually outperform lower buckets?",
            "Does recent expectancy differ materially from the earlier sample?",
        ],
        "retuning_allowed": False,
        "live_capital_allowed": False,
        "note": "Descriptive only. Use these diagnostics to design a separately tested challenger; do not retune V4 thresholds to this same sample.",
    }
