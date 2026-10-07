"""Versioned challenger evaluations; production champion changes require code review."""

from datetime import datetime, timezone
from statistics import mean
from app.investment.evidence_lifecycle import FREEZES, classify_observation
from app.investment.prospective_evidence import (
    OBSERVATIONS,
    POLICY_VERSION,
    append_record,
    read_records,
)
from app.investment.prospective_outcomes import OUTCOMES
from app.investment.storage import DATA_DIR

EVALUATIONS = DATA_DIR / "challenger_evaluations.jsonl"


def evaluate_challengers(
    freezes_path=FREEZES, observations_path=OBSERVATIONS, outcomes_path=OUTCOMES
):
    observations = read_records(observations_path)
    outcomes = {row["observation_id"]: row for row in read_records(outcomes_path)}
    evaluations = []
    for freeze in read_records(freezes_path):
        rows = [
            row
            for row in observations
            if row.get("policy_version") == freeze["version"]
        ]
        cohorts = {}
        for evidence in ("DEVELOPMENT", "HOLDOUT"):
            selected = [
                row for row in rows if classify_observation(row, freeze) == evidence
            ]
            returns = [
                outcomes.get(row["observation_id"], {})
                .get("measures", {})
                .get("return_20d")
                for row in selected
            ]
            resolved = [value for value in returns if value is not None]
            cohorts[evidence] = {
                "sample_size": len(selected),
                "resolved_20_session_outcomes": len(resolved),
                "mean_price_return": mean(resolved) if resolved else None,
                "unresolved": len(selected) - len(resolved),
                "economic_expectancy_r": None,
                "benchmark_comparison": "UNKNOWN",
                "calibration": "SEE_PROSPECTIVE_REPORT",
                "regime_stability": "INSUFFICIENT_EVIDENCE",
            }
        evaluations.append(
            {
                "version": freeze["version"],
                "role": "CHALLENGER",
                "freeze": freeze,
                "cohorts": cohorts,
                "promotion_status": "NOT_PROMOTED",
                "promotion_rationale": "Requires approved economic criteria, mature untouched holdout, conservative execution, benchmark evidence, regression tests and explicit reviewed policy change.",
            }
        )
    return {
        "champion": POLICY_VERSION,
        "challengers": evaluations,
        "automatic_promotion": False,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
