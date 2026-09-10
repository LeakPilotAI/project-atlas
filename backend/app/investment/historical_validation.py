"""Historical validation for Quality Dips research.

Read-only research diagnostics. Joins past observations to later look-ahead-protected
outcomes and measures whether research strata corresponded to subsequent returns.
Never changes classifications, scores, ladders, or brokerage actions.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, median
from typing import Any, Iterable

from app.investment.integrity import is_validation_eligible

HORIZONS = ("1d", "5d", "20d", "60d", "252d")
ACTIONABLE = {"ACCUMULATION", "DEEP_VALUE", "GENERATIONAL_OPPORTUNITY", "ACCUMULATE"}


def _research(obs: dict[str, Any]) -> dict[str, Any]:
    rec = obs.get("research")
    return rec if isinstance(rec, dict) else obs


def _field(obs: dict[str, Any], key: str, default: Any = None) -> Any:
    rec = _research(obs)
    value = rec.get(key) if isinstance(rec, dict) else None
    return obs.get(key, default) if value is None else value


def _score(obs: dict[str, Any]) -> float | None:
    value = _field(obs, "opportunity_score")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _latest_outcomes(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        oid = str(row.get("observation_id") or "")
        if not oid:
            continue
        prior = latest.get(oid)
        if prior is None or str(row.get("enriched_at") or "") >= str(prior.get("enriched_at") or ""):
            latest[oid] = row
    return latest


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean_return": None, "median_return": None, "positive_rate": None}
    positives = sum(v > 0 for v in values)
    return {
        "n": len(values),
        "mean_return": round(mean(values), 6),
        "median_return": round(median(values), 6),
        "positive_rate": round(positives / len(values), 4),
    }


def _bucket_report(joined: list[tuple[dict[str, Any], dict[str, Any]]], key_fn) -> dict[str, Any]:
    buckets: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for pair in joined:
        buckets[str(key_fn(pair[0]))].append(pair)
    out: dict[str, Any] = {}
    for name, pairs in sorted(buckets.items()):
        out[name] = {
            h: _stats([
                float(outcome[f"return_{h}"])
                for _, outcome in pairs
                if outcome.get(f"return_{h}") is not None
            ])
            for h in HORIZONS
        }
    return out


def build_historical_validation(
    observations: Iterable[dict[str, Any]],
    outcomes: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
    stale_after_hours: float = 36.0,
) -> dict[str, Any]:
    """Join only point-in-time-safe observations to future outcomes.

    Unsafe/missing-lineage rows stay in the append-only corpus for auditability but
    are quarantined from all return, score, classification, evidence, and thesis stats.
    """
    now = now or datetime.now(timezone.utc)
    all_obs_rows = [r for r in observations if isinstance(r, dict)]
    obs_rows = [r for r in all_obs_rows if is_validation_eligible(r)]
    quarantined = len(all_obs_rows) - len(obs_rows)
    outcome_map = _latest_outcomes(outcomes)
    joined: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for obs in obs_rows:
        oid = str(obs.get("observation_id") or "")
        if oid and oid in outcome_map:
            joined.append((obs, outcome_map[oid]))

    horizon_stats = {
        h: _stats([
            float(outcome[f"return_{h}"])
            for _, outcome in joined
            if outcome.get(f"return_{h}") is not None
        ])
        for h in HORIZONS
    }

    score_pairs: dict[str, list[tuple[float, float]]] = {h: [] for h in HORIZONS}
    for obs, outcome in joined:
        score = _score(obs)
        if score is None:
            continue
        for h in HORIZONS:
            value = outcome.get(f"return_{h}")
            if value is not None:
                score_pairs[h].append((score, float(value)))

    score_signal: dict[str, Any] = {}
    for h, pairs in score_pairs.items():
        if len(pairs) < 4:
            score_signal[h] = {"n": len(pairs), "higher_score_outperformed": None, "high_mean": None, "low_mean": None}
            continue
        ordered = sorted(pairs, key=lambda x: x[0])
        split = max(1, len(ordered) // 2)
        low = [r for _, r in ordered[:split]]
        high = [r for _, r in ordered[split:]]
        high_mean = mean(high) if high else None
        low_mean = mean(low) if low else None
        score_signal[h] = {
            "n": len(pairs),
            "higher_score_outperformed": None if high_mean is None or low_mean is None else high_mean > low_mean,
            "high_mean": None if high_mean is None else round(high_mean, 6),
            "low_mean": None if low_mean is None else round(low_mean, 6),
        }

    timestamps = [_ts(obs.get("as_of") or obs.get("timestamp")) for obs in obs_rows]
    valid_ts = [t for t in timestamps if t is not None]
    latest = max(valid_ts) if valid_ts else None
    freshness_hours = None if latest is None else round(max(0.0, (now - latest.astimezone(timezone.utc)).total_seconds() / 3600.0), 2)

    coverage = round(len(joined) / len(obs_rows), 4) if obs_rows else 0.0
    actionable = [pair for pair in joined if str(_field(pair[0], "classification", "NO_ACTION")).upper() in ACTIONABLE]
    actionable_20d = [float(o["return_20d"]) for _, o in actionable if o.get("return_20d") is not None]

    evidence = "INSUFFICIENT"
    completed_20d = horizon_stats["20d"]["n"]
    if completed_20d >= 30 and coverage >= 0.5:
        evidence = "BUILDING"
    if completed_20d >= 100 and coverage >= 0.8:
        evidence = "HISTORICAL_EVIDENCE_READY"

    return {
        "domain": "EQUITY_INVESTMENT",
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "observations": len(all_obs_rows),
        "validation_eligible_observations": len(obs_rows),
        "quarantined_observations": quarantined,
        "matched_observations": len(joined),
        "outcome_coverage": coverage,
        "latest_observation_age_hours": freshness_hours,
        "research_stale": freshness_hours is None or freshness_hours > stale_after_hours,
        "stale_after_hours": stale_after_hours,
        "by_horizon": horizon_stats,
        "by_classification": _bucket_report(joined, lambda r: _field(r, "classification", "NO_ACTION")),
        "by_evidence_quality": _bucket_report(joined, lambda r: _field(r, "evidence_quality", "UNKNOWN")),
        "by_thesis": _bucket_report(joined, lambda r: _field(r, "thesis", _field(r, "thesis_state", "UNKNOWN"))),
        "score_signal": score_signal,
        "actionable_20d": _stats(actionable_20d),
        "evidence_status": evidence,
        "score_is_probability": False,
        "strategy_frozen": True,
        "live_capital_allowed": False,
        "note": (
            "Only point-in-time validation-eligible observations are used. Unsafe legacy rows are quarantined, "
            "not rewritten. Historical associations are descriptive and may not persist. No thresholds are retuned "
            "and no Robinhood orders are placed."
        ),
    }
