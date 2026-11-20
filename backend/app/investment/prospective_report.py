"""Read-only evidence, calibration and opportunity-cost summaries."""

from collections import defaultdict
from statistics import mean

from app.investment.prospective_evidence import OBSERVATIONS, read_records
from app.investment.prospective_outcomes import OUTCOMES
from app.investment.daily_research_plan import PLAN_PATH
from app.investment.evidence_lifecycle import FREEZES, classify_observation
from app.investment.benchmark_research import compare_benchmark


def evidence_report(
    observations_path=OBSERVATIONS, outcomes_path=OUTCOMES, benchmark_symbol="SPY"
):
    observations = [
        row
        for row in read_records(observations_path)
        if row.get("evidence_class") == "FORWARD_COLLECTION"
    ]
    outcomes = {row["observation_id"]: row for row in read_records(outcomes_path)}
    buckets = defaultdict(list)
    waiting = []
    for obs in observations:
        outcome = outcomes.get(obs["observation_id"], {})
        measures = outcome.get("measures", {})
        source = obs.get("source_snapshot") or {}
        for horizon in ("1d", "5d", "20d", "60d", "252d"):
            result = measures.get("return_" + horizon)
            key = (
                obs["policy_version"],
                obs["execution_model_version"],
                obs.get("confidence", "UNKNOWN"),
                obs.get("classification", "UNKNOWN"),
                str(source.get("sector") or "UNKNOWN"),
                str(source.get("market_regime") or "UNKNOWN"),
                horizon,
            )
            buckets[key].append((obs, outcome, result))
        path = outcome.get("price_path") or []
        buy_return = (
            path[-1]["close"] / obs["price"] - 1
            if path and path[-1].get("close")
            else None
        )
        for interaction in outcome.get("target_interactions", []):
            waiting.append(
                {
                    "observation_id": obs["observation_id"],
                    "symbol": obs["symbol"],
                    **interaction,
                    "observed_sessions": len(path),
                    "buy_at_observation_price_return": buy_return,
                    "policy_version": obs["policy_version"],
                    "execution_model_version": obs["execution_model_version"],
                    "cash_drag_vs_buy": (
                        buy_return if not interaction.get("touch_session") else None
                    ),
                    "missed_upside": (
                        max(0, buy_return)
                        if buy_return is not None
                        and not interaction.get("touch_session")
                        else None
                    ),
                    "drawdown_avoided_while_unfilled": (
                        max(
                            0,
                            -(
                                outcome.get("measures", {}).get("max_adverse_excursion")
                                or 0
                            ),
                        )
                        if path and not interaction.get("touch_session")
                        else None
                    ),
                    "return_after_waiting": None,
                    "cash_return_assumption": 0,
                    "fill_status": "UNKNOWN",
                    "note": "Touch is not a fill. Cash comparisons exclude interest; losses and unresolved waits retained.",
                }
            )
    calibration = []
    for key, rows in sorted(buckets.items()):
        resolved = [r for _, _, r in rows if r is not None]
        coverage = []
        for obs, outcome, result in rows:
            value = obs.get("valuation") or {}
            low, high = value.get("conservative"), value.get("optimistic")
            if (
                result is not None
                and isinstance(low, (int, float))
                and isinstance(high, (int, float))
            ):
                price = obs["price"] * (1 + result)
                coverage.append(low <= price <= high)
        calibration.append(
            dict(
                zip(
                    (
                        "policy_version",
                        "execution_model_version",
                        "confidence",
                        "classification",
                        "sector",
                        "regime",
                        "horizon",
                    ),
                    key,
                ),
                observations=len(rows),
                resolved=len(resolved),
                unresolved=len(rows) - len(resolved),
                mean_price_return=mean(resolved) if resolved else None,
                fair_value_range_coverage=mean(coverage) if coverage else None,
                note="Valuation ranges are not probability intervals; ordinal scores are not win probabilities.",
            )
        )
    comparisons = []
    benchmark_observations = {
        (row["timestamp"], row.get("source_timestamp"), row["policy_version"]): row
        for row in observations
        if row["symbol"] == benchmark_symbol
    }
    for obs in observations:
        if obs["symbol"] == benchmark_symbol:
            continue
        benchmark = benchmark_observations.get(
            (obs["timestamp"], obs.get("source_timestamp"), obs["policy_version"])
        )
        if not benchmark:
            continue
        path = outcomes.get(obs["observation_id"], {}).get("price_path") or []
        baseline = outcomes.get(benchmark["observation_id"], {}).get("price_path") or []
        own_points = [(obs["timestamp"], obs["price"])] + [
            (row["date"], row["close"]) for row in path if row.get("close")
        ]
        bench_points = [(benchmark["timestamp"], benchmark["price"])] + [
            (row["date"], row["close"]) for row in baseline if row.get("close")
        ]
        comparison = compare_benchmark(
            own_points,
            bench_points,
            symbol=benchmark_symbol,
            return_basis="PRICE_RETURN",
        )
        comparisons.append(
            {
                "observation_id": obs["observation_id"],
                "symbol": obs["symbol"],
                "classification": obs.get("classification"),
                **comparison,
                "interpretation": "REFERENCE_PRICE_COMPARISON_NOT_EXECUTED_STRATEGY_EQUITY",
            }
        )
    measured = [row for row in comparisons if row.get("outperformed") is not None]
    mature = sum(
        outcomes.get(row["observation_id"], {}).get("measures", {}).get("return_20d")
        is not None
        for row in observations
    )
    freezes = read_records(FREEZES)
    untouched = sum(
        any(classify_observation(row, freeze) == "HOLDOUT" for freeze in freezes)
        for row in observations
    )
    evidence_facts = {
        "forward_observations": len(observations),
        "mature_20_session_outcomes": mature,
        "untouched_holdout": untouched,
        "conservative_cost_expectancy_r": None,
        "execution_model_versions": sorted(
            {row["execution_model_version"] for row in observations}
        ),
        "matched_benchmark_comparisons": len(measured),
        "benchmark_underperformers": sum(not row["outperformed"] for row in measured),
        "regime_stability": "UNKNOWN",
        "profit_concentration": "UNKNOWN",
        "runtime_reliability": "REQUIRES_DATED_OPERATOR_VALIDATION",
        "reconciliation_integrity": "SEE_PAPER_RECONCILIATION",
        "leakage_checks": "PROSPECTIVE_TIMESTAMPS_AND_SEPARATE_OUTCOME_REVISIONS",
    }
    return {
        "observation_count": len(observations),
        "outcome_record_count": len(outcomes),
        "calibration": calibration,
        "opportunity_cost": waiting,
        "benchmark": {
            "status": (
                "DESCRIPTIVE_COMPARISONS_AVAILABLE"
                if measured
                else "INSUFFICIENT_MATCHED_PIT_BENCHMARK_EVIDENCE"
            ),
            "outperformed": None,
            "symbol": benchmark_symbol,
            "comparisons": comparisons,
            "note": "Matched original observation/source timestamps and identical later dates. Reference-price comparisons do not assume execution or establish strategy edge.",
        },
        "historical_perps_holdout": {
            "trades": 546,
            "total_r": -26.7235,
            "expectancy_r": -0.04894,
            "status": "FAILED_NEGATIVE",
            "immutable": True,
        },
        "readiness": {
            "status": "INSUFFICIENT_EVIDENCE",
            "reasons": [
                "No approved economic acceptance thresholds",
                "Untouched prospective holdout and matched benchmark evidence required",
                "Runtime/reconciliation/leakage approval cannot be inferred from sample count",
            ],
            "evidence": evidence_facts,
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        },
        "execution": "MANUAL_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
