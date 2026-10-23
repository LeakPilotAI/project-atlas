"""Bounded offline holdout adequacy; no independent-sample or skill authority."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime

from app.backtest.forecast_baselines import fingerprint
from app.backtest.forecast_evaluation import ForecastEvidenceRefused, _time


def _declared_time(value):
    if type(value) is not str:
        raise ForecastEvidenceRefused("Explicit timestamp required")
    try:
        return _time(datetime.fromisoformat(value))
    except ValueError as error:
        raise ForecastEvidenceRefused("Malformed timestamp") from error


def assess_holdout_sample(plan, *, diagnostic_hits=None):
    """Audit a Stage 20 plan; optional synthetic hits yield only a naive sensitivity interval.

    The Wilson calculation assumes independent Bernoulli cases. Structural checks can
    disprove that assumption but cannot prove it, so the result never establishes
    calibrated coverage, predictive skill, or an authoritative confidence interval.
    """
    if (type(plan) is not dict or plan.get("schema") != "AFI_OFFLINE_HOLDOUT_READINESS_V1"
            or type(plan.get("cases")) is not list or not 1 <= len(plan["cases"]) <= 64
            or type(plan.get("selection_n")) is not int or type(plan.get("holdout_n")) is not int
            or plan["selection_n"] + plan["holdout_n"] != len(plan["cases"])):
        raise ForecastEvidenceRefused("Exact bounded Stage 20 holdout plan required")
    digest = plan.get("protocol_sha256")
    if type(digest) is not str or fingerprint({k: v for k, v in plan.items() if k != "protocol_sha256"}) != digest:
        raise ForecastEvidenceRefused("Holdout plan commitment mismatch")
    if (plan.get("authoritative_scored_n") != 0 or plan.get("sample_minimum_approved") is not False
            or plan.get("holdout_independently_unseen") is not False
            or plan.get("dataset_freeze_independently_witnessed") is not False):
        raise ForecastEvidenceRefused("Holdout plan claims unsupported authority")
    frozen, asof = _declared_time(plan.get("frozen_at")), _declared_time(plan.get("asof"))
    if frozen > asof:
        raise ForecastEvidenceRefused("Invalid freeze/evaluation order")
    partitions = Counter()
    seen, targets, cohorts = set(), set(), defaultdict(list)
    eligible = []
    excluded = Counter()
    for row in plan["cases"]:
        if type(row) is not dict or set(row) != {"forecast_sha256", "partition", "cohort", "issued_at",
                                                "target_at", "window_status", "outcome_status", "exclusion_reason"}:
            raise ForecastEvidenceRefused("Incomplete holdout case")
        ident, partition, cohort = row["forecast_sha256"], row["partition"], row["cohort"]
        if type(ident) is not str or len(ident) != 64 or any(c not in "0123456789abcdef" for c in ident):
            raise ForecastEvidenceRefused("Malformed forecast identity")
        if ident in seen or partition not in ("SELECTION", "HOLDOUT") or type(cohort) is not dict:
            raise ForecastEvidenceRefused("Repeated or unpartitioned forecast")
        seen.add(ident)
        partitions[partition] += 1
        required = ("asset_class", "asset_id", "horizon", "source_id", "model", "model_version",
                    "forecast_dataset_id")
        if any(type(cohort.get(key)) is not str or not cohort[key] for key in required):
            raise ForecastEvidenceRefused("Incomplete cohort provenance")
        for key in ("model_configuration_sha256", "release_source_sha256"):
            if cohort.get(key) is not None and (type(cohort[key]) is not str or not cohort[key]):
                raise ForecastEvidenceRefused("Malformed optional cohort binding")
        issue, target = (_declared_time(row[key]) for key in ("issued_at", "target_at"))
        if issue >= target or issue > asof or (partition == "SELECTION" and issue >= frozen) or (partition == "HOLDOUT" and issue < frozen):
            raise ForecastEvidenceRefused("Contradictory holdout chronology")
        if (row["window_status"] not in ("COMPLETE", "IMMATURE", "PARTIAL", "MISSING", "CONTRADICTORY", "UNVERIFIED")
                or row["outcome_status"] not in ("RESOLVED", "FORECAST_ONLY", "PENDING")
                or row["exclusion_reason"] is not None and type(row["exclusion_reason"]) is not str):
            raise ForecastEvidenceRefused("Malformed evidence state")
        if partition == "SELECTION" and (
            target >= frozen or row["window_status"] != "COMPLETE"
            or row["outcome_status"] != "RESOLVED" or row["exclusion_reason"] is not None
        ):
            raise ForecastEvidenceRefused("Selection label unavailable or incomplete before freeze")
        observation = (cohort["asset_class"], cohort["asset_id"], cohort["source_id"], target)
        if observation in targets:
            raise ForecastEvidenceRefused("Repeated observation across models or horizons")
        targets.add(observation)
        if partition == "HOLDOUT":
            key = (cohort["asset_class"], cohort["asset_id"], cohort["source_id"])
            cohorts[key].append((issue, target, ident))
            if (row["window_status"] == "COMPLETE" and row["outcome_status"] == "RESOLVED"
                    and row["exclusion_reason"] is None):
                eligible.append(ident)
            else:
                reason = row["exclusion_reason"] or (row["window_status"] if row["window_status"] != "COMPLETE"
                                                      else row["outcome_status"])
                excluded[str(reason)] += 1
    if partitions != {"SELECTION": plan["selection_n"], "HOLDOUT": plan["holdout_n"]}:
        raise ForecastEvidenceRefused("Holdout partition count mismatch")
    selected = sorted(row["forecast_sha256"] for row in plan["cases"] if row["partition"] == "SELECTION")
    held = sorted(row["forecast_sha256"] for row in plan["cases"] if row["partition"] == "HOLDOUT")
    if (fingerprint(selected) != plan.get("selection_partition_sha256")
            or fingerprint(held) != plan.get("holdout_partition_sha256")
            or len(eligible) != plan.get("holdout_mature_n")):
        raise ForecastEvidenceRefused("Holdout membership or eligibility mismatch")
    overlap = 0
    for rows in cohorts.values():
        ordered = sorted(rows)
        # Count windows intersecting any earlier window, including nested spans.
        # An immediately preceding short window need not have the latest end.
        latest_end = None
        for issue, target, _ident in ordered:
            if latest_end is not None and issue < latest_end:
                overlap += 1
            latest_end = target if latest_end is None else max(latest_end, target)
    concentration = Counter(row["cohort"]["asset_id"] for row in plan["cases"]
                            if row["partition"] == "HOLDOUT" and row["forecast_sha256"] in eligible)
    source_count = Counter(row["cohort"]["source_id"] for row in plan["cases"]
                           if row["partition"] == "HOLDOUT" and row["forecast_sha256"] in eligible)
    horizon_count = Counter(row["cohort"]["horizon"] for row in plan["cases"]
                            if row["partition"] == "HOLDOUT" and row["forecast_sha256"] in eligible)
    model_count = Counter((row["cohort"]["model"], row["cohort"]["model_version"])
                          for row in plan["cases"] if row["partition"] == "HOLDOUT"
                          and row["forecast_sha256"] in eligible)
    interval_cohorts = {(row["cohort"]["horizon"], row["cohort"]["source_id"],
                         row["cohort"]["model"], row["cohort"]["model_version"],
                         row["cohort"].get("model_configuration_sha256"),
                         row["cohort"]["forecast_dataset_id"])
                        for row in plan["cases"] if row["forecast_sha256"] in eligible}
    result = {"schema": "AFI_HOLDOUT_SAMPLE_ADEQUACY_V1", "plan_sha256": digest,
              "holdout_n": plan["holdout_n"], "eligible_n": len(eligible),
              "distinct_observation_n": len({row["target_at"] + ":" + row["cohort"]["asset_id"] + ":" + row["cohort"]["source_id"]
                                               for row in plan["cases"] if row["forecast_sha256"] in eligible}),
              "excluded_n": plan["holdout_n"] - len(eligible), "exclusion_counts": dict(sorted(excluded.items())),
              "overlapping_window_n": overlap, "asset_counts": dict(sorted(concentration.items())),
              "source_counts": dict(sorted(source_count.items())), "horizon_counts": dict(sorted(horizon_count.items())),
              "model_counts": {"/".join(key): count for key, count in sorted(model_count.items())},
              "interval_cohort_n": len(interval_cohorts),
              "max_asset_share": max(concentration.values()) / len(eligible) if eligible else None,
              "independent_samples_established": False, "effective_sample_n": None,
              "sample_minimum_approved": False, "interval": None, "authoritative_scored_n": 0,
              "calibration_established": False, "predictive_skill_established": False,
              "production_approved": False}
    if diagnostic_hits is not None:
        if (type(diagnostic_hits) is not dict or set(diagnostic_hits) != set(eligible)
                or any(type(value) is not bool for value in diagnostic_hits.values())):
            raise ForecastEvidenceRefused("Exact eligible binary diagnostic outcomes required")
        # z=1.96 is a conventional *assumed-independent* 95% sensitivity calculation.
        n = len(eligible)
        if n >= 2 and overlap == 0 and len(concentration) >= 2 and len(interval_cohorts) == 1:
            rate = sum(diagnostic_hits.values()) / n
            z2 = 1.96 ** 2
            center = (rate + z2 / (2 * n)) / (1 + z2 / n)
            half = 1.96 * math.sqrt(rate * (1 - rate) / n + z2 / (4 * n * n)) / (1 + z2 / n)
            result["interval"] = {"method": "WILSON_BERNOULLI_ASSUMED_INDEPENDENT",
                                  "status": "ASSUMPTION_BOUND_DIAGNOSTIC_ONLY", "n": n,
                                  "hit_n": sum(diagnostic_hits.values()), "observed_rate": rate,
                                  "lower": max(0.0, center - half), "upper": min(1.0, center + half),
                                  "independence_verified": False}
    result["status"] = ("NO_ELIGIBLE_CASES" if not eligible else
                        "STRUCTURAL_DEPENDENCE_OR_CONCENTRATION" if overlap or len(concentration) < 2
                        or len(interval_cohorts) != 1 else
                        "UNAPPROVED_SAMPLE_ADEQUACY")
    return {**result, "assessment_sha256": fingerprint(result)}
