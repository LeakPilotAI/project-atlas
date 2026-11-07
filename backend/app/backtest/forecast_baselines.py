"""Pure synthetic AFI baselines. No fitting against real/provider data is admitted."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta

from app.backtest.forecast_dataset import (
    DatasetReview,
    _date,
    _future_closes,
    _grid,
    _json,
    review_dataset,
)
from app.backtest.forecast_evaluation import (
    Forecast,
    ForecastEvidenceRefused,
    Observation,
    _asset,
    _number,
    _time,
    select_asof,
)
from app.backtest.forecast_source import validate_source


def canonical(value):
    """Canonical bounded research artifact encoding; no authentication implied."""
    if isinstance(value, datetime):
        return _time(value).isoformat()
    raise TypeError("Unsupported artifact value")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, default=canonical, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def checked_dataset(review, asof):
    if type(review) is not DatasetReview:
        raise ForecastEvidenceRefused("Exact dataset review required")
    checked = review_dataset(review.manifest_bytes, review.payload_bytes, asof=_time(asof))
    if checked != review or checked.status != "ACCEPTED_SYNTHETIC":
        raise ForecastEvidenceRefused("Synthetic accepted dataset integrity required")
    return _json(review.manifest_bytes), _json(review.payload_bytes)


@dataclass(frozen=True)
class BaselineModel:
    schema: str
    asset_id: str
    asset_class: str
    method: str
    lookback: int
    horizon: str
    issued_at: datetime
    dataset_id: str
    dataset_version: str
    dataset_sha256: str
    manifest_sha256: str
    implementation_sha256: str
    training: tuple[Observation, ...]
    training_sha256: str
    reference_price: float
    drift_per_session: float
    production_approved: bool = False
    release_source_sha256: str | None = None


def fit_baseline(review, *, asset_id, issued_at, evidence_asof, method="NO_CHANGE", lookback=20, horizon="1D", source_review=None):
    """Fit last-value or endpoint drift, using ONLY revisions known by issuance.

    Contiguous eligible close history is required. Drift is per trading/UTC
    close, not calendar day; corporate-action unit changes refuse.
    """
    release_sha = validate_source(source_review) if source_review is not None else None
    manifest, payload = checked_dataset(review, evidence_asof)
    issued_at = _time(issued_at)
    if issued_at > _time(evidence_asof):
        raise ForecastEvidenceRefused("Not-yet-issued model")
    if method not in ("NO_CHANGE", "ENDPOINT_DRIFT") or horizon not in ("1D", "5D"):
        raise ForecastEvidenceRefused("Unsupported baseline method/horizon")
    if type(lookback) is not int or not 2 <= lookback <= 10000:
        raise ForecastEvidenceRefused("Bounded explicit training sample required")
    asset = next((a for a in manifest["assets"] if a["asset_id"] == asset_id), None)
    if asset is None:
        raise ForecastEvidenceRefused("Unknown training asset")
    _asset(asset_id, asset["asset_class"])
    member = next(u for u in payload["universe"] if u["asset_id"] == asset_id)
    if (_date(member["listed_at"]) > issued_at or _date(member["listing_available_at"]) > issued_at
            or (member["delisted_at"] is not None and _date(member["delisted_at"]) <= issued_at)):
        raise ForecastEvidenceRefused("Asset outside issue-time universe")
    selected = select_asof(review.observations, asset_id=asset_id, asset_class=asset["asset_class"],
                           cutoff=issued_at, max_age=timedelta(seconds=asset["freshness_seconds"]))
    if selected["record"] is None:
        raise ForecastEvidenceRefused("Fresh training reference unavailable")
    latest = {}
    for row in review.observations:
        if row.asset_id == asset_id and row.observed_at <= issued_at and row.available_at <= issued_at:
            prior = latest.get(row.observed_at)
            if prior is None or row.available_at > prior.available_at:
                latest[row.observed_at] = row
    rows = tuple(latest[t] for t in sorted(latest))[-lookback:]
    if len(rows) < lookback:
        raise ForecastEvidenceRefused("Insufficient known-at training history")
    expected = _grid(rows[0].observed_at, rows[-1].observed_at, asset)
    if [r.observed_at for r in rows] != expected:
        raise ForecastEvidenceRefused("Training history has an unavailable or missing session")
    if any(a["asset_id"] == asset_id and a["kind"] == "SPLIT"
           and rows[0].observed_at < _date(a["effective_at"]) <= issued_at for a in payload["actions"]):
        raise ForecastEvidenceRefused("Cross-split training units not accepted")
    reference = rows[-1].value
    slope = (reference - rows[0].value) / (len(rows) - 1) if method == "ENDPOINT_DRIFT" else 0.0
    _number(slope)
    # Version/hash binds the declared algorithm and all fitting conventions.
    implementation = fingerprint({"algorithm": "AFI_BASELINE_V1", "methods": ["LAST_CLOSE", "ENDPOINT_PER_SESSION"],
                                  "missing": "REFUSE", "split": "REFUSE", "training": "AVAILABLE_BY_ISSUE"})
    if release_sha is not None:
        implementation = fingerprint({"algorithm_sha256":implementation,"release_source_sha256":release_sha})
    return BaselineModel("AFI_BASELINE_MODEL_V1", asset_id, asset["asset_class"], method, lookback, horizon,
                         issued_at, manifest["dataset_id"], manifest["version"], review.content_sha256,
                         review.manifest_sha256, implementation, rows,
                         fingerprint([asdict(r) for r in rows]), reference, slope, release_source_sha256=release_sha)


def model_fingerprint(model):
    if type(model) is not BaselineModel:
        raise ForecastEvidenceRefused("Exact baseline artifact required")
    return fingerprint(model_payload(model))


def model_payload(model):
    result = asdict(model)
    if model.release_source_sha256 is None:
        result.pop("release_source_sha256")
    return result



def model_configuration_sha256(model):
    """Stable declared parameters, not fitted values or independent model approval."""
    if type(model) is not BaselineModel:
        raise ForecastEvidenceRefused("Exact model configuration required")
    return fingerprint({"schema":"AFI_BASELINE_CONFIGURATION_V1","method":model.method,
                        "lookback":model.lookback,"horizon":model.horizon,
                        "implementation_sha256":model.implementation_sha256})

def predict_baseline(model, review, *, evidence_asof, source_review=None):
    """Refit-and-compare before trusting supplied parameters; no fixture authority."""
    if type(model) is not BaselineModel:
        raise ForecastEvidenceRefused("Exact baseline artifact required")
    expected = fit_baseline(review, asset_id=model.asset_id, issued_at=model.issued_at,
                            evidence_asof=evidence_asof, method=model.method, lookback=model.lookback, horizon=model.horizon, source_review=source_review)
    if expected != model:
        raise ForecastEvidenceRefused("Substituted or inconsistent fitted artifact")
    manifest, payload = checked_dataset(review, evidence_asof)
    asset = next(a for a in manifest["assets"] if a["asset_id"] == model.asset_id)
    closes = _future_closes(model.issued_at,asset)
    steps = 1 if model.horizon == "1D" else 5
    if len(closes) < steps:
        raise ForecastEvidenceRefused("Target calendar unavailable")
    target = closes[steps-1]
    if any(a["asset_id"] == model.asset_id and a["kind"] == "SPLIT"
           and model.training[-1].observed_at < _date(a["effective_at"]) <= target for a in payload["actions"]):
        raise ForecastEvidenceRefused("Cross-split target units not accepted")
    point = _number(model.reference_price + steps * model.drift_per_session, positive=True)
    identity = model_fingerprint(model)
    return Forecast(identity, model.asset_id, model.asset_class, model.horizon, model.issued_at, target,
                    max(r.available_at for r in model.training), model.training[-1].observed_at,
                    model.training[-1].available_at, model.reference_price, point, model.method,
                    model.implementation_sha256, model.dataset_id, model.dataset_sha256,
                    model.implementation_sha256, "SYNTHETIC", dataset_manifest_sha256=model.manifest_sha256,
                    dataset_version=model.dataset_version,model_configuration_sha256=model_configuration_sha256(model))


PROBABILITY_METHOD = 'EMPIRICAL_UP_LAPLACE_V1'


def probability_algorithm():
    """Fresh fixed declaration shared by publication and evaluation protocols."""
    return {'method':PROBABILITY_METHOD,'binary_event':'NEXT_CLOSE_STRICTLY_ABOVE_REFERENCE; FLAT_IS_NOT_UP',
            'training':'ISSUE_TIME_KNOWN_CONTIGUOUS_CLOSE_TRANSITIONS','alpha':1,'beta':1,'horizon':'1D'}


def predict_probability_baseline(model, review, *, evidence_asof, source_review=None):
    """Return a synthetic next-close frequency baseline and its training audit.

    Laplace smoothing is a fixed convention, not a calibrated probability model.
    The point model is refitted/verified first; no unavailable revision or future
    close enters its contiguous training window. Only one-session targets fit
    this event definition. No five-day extrapolation is inferred.
    """
    forecast=predict_baseline(model,review,evidence_asof=evidence_asof,source_review=source_review)
    if model.horizon!='1D':raise ForecastEvidenceRefused('Empirical probability requires a one-session target')
    changes=[b.value-a.value for a,b in zip(model.training,model.training[1:])]
    up=sum(v>0 for v in changes);down=sum(v<0 for v in changes);flat=sum(v==0 for v in changes)
    probability=(up+1)/(len(changes)+2)
    algorithm=probability_algorithm()
    implementation=fingerprint({'point_implementation_sha256':model.implementation_sha256,'probability_algorithm':algorithm})
    configuration=fingerprint({'schema':'AFI_PROBABILITY_CONFIGURATION_V1','point_configuration_sha256':forecast.model_configuration_sha256,'probability_algorithm':algorithm})
    identity=fingerprint({'point_forecast_id':forecast.forecast_id,'probability_implementation_sha256':implementation})
    result=replace(forecast,forecast_id=identity,model_id=forecast.model_id+'_EMPIRICAL_UP',model_version=implementation,
                   code_sha256=implementation,model_configuration_sha256=configuration,probability_up=probability)
    audit={**algorithm,'transition_n':len(changes),'up_n':up,'down_n':down,'flat_n':flat,
           'probability_up':probability,'training_sha256':model.training_sha256,
           'implementation_sha256':implementation,'configuration_sha256':configuration,
           'calibration_established':False,'predictive_skill_established':False,'production_approved':False,'trading_authority':False}
    return result,audit
