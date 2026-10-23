"""Offline multi-market comparison and explicitly assumption-driven scenarios."""
from __future__ import annotations

import math

from app.backtest.forecast_artifacts import artifact_envelope
from app.backtest.forecast_baselines import fingerprint
from app.backtest.forecast_dataset import _json
from app.backtest.forecast_evaluation import ForecastEvidenceRefused, _number, _time


def _comparison_percent(numerator, denominator):
    """Preserve ordinary arithmetic; recover only avoidable intermediate overflow."""
    value = 100*numerator/denominator
    if not math.isfinite(value):
        value = (numerator/denominator)*100
    if not math.isfinite(value) or (numerator != 0 and value == 0):
        raise ForecastEvidenceRefused('Normalized comparison exceeds supported numeric range')
    return value


def compare_forecasts(entries, *, evidence_asof, source_review=None):
    """Reconstruct each forecast; compare normalized deltas without pooled prices.

    One forecast is not an accuracy sample. No cross-asset ranking, confidence or
    calibration claim is inferred from a predicted percentage change.
    """
    if not isinstance(entries, (list, tuple)) or not 1 <= len(entries) <= 64:
        raise ForecastEvidenceRefused("Bounded explicit comparison entries required")
    entries = tuple(entries)
    rows, identities = [], set()
    for entry in entries:
        if type(entry) is not tuple or len(entry) not in (2,3,4,5):
            raise ForecastEvidenceRefused("Exact dataset/model/optional-interval/probability/source entry required")
        review, model = entry[:2]
        effective_source=entry[4] if len(entry)==5 else source_review
        if len(entry)==5 and source_review is not None and effective_source!=source_review:
            raise ForecastEvidenceRefused('Conflicting global and per-entry source binding')
        envelope = artifact_envelope(review, model, evidence_asof=evidence_asof, source_review=effective_source,
                                     interval=entry[2] if len(entry)>=3 else None,probability_method=entry[3] if len(entry)>=4 else None)
        forecast = envelope["forecast"]
        identity = envelope["forecast_sha256"]
        if identity in identities:
            raise ForecastEvidenceRefused("Repeated comparison forecast")
        identities.add(identity)
        manifest = _json(review.manifest_bytes)
        asset = next(a for a in manifest["assets"] if a["asset_id"]==forecast["asset_id"])
        outcomes = [r for r in review.observations if r.asset_id==forecast["asset_id"]
                    and r.observed_at==forecast["target_at"] and r.available_at<=_time(evidence_asof)]
        outcome = max(outcomes,key=lambda r:r.available_at) if outcomes else None
        implied = _comparison_percent(forecast["point"]-forecast["reference_price"], forecast["reference_price"])
        absolute_error = abs(forecast["point"]-outcome.value) if outcome else None
        relative_error = _comparison_percent(absolute_error, outcome.value) if outcome else None
        rows.append({"asset_id":forecast["asset_id"],"asset_class":forecast["asset_class"],
                     "currency":asset["currency"],"method":forecast["model_id"],"horizon":forecast["horizon"],
                     "issued_at":forecast["issued_at"].isoformat(),"target_at":forecast["target_at"].isoformat(),
                     "reference":forecast["reference_price"],"point":forecast["point"],"implied_change_percent":implied,
                     "actual":outcome.value if outcome else None,"status":"RESOLVED_SYNTHETIC" if outcome else "PENDING",
                     "absolute_error":absolute_error,
                     "relative_error_percent":relative_error,
                     "lower":forecast["lower"],"upper":forecast["upper"],"interval_level":forecast["interval_level"],
                     "probability_up":forecast["probability_up"],"probability_method":envelope.get('probability_method'),
                     "dataset_id":forecast["dataset_id"],"dataset_version":forecast["dataset_version"],
                     "dataset_sha256":review.content_sha256,"manifest_sha256":review.manifest_sha256,
                     "release_source_sha256":model.release_source_sha256,
                     "source_binding":"SUPPLIED_ARCHIVE_BYTES_VERIFIED" if effective_source else "UNBOUND_LEGACY_DIAGNOSTIC",
                     "forecast_sha256":identity,"training_n":len(model.training),"missing_n":review.missing_n,
                     "accuracy_status":"INSUFFICIENT_EVIDENCE","evidence_class":"SYNTHETIC"})
    return {"schema":"AFI_SYNTHETIC_COMPARISON_V1","asof":_time(evidence_asof).isoformat(),
            "rows":sorted(rows,key=lambda r:(r["asset_class"],r["asset_id"],r["horizon"],r["method"],r["issued_at"])),
            "pooled_price_error":None,"ranking":None,"calibration_established":False,
            "production_approved":False,"trading_authority":False,"predictive_skill_established":False}


def scenario_research(*, base_year, milestones, annual_assumptions):
    """Conditional index paths, NOT statistical forecasts or probability intervals.

    Assumptions are explicit user/research inputs. No prices, automatic growth
    estimate, target guarantee or scenario probability is manufactured.
    """
    if type(base_year) is not int or not 1900 <= base_year <= 2100:
        raise ForecastEvidenceRefused("Explicit scenario base year required")
    if (not isinstance(milestones,(list,tuple)) or not 1<=len(milestones)<=20
            or any(type(y) is not int or not base_year<y<=base_year+100 for y in milestones)
            or len(set(milestones))!=len(milestones)):
        raise ForecastEvidenceRefused("Explicit unique future scenario years required")
    if type(annual_assumptions) is not dict or set(annual_assumptions)!={"bear","base","bull"}:
        raise ForecastEvidenceRefused("Explicit bear/base/bull assumptions required")
    rates = {k:_number(v) for k,v in annual_assumptions.items()}
    if not -1<rates["bear"]<=rates["base"]<=rates["bull"]<=.5:
        raise ForecastEvidenceRefused("Unsupported or unordered scenario assumptions")
    rows = [{"year":y,"years":y-base_year,"conditional_index":{k:100*(1+v)**(y-base_year) for k,v in rates.items()}}
            for y in sorted(milestones)]
    if any(not math.isfinite(value) or value <= 0
           for row in rows for value in row['conditional_index'].values()):
        raise ForecastEvidenceRefused('Scenario index exceeds supported positive finite numeric range')
    result = {"schema":"AFI_ASSUMPTION_SCENARIOS_V1","base_year":base_year,"base_index":100,
              "unit":"ILLUSTRATIVE_INDEX_NOT_ASSET_PRICE","annual_assumptions":rates,"milestones":rows,
              "status":"CONDITIONAL_SCENARIOS_NOT_FORECASTS","probabilities":None,"coverage_guarantee":False,
              "limitations":["Structural breaks and changing growth are not modeled","Returns are assumptions, not fitted estimates",
                             "No inflation, dividends, fees, taxes or market-calendar claim","Long horizons have unquantified uncertainty"],
              "production_approved":False,"trading_authority":False}
    return {**result,"scenario_sha256":fingerprint(result)}
