"""Read-only forward/OOS and cost robustness analysis for paper trades.

This module never changes strategy thresholds, never places orders, and never unlocks
live capital. It describes how a fixed paper strategy behaves across chronology, side,
regime, rolling windows, and simple additional execution-cost stress scenarios.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from app.analytics.regime import normalize_regime
from app.services.paper_validation import metrics, uncertainty


def _chrono_key(row: dict[str, Any]) -> str:
    return str(row.get("exit_timestamp") or row.get("entry_timestamp") or row.get("signal_timestamp") or "")


def _sorted_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted([dict(r) for r in rows if isinstance(r, dict)], key=_chrono_key)


def _r(row: dict[str, Any]) -> float:
    for key in ("net_pnl_r", "R_multiple", "hypothetical_r"):
        try:
            if row.get(key) is not None:
                return float(row[key])
        except (TypeError, ValueError):
            pass
    return 0.0


def _cost_adjust(rows: list[dict[str, Any]], extra_cost_r: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    cost = max(0.0, float(extra_cost_r))
    for row in rows:
        clone = dict(row)
        clone["net_pnl_r"] = _r(row) - cost
        out.append(clone)
    return out


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    m = metrics(rows)
    u = uncertainty(rows)
    return {
        "n": m["n"],
        "winrate": m["winrate"],
        "expectancy_r": m["expectancy"],
        "expectancy_ci95": u.get("expectancy_ci95"),
        "profit_factor": m.get("profit_factor"),
        "total_r": m["total_r"],
        "max_drawdown_r": m["max_drawdown_r"],
        "longest_losing_streak": m["longest_losing_streak"],
    }


def chronological_holdout(rows: Iterable[dict[str, Any]], *, holdout_fraction: float = 0.30) -> dict[str, Any]:
    ordered = _sorted_rows(rows)
    n = len(ordered)
    if n < 2:
        return {"n": n, "train": _summary(ordered), "holdout": _summary([]), "holdout_fraction": 0.0, "status": "INSUFFICIENT"}
    frac = min(0.50, max(0.10, float(holdout_fraction)))
    holdout_n = max(1, int(round(n * frac)))
    split = max(1, n - holdout_n)
    train, holdout = ordered[:split], ordered[split:]
    tr, ho = _summary(train), _summary(holdout)
    status = "INSUFFICIENT"
    if len(holdout) >= 30:
        status = "HOLDOUT_NEGATIVE" if float(ho["expectancy_r"]) <= 0 else "HOLDOUT_POSITIVE"
    return {
        "n": n,
        "holdout_fraction": round(len(holdout) / n, 4),
        "train": tr,
        "holdout": ho,
        "expectancy_delta_r": round(float(ho["expectancy_r"]) - float(tr["expectancy_r"]), 4),
        "status": status,
        "note": "Chronological split only; no thresholds are fit or changed from either partition.",
    }


def rolling_expectancy(rows: Iterable[dict[str, Any]], *, window: int = 30, step: int = 10) -> dict[str, Any]:
    ordered = _sorted_rows(rows)
    w = max(10, int(window))
    s = max(1, int(step))
    windows: list[dict[str, Any]] = []
    for start in range(0, max(0, len(ordered) - w + 1), s):
        chunk = ordered[start:start + w]
        summary = _summary(chunk)
        windows.append({"start_trade": start + 1, "end_trade": start + len(chunk), **summary})
    recent = windows[-1] if windows else None
    prior = windows[-2] if len(windows) >= 2 else None
    decay_flag = False
    if recent and prior:
        decay_flag = float(recent["expectancy_r"]) < 0 and float(prior["expectancy_r"]) > 0
    return {
        "window": w,
        "step": s,
        "windows": windows,
        "recent_expectancy_r": None if recent is None else recent["expectancy_r"],
        "edge_decay_flag": decay_flag,
        "note": "Rolling windows are descriptive edge-decay diagnostics, not a retuning signal.",
    }


def side_and_regime_splits(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    ordered = _sorted_rows(rows)
    sides: dict[str, list[dict[str, Any]]] = defaultdict(list)
    regimes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ordered:
        sides[str(row.get("side") or "UNKNOWN").upper()].append(row)
        raw_regime = row.get("regime")
        if raw_regime is None and isinstance(row.get("features"), dict):
            raw_regime = row["features"].get("regime")
        try:
            regime = str(normalize_regime(raw_regime) or "UNKNOWN")
        except Exception:
            regime = str(raw_regime or "UNKNOWN").upper()
        regimes[regime].append(row)
    return {
        "side": {name: _summary(chunk) for name, chunk in sorted(sides.items())},
        "regime": {name: _summary(chunk) for name, chunk in sorted(regimes.items())},
        "note": "Subgroup results are descriptive and can be unstable at small sample sizes.",
    }


def cost_stress(rows: Iterable[dict[str, Any]], *, scenarios_r: tuple[float, ...] = (0.0, 0.02, 0.05, 0.10)) -> dict[str, Any]:
    ordered = _sorted_rows(rows)
    scenarios: list[dict[str, Any]] = []
    for extra in scenarios_r:
        summary = _summary(_cost_adjust(ordered, float(extra)))
        scenarios.append({"extra_cost_r_per_trade": round(float(extra), 4), **summary})
    breakeven = next((s["extra_cost_r_per_trade"] for s in scenarios if float(s["expectancy_r"]) <= 0), None)
    return {
        "scenarios": scenarios,
        "first_nonpositive_expectancy_cost_r": breakeven,
        "note": "Extra-cost stress is applied per closed trade on top of recorded net R; it does not model venue-specific fills exactly.",
    }


def build_oos_cost_report(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    ordered = _sorted_rows(rows)
    holdout = chronological_holdout(ordered)
    rolling = rolling_expectancy(ordered)
    splits = side_and_regime_splits(ordered)
    costs = cost_stress(ordered)
    recent = rolling.get("recent_expectancy_r")
    holdout_exp = float(holdout.get("holdout", {}).get("expectancy_r") or 0.0)
    flags: list[str] = []
    if holdout.get("status") == "HOLDOUT_NEGATIVE":
        flags.append("chronological_holdout_nonpositive")
    if rolling.get("edge_decay_flag"):
        flags.append("rolling_expectancy_decay")
    if recent is not None and float(recent) <= 0:
        flags.append("recent_window_nonpositive")
    if costs.get("first_nonpositive_expectancy_cost_r") == 0.0:
        flags.append("baseline_expectancy_nonpositive")
    status = "INSUFFICIENT"
    if len(ordered) >= 50:
        status = "CAUTION" if flags else "PROMISING_RESEARCH_ONLY"
    return {
        "domain": "HYPERLIQUID_PERPS",
        "mode": "PAPER_RESEARCH_ONLY",
        "strategy_frozen": True,
        "closed_trades": len(ordered),
        "holdout": holdout,
        "rolling": rolling,
        "splits": splits,
        "cost_stress": costs,
        "edge_decay_flags": flags,
        "evidence_status": status,
        "live_capital_allowed": False,
        "note": "This report cannot unlock live capital and does not optimize strategy settings.",
    }
