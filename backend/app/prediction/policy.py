"""Permanent prediction-market safety and strategy policy.

This module contains Atlas invariants that must be enforced independently of any
provider-side filters.  Prediction markets remain PAPER/research-only until a
separate future live-capital gate is explicitly designed and approved.
"""
from __future__ import annotations

from typing import Any

POLICY_VERSION = "prediction-single-market-pre-event-v1"

MAX_CONCURRENT_PREDICTION_POSITIONS = 1
SINGLE_MARKET_ONLY = True
COMBOS_ALLOWED = False
PARLAYS_ALLOWED = False
MULTIVARIATE_ALLOWED = False
STACKING_ALLOWED = False
PRE_EVENT_ONLY = True
MUST_EXIT_BEFORE_EVENT_START = True
HOLD_THROUGH_EVENT_START = False
HOLD_TO_SETTLEMENT = False
LIVE_EXECUTION = False
LIVE_CAPITAL_ALLOWED = False
AUTOMATIC_REAL_MONEY_EXECUTION = False


def is_multivariate_market(row: dict[str, Any]) -> bool:
    """Return True only from explicit provider multivariate metadata.

    Do not infer combo status from a title string when Kalshi exposes canonical
    multivariate fields directly.
    """
    collection = str(row.get("mve_collection_ticker") or "").strip()
    legs = row.get("mve_selected_legs")
    return bool(collection) or (isinstance(legs, list) and len(legs) > 0)


def policy_snapshot() -> dict[str, Any]:
    return {
        "version": POLICY_VERSION,
        "single_market_only": SINGLE_MARKET_ONLY,
        "max_concurrent_prediction_positions": MAX_CONCURRENT_PREDICTION_POSITIONS,
        "combos_allowed": COMBOS_ALLOWED,
        "parlays_allowed": PARLAYS_ALLOWED,
        "multivariate_allowed": MULTIVARIATE_ALLOWED,
        "stacking_allowed": STACKING_ALLOWED,
        "pre_event_only": PRE_EVENT_ONLY,
        "must_exit_before_event_start": MUST_EXIT_BEFORE_EVENT_START,
        "hold_through_event_start": HOLD_THROUGH_EVENT_START,
        "hold_to_settlement": HOLD_TO_SETTLEMENT,
        "live_execution": LIVE_EXECUTION,
        "live_capital_allowed": LIVE_CAPITAL_ALLOWED,
        "automatic_real_money_execution": AUTOMATIC_REAL_MONEY_EXECUTION,
    }
