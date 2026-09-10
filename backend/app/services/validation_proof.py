"""Read-only proof summary for Atlas research validation.

Engineering health is not trading edge. This module reports evidence already collected
inside each isolated domain and never changes thresholds or unlocks live capital.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.investment.freshness_proof import build_freshness_proof
from app.investment.historical_validation import build_historical_validation
from app.services.oos_cost_validation import build_oos_cost_report
from app.services.paper_validation import metrics, uncertainty


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _age_hours(value: Any, *, now: datetime) -> float | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return round(max(0.0, (now - dt.astimezone(timezone.utc)).total_seconds() / 3600.0), 2)
    except Exception:
        return None


def build_perp_proof(closed_rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(closed_rows)
    m = metrics(rows)
    u = uncertainty(rows)
    exp_ci = u.get("expectancy_ci95") or [None, None]
    lower = exp_ci[0] if len(exp_ci) > 0 else None
    evidence = "INSUFFICIENT"
    if m["n"] >= 50:
        evidence = "DIRECTIONAL"
    if m["n"] >= 100 and lower is not None and float(lower) > 0:
        evidence = "PROMISING_NOT_LIVE_READY"
    return {
        "domain": "HYPERLIQUID_PERPS",
        "mode": "PAPER_RESEARCH_ONLY",
        "closed_trades": m["n"],
        "winrate": m["winrate"],
        "expectancy_r": m["expectancy"],
        "expectancy_ci95": exp_ci,
        "profit_factor": m.get("profit_factor"),
        "max_drawdown_r": m["max_drawdown_r"],
        "longest_losing_streak": m["longest_losing_streak"],
        "evidence_status": evidence,
        "live_capital_allowed": False,
        "note": "Paper statistics are evidence, not proof of future profitability. No automatic live unlock exists.",
    }


def build_investment_proof(
    opportunity_rows: Iterable[dict[str, Any]],
    outcome_rows: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    opportunities = [r for r in opportunity_rows if isinstance(r, dict)]
    outcomes = [r for r in outcome_rows if isinstance(r, dict)]
    symbols = {str(r.get("symbol") or "").upper() for r in opportunities if r.get("symbol")}
    outcome_symbols = {str(r.get("symbol") or "").upper() for r in outcomes if r.get("symbol")}
    timestamps = [r.get("timestamp") or r.get("observed_at") for r in opportunities]
    ages = [a for a in (_age_hours(v, now=now) for v in timestamps) if a is not None]
    matched = len(symbols & outcome_symbols)
    coverage = round(matched / len(symbols), 4) if symbols else 0.0
    status = "INSUFFICIENT"
    if len(outcomes) >= 30 and coverage >= 0.5:
        status = "BUILDING"
    if len(outcomes) >= 100 and coverage >= 0.8:
        status = "HISTORICAL_REVIEW_READY"
    return {
        "domain": "EQUITY_INVESTMENT",
        "mode": "RESEARCH_ONLY",
        "research_records": len(opportunities),
        "research_symbols": len(symbols),
        "outcome_records": len(outcomes),
        "symbols_with_outcomes": matched,
        "outcome_symbol_coverage": coverage,
        "freshest_research_age_hours": min(ages) if ages else None,
        "oldest_research_age_hours": max(ages) if ages else None,
        "evidence_status": status,
        "live_capital_allowed": False,
        "note": "Coverage/freshness measure dataset maturity only; they do not establish that Quality Dips has predictive edge.",
    }


def build_validation_proof(
    *,
    paper_rows: Iterable[dict[str, Any]],
    opportunity_rows: Iterable[dict[str, Any]],
    outcome_rows: Iterable[dict[str, Any]],
    observation_rows: Iterable[dict[str, Any]] = (),
    investment_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    paper = list(paper_rows)
    opportunities = list(opportunity_rows)
    outcomes = list(outcome_rows)
    observations = list(observation_rows)
    readiness = investment_readiness or {"status": "NOT READY", "checks": {}}
    return {
        "domain": "VALIDATION_ORCHESTRATION",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engineering_complete_is_not_edge": True,
        "live_capital_allowed": False,
        "perps": build_perp_proof(paper),
        "perp_oos_cost": build_oos_cost_report(paper),
        "investments": build_investment_proof(opportunities, outcomes),
        "investment_historical": build_historical_validation(observations, outcomes),
        "investment_freshness": build_freshness_proof(readiness),
        "next_gate": "Keep collecting forward evidence. Engineering completion does not authorize live capital; review empirical stability before any future live-capital decision.",
    }
