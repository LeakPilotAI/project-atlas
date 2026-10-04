"""Read-only PAPER trade attribution and strategy scorecards.

This module explains what the durable journal can support without changing strategy,
orders, thresholds, exits, or live permissions. Attribution labels are evidence
descriptions, not causal claims. UNKNOWN is preferred to invented certainty.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.analytics.regime import normalize_regime
from app.services.edge_diagnostics import load_paper_closes_safe
from app.services.paper_validation import metrics

ATTRIBUTION_VERSION = "paper-attribution-v1"
SCORECARD_VERSION = "strategy-regime-scorecard-v1"

NON_PERFORMANCE_RESULTS = {"SESSION_ROLL", "INTERRUPTED"}


def _f(row: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        try:
            out = float(value)
        except (TypeError, ValueError):
            continue
        if out == out and abs(out) != float("inf"):
            return out
    return None


def _features(row: Dict[str, Any]) -> Dict[str, Any]:
    return row.get("features") if isinstance(row.get("features"), dict) else {}


def _cost_r(row: Dict[str, Any]) -> Optional[float]:
    gross = _f(row, "gross_pnl_r", "R_multiple")
    net = _f(row, "net_pnl_r")
    if gross is None or net is None:
        return None
    return max(0.0, gross - net)


def _hour_utc(row: Dict[str, Any]) -> Optional[int]:
    raw = row.get("entry_timestamp") or row.get("signal_timestamp")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).hour
    except (TypeError, ValueError):
        return None


def _strategy_version(row: Dict[str, Any]) -> str:
    feats = _features(row)
    for key in ("strategy_version", "policy_version"):
        value = row.get(key) or feats.get(key)
        if value:
            return str(value)
    execution = feats.get("paper_execution_model_version")
    strategy = str(row.get("strategy") or "UNKNOWN")
    return f"{strategy}|{execution or 'UNVERSIONED'}"


def attribute_trade(row: Dict[str, Any]) -> Dict[str, Any]:
    """Classify journal-supported trade symptoms without asserting hidden causality."""
    result = str(row.get("result") or "").upper()
    if result in NON_PERFORMANCE_RESULTS:
        return {
            "trade_id": row.get("trade_id"),
            "eligible": False,
            "primary": "NON_PERFORMANCE_RECORD",
            "observations": [],
            "unknown": False,
            "version": ATTRIBUTION_VERSION,
        }

    net = _f(row, "net_pnl_r", "R_multiple")
    gross = _f(row, "gross_pnl_r", "R_multiple")
    mfe = _f(row, "mfe_r")
    mae = _f(row, "mae_r")
    cost = _cost_r(row)
    observations: List[str] = []

    if net is None:
        return {
            "trade_id": row.get("trade_id"),
            "eligible": False,
            "primary": "EXECUTION_OR_DATA_ISSUE",
            "observations": ["MISSING_FINITE_NET_R"],
            "unknown": False,
            "version": ATTRIBUTION_VERSION,
        }

    # These labels describe recorded path/outcome evidence. They do not claim why
    # the market moved or that a different action would necessarily have profited.
    if net < 0 and (mfe is None or mfe < 0.25) and mae is not None and mae >= 0.75:
        observations.append("DIRECTION_OR_SIGNAL_FAILURE_PATTERN")
    if net <= 0 and mfe is not None and mfe >= 0.5:
        observations.append("POSITIVE_EXCURSION_NOT_CAPTURED")
    if net > 0 and mfe is not None and mfe >= net + 0.25:
        observations.append("PROFIT_GIVEBACK_PATTERN")
    if net < 0 and gross is not None and gross >= 0 and cost is not None and cost > 0:
        observations.append("COST_DRAG_FLIPPED_NONNEGATIVE_GROSS")
    elif cost is not None and cost >= 0.10:
        observations.append("MATERIAL_RECORDED_COST_DRAG")
    if net < 0 and result in {"STOP", "STOPPED", "SL", "STOP_LOSS"}:
        observations.append("STOP_EXIT_LOSS")
    if net < 0 and mfe is not None and mfe < 0.5:
        observations.append("TARGET_NOT_REACHED")
    if normalize_regime(row.get("regime_normalized") or row.get("regime")) == "UNKNOWN":
        observations.append("REGIME_UNKNOWN")
    if _hour_utc(row) is None:
        observations.append("ENTRY_TIME_UNKNOWN")

    if net < 0:
        if "COST_DRAG_FLIPPED_NONNEGATIVE_GROSS" in observations:
            primary = "COST_DRAG"
        elif "POSITIVE_EXCURSION_NOT_CAPTURED" in observations:
            primary = "EXIT_CAPTURE_PATTERN"
        elif "DIRECTION_OR_SIGNAL_FAILURE_PATTERN" in observations:
            primary = "SIGNAL_FAILURE_PATTERN"
        elif "STOP_EXIT_LOSS" in observations:
            primary = "STOP_EXIT_PATTERN"
        elif "TARGET_NOT_REACHED" in observations:
            primary = "TARGET_FAILURE_PATTERN"
        else:
            primary = "UNRESOLVED_NEGATIVE_EDGE"
    elif net > 0:
        primary = "PROFITABLE_OUTCOME"
    else:
        primary = "SCRATCH_OUTCOME"

    unknown = primary == "UNRESOLVED_NEGATIVE_EDGE"
    return {
        "trade_id": row.get("trade_id"),
        "symbol": row.get("symbol"),
        "side": row.get("side"),
        "strategy": row.get("strategy") or "UNKNOWN",
        "strategy_version": _strategy_version(row),
        "regime": normalize_regime(row.get("regime_normalized") or row.get("regime")),
        "net_pnl_r": net,
        "gross_pnl_r": gross,
        "cost_r": cost,
        "mfe_r": mfe,
        "mae_r": mae,
        "primary": primary,
        "observations": observations,
        "unknown": unknown,
        "eligible": True,
        "causation_established": False,
        "version": ATTRIBUTION_VERSION,
    }


def _scorecard(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    m = metrics(rows)
    attrs = [attribute_trade(row) for row in rows]
    primary = Counter(a["primary"] for a in attrs if a.get("eligible"))
    observations = Counter(
        label
        for a in attrs
        for label in a.get("observations", [])
        if a.get("eligible")
    )
    costs = [_cost_r(row) for row in rows]
    costs = [x for x in costs if x is not None]
    scratches = sum(
        bool(row.get("scratch")) or str(row.get("result") or "").upper() in {"BE", "SCRATCH"}
        for row in rows
    )
    return {
        **m,
        "scratches": scratches,
        "recorded_cost_r_total": round(sum(costs), 4) if costs else None,
        "recorded_cost_r_average": round(sum(costs) / len(costs), 4) if costs else None,
        "attribution_primary": dict(primary),
        "attribution_observations": dict(observations),
        "unresolved_negative_edge": primary.get("UNRESOLVED_NEGATIVE_EDGE", 0),
        "attribution_version": ATTRIBUTION_VERSION,
        "causation_established": False,
    }


def build_scorecards(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate immutable close rows by strategy/version/regime."""
    usable = [
        row for row in rows
        if str(row.get("result") or "").upper() not in NON_PERFORMANCE_RESULTS
    ]
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_strategy: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_regime: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for row in usable:
        strategy = str(row.get("strategy") or "UNKNOWN")
        version = _strategy_version(row)
        regime = normalize_regime(row.get("regime_normalized") or row.get("regime"))
        grouped[f"{strategy}::{version}::{regime}"].append(row)
        by_strategy[f"{strategy}::{version}"].append(row)
        by_regime[regime].append(row)

    return {
        "scorecard_version": SCORECARD_VERSION,
        "attribution_version": ATTRIBUTION_VERSION,
        "closed_performance_records": len(usable),
        "overall": _scorecard(usable),
        "by_strategy_version": {
            key: _scorecard(chunk) for key, chunk in sorted(by_strategy.items())
        },
        "by_regime": {
            key: _scorecard(chunk) for key, chunk in sorted(by_regime.items())
        },
        "by_strategy_version_regime": {
            key: _scorecard(chunk) for key, chunk in sorted(grouped.items())
        },
        "interpretation": {
            "attribution_is_causal": False,
            "thin_buckets_are_proof": False,
            "negative_evidence_preserved": True,
            "thresholds_modified": False,
            "production_strategy_modified": False,
        },
        "execution": "READ_ONLY_PAPER_RESEARCH",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def attribution_report() -> Dict[str, Any]:
    rows, malformed, counts = load_paper_closes_safe()
    attrs = [attribute_trade(row) for row in rows]
    return {
        "title": "ATLAS DAY TRADING PAPER ATTRIBUTION",
        "journal_counts": counts,
        "malformed_count": len(malformed),
        "trades": attrs,
        "scorecards": build_scorecards(rows),
        "rules": {
            "outcome_alone_proves_cause": False,
            "unknown_allowed": True,
            "macro_event_attribution": "UNKNOWN unless point-in-time event evidence is attached",
            "regime_mismatch_attribution": "descriptive bucket only; no causal label from regime alone",
        },
        "execution": "READ_ONLY_PAPER_RESEARCH",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
