"""Pure offline forecast-evidence diagnostics, not a model or trading service.

Caller declarations are validated, not authenticated. No data is fetched, no
journal is created and no admission/recovery/execution authority can be granted.
Prices and accuracy from synthetic fixtures are never production skill evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from statistics import fmean

ASSET_CLASSES = frozenset({"US_EQUITY", "ETF", "CRYPTO"})
HORIZONS = frozenset({"1D", "5D", "1W", "1M", "3M", "6M", "1Y", "5Y",
                      "SCENARIO_2030", "SCENARIO_2040", "SCENARIO_2050"})


class ForecastEvidenceRefused(ValueError):
    """Malformed, contradictory or leaking research declarations."""


def _time(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ForecastEvidenceRefused("Timezone-aware evidence time required")
    return value.astimezone(UTC)


def _identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", value):
        raise ForecastEvidenceRefused("Explicit bounded evidence identity required")
    return value


def _number(value, *, positive=False):
    try:
        if type(value) not in (int, float) or not math.isfinite(value) or (positive and value <= 0):
            raise ForecastEvidenceRefused("Finite numeric evidence required")
        return float(value)
    except OverflowError as error:
        raise ForecastEvidenceRefused("Numeric evidence exceeds supported range") from error


def _asset(asset, asset_class):
    _identity(asset)
    if (type(asset_class) is not str or asset_class not in ASSET_CLASSES
            or not asset.startswith(asset_class + ":") or len(asset) <= len(asset_class) + 1):
        raise ForecastEvidenceRefused("Unsupported asset class")


def _bounded(items, expected):
    if not isinstance(items, (list, tuple)) or len(items) > 10000 or any(type(x) is not expected for x in items):
        raise ForecastEvidenceRefused("Bounded typed evidence required")


@dataclass(frozen=True)
class Observation:
    record_id: str
    asset_id: str
    asset_class: str
    observed_at: datetime
    available_at: datetime
    value: float
    source_id: str
    revision: str


def select_asof(observations, *, asset_id, asset_class, cutoff, max_age):
    """Latest observation/revision actually declared available at cutoff."""
    _bounded(observations, Observation)
    observations = tuple(observations)
    _asset(asset_id, asset_class)
    cutoff = _time(cutoff)
    if type(max_age) is not timedelta or max_age <= timedelta(0):
        raise ForecastEvidenceRefused("Positive explicit freshness interval required")
    ids, revisions, candidates = set(), set(), []
    for row in observations:
        for value in (row.record_id, row.source_id, row.revision):
            _identity(value)
        _asset(row.asset_id, row.asset_class)
        observed, available = _time(row.observed_at), _time(row.available_at)
        if available < observed or row.record_id in ids:
            raise ForecastEvidenceRefused("Contradictory availability or repeated observation identity")
        ids.add(row.record_id)
        revision_key = (row.asset_id, row.asset_class, row.source_id, observed, row.revision)
        if revision_key in revisions:
            raise ForecastEvidenceRefused("Reused immutable observation revision identity")
        revisions.add(revision_key)
        _number(row.value, positive=True)
        if row.asset_id == asset_id and row.asset_class == asset_class and observed <= cutoff and available <= cutoff:
            candidates.append(row)
    if not candidates:
        return {"status": "INSUFFICIENT_EVIDENCE", "reason": "NO_AVAILABLE_OBSERVATION", "record": None}
    best_key = max((_time(r.observed_at), _time(r.available_at)) for r in candidates)
    best = [r for r in candidates if (_time(r.observed_at), _time(r.available_at)) == best_key]
    if len(best) != 1:
        raise ForecastEvidenceRefused("Ambiguous equally timed source/revision evidence")
    if cutoff - _time(best[0].observed_at) > max_age:
        return {"status": "INSUFFICIENT_EVIDENCE", "reason": "STALE_OBSERVATION", "record": None}
    return {"status": "AVAILABLE", "reason": None, "record": best[0]}


@dataclass(frozen=True)
class ReplayWindow:
    case_id: str
    issued_at: datetime
    target_at: datetime
    outcome_available_at: datetime | None


def walk_forward_plan(windows, *, min_train=2, test_size=1, embargo=timedelta(0)):
    """Expanding chronological folds; purge all labels unavailable before origin.

    This plans IDs only: feature fitting, calendar semantics, model selection,
    licensed datasets and independent holdout acceptance remain separate work.
    """
    _bounded(windows, ReplayWindow)
    windows = tuple(windows)
    if type(min_train) is not int or min_train < 2 or type(test_size) is not int or test_size < 1:
        raise ForecastEvidenceRefused("Invalid replay sample requirements")
    if type(embargo) is not timedelta or embargo < timedelta(0):
        raise ForecastEvidenceRefused("Nonnegative embargo required")
    ids = set()
    for row in windows:
        _identity(row.case_id)
        if row.case_id in ids or _time(row.target_at) <= _time(row.issued_at):
            raise ForecastEvidenceRefused("Replayed identity or invalid target window")
        if row.outcome_available_at is not None and _time(row.outcome_available_at) < _time(row.target_at):
            raise ForecastEvidenceRefused("Outcome available before target")
        ids.add(row.case_id)
    ordered = sorted(windows, key=lambda r: (_time(r.issued_at), r.case_id))
    if max(0, (len(ordered)-min_train+test_size-1)//test_size) > 128:
        raise ForecastEvidenceRefused("Replay plan exceeds 128 bounded folds; use larger test blocks")
    folds = []
    for start in range(min_train, len(ordered), test_size):
        test = ordered[start:start + test_size]
        origin = min(_time(w.issued_at) for w in test)
        cutoff = origin - embargo
        train = [w for w in ordered[:start] if w.outcome_available_at is not None
                 and _time(w.outcome_available_at) < cutoff and _time(w.target_at) < cutoff
                 and _time(w.issued_at) < origin]
        folds.append({"status": "PLANNED" if len(train) >= min_train else "INSUFFICIENT_EVIDENCE",
                      "origin": origin.isoformat(), "label_cutoff_exclusive": cutoff.isoformat(),
                      "train_ids": [w.case_id for w in train], "test_ids": [w.case_id for w in test],
                      "purged_train_count": start - len(train)})
    return {"status": "PLANNED" if any(f["status"] == "PLANNED" for f in folds) else "INSUFFICIENT_EVIDENCE",
            "folds": folds, "model_fitted": False, "production_approved": False}


@dataclass(frozen=True)
class Forecast:
    forecast_id: str
    asset_id: str
    asset_class: str
    horizon: str
    issued_at: datetime
    target_at: datetime
    training_available_through: datetime
    input_observed_at: datetime
    input_available_at: datetime
    reference_price: float
    point: float
    model_id: str
    model_version: str
    dataset_id: str
    dataset_sha256: str
    code_sha256: str
    evidence_class: str
    probability_up: float | None = None
    lower: float | None = None
    upper: float | None = None
    interval_level: float | None = None
    dataset_manifest_sha256: str | None = None
    dataset_version: str | None = None
    model_configuration_sha256: str | None = None


def _forecast(row):
    if type(row) is not Forecast:
        raise ForecastEvidenceRefused("Exact forecast contract required")
    _asset(row.asset_id, row.asset_class)
    for identity in (row.forecast_id, row.model_id, row.model_version, row.dataset_id):
        _identity(identity)
    if type(row.horizon) is not str or row.horizon not in HORIZONS or type(row.evidence_class) is not str or row.evidence_class not in {"SYNTHETIC", "HISTORICAL", "PROSPECTIVE"}:
        raise ForecastEvidenceRefused("Unsupported horizon or evidence class")
    for value in (row.dataset_sha256, row.code_sha256):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ForecastEvidenceRefused("Dataset and code revision hashes required")
    if (row.dataset_manifest_sha256 is None) != (row.dataset_version is None):
        raise ForecastEvidenceRefused("Incomplete dataset manifest binding")
    if row.dataset_manifest_sha256 is not None:
        if not isinstance(row.dataset_manifest_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", row.dataset_manifest_sha256):
            raise ForecastEvidenceRefused("Invalid manifest hash")
        _identity(row.dataset_version)
    if row.model_configuration_sha256 is not None and (type(row.model_configuration_sha256) is not str or not re.fullmatch(r"[0-9a-f]{64}",row.model_configuration_sha256)):
        raise ForecastEvidenceRefused("Invalid model configuration commitment")
    issued, target = _time(row.issued_at), _time(row.target_at)
    if target <= issued or _time(row.training_available_through) > issued:
        raise ForecastEvidenceRefused("Forecast target or training availability leaks")
    if not _time(row.input_observed_at) <= _time(row.input_available_at) <= issued:
        raise ForecastEvidenceRefused("Input unavailable at issue time")
    _number(row.reference_price, positive=True)
    _number(row.point, positive=True)
    if row.probability_up is not None and not 0 <= _number(row.probability_up) <= 1:
        raise ForecastEvidenceRefused("Invalid up probability")
    interval = (row.lower, row.upper, row.interval_level)
    if any(v is not None for v in interval):
        if any(v is None for v in interval):
            raise ForecastEvidenceRefused("Incomplete interval evidence")
        low, high, level = map(_number, interval)
        if not 0 <= low <= row.point <= high or not 0 < level < 1:
            raise ForecastEvidenceRefused("Invalid interval evidence")


def forecast_fingerprint(row):
    _forecast(row)
    values = {k: (_time(v).isoformat() if isinstance(v, datetime) else v) for k, v in asdict(row).items()}
    # Preserve legacy fingerprints when no stronger dataset binding was supplied.
    if row.dataset_manifest_sha256 is None:
        values.pop("dataset_manifest_sha256")
        values.pop("dataset_version")
    if row.model_configuration_sha256 is None:
        values.pop("model_configuration_sha256")
    raw = json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Outcome:
    forecast_id: str
    asset_id: str
    asset_class: str
    target_at: datetime
    observed_at: datetime
    available_at: datetime
    price: float
    source_id: str
    revision: str
    evidence_class: str


def probability_reliability(probability, minimum_samples=20):
    """Fixed ten-bin descriptive metrics for one caller-declared cohort."""
    if (not isinstance(probability,(list,tuple)) or len(probability)>10000
            or type(minimum_samples) is not int or not 1<=minimum_samples<=10000):
        raise ForecastEvidenceRefused('Bounded probability cohort and sample minimum required')
    for pair in probability:
        if not isinstance(pair,(list,tuple)) or len(pair)!=2 or type(pair[1]) is not int or pair[1] not in (0,1) or not 0<=_number(pair[0])<=1:
            raise ForecastEvidenceRefused('Recorded probability and binary outcome required')
    bins=[]
    for index in range(10):
        sample=[(p,y) for p,y in probability if min(int(p*10),9)==index]
        if sample:
            bins.append({'bin':index,'n':len(sample),'mean_probability':fmean(p for p,_ in sample),
                         'observed_up_fraction':fmean(y for _,y in sample),
                         'status':'DIAGNOSTIC_ONLY' if len(sample)>=minimum_samples else 'INSUFFICIENT_EVIDENCE'})
    return {'probability_n':len(probability),'calibration_bins':bins,
            'brier':fmean((p-y)**2 for p,y in probability) if probability else None,
            'uninformative_half_probability_brier':.25 if probability else None,
            'expected_calibration_error':sum(b['n']*abs(b['mean_probability']-b['observed_up_fraction']) for b in bins)/len(probability) if probability else None}


def _metrics(pairs, minimum_samples):
    if not pairs:
        return {"n": 0, "status": "INSUFFICIENT_EVIDENCE", "mae": None, "rmse": None,
                "no_change_mae": None, "no_change_rmse": None, "mape_percent": None,
                "smape_percent": None, "mae_ratio_to_no_change": None, "directional_accuracy": None, "brier": None,
                "flat_outcome_n": 0, "probability_n": 0, "expected_calibration_error": None,
                "uninformative_half_probability_brier": None, "interval_n": 0,
                "interval_coverage": None, "mean_interval_width": None,
                "mean_interval_score": None, "calibration_bins": []}
    errors = [f.point - o.price for f, o in pairs]
    sign = lambda x: (x > 0) - (x < 0)
    probability = [(f.probability_up, int(o.price > f.reference_price)) for f, o in pairs if f.probability_up is not None]
    reliability=probability_reliability(probability,minimum_samples);bins=reliability['calibration_bins']
    interval = [(f, o) for f, o in pairs if f.interval_level is not None]
    scores = []
    for f, o in interval:
        width = f.upper - f.lower
        penalty = max(f.lower - o.price, 0) + max(o.price - f.upper, 0)
        scores.append(width + 2 * penalty / (1 - f.interval_level))
    baseline_mae = fmean(abs(o.price - f.reference_price) for f, o in pairs)
    result = {"n": len(pairs), "status": "DIAGNOSTIC_ONLY" if len(pairs) >= minimum_samples else "INSUFFICIENT_EVIDENCE",
              "mae": fmean(abs(e) for e in errors), "rmse": math.sqrt(fmean(e * e for e in errors)),
              "no_change_mae": baseline_mae,
              "no_change_rmse": math.sqrt(fmean((o.price - f.reference_price) ** 2 for f, o in pairs)),
              "mape_percent": fmean(100 * abs((f.point - o.price) / o.price) for f, o in pairs),
              "smape_percent": fmean(200 * abs(f.point - o.price) / (abs(f.point) + abs(o.price)) for f, o in pairs),
              "mae_ratio_to_no_change": fmean(abs(e) for e in errors) / baseline_mae if baseline_mae else None,
              "directional_accuracy": fmean(sign(f.point - f.reference_price) == sign(o.price - f.reference_price) for f, o in pairs),
              "flat_outcome_n": sum(o.price == f.reference_price for f, o in pairs),
              **{k:v for k,v in reliability.items() if k!='calibration_bins'},
              "interval_n": len(interval), "interval_coverage": fmean(f.lower <= o.price <= f.upper for f, o in interval) if interval else None,
              "mean_interval_width": fmean(f.upper - f.lower for f, _ in interval) if interval else None,
              "mean_interval_score": fmean(scores) if scores else None, "calibration_bins": bins}
    if any(type(v) is float and not math.isfinite(v) for v in result.values()):
        raise ForecastEvidenceRefused("Non-finite aggregate evidence")
    return result


def score_forecasts(forecasts, outcomes, *, asof, minimum_samples=20):
    """Paired diagnostics only; unresolved cases never become zero-error outcomes."""
    _bounded(forecasts, Forecast)
    _bounded(outcomes, Outcome)
    forecasts, outcomes = tuple(forecasts), tuple(outcomes)
    asof = _time(asof)
    if type(minimum_samples) is not int or not 2 <= minimum_samples <= 10000:
        raise ForecastEvidenceRefused("Invalid minimum sample requirement")
    by_id = {}
    cases = {}
    for row in forecasts:
        _forecast(row)
        if row.forecast_id in by_id or _time(row.issued_at) > asof:
            raise ForecastEvidenceRefused("Repeated or not-yet-issued forecast")
        case = (row.asset_id, row.asset_class, row.horizon, _time(row.issued_at), _time(row.target_at),
                row.model_id, row.model_version, row.dataset_id, row.dataset_sha256, row.code_sha256, row.evidence_class, row.interval_level, row.dataset_manifest_sha256, row.dataset_version)
        configurations=cases.setdefault(case,set());configuration=row.model_configuration_sha256
        if configuration in configurations or (configurations and (configuration is None or None in configurations)):
            raise ForecastEvidenceRefused("Duplicate or ambiguous legacy/configured forecast case")
        configurations.add(configuration)
        by_id[row.forecast_id] = row
    resolved = {}
    for outcome in outcomes:
        if outcome.forecast_id not in by_id or outcome.forecast_id in resolved:
            raise ForecastEvidenceRefused("Unknown or repeated outcome forecast identity")
        forecast = by_id[outcome.forecast_id]
        _asset(outcome.asset_id, outcome.asset_class)
        _identity(outcome.source_id)
        _identity(outcome.revision)
        _number(outcome.price, positive=True)
        if (outcome.asset_id != forecast.asset_id or outcome.asset_class != forecast.asset_class
                or outcome.evidence_class != forecast.evidence_class
                or _time(outcome.target_at) != _time(forecast.target_at)
                or _time(outcome.observed_at) != _time(outcome.target_at)
                or _time(outcome.available_at) < _time(outcome.target_at)):
            raise ForecastEvidenceRefused("Outcome provenance/target mismatch")
        resolved[outcome.forecast_id] = outcome
    groups = defaultdict(list)
    pending = 0
    for forecast in forecasts:
        # Never pool price errors across assets, horizons, model/data versions,
        # nominal interval levels or synthetic/real evidence classes.
        key = (forecast.asset_id, forecast.asset_class, forecast.horizon, forecast.model_id,
               forecast.model_version, forecast.dataset_id, forecast.dataset_sha256,
               forecast.code_sha256, forecast.evidence_class, forecast.interval_level,
               forecast.dataset_manifest_sha256, forecast.dataset_version, forecast.model_configuration_sha256)
        groups[key]  # include unresolved cohorts explicitly
        outcome = resolved.get(forecast.forecast_id)
        if outcome is None or _time(outcome.available_at) > asof or _time(forecast.target_at) > asof:
            pending += 1
        else:
            groups[key].append((forecast, outcome))
    try:
        fields = ("asset_id", "asset_class", "horizon", "model_id", "model_version", "dataset_id",
                  "dataset_sha256", "code_sha256", "evidence_class", "interval_level", "dataset_manifest_sha256", "dataset_version", "model_configuration_sha256")
        cohorts = [{"cohort": {k:v for k,v in zip(fields,key,strict=True) if k!="model_configuration_sha256" or v is not None}, **_metrics(pairs, minimum_samples)}
                   for key, pairs in sorted(groups.items(), key=lambda item: repr(item[0]))]
    except (OverflowError, ValueError) as error:
        raise ForecastEvidenceRefused("Numeric scoring refused") from error
    return {"scope": "OFFLINE_DIAGNOSTIC", "asof": asof.isoformat(), "issued_n": len(forecasts),
            "scored_n": len(forecasts) - pending, "pending_n": pending, "cohorts": cohorts,
            "status": "DIAGNOSTIC_ONLY" if any(c["status"] == "DIAGNOSTIC_ONLY" for c in cohorts) else "INSUFFICIENT_EVIDENCE",
            "binary_event": "PRICE_STRICTLY_ABOVE_REFERENCE; FLAT_IS_NOT_UP",
            "baseline": "PAIRED_NO_PRICE_CHANGE_AND_UNINFORMATIVE_P_UP_0.5",
            "calendar_horizon_semantics": "CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED",
            "dataset_authenticated": False, "calibration_established": False,
            "production_approved": False, "trading_authority": False}


def audit_selection_protocol(windows, *, selection_ids, holdout_ids, frozen_at, asof):
    """Validate declared pre-selection freeze; cannot prove an unseen holdout stayed unseen."""
    _bounded(windows, ReplayWindow)
    windows = tuple(windows)
    frozen_at, asof = _time(frozen_at), _time(asof)
    if frozen_at > asof:
        raise ForecastEvidenceRefused("Selection freeze is in the future")
    by_id = {}
    for row in windows:
        _identity(row.case_id)
        if row.case_id in by_id or _time(row.target_at) <= _time(row.issued_at):
            raise ForecastEvidenceRefused("Repeated or invalid selection case")
        if row.outcome_available_at is not None and _time(row.outcome_available_at) < _time(row.target_at):
            raise ForecastEvidenceRefused("Selection label predates target")
        by_id[row.case_id] = row
    groups = []
    for ids in (selection_ids, holdout_ids):
        if (not isinstance(ids, (list, tuple)) or not ids or len(ids) > 10000
                or any(type(x) is not str for x in ids) or len(set(ids)) != len(ids)
                or any(x not in by_id for x in ids)):
            raise ForecastEvidenceRefused("Explicit unique known selection/holdout identities required")
        groups.append(set(ids))
    if groups[0] & groups[1] or groups[0] | groups[1] != set(by_id):
        raise ForecastEvidenceRefused("Contaminated or undeclared selection/holdout partition")
    for key in groups[0]:
        row = by_id[key]
        if row.outcome_available_at is None or _time(row.outcome_available_at) >= frozen_at:
            raise ForecastEvidenceRefused("Selection label was unavailable before freeze")
    if any(_time(by_id[key].issued_at) < frozen_at for key in groups[1]):
        raise ForecastEvidenceRefused("Holdout started before selection freeze")
    return {"status": "CONSISTENT_DECLARATIONS", "selection_n": len(groups[0]),
            "holdout_n": len(groups[1]), "independently_unseen": False,
            "production_approved": False, "trading_authority": False}
