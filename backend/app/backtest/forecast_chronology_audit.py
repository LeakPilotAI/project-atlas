"""Read-only chronology audit of declared AFI clocks, never third-party attestation."""
from __future__ import annotations

from datetime import datetime

from app.backtest.forecast_dataset import _json
from app.backtest.forecast_evaluation import ForecastEvidenceRefused, _time
from app.backtest.forecast_outcomes import verify_outcome_history
from app.backtest.forecast_report import ForecastHistory


def _clock(value):
    if type(value) is not str:
        raise ForecastEvidenceRefused("Missing declared chronology timestamp")
    try:
        return _time(datetime.fromisoformat(value))
    except ValueError as error:
        raise ForecastEvidenceRefused("Malformed declared chronology timestamp") from error


def audit_declared_chronology(entries, *, evidence_asof):
    """Inspect each verified history independently of V2 rendering or scores.

    Dataset availability and generation clocks are retrospective local claims.
    No returned state authenticates provider publication or local receipt time.
    """
    if not isinstance(entries, (list, tuple)) or not 1 <= len(entries) <= 64 or any(
        type(entry) is not ForecastHistory for entry in entries
    ):
        raise ForecastEvidenceRefused("Bounded exact forecast histories required")
    asof = _time(evidence_asof)
    seen, cases = set(), []
    for entry in entries:
        checked = verify_outcome_history(entry.forecast_path, entry.forecast_review,
                                         evidence_asof=asof, history=entry.history,
                                         expected_head=entry.expected_head,
                                         source_review=entry.source_review)
        forecast = checked["forecast"]
        identity = forecast["forecast_sha256"]
        if identity in seen:
            raise ForecastEvidenceRefused("Duplicate chronology forecast case")
        seen.add(identity)
        fields = forecast["forecast"]
        issue, input_observed = _clock(fields["issued_at"]), _clock(fields["input_observed_at"])
        input_available = _clock(fields["input_available_at"])
        original = _json(entry.forecast_review.manifest_bytes)
        if input_observed > input_available or input_available > issue or issue > asof:
            raise ForecastEvidenceRefused("Forecast issue-time input chronology conflicts")
        reasons = []
        if _clock(original["generated_at"]) > issue:
            reasons.append("RETROSPECTIVE_FORECAST_REVIEW")
        prior_cutoff = None
        for record, item in zip(checked["records"], entry.history):
            review = _json(item[1].manifest_bytes)
            cutoff = _clock(record["outcome_asof"])
            if cutoff > asof or (prior_cutoff is not None and cutoff <= prior_cutoff):
                raise ForecastEvidenceRefused("Outcome chronology regressed or exceeds evaluation")
            if _clock(review["generated_at"]) > cutoff:
                reasons.append("REVIEW_POSTDATES_OUTCOME_CUTOFF")
            observation = record["observation"]
            if observation is not None:
                observed = _clock(observation["observed_at"])
                available = _clock(observation["available_at"])
                if observed > available or available > cutoff:
                    raise ForecastEvidenceRefused("Observed outcome publication conflicts with cutoff")
                if record["event"] == "CORRECTION" and prior_cutoff is not None and available <= prior_cutoff:
                    reasons.append("CORRECTION_CLAIMED_AVAILABLE_BEFORE_PRIOR_OUTCOME")
            prior_cutoff = cutoff
        cases.append({"forecast_sha256": identity, "asset_id": fields["asset_id"],
                      "model_version": fields["model_version"], "issued_at": issue.isoformat(),
                      "source_id": original["source"]["id"], "history_n": len(checked["records"]),
                      "declared_clock_consistency": "UNVERIFIED" if reasons else "CONSISTENT",
                      "reasons": sorted(set(reasons)), "provider_publication_witnessed": False,
                      "local_receipt_time_bound": False, "authoritative_scored_n": 0})
    return {"schema": "AFI_DECLARED_CHRONOLOGY_AUDIT_V1", "asof": asof.isoformat(),
            "cases": sorted(cases, key=lambda case: case["forecast_sha256"]),
            "independent_attestation": False, "authoritative_scored_n": 0,
            "production_approved": False}
