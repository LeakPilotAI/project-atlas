"""Forward-only V5 challenger cohort for Hyperliquid perp paper research.

The challenger is intentionally *not* an execution strategy.  It labels future V4
paper closes with a predeclared research policy so Atlas can compare a prospective
subset against the unchanged V4 baseline.  Historical rows before the deployment
cutoff are never used as challenger evidence.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Iterable

# Locked before prospective collection.  Do not move this timestamp backward.
V5_CHALLENGER_FORWARD_START = "2026-09-11T08:30:00+00:00"
V5_MIN_SCORE = 80.0
V5_ALLOWED_REGIMES = frozenset({"TREND_UP", "TREND_DOWN"})


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if out.tzinfo is None:
            out = out.replace(tzinfo=timezone.utc)
        return out.astimezone(timezone.utc)
    except Exception:
        return None


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "expectancy_r": None,
            "winrate": None,
            "profit_factor": None,
            "total_r": 0.0,
        }
    pnl = [_f(row.get("net_pnl_r")) for row in rows]
    wins = [value for value in pnl if value > 0]
    losses = [value for value in pnl if value < 0]
    gross_loss = abs(sum(losses))
    return {
        "n": len(rows),
        "expectancy_r": round(mean(pnl), 4),
        "winrate": round(len(wins) / len(rows), 4),
        "profit_factor": round(sum(wins) / gross_loss, 4) if gross_loss > 0 else None,
        "total_r": round(sum(pnl), 4),
    }


def classify_v5_candidate(row: dict[str, Any]) -> tuple[bool, str]:
    """Apply the locked prospective challenger policy to one already-closed row."""
    score = _f(row.get("signal_score"), -1.0)
    if score < V5_MIN_SCORE:
        return False, "SCORE_BELOW_80"
    regime = str(row.get("regime_normalized") or row.get("regime") or "UNKNOWN").upper()
    if regime not in V5_ALLOWED_REGIMES:
        return False, "NON_TREND_REGIME"
    return True, "QUALIFIED"


def build_v5_challenger_report(
    closed_rows: Iterable[dict[str, Any]],
    *,
    forward_start_at: str = V5_CHALLENGER_FORWARD_START,
) -> dict[str, Any]:
    cutoff = _dt(forward_start_at)
    if cutoff is None:
        raise ValueError("forward_start_at must be an ISO-8601 timestamp")

    future: list[dict[str, Any]] = []
    rejected = Counter()
    challenger: list[dict[str, Any]] = []
    missing_timestamp = 0

    for raw in closed_rows:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        entered = _dt(row.get("entry_timestamp") or row.get("signal_timestamp"))
        if entered is None:
            missing_timestamp += 1
            continue
        if entered < cutoff:
            continue
        future.append(row)
        qualified, reason = classify_v5_candidate(row)
        if qualified:
            challenger.append(row)
        else:
            rejected[reason] += 1

    return {
        "domain": "HYPERLIQUID_PERPS",
        "mode": "FORWARD_SHADOW_COHORT_ONLY",
        "policy_locked": True,
        "forward_start_at": cutoff.isoformat(),
        "policy": {
            "minimum_signal_score": V5_MIN_SCORE,
            "allowed_regimes": sorted(V5_ALLOWED_REGIMES),
            "allowed_sides": ["LONG", "SHORT"],
            "uses_future_information": False,
        },
        "baseline_future": _summary(future),
        "challenger_future": _summary(challenger),
        "qualified_rate": round(len(challenger) / len(future), 4) if future else None,
        "rejected_reasons": dict(sorted(rejected.items())),
        "rows_missing_entry_timestamp": missing_timestamp,
        "minimum_evidence_target": 100,
        "evidence_status": "COLLECTING" if len(challenger) < 100 else "REVIEW_READY_NOT_LIVE_READY",
        "retuning_allowed": False,
        "changes_v4_execution": False,
        "live_capital_allowed": False,
        "note": (
            "Prospective shadow cohort only. The policy was locked after exploratory V5 diagnostics; "
            "pre-cutoff history is excluded from challenger evidence and V4 paper execution is unchanged."
        ),
    }
