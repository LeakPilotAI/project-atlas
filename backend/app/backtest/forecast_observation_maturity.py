"""Offline, source-bound daily outcome-window completeness diagnostics.

COMPLETE here means a synthetic window is structurally complete. It never
authenticates publication, grants production authority, or proves market skill.
"""
from __future__ import annotations

from datetime import timedelta

from app.backtest.forecast_dataset import (
    DatasetReview,
    _date,
    _future_closes,
    _json,
    review_dataset,
)
from app.backtest.forecast_evaluation import (
    Forecast,
    ForecastEvidenceRefused,
    Outcome,
    _bounded,
    _forecast,
    _time,
    score_forecasts,
    select_asof,
)


def assess_observation_window(review: DatasetReview, forecast: Forecast, *, asof):
    """Classify the exact 1D/5D daily-close path, never filling a missing close."""
    if type(review) is not DatasetReview:
        raise ForecastEvidenceRefused("Exact dataset review required")
    _forecast(forecast)
    asof = _time(asof)
    manifest = _json(review.manifest_bytes)
    payload = _json(review.payload_bytes)
    checked = review_dataset(review.manifest_bytes, review.payload_bytes,
                             asof=max(asof, _date(manifest["generated_at"])))
    if checked != review:
        raise ForecastEvidenceRefused("Substituted dataset review")
    asset = next((a for a in manifest["assets"] if a["asset_id"] == forecast.asset_id), None)
    if (asset is None or forecast.horizon not in ("1D", "5D")
            or forecast.dataset_id != manifest["dataset_id"]
            or forecast.dataset_sha256 != review.content_sha256
            or forecast.dataset_manifest_sha256 != review.manifest_sha256
            or forecast.dataset_version != manifest["version"]
            or forecast.evidence_class != manifest["evidence_class"]
            or forecast.asset_class != asset["asset_class"]):
        raise ForecastEvidenceRefused("Unsupported or unbound observation window")
    if asof < _time(forecast.issued_at):
        raise ForecastEvidenceRefused("Evaluation precedes forecast issue")
    selected = select_asof(review.observations, asset_id=forecast.asset_id,
                           asset_class=forecast.asset_class, cutoff=forecast.issued_at,
                           max_age=timedelta(seconds=asset["freshness_seconds"]))["record"]
    if (selected is None or selected.value != forecast.reference_price
            or selected.observed_at != forecast.input_observed_at
            or selected.available_at != forecast.input_available_at
            or selected.source_id != manifest["source"]["id"]):
        raise ForecastEvidenceRefused("Forecast input is not source-bound at issue time")
    expected = _future_closes(_time(forecast.issued_at), asset)
    count = 1 if forecast.horizon == "1D" else 5
    if len(expected) < count or expected[count - 1] != _time(forecast.target_at):
        raise ForecastEvidenceRefused("Forecast target is not the declared session horizon")
    required = expected[:count]
    base = {"forecast_id": forecast.forecast_id, "asset_id": forecast.asset_id,
            "horizon": forecast.horizon, "issued_at": _time(forecast.issued_at).isoformat(),
            "target_at": required[-1].isoformat(), "asof": asof.isoformat(),
            "source_id": manifest["source"]["id"], "dataset_sha256": review.content_sha256,
            "manifest_sha256": review.manifest_sha256, "required_n": count,
            "authenticated_publication": False, "authoritative_aggregate_eligible": False}
    if review.status != "ACCEPTED_SYNTHETIC":
        return {**base, "status": "UNVERIFIED", "available_n": 0,
                "missing_at": [t.isoformat() for t in required],
                "reason": "Source rights and historical publication are not independently verified"}
    if asof < required[-1]:
        return {**base, "status": "IMMATURE", "available_n": 0,
                "missing_at": [t.isoformat() for t in required], "reason": "Target window has not ended"}
    ordered_availability = [_date(row["available_at"]) for row in payload["records"]
                            if row["asset_id"] == forecast.asset_id
                            and _date(row["observed_at"]) in required]
    if ordered_availability != sorted(ordered_availability):
        return {**base, "status": "CONTRADICTORY", "available_n": 0,
                "missing_at": [t.isoformat() for t in required],
                "reason": "Source record publication order regressed"}
    observed = {}
    for row in review.observations:
        if row.asset_id != forecast.asset_id or row.observed_at not in required:
            continue
        if row.source_id != manifest["source"]["id"]:
            return {**base, "status": "CONTRADICTORY", "available_n": 0,
                    "missing_at": [t.isoformat() for t in required], "reason": "Source identity conflict"}
        if _time(row.available_at) > asof:
            continue
        current = observed.get(row.observed_at)
        if current is None or row.available_at > current.available_at:
            observed[row.observed_at] = row
        elif row.available_at == current.available_at:
            return {**base, "status": "CONTRADICTORY", "available_n": 0,
                    "missing_at": [t.isoformat() for t in required], "reason": "Ambiguous same-time revision"}
    missing = [t.isoformat() for t in required if t not in observed]
    status = "MISSING" if not observed else "PARTIAL" if missing else "COMPLETE"
    return {**base, "status": status, "available_n": len(observed), "missing_at": missing,
            "reason": None if status == "COMPLETE" else "Required daily close unavailable"}


