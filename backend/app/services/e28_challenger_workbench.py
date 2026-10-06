"""Execution 28: outcome-blind Perps Setup V2 challenger definition.

Thresholds are derived only from pre-freeze PAPER open snapshots. Close/PnL,
MFE/MAE and exit fields are never read by the derivation path. The resulting
rule is frozen for forward PAPER comparison against the unchanged baseline.
"""
from __future__ import annotations

from math import isfinite
from statistics import median
from typing import Any, Dict, Iterable, List

from app.services.e27_preregistration import (
    BASELINE_EXECUTION_MODEL,
    BASELINE_STRATEGY,
    REGISTRY_VERSION,
)
from app.services.paper_journal import JOURNAL_PATH, iter_jsonl

WORKBENCH_VERSION = "perp-setup-v2-e28-workbench-v1"
CHALLENGER_VERSION = "perp-setup-v2-long-selection-v1"
FREEZE_START_UTC = "2026-10-06T03:28:53.4195759Z"
ALLOWED_OPEN_FIELDS = ("signal_score", "momentum_pct", "trend_pct", "volatility_pct")
FORBIDDEN_OUTCOME_FIELDS = (
    "pnl_r", "pnl_usd", "mfe_r", "mae_r", "exit_reason", "exit_price",
    "close_timestamp", "stop_overshoot_r", "realized_pnl",
)


def _num(value: Any) -> float | None:
    try:
        x=float(value)
        return x if isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _snapshot(row: Dict[str, Any]) -> Dict[str, Any]:
    f=row.get("features") if isinstance(row.get("features"),dict) else {}
    return {
        "trade_id": str(row.get("trade_id") or ""),
        "symbol": str(row.get("symbol") or "UNKNOWN"),
        "entry_timestamp": row.get("entry_timestamp") or row.get("signal_timestamp"),
        "signal_score": _num(row.get("signal_score")),
        "momentum_pct": _num(f.get("momentum_pct")),
        "trend_pct": _num(f.get("trend_pct")),
        "volatility_pct": _num(f.get("volatility_pct")),
    }


def eligible_derivation_open(row: Dict[str, Any]) -> bool:
    f=row.get("features") if isinstance(row.get("features"),dict) else {}
    ts=str(row.get("entry_timestamp") or row.get("signal_timestamp") or "")
    return (
        row.get("event")=="open"
        and str(row.get("trade_type") or "PAPER").upper()=="PAPER"
        and row.get("strategy")==BASELINE_STRATEGY
        and row.get("side")=="LONG"
        and f.get("paper_execution_model_version")==BASELINE_EXECUTION_MODEL
        and bool(ts)
        and ts < FREEZE_START_UTC
    )


def derive_outcome_blind_rule(opens: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    snapshots=[_snapshot(r) for r in opens if eligible_derivation_open(r)]
    coverage={k:sum(1 for s in snapshots if s[k] is not None) for k in ALLOWED_OPEN_FIELDS}
    complete=[s for s in snapshots if all(s[k] is not None for k in ALLOWED_OPEN_FIELDS)]
    if not complete:
        thresholds={"momentum_pct_min":None,"trend_pct_min":None}
        status="INSUFFICIENT_COMPLETE_OPEN_SNAPSHOTS"
    else:
        # Outcome-blind and deterministic: central split of the pre-freeze open population.
        thresholds={
            "momentum_pct_min":round(float(median(s["momentum_pct"] for s in complete)),6),
            "trend_pct_min":round(float(median(s["trend_pct"] for s in complete)),6),
        }
        status="FROZEN"
    return {
        "status":status,
        "derivation_open_count":len(snapshots),
        "complete_open_count":len(complete),
        "feature_coverage":coverage,
        "thresholds":thresholds,
        "rule":"LONG open qualifies iff all four registered features are present AND momentum_pct >= frozen median AND trend_pct >= frozen median.",
        "score_role":"required recorded covariate; not thresholded in v1",
        "volatility_role":"required recorded covariate; not thresholded in v1",
        "threshold_derivation":"median of pre-freeze complete PAPER open snapshots; no outcome optimization",
    }


def qualifies(snapshot: Dict[str, Any], thresholds: Dict[str, Any]) -> bool:
    vals={k:_num(snapshot.get(k)) for k in ALLOWED_OPEN_FIELDS}
    if any(vals[k] is None for k in ALLOWED_OPEN_FIELDS):
        return False
    m=thresholds.get("momentum_pct_min")
    t=thresholds.get("trend_pct_min")
    return m is not None and t is not None and vals["momentum_pct"] >= m and vals["trend_pct"] >= t


def e28_workbench(*, rows: Iterable[Dict[str, Any]] | None=None) -> Dict[str, Any]:
    source=list(iter_jsonl(JOURNAL_PATH)) if rows is None else list(rows)
    derivation=derive_outcome_blind_rule(source)
    return {
        "ok":True,
        "title":"ATLAS E28 PERPS SETUP V2 OUTCOME-BLIND CHALLENGER WORKBENCH",
        "workbench_version":WORKBENCH_VERSION,
        "challenger_version":CHALLENGER_VERSION,
        "parent_registry":REGISTRY_VERSION,
        "freeze_start_utc":FREEZE_START_UTC,
        "baseline":{"strategy":BASELINE_STRATEGY,"execution_model":BASELINE_EXECUTION_MODEL,"side":"LONG","frozen":True},
        "challenger_definition":derivation,
        "forward_membership":{
            "starts_at":FREEZE_START_UTC,
            "historical_rows_count_as_prospective":False,
            "membership_decidable_from_open_snapshot_only":True,
            "missing_any_registered_feature":"REJECT_FROM_CHALLENGER_ARM",
            "baseline_continues_concurrently":True,
        },
        "leakage_controls":{
            "derivation_event_type":"open_only",
            "allowed_fields":list(ALLOWED_OPEN_FIELDS),
            "forbidden_outcome_fields":list(FORBIDDEN_OUTCOME_FIELDS),
            "close_rows_read_for_threshold_derivation":False,
            "pnl_optimization":False,
            "mfe_mae_optimization":False,
            "exit_reason_optimization":False,
            "best_historical_bucket_selection":False,
        },
        "e27_acceptance_gate_unchanged":True,
        "production_strategy_modified":False,
        "strategy_action":None,
        "sizing_change":None,
        "execution_change":None,
        "automatic_promotion":False,
        "promotion_allowed":False,
        "execution":"PAPER_RESEARCH_ONLY",
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
    }