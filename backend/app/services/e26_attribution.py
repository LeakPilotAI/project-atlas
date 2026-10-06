"""Execution 26 read-only stop-tail and current adaptive LONG attribution."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict

from app.services.edge_diagnostics import load_paper_closes_safe

STRATEGY = "perp_setup_auto_v2_resting_limit"
CURRENT_MODEL = "paper-exec-v2-conservative-gap-target+adaptive-exit-v1"


def _r(row: Dict[str, Any]) -> float:
    return float(row.get("net_pnl_r", row.get("R_multiple", 0.0)) or 0.0)


def _summary(rows: list[Dict[str, Any]]) -> Dict[str, Any]:
    vals = [_r(r) for r in rows]
    n = len(vals)
    return {"sample_size": n, "total_r": round(sum(vals), 4),
            "expectancy_r": round(sum(vals) / n, 4) if n else None,
            "win_rate": round(sum(v > 0 for v in vals) / n, 4) if n else None}


def _features(row: Dict[str, Any]) -> Dict[str, Any]:
    return row.get("features") or {}


def _model(row: Dict[str, Any]) -> str:
    return str(_features(row).get("paper_execution_model_version") or "UNKNOWN")


def _overshoot(row: Dict[str, Any]) -> float | None:
    if row.get("exit_reason") != "SETUP_STOP":
        return None
    risk = abs(float(row.get("risk_price") or 0.0))
    if not risk:
        return None
    stop = float(row.get("initial_stop") or 0.0)
    exit_price = float(row.get("actual_exit_price") or 0.0)
    return (stop - exit_price) / risk if row.get("side") == "LONG" else (exit_price - stop) / risk


def _bucket_num(value: Any, cuts: tuple[float, ...], labels: tuple[str, ...]) -> str:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "UNKNOWN"
    for cut, label in zip(cuts, labels):
        if x < cut:
            return label
    return labels[-1]


def _group(rows: list[Dict[str, Any]], fn: Callable[[Dict[str, Any]], str]) -> list[Dict[str, Any]]:
    groups: dict[str, list[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(fn(row) or "UNKNOWN")].append(row)
    return [{"cohort": k, **_summary(v)} for k, v in
            sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))]


def _time_cohort(row: Dict[str, Any]) -> str:
    raw = row.get("entry_timestamp") or row.get("signal_timestamp") or row.get("timestamp")
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return "UNKNOWN"


def _overshoot_bucket(row: Dict[str, Any]) -> str:
    x = _overshoot(row)
    if x is None: return "NOT_SETUP_STOP"
    if x <= 0.25: return "<=0.25R"
    if x <= 1.0: return "0.25-1.00R"
    if x <= 2.0: return "1.00-2.00R"
    if x <= 5.0: return "2.00-5.00R"
    return ">5.00R"


def _stop_tail_report(rows: list[Dict[str, Any]]) -> Dict[str, Any]:
    stops = [r for r in rows if _overshoot(r) is not None]
    negative_total = sum(_r(r) for r in rows if _r(r) < 0)
    groups = _group(stops, _overshoot_bucket)
    for group in groups:
        members = [r for r in stops if _overshoot_bucket(r) == group["cohort"]]
        neg = sum(_r(r) for r in members if _r(r) < 0)
        group["share_of_all_negative_r"] = round(neg / negative_total, 4) if negative_total else None
    return {
        "setup_stops": _summary(stops),
        "all_negative_r": round(negative_total, 4),
        "by_overshoot_bucket": groups,
        "by_execution_model_side": _group(stops, lambda r: f"{_model(r)}|{r.get('side') or 'UNKNOWN'}"),
        "by_time_day": _group(stops, _time_cohort),
        "by_symbol": _group(stops, lambda r: str(r.get("symbol") or "UNKNOWN")),
        "by_volatility": _group(stops, lambda r: _bucket_num(
            _features(r).get("volatility_pct"), (0.15, 0.30, 0.60, float("inf")),
            ("<0.15", "0.15-0.29", "0.30-0.59", ">=0.60"))),
    }


def _current_long_report(rows: list[Dict[str, Any]]) -> Dict[str, Any]:
    current = [r for r in rows if r.get("side") == "LONG" and _model(r) == CURRENT_MODEL]
    return {
        "overall": _summary(current),
        "by_score": _group(current, lambda r: _bucket_num(
            r.get("signal_score"), (65, 70, 75, 80, float("inf")),
            ("<65", "65-69", "70-74", "75-79", ">=80"))),
        "by_momentum": _group(current, lambda r: _bucket_num(
            _features(r).get("momentum_pct"), (-0.25, 0.0, 0.25, 0.50, float("inf")),
            ("<-0.25", "-0.25--0.01", "0.00-0.24", "0.25-0.49", ">=0.50"))),
        "by_trend": _group(current, lambda r: _bucket_num(
            _features(r).get("trend_pct"), (-0.50, 0.0, 0.50, 1.0, float("inf")),
            ("<-0.50", "-0.50--0.01", "0.00-0.49", "0.50-0.99", ">=1.00"))),
        "by_volatility": _group(current, lambda r: _bucket_num(
            _features(r).get("volatility_pct"), (0.15, 0.30, 0.60, float("inf")),
            ("<0.15", "0.15-0.29", "0.30-0.59", ">=0.60"))),
        "by_mfe": _group(current, lambda r: _bucket_num(
            r.get("mfe_r"), (0.25, 0.50, 1.0, 1.8, float("inf")),
            ("<0.25R", "0.25-0.49R", "0.50-0.99R", "1.00-1.79R", ">=1.80R"))),
        "by_mae": _group(current, lambda r: _bucket_num(
            r.get("mae_r"), (0.50, 1.0, 1.5, float("inf")),
            ("<0.50R", "0.50-0.99R", "1.00-1.49R", ">=1.50R"))),
        "by_exit_family": _group(current, lambda r: str(r.get("exit_reason") or "UNKNOWN")),
    }


def build_e26_attribution(all_rows: list[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [r for r in all_rows if r.get("strategy") == STRATEGY]
    return {
        "title": "ATLAS EXECUTION 26 STOP-TAIL + CURRENT LONG ATTRIBUTION",
        "strategy": STRATEGY,
        "overall": _summary(rows),
        "stop_tail_attribution": _stop_tail_report(rows),
        "current_adaptive_long": _current_long_report(rows),
        "current_execution_model": CURRENT_MODEL,
        "exploratory_cohorts_not_promotion_evidence": True,
        "counterfactual_fills_rewritten": False,
        "unknown_metadata_backfilled": False,
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


def e26_attribution() -> Dict[str, Any]:
    rows, malformed, _counts = load_paper_closes_safe()
    report = build_e26_attribution(rows)
    report["coverage"] = {"all_finite_closed_records": len(rows),
                          "v2_setup_records": report["overall"]["sample_size"],
                          "malformed_records": len(malformed),
                          "durable_source": "DAY_TRADING_PAPER_JOURNAL"}
    return report
