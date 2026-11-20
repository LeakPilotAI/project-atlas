"""Read-only Quality Dips freshness/readiness projection.

This module summarizes existing dataset quality controls. It does not score assets,
change investment classifications, build ladders, or place brokerage orders.
"""
from __future__ import annotations

from typing import Any, Mapping


QUALITY_CHECKS = (
    "provider_reliability",
    "fundamental_completeness",
    "valuation_completeness",
    "historical_price_coverage",
    "point_in_time_integrity",
    "look_ahead",
)


def build_freshness_proof(readiness: Mapping[str, Any]) -> dict[str, Any]:
    checks = readiness.get("checks") if isinstance(readiness, Mapping) else {}
    checks = checks if isinstance(checks, Mapping) else {}
    selected: dict[str, dict[str, Any]] = {}
    for name in QUALITY_CHECKS:
        raw = checks.get(name)
        if isinstance(raw, Mapping):
            selected[name] = {
                "ok": bool(raw.get("ok")),
                "detail": str(raw.get("detail") or ""),
            }
        else:
            selected[name] = {"ok": False, "detail": "check unavailable"}

    failed = [name for name, row in selected.items() if not row["ok"]]
    return {
        "domain": "EQUITY_INVESTMENT",
        "mode": "DATA_QUALITY_ONLY",
        "dataset_status": str(readiness.get("status") or "NOT READY"),
        "checks": selected,
        "quality_gate_passed": not failed,
        "failed_checks": failed,
        "strategy_frozen": True,
        "live_capital_allowed": False,
        "note": (
            "Freshness/readiness is a data-quality gate only. Passing it does not establish "
            "predictive edge or authorize live capital."
        ),
    }
