"""Read-only cohort attribution for the DAY_TRADING PAPER journal.

This module describes preserved evidence. It never changes strategy parameters,
orders, sizing, exits, promotion state, or live-capital permissions.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable

from app.services.edge_diagnostics import load_paper_closes_safe


def _r(row: Dict[str, Any]) -> float:
    return float(row.get("net_pnl_r", row.get("R_multiple", 0.0)) or 0.0)


def _summary(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    items = list(rows)
    values = [_r(row) for row in items]
    n = len(values)
    return {
        "sample_size": n,
        "total_r": round(sum(values), 4),
        "expectancy_r": round(sum(values) / n, 4) if n else None,
        "win_rate": round(sum(value > 0 for value in values) / n, 4) if n else None,
    }


def _group(rows: list[Dict[str, Any]], key_fn) -> list[Dict[str, Any]]:
    groups: dict[str, list[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(key_fn(row) or "UNKNOWN")].append(row)
    return [
        {"cohort": key, **_summary(items)}
        for key, items in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    ]


def build_day_trading_cohort_diagnostics(rows: list[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "title": "ATLAS DAY TRADING PAPER COHORT DIAGNOSTICS",
        "overall": _summary(rows),
        "by_strategy": _group(rows, lambda row: row.get("strategy")),
        "by_side": _group(rows, lambda row: row.get("side")),
        "by_regime": _group(rows, lambda row: row.get("regime_normalized") or row.get("regime")),
        "by_execution_model": _group(
            rows, lambda row: (row.get("features") or {}).get("paper_execution_model_version")
        ),
        "by_exit_reason": _group(rows, lambda row: row.get("exit_reason")),
        "interpretation_only": True,
        "strategy_action": None,
        "threshold_change": None,
        "sizing_change": None,
        "execution_change": None,
        "promotion_allowed": False,
        "historical_evidence_rewritten": False,
        "execution": "READ_ONLY_PAPER_RESEARCH",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def day_trading_cohort_diagnostics() -> Dict[str, Any]:
    rows, malformed, _counts = load_paper_closes_safe()
    report = build_day_trading_cohort_diagnostics(rows)
    report["coverage"] = {
        "finite_closed_records": len(rows),
        "malformed_records": len(malformed),
        "durable_source": "DAY_TRADING_PAPER_JOURNAL",
    }
    return report
