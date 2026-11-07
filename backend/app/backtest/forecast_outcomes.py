"""Immutable synthetic outcome/correction artifacts, never trading or recovery authority.

Caller-supplied expected heads detect missing chain evidence. They are NOT an
independent witness or exclusion of external writers/forks/full-machine rollback.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app.backtest.forecast_artifacts import _publish_raw, _root, artifact_bytes, read_forecast
from app.backtest.forecast_baselines import checked_dataset, fingerprint
from app.backtest.forecast_dataset import _date, _hash, _json
from app.backtest.forecast_evaluation import (
    Forecast,
    ForecastEvidenceRefused,
    Outcome,
    _time,
    score_forecasts,
)
from app.backtest.forecast_source import validate_source


def _forecast(data):
    fields = dict(data['forecast'])
    for name in ('issued_at','target_at','training_available_through','input_observed_at','input_available_at'):
        fields[name] = datetime.fromisoformat(fields[name])
    return Forecast(**fields)


def _pin_version(manifest, digest, versions):
    key = (manifest['dataset_id'], manifest['version'])
    if key in versions and versions[key] != digest:
        raise ForecastEvidenceRefused('Dataset version reused with different content')
    versions[key] = digest


def _pin_records(review, committed):
    rows = {r['record_id']:fingerprint(r) for r in _json(review.payload_bytes)['records']}
    if any(rows.get(key)!=digest for key,digest in committed.items()):
        raise ForecastEvidenceRefused('Committed as-published records were removed or rewritten')
    committed.update(rows)


def _derive(forecast_data, forecast_review, outcome_review, *, evidence_asof, outcome_asof, previous, versions, committed, outcome_source):
    original, _ = checked_dataset(forecast_review, evidence_asof)
    manifest, payload = checked_dataset(outcome_review, evidence_asof)
    forecast = _forecast(forecast_data)
    cutoff = _time(outcome_asof)
    if not forecast.issued_at <= cutoff <= _time(evidence_asof):
        raise ForecastEvidenceRefused('Outcome observation outside available evidence window')
    if manifest['dataset_id'] != original['dataset_id'] or manifest['source']['id'] != original['source']['id']:
        raise ForecastEvidenceRefused('Outcome dataset/source identity mismatch')
    original_asset = next(a for a in original['assets'] if a['asset_id']==forecast.asset_id)
    asset = next((a for a in manifest['assets'] if a['asset_id']==forecast.asset_id),None)
    if asset != original_asset:
        raise ForecastEvidenceRefused('Outcome asset/units/calendar convention changed')
    if any(a['asset_id']==forecast.asset_id and a['kind']=='SPLIT'
           and forecast.input_observed_at < _date(a['effective_at']) <= forecast.target_at for a in payload['actions']):
        raise ForecastEvidenceRefused('Cross-split outcome units not accepted')
    _pin_version(manifest, outcome_review.content_sha256, versions)
    _pin_records(outcome_review,committed)
    source_sha = None
    if outcome_source is not None:
        source_sha = validate_source(outcome_source)
        if 'app/backtest/forecast_outcomes.py' not in dict(outcome_source.source_files):
            raise ForecastEvidenceRefused('Outcome implementation absent from source archive')
    candidates = [r for r in outcome_review.observations if r.asset_id==forecast.asset_id and r.observed_at==forecast.target_at]
    available = [r for r in candidates if r.available_at<=cutoff]
    row = max(available,key=lambda r:r.available_at) if available else None
    status = ('RESOLVED' if row else 'PENDING_TARGET' if cutoff<forecast.target_at
              else 'PENDING_PUBLICATION' if candidates else 'MISSING_OUTCOME')
    event = 'OBSERVATION'
    if previous is not None:
        if cutoff <= datetime.fromisoformat(previous['outcome_asof']):
            raise ForecastEvidenceRefused('Outcome history cannot be backdated or forked at the same observation time')
        prior = previous['observation']
        if prior is not None:
            if row is None or row.available_at < datetime.fromisoformat(prior['available_at']):
                raise ForecastEvidenceRefused('Previously resolved evidence disappeared or regressed')
            event = 'CORRECTION' if (row.value,row.revision,row.record_id)!=(prior['value'],prior['revision'],prior['record_id']) else 'REOBSERVATION'
        elif row is not None:
            event = 'RESOLUTION'
    outcomes = [] if row is None else [Outcome(forecast.forecast_id,forecast.asset_id,forecast.asset_class,forecast.target_at,
                                               row.observed_at,row.available_at,row.value,row.source_id,row.revision,'SYNTHETIC')]
    score = score_forecasts([forecast],outcomes,asof=cutoff)
    result = {'schema':'AFI_SYNTHETIC_OUTCOME_V1','forecast_artifact_sha256':forecast_data['artifact_sha256'],
              'forecast_sha256':forecast_data['forecast_sha256'],'asset_id':forecast.asset_id,
              'forecast_id':forecast.forecast_id,'target_at':forecast.target_at.isoformat(),
              'forecast_dataset_sha256':forecast_review.content_sha256,'outcome_dataset_sha256':outcome_review.content_sha256,
              'outcome_manifest_sha256':outcome_review.manifest_sha256,'outcome_dataset_version':manifest['version'],
              'outcome_asof':cutoff.isoformat(),'status':status,'event':event,
              'previous_outcome_sha256':previous['artifact_sha256'] if previous else None,
              'observation':asdict(row) if row else None,'evaluation':score,
              'outcome_source_sha256':source_sha,'evidence_class':'SYNTHETIC',
              'history_completeness_verified':False,'external_writer_exclusion_established':False,
              'production_approved':False,'trading_authority':False,'recovery_authorized':False}
    # Normalize times before comparisons with persisted JSON.
    result = _json(artifact_bytes(result))
    return {**result,'artifact_sha256':fingerprint(result)}


def _read(path):
    path = Path(path)
    _root(path.parent)
    if path.is_symlink() or path.is_junction() or path.stat().st_nlink != 1:
        raise ForecastEvidenceRefused('Linked outcome artifact refused')
    with path.open('rb') as handle:
        raw = handle.read(2_000_001)
    if len(raw)>2_000_000:
        raise ForecastEvidenceRefused('Outcome artifact exceeds bound')
    data = _json(raw)
    if type(data) is not dict or type(data.get('artifact_sha256')) is not str:
        raise ForecastEvidenceRefused('Malformed outcome artifact')
    _hash(data['artifact_sha256'])
    if path.name != data['artifact_sha256']+'.json':
        raise ForecastEvidenceRefused('Outcome filename identity mismatch')
    return raw,data


def verify_outcome_history(forecast_path, forecast_review, *, evidence_asof, history=(), expected_head=None, source_review=None):
    """Reconstruct every supplied link against its original dataset/source archive.

    Entries are (path, dataset_review[, outcome_source_review]); no directory
    scan silently substitutes for an explicit expected head or source evidence.
    """
    if not isinstance(history,(list,tuple)) or len(history)>128:
        raise ForecastEvidenceRefused('Bounded explicit outcome history required')
    if bool(history) != (expected_head is not None):
        raise ForecastEvidenceRefused('Explicit expected history head required')
    if expected_head is not None:
        _hash(expected_head)
    data = read_forecast(forecast_path,forecast_review,evidence_asof=evidence_asof,source_review=source_review)
    original,_ = checked_dataset(forecast_review,evidence_asof)
    versions = {(original['dataset_id'],original['version']):forecast_review.content_sha256}
    committed = {}
    _pin_records(forecast_review,committed)
    verified = []
    for item in tuple(history):
        if type(item) is not tuple or len(item) not in (2,3):
            raise ForecastEvidenceRefused('Exact outcome history entry required')
        path,review = item[:2]
        outcome_source = item[2] if len(item)==3 else None
        raw,record = _read(path)
        try:
            expected = _derive(data,forecast_review,review,evidence_asof=evidence_asof,
                               outcome_asof=datetime.fromisoformat(record['outcome_asof']),
                               previous=verified[-1] if verified else None,versions=versions,committed=committed,outcome_source=outcome_source)
        except (KeyError,TypeError,ValueError) as error:
            if isinstance(error,ForecastEvidenceRefused):
                raise
            raise ForecastEvidenceRefused('Malformed outcome history') from error
        if record != expected or raw != artifact_bytes(expected):
            raise ForecastEvidenceRefused('Outcome history differs from reconstructed evidence')
        verified.append(expected)
    if verified and verified[-1]['artifact_sha256'] != expected_head:
        raise ForecastEvidenceRefused('Expected outcome history head is missing or replaced')
    return {'forecast':data,'records':verified,'versions':versions,'committed':committed,'expected_subset_verified':True,
            'history_completeness_verified':False,'production_approved':False}


def preview_outcome(forecast_path, forecast_review, outcome_review, *, evidence_asof, outcome_asof,
                   history=(), expected_head=None, source_review=None, outcome_source=None):
    """Reconstruct the exact proposed record without opening an output file."""
    verified = verify_outcome_history(forecast_path,forecast_review,evidence_asof=evidence_asof,
                                     history=history,expected_head=expected_head,source_review=source_review)
    records = verified['records']
    previous = records[-1] if records else None
    same_time_retry = previous is not None and datetime.fromisoformat(previous['outcome_asof'])==_time(outcome_asof)
    if same_time_retry:
        previous = records[-2] if len(records)>1 else None
    record = _derive(verified['forecast'],forecast_review,outcome_review,evidence_asof=evidence_asof,
                     outcome_asof=outcome_asof,previous=previous,versions=verified['versions'],committed=verified['committed'],outcome_source=outcome_source)
    if same_time_retry and record != records[-1]:
        raise ForecastEvidenceRefused('Conflicting outcome retry at the same observation time')
    return record


def append_outcome(root, forecast_path, forecast_review, outcome_review, *, evidence_asof, outcome_asof,
                   history=(), expected_head=None, source_review=None, outcome_source=None):
    record=preview_outcome(forecast_path,forecast_review,outcome_review,evidence_asof=evidence_asof,outcome_asof=outcome_asof,
                           history=history,expected_head=expected_head,source_review=source_review,outcome_source=outcome_source)
    path = _publish_raw(root,artifact_bytes(record),record['artifact_sha256'],'.json')
    return path,record
