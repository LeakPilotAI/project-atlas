"""Local immutable daily manual research plan. No brokerage integration."""

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math

from app.investment.adaptive_valuation import actionability, version_valuation
from app.investment.portfolio import (
    load_portfolio,
    existing_position_value,
    sector_value,
)
from app.investment.prospective_evidence import (
    OBSERVATIONS,
    POLICY_VERSION,
    append_record,
    read_records,
    _lock,
)
from app.investment.research_math import etf_research
from app.investment.storage import DATA_DIR

PLAN_PATH = DATA_DIR / "daily_manual_research_plans.jsonl"
CONFIG_PATH = DATA_DIR / "daily_research_config.json"


def load_config(path=CONFIG_PATH):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_plan(observations, portfolio, config):
    now = datetime.now(timezone.utc)
    latest = {}
    for row in observations:
        if row.get("evidence_class") != "FORWARD_COLLECTION":
            continue
        if row["timestamp"][:10] == now.date().isoformat():
            latest[row["symbol"]] = row
    reasons = []
    allocations = config.get("target_allocations") or {}
    stages = config.get("stage_weights") or {}
    valid_weights = (
        lambda values: bool(values)
        and all(
            isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1
            for v in values.values()
        )
        and sum(values.values()) <= 1
    )
    if not portfolio.is_complete_for_personalized_plan():
        reasons.append("Capital, portfolio value or desired reserve is missing")
    if (
        str(portfolio.risk_tolerance.value) == "UNKNOWN"
        or str(portfolio.investment_horizon.value) == "UNKNOWN"
    ):
        reasons.append("Risk profile and investment horizon must be supplied")
    if not valid_weights(allocations) or set(allocations) - {
        "QUALITY_DIPS",
        "ETF_CORE",
        "RESERVE_CASH",
    }:
        reasons.append("Explicit target allocations are missing or invalid")
        allocations = {}
    if not valid_weights(stages) or set(stages) - {"CURRENT", "L1", "L2", "L3", "L4"}:
        reasons.append("Explicit stage weights are missing or invalid")
        stages = {}
    if any(
        value is not None and (not math.isfinite(value) or value < 0)
        for value in (
            portfolio.portfolio_value,
            portfolio.maximum_position_percent,
            portfolio.maximum_sector_exposure_percent,
        )
    ):
        reasons.append("Invalid portfolio risk limits")
    if portfolio.maximum_position_percent > 100 or (
        portfolio.maximum_sector_exposure_percent is not None
        and portfolio.maximum_sector_exposure_percent > 100
    ):
        reasons.append("Exposure limits cannot exceed 100 percent")
    if any(
        not math.isfinite(h.shares)
        or h.shares < 0
        or (
            h.current_value is not None
            and (not math.isfinite(h.current_value) or h.current_value < 0)
        )
        for h in portfolio.holdings
    ):
        reasons.append("Invalid holding values or unsupported short exposure")
    cash = portfolio.available_cash
    reserve = portfolio.minimum_cash_reserve
    if cash is not None and (not math.isfinite(cash) or cash < 0):
        reasons.append("Invalid cash")
    if reserve is not None and (not math.isfinite(reserve) or reserve < 0):
        reasons.append("Invalid reserve")
    deployable = max(0, cash - reserve) if not reasons else 0
    budget = deployable * allocations.get("QUALITY_DIPS", 0)
    candidates = []
    for symbol, observation in sorted(latest.items()):
        zone = actionability(observation, config)
        decision = (observation.get("features") or {}).get("decision_inputs") or {}
        source = observation.get("source_snapshot") or {}
        sector = source.get("sector") or (source.get("asset") or {}).get("sector")
        blockers = list(reasons) + zone["blockers"]
        if not sector or portfolio.maximum_sector_exposure_percent is None:
            blockers.append("Sector exposure or sector limit is unknown")
        if portfolio.holdings and any(
            h.current_value is None and h.symbol != symbol for h in portfolio.holdings
        ):
            blockers.append("Current holding values required for exposure checks")
        concentration = 0
        if portfolio.portfolio_value and portfolio.portfolio_value > 0:
            concentration = max(
                0,
                portfolio.portfolio_value * portfolio.maximum_position_percent / 100
                - existing_position_value(portfolio, symbol, observation["price"]),
            )
            if sector and portfolio.maximum_sector_exposure_percent is not None:
                concentration = min(
                    concentration,
                    max(
                        0,
                        portfolio.portfolio_value
                        * portfolio.maximum_sector_exposure_percent
                        / 100
                        - sector_value(portfolio, sector),
                    ),
                )
        if concentration <= 0:
            blockers.append("NO_ADDITIONAL_ALLOCATION: position or sector limit")
        candidates.append(
            {
                "symbol": symbol,
                "observation_id": observation["observation_id"],
                "price": observation["price"],
                "classification": observation["classification"],
                "valuation": observation.get("valuation"),
                "actionability": zone,
                "confidence": observation["confidence"],
                "missing_data": observation["missing_data"],
                "sector": sector,
                "capacity": concentration,
                "blockers": blockers,
                "thesis_conditions": {
                    "intact": decision.get("thesis_intact"),
                    "value_trap": decision.get("value_trap"),
                },
                "source_timestamp": observation["source_timestamp"],
            }
        )
    eligible = [
        row
        for row in candidates
        if not row["blockers"]
        and row["actionability"]["status"] == "ACTIONABLE_RESEARCH_ZONE"
    ]
    sector_remaining = {}
    for row in candidates:
        amount = (
            min(row["capacity"], budget / max(1, len(eligible)))
            if row in eligible
            else 0
        )
        sector = row["sector"]
        if amount and sector:
            remaining = sector_remaining.setdefault(
                sector,
                max(
                    0,
                    portfolio.portfolio_value
                    * portfolio.maximum_sector_exposure_percent
                    / 100
                    - sector_value(portfolio, sector),
                ),
            )
            amount = min(amount, remaining)
            sector_remaining[sector] -= amount
        row["staged_research_capital"] = {
            level: amount * weight for level, weight in stages.items()
        }
        row["current_manual_research_amount"] = row["staged_research_capital"].get(
            "CURRENT", 0
        )
        row["reason"] = (
            "; ".join(row["blockers"])
            if row["blockers"]
            else (
                "Within supplied research risk budget"
                if amount
                else "WAIT: current price outside actionable zone"
            )
        )
    current = sum(row["current_manual_research_amount"] for row in candidates)
    return {
        "plan_id": hashlib.sha256(
            f"{now.date()}|{POLICY_VERSION}".encode()
        ).hexdigest(),
        "timestamp": now.isoformat(),
        "evidence_class": "FORWARD_COLLECTION",
        "policy_version": POLICY_VERSION,
        "planning_model_version": "manual-daily-research-v1",
        "status": "MANUAL_RESEARCH_ONLY" if current else "BUY_NOTHING_TODAY",
        "reasons": reasons,
        "portfolio": asdict(portfolio),
        "configuration": config,
        "quality_dips": candidates,
        "etf_core": [
            etf_research(symbol, evidence)
            for symbol, evidence in (config.get("etf_evidence") or {}).items()
        ],
        "etf_allocation_status": "WAIT_FOR_ETF_SUITABILITY_AND_OVERLAP_EVIDENCE",
        "available_research_cash": cash,
        "desired_reserve": reserve,
        "current_research_allocation": current,
        "reserve_cash": cash - current if cash is not None else None,
        "market_regime": "UNKNOWN",
        "upcoming_catalysts": "UNKNOWN",
        "correlation": "UNKNOWN",
        "etf_overlap": "UNKNOWN",
        "execution": "MANUAL_ONLY",
        "automatic_perps_execution": "DISABLED",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def persist_daily_plan(
    observations_path=OBSERVATIONS, path=PLAN_PATH, config=None, portfolio=None
):
    with _lock:
        today = datetime.now(timezone.utc).date().isoformat()
        previous = next(
            (
                row
                for row in reversed(read_records(path))
                if row["timestamp"][:10] == today
            ),
            None,
        )
        if previous:
            return previous
        observations = read_records(observations_path)
        if not any(row["timestamp"][:10] == today for row in observations):
            return None
        plan = build_plan(
            observations,
            portfolio or load_portfolio(),
            config if config is not None else load_config(),
        )
        from app.investment.etf_local_research import local_etf_report

        plan["etf_core"] = local_etf_report(plan["configuration"])
        append_record(path, plan)
        return plan
