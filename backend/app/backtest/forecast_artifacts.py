"""Isolated synthetic forecast artifacts; reuse checked durable I/O.

Exclusive create preserves partial failures; readers validate complete canonical
bytes. Not crash-atomic namespace publication, an independent history witness,
or a solution to hostile/privileged filesystem replacement.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

from app.backtest.forecast_baselines import (
    PROBABILITY_METHOD,
    canonical,
    fingerprint,
    fit_baseline,
    model_fingerprint,
    model_payload,
    predict_baseline,
    predict_probability_baseline,
)
from app.backtest.forecast_dataset import _json
from app.backtest.forecast_evaluation import ForecastEvidenceRefused, forecast_fingerprint
from app.backtest.forecast_source import validate_source
from app.backtest.forecast_uncertainty import predict_interval
from app.core.durable_io import sync_parent, write_flushed


def artifact_envelope(review, model, *, evidence_asof, interval=None, source_review=None, probability_method=None, _legacy_configuration=False):
    if probability_method is not None and (type(probability_method) is not str or probability_method!=PROBABILITY_METHOD or _legacy_configuration):
        raise ForecastEvidenceRefused('Explicit supported probability method and configuration binding required')
    forecast = predict_baseline(model, review, evidence_asof=evidence_asof, source_review=source_review)
    if _legacy_configuration:
        forecast=replace(forecast,model_configuration_sha256=None)
    if interval is not None:
        with_interval = predict_interval(review, interval, issued_at=model.issued_at, evidence_asof=evidence_asof, source_review=source_review)
        if _legacy_configuration:
            with_interval=replace(with_interval,model_configuration_sha256=None)
        # Every point-forecast field must match, not merely method/price.
        point_identity = replace(with_interval, forecast_id=forecast.forecast_id,
                                 lower=None, upper=None, interval_level=None)
        if point_identity != forecast or interval["selection"]["lookback"] != model.lookback:
            raise ForecastEvidenceRefused("Interval belongs to a different fitted model")
        forecast = with_interval
    probability=None
    if probability_method is not None:
        probabilistic,probability=predict_probability_baseline(model,review,evidence_asof=evidence_asof,source_review=source_review)
        if interval is not None:
            probabilistic=replace(probabilistic,lower=forecast.lower,upper=forecast.upper,interval_level=forecast.interval_level,
                                  forecast_id=fingerprint({'interval_forecast_id':forecast.forecast_id,'probability_forecast_id':probabilistic.forecast_id}))
        forecast=probabilistic
    result = {"schema": "AFI_SYNTHETIC_FORECAST_ARTIFACT_V1", "model": model_payload(model),
              "model_sha256": model_fingerprint(model), "forecast": asdict(forecast),
              "forecast_sha256": forecast_fingerprint(forecast), "interval": interval,
              "evidence_class": "SYNTHETIC", "production_approved": False, "trading_authority": False}
    if forecast.model_configuration_sha256 is None:
        result["forecast"].pop("model_configuration_sha256")
    if source_review is not None:
        result["schema"] = "AFI_SYNTHETIC_FORECAST_ARTIFACT_V2"
        result["release_source_sha256"] = validate_source(source_review)
        result["release_source_manifest"] = _json(source_review.manifest_bytes)
    if probability_method is not None:
        result['schema']='AFI_SYNTHETIC_FORECAST_ARTIFACT_V3'
        result['probability_method']=probability_method
        result['probability_training']=probability
    return {**result, "artifact_sha256": fingerprint(result)}


def artifact_bytes(envelope):
    import json
    raw = (json.dumps(envelope, default=canonical, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()
    if len(raw) > 2_000_000:
        raise ForecastEvidenceRefused("Artifact exceeds output bound")
    return raw


def _root(root):
    root = Path(root).absolute()
    if not root.is_dir() or any(p.is_symlink() or p.is_junction() for p in (root, *root.parents)):
        raise ForecastEvidenceRefused("Existing unlinked isolated output directory required")
    return root


def publish_forecast(root, review, model, *, evidence_asof, interval=None, source_review=None, probability_method=None):
    """Explicit caller-owned fixture root only. No directory provisioning/defaults.

    File sync is re-established on identical retry without rewriting evidence.
    Failed partial files remain, and conflicting retries refuse.
    """
    envelope = artifact_envelope(review, model, evidence_asof=evidence_asof, interval=interval, source_review=source_review, probability_method=probability_method)
    return _publish_raw(root, artifact_bytes(envelope), envelope["artifact_sha256"], ".json")


def publish_research_text(root, text, *, extension):
    """Explicit isolated derived HTML/JSON, with the same checked publication."""
    if type(text) is not str:
        raise ForecastEvidenceRefused("Exact derived text required")
    raw = text.encode("utf-8")
    return _publish_raw(root, raw, hashlib.sha256(raw).hexdigest(), extension)


def _publish_raw(root, raw, identity, extension):
    root = _root(root)
    if (type(raw) is not bytes or len(raw)>2_000_000 or extension not in (".json", ".html")
            or type(identity) is not str or len(identity)!=64 or any(c not in "0123456789abcdef" for c in identity)):
        raise ForecastEvidenceRefused("Bounded exact research artifact identity required")
    output = root/(identity+extension)
    if output.is_symlink() or output.is_junction():
        raise ForecastEvidenceRefused("Linked artifact refused")
    try:
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            write_flushed(handle, raw.decode())
    except FileExistsError:
        if output.stat().st_nlink != 1:
            raise ForecastEvidenceRefused("Hard-linked artifact refused")
        with output.open("r+b") as handle:
            existing = handle.read(2_000_001)
            if existing != raw:
                raise ForecastEvidenceRefused("Conflicting or incomplete immutable artifact")
            os.fsync(handle.fileno())
    sync_parent(output)
    return output


def read_forecast(path, review, *, evidence_asof, source_review=None):
    """Rebuild from dataset/model configuration; never trust stored success flags."""
    path = Path(path)
    _root(path.parent)
    if path.is_symlink() or path.is_junction() or path.stat().st_nlink != 1:
        raise ForecastEvidenceRefused("Linked artifact refused")
    with path.open("rb") as handle:
        raw = handle.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ForecastEvidenceRefused("Artifact exceeds input bound")
    data = _json(raw)
    try:
        m = data["model"]
        model = fit_baseline(review, asset_id=m["asset_id"], issued_at=datetime.fromisoformat(m["issued_at"]),
                             evidence_asof=evidence_asof, method=m["method"], lookback=m["lookback"], horizon=m["horizon"], source_review=source_review)
        expected = artifact_envelope(review, model, evidence_asof=evidence_asof, interval=data["interval"], source_review=source_review,
                                     probability_method=data.get('probability_method'),_legacy_configuration="model_configuration_sha256" not in data["forecast"])
        if path.name != expected["artifact_sha256"]+".json" or raw != artifact_bytes(expected):
            raise ForecastEvidenceRefused("Artifact content/identity differs from reconstructed evidence")
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        if isinstance(error, ForecastEvidenceRefused):
            raise
        raise ForecastEvidenceRefused("Malformed forecast artifact") from error
    return _json(raw)


def audit_expected_history(root, expected_ids, review, *, evidence_asof, source_review=None):
    """Compare explicit caller-supplied commitments, never infer history completeness."""
    root = _root(root)
    if (not isinstance(expected_ids, (list, tuple)) or len(expected_ids) > 10000
            or any(type(x) is not str or len(x) != 64 or any(c not in "0123456789abcdef" for c in x) for x in expected_ids)
            or len(set(expected_ids)) != len(expected_ids)):
        raise ForecastEvidenceRefused("Bounded exact expected artifact identities required")
    missing, verified = [], []
    for identity in expected_ids:
        path = root/(identity+".json")
        if not path.exists():
            missing.append(identity)
        else:
            read_forecast(path, review, evidence_asof=evidence_asof, source_review=source_review)
            verified.append(identity)
    return {"status": "MISSING_EXPECTED_EVIDENCE" if missing else "EXPECTED_SUBSET_VERIFIED",
            "verified": verified, "missing": missing, "history_completeness_verified": False,
            "production_approved": False, "recovery_authorized": False}
