"""Read-only causal attribution for perp_setup_auto_v2_resting_limit PAPER evidence.

Preserves strategy/execution-model boundaries and reports only fields recorded in
the durable journal. It has no authority to mutate trading behavior.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Callable, Dict

from app.services.edge_diagnostics import load_paper_closes_safe

STRATEGY = "perp_setup_auto_v2_resting_limit"


def _r(row: Dict[str, Any]) -> float:
    return float(row.get("net_pnl_r", row.get("R_multiple", 0.0)) or 0.0)


def _summary(rows: list[Dict[str, Any]]) -> Dict[str, Any]:
    values = [_r(row) for row in rows]
    n = len(values)
    return {
        "sample_size": n,
        "total_r": round(sum(values), 4),
        "expectancy_r": round(sum(values) / n, 4) if n else None,
        "win_rate": round(sum(value > 0 for value in values) / n, 4) if n else None,
    }


def _group(rows: list[Dict[str, Any]], fn: Callable[[Dict[str, Any]], str]) -> list[Dict[str, Any]]:
    groups: dict[str, list[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(fn(row) or "UNKNOWN")].append(row)
    return [{"cohort": key, **_summary(items)}
            for key, items in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))]


def _model(row: Dict[str, Any]) -> str:
    return str((row.get("features") or {}).get("paper_execution_model_version") or "UNKNOWN")


def _score_bucket(row: Dict[str, Any]) -> str:
    score = float(row.get("signal_score") or 0.0)
    lo = int(score // 5) * 5
    return f"{lo:02d}-{lo + 4:02d}"


def _mfe_bucket(row: Dict[str, Any]) -> str:
    value = float(row.get("mfe_r") or 0.0)
    if value < 0.25: return "<0.25R"
    if value < 0.5: return "0.25-0.49R"
    if value < 1.0: return "0.50-0.99R"
    if value < 1.8: return "1.00-1.79R"
    return ">=1.80R"


def _mae_bucket(row: Dict[str, Any]) -> str:
    value = float(row.get("mae_r") or 0.0)
    if value < 0.5: return "<0.50R"
    if value < 1.0: return "0.50-0.99R"
    if value < 1.5: return "1.00-1.49R"
    return ">=1.50R"


def _stop_overshoot(rows: list[Dict[str, Any]]) -> Dict[str, Any]:
    values: list[float] = []
    for row in rows:
        if row.get("exit_reason") != "SETUP_STOP":
            continue
        risk = abs(float(row.get("risk_price") or 0.0))
        if not risk:
            continue
        stop = float(row.get("initial_stop") or 0.0)
        exit_price = float(row.get("actual_exit_price") or 0.0)
        side = str(row.get("side") or "")
        overshoot = (stop - exit_price) / risk if side == "LONG" else (exit_price - stop) / risk
        values.append(overshoot)
    ordered = sorted(values)
    def pct(p: float) -> float | None:
        if not ordered: return None
        return round(ordered[min(len(ordered)-1, int((len(ordered)-1)*p))], 4)
    return {
        "sample_size": len(values),
        "average_r_beyond_initial_stop": round(sum(values)/len(values), 4) if values else None,
        "median_r_beyond_initial_stop": round(median(values), 4) if values else None,
        "p90_r_beyond_initial_stop": pct(0.90),
        "max_r_beyond_initial_stop": round(max(values), 4) if values else None,
    }


def build_v2_setup_attribution(all_rows: list[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [row for row in all_rows if row.get("strategy") == STRATEGY]
    return {
        "title": "ATLAS V2 SETUP PAPER CAUSAL ATTRIBUTION",
        "strategy": STRATEGY,
        "overall": _summary(rows),
        "by_execution_model_and_side": _group(rows, lambda r: f"{_model(r)}|{r.get('side') or 'UNKNOWN'}"),
        "by_score_and_side": _group(rows, lambda r: f"{r.get('side') or 'UNKNOWN'}|{_score_bucket(r)}"),
        "by_mfe_bucket": _group(rows, _mfe_bucket),
        "by_mae_bucket": _group(rows, _mae_bucket),
        "by_exit_family": _group(rows, lambda r: str(r.get("exit_reason") or "UNKNOWN")),
        "setup_stop_overshoot": {
            "all": _stop_overshoot(rows),
            "long": _stop_overshoot([r for r in rows if r.get("side") == "LONG"]),
            "short": _stop_overshoot([r for r in rows if r.get("side") == "SHORT"]),
        },
        "selection_execution_exit_not_causally_resolved": True,
        "unknown_metadata_backfilled": False,
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


def v2_setup_attribution() -> Dict[str, Any]:
    rows, malformed, _counts = load_paper_closes_safe()
    report = build_v2_setup_attribution(rows)
    report["coverage"] = {
        "all_finite_closed_records": len(rows),
        "v2_setup_records": report["overall"]["sample_size"],
        "malformed_records": len(malformed),
        "durable_source": "DAY_TRADING_PAPER_JOURNAL",
    }
    return report