def summarize_observation_windows(results):
    """Never promote locally complete or unverified windows to authoritative skill."""
    if not isinstance(results, (tuple, list)) or len(results) > 10000:
        raise ForecastEvidenceRefused("Bounded window results required")
    allowed = {"COMPLETE", "IMMATURE", "PARTIAL", "MISSING", "CONTRADICTORY", "UNVERIFIED"}
    counts = {state: 0 for state in sorted(allowed)}
    by_source = {}
    seen = set()
    for result in results:
        if type(result) is not dict or result.get("status") not in allowed:
            raise ForecastEvidenceRefused("Invalid window status")
        identity = result.get("forecast_id")
        if type(identity) is not str or not identity or identity in seen:
            raise ForecastEvidenceRefused("Duplicate or missing forecast identity")
        seen.add(identity)
        if result.get("authoritative_aggregate_eligible") is not False:
            raise ForecastEvidenceRefused("Unverified authority claim")
        counts[result["status"]] += 1
        cohort = (result.get("source_id"), result.get("asset_id"), result.get("horizon"),
                  result.get("dataset_sha256"), result.get("manifest_sha256"))
        if any(type(value) is not str or not value for value in cohort):
            raise ForecastEvidenceRefused("Incomplete source cohort")
        by_source.setdefault(cohort, {state: 0 for state in sorted(allowed)})[result["status"]] += 1
    return {"requested_n": len(results), "statuses": counts,
            "source_cohorts": [{"source_id": key[0], "asset_id": key[1], "horizon": key[2],
                                "dataset_sha256": key[3], "manifest_sha256": key[4], "statuses": value}
                               for key, value in sorted(by_source.items())],
            "authoritative_scored_n": 0, "authoritative_performance": None,
            "production_approved": False}


def score_complete_synthetic_windows(review, forecasts, outcomes, *, asof):
    """Exclude partial windows from a separate, non-authoritative diagnostic."""
    from app.backtest.forecast_dataset import score_dataset_forecasts

    _bounded(forecasts, Forecast)
    _bounded(outcomes, Outcome)
    forecasts, outcomes = tuple(forecasts), tuple(outcomes)
    windows = [assess_observation_window(review, forecast, asof=asof) for forecast in forecasts]
    summary = summarize_observation_windows(windows)
    ids = {forecast.forecast_id for forecast in forecasts}
    if len(ids) != len(forecasts) or any(outcome.forecast_id not in ids for outcome in outcomes):
        raise ForecastEvidenceRefused("Unknown or repeated forecast identity")
    # Validate even excluded caller-supplied outcomes; exclusion must not hide
    # malformed or contradictory evidence.
    score_forecasts(forecasts, outcomes, asof=asof)
    complete = {row["forecast_id"] for row in windows if row["status"] == "COMPLETE"}
    diagnostic = (score_dataset_forecasts(
        review, [forecast for forecast in forecasts if forecast.forecast_id in complete],
        [outcome for outcome in outcomes if outcome.forecast_id in complete], asof=asof,
    ) if complete else {"scope": "OFFLINE_DIAGNOSTIC", "scored_n": 0,
                        "status": "INSUFFICIENT_EVIDENCE", "dataset_authenticated": False,
                        "production_approved": False})
    return {"window_evidence": windows, "source_completeness": summary,
            "diagnostic": diagnostic, "excluded_n": len(forecasts) - len(complete),
            "authoritative_scored_n": 0, "production_approved": False}
