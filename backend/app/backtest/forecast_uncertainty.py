"""Synthetic interval diagnostics. No exchangeability or coverage guarantee is granted."""
from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime, timedelta

from app.backtest.forecast_baselines import fingerprint, fit_baseline, predict_baseline
from app.backtest.forecast_evaluation import ForecastEvidenceRefused, _number, _time
from app.backtest.forecast_replay import evaluate_holdout


def fit_interval(review, selection, *, calibration_issues, calibrated_at, evidence_asof, level=.8, source_review=None):
    """Fixed-model absolute-error order statistic; no fitting on holdout outcomes.

    ceil((n+1)*level) is deliberately refused if the sample cannot support a
    finite empirical quantile. Time-series exchangeability is NOT established.
    """
    level = _number(level)
    if not 0 < level < 1:
        raise ForecastEvidenceRefused("Explicit probability level required")
    calibrated_at = _time(calibrated_at)
    if calibrated_at > _time(evidence_asof):
        raise ForecastEvidenceRefused("Calibration freeze is in the future")
    replay = evaluate_holdout(review, selection, holdout_issues=calibration_issues,
                              evidence_asof=evidence_asof, outcome_asof=calibrated_at-timedelta(microseconds=1), source_review=source_review)["reports"][selection["selected_method"]]
    if (replay["refused_n"] or len(replay["outcomes"]) != replay["requested_n"]
            or any(f.issued_at >= calibrated_at or f.target_at >= calibrated_at for f in replay["forecasts"])
            or any(o.available_at >= calibrated_at for o in replay["outcomes"])):
        raise ForecastEvidenceRefused("Calibration requires resolved pre-freeze labels")
    by_id = {o.forecast_id:o for o in replay["outcomes"]}
    errors = sorted(abs(f.point-by_id[f.forecast_id].price) for f in replay["forecasts"])
    rank = math.ceil((len(errors)+1)*level)
    if len(errors) < 20 or rank > len(errors):
        raise ForecastEvidenceRefused("Insufficient finite-sample interval evidence")
    result = {"schema": "AFI_SYNTHETIC_INTERVAL_V1", "selection": selection,
              "calibration_issues": [_time(t).isoformat() for t in calibration_issues],
              "calibrated_at": calibrated_at.isoformat(), "level": level, "n": len(errors),
              "rank": rank, "absolute_error_quantile": errors[rank-1],
              "residuals_sha256": fingerprint(errors), "method": "FIXED_MODEL_ABSOLUTE_RESIDUAL_ORDER_STATISTIC",
              "exchangeability_established": False, "calibration_established": False, "production_approved": False}
    return {**result,"interval_sha256":fingerprint(result)}


def predict_interval(review, interval, *, issued_at, evidence_asof, source_review=None):
    """Reconstruct and verify calibration before applying it to a later forecast."""
    if type(interval) is not dict:
        raise ForecastEvidenceRefused("Exact interval artifact required")
    try:
        expected = fit_interval(review, interval["selection"],
                                calibration_issues=[datetime.fromisoformat(t) for t in interval["calibration_issues"]],
                                calibrated_at=datetime.fromisoformat(interval["calibrated_at"]),
                                evidence_asof=evidence_asof, level=interval["level"], source_review=source_review)
        if interval != expected or _time(issued_at) < datetime.fromisoformat(interval["calibrated_at"]):
            raise ForecastEvidenceRefused("Substituted calibration or forecast predates freeze")
        selection = interval["selection"]
        model = fit_baseline(review, asset_id=selection["asset_id"], issued_at=issued_at, evidence_asof=evidence_asof,
                             method=selection["selected_method"], lookback=selection["lookback"], horizon=selection["horizon"], source_review=source_review)
        point = predict_baseline(model, review, evidence_asof=evidence_asof, source_review=source_review)
        q = interval["absolute_error_quantile"]
        return replace(point, forecast_id=fingerprint({"point":point.forecast_id,"interval":interval["interval_sha256"]}),
                       lower=max(0.0, point.point-q), upper=point.point+q, interval_level=interval["level"])
    except (KeyError, ValueError, TypeError, OverflowError) as error:
        if isinstance(error, ForecastEvidenceRefused):
            raise
        raise ForecastEvidenceRefused("Malformed interval artifact") from error
