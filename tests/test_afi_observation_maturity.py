"""Synthetic daily-close window and source-completeness acceptance."""
import hashlib
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from app.backtest.forecast_dataset import review_dataset
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_observation_maturity import (
    assess_observation_window,
    score_complete_synthetic_windows,
    summarize_observation_windows,
)
from test_afi_dataset_integrity import ASOF, bound_forecast, encode, fixture, review


def test_exact_maturity_and_one_interval_short():
    data = review(*fixture())
    forecast, _ = bound_forecast(data)
    exact = assess_observation_window(data, forecast, asof=forecast.target_at)
    assert exact['status'] == 'COMPLETE' and exact['available_n'] == 1
    early = assess_observation_window(data, forecast, asof=datetime(2026, 10, 19, 19, 59, tzinfo=UTC))
    assert early['status'] == 'IMMATURE' and early['authoritative_aggregate_eligible'] is False


def test_target_missing_and_late_publication_are_not_complete():
    data = review(*fixture())
    forecast, _ = bound_forecast(data)
    missing = replace(data, observations=tuple(row for row in data.observations if row.observed_at != forecast.target_at))
    with pytest.raises(ForecastEvidenceRefused, match='Substituted'):
        assess_observation_window(missing, forecast, asof=ASOF)
    manifest, payload = fixture()
    payload['records'] = payload['records'][:1]
    manifest['quality']['max_missing_fraction'] = .2
    sparse = review(manifest, payload)
    assert sparse.status == 'INSUFFICIENT_EVIDENCE'
    assert assess_observation_window(sparse, replace(forecast,
        dataset_sha256=sparse.content_sha256, dataset_manifest_sha256=sparse.manifest_sha256),
        asof=ASOF)['status'] == 'UNVERIFIED'


def test_wrong_target_and_nonfinite_dataset_fail_closed():
    data = review(*fixture())
    forecast, _ = bound_forecast(data)
    with pytest.raises(ForecastEvidenceRefused, match='session horizon'):
        assess_observation_window(data, replace(forecast, target_at=forecast.target_at.replace(hour=19)), asof=ASOF)
    manifest, payload = fixture()
    payload['records'][1]['value'] = float('nan')
    with pytest.raises(ValueError):
        review(manifest, payload)


def test_unverified_windows_never_enter_authoritative_aggregate():
    data = review(*fixture())
    forecast, _ = bound_forecast(data)
    complete = assess_observation_window(data, forecast, asof=ASOF)
    report = summarize_observation_windows([complete])
    assert report['statuses']['COMPLETE'] == 1
    assert report['source_cohorts'][0]['source_id'] == 'fixture'
    assert report['authoritative_scored_n'] == 0 and report['authoritative_performance'] is None
    with pytest.raises(ForecastEvidenceRefused, match='authority'):
        summarize_observation_windows([{**complete, 'authoritative_aggregate_eligible': True}])


def test_five_session_window_refuses_missing_interior_close():
    manifest, payload = fixture()
    times = ['2026-10-16T20:00:00+00:00', '2026-10-19T20:00:00+00:00',
             '2026-10-20T20:00:00+00:00', '2026-10-21T20:00:00+00:00',
             '2026-10-22T20:00:00+00:00', '2026-10-23T20:00:00+00:00']
    payload['records'] = [{**payload['records'][0], 'record_id': f'r{i}',
                           'observed_at': value, 'available_at': value,
                           'raw_price': 100+i, 'value': 100+i}
                          for i, value in enumerate(times) if i != 3]
    manifest.update(period_end=times[-1], acquired_at=times[-1], generated_at=times[-1])
    manifest['quality']['max_missing_fraction'] = .2
    raw = encode(payload)
    manifest['content_sha256'] = hashlib.sha256(raw).hexdigest()
    manifest['record_count'] = len(payload['records'])
    asof = datetime(2026, 10, 24, tzinfo=UTC)
    data = review_dataset(encode(manifest), raw, asof=asof)
    forecast, outcome = bound_forecast(data)
    forecast = replace(forecast, horizon='5D', target_at=datetime.fromisoformat(times[-1]))
    outcome = replace(outcome, target_at=forecast.target_at, observed_at=forecast.target_at,
                      available_at=forecast.target_at, price=105)
    result = assess_observation_window(data, forecast, asof=asof)
    assert result['status'] == 'PARTIAL' and result['available_n'] == 4
    assert result['missing_at'] == [times[3]]
    strict = score_complete_synthetic_windows(data, [forecast], [outcome], asof=asof)
    assert strict['excluded_n'] == 1 and strict['diagnostic']['scored_n'] == 0
    assert strict['authoritative_scored_n'] == 0
    payload['records'] = list(reversed(payload['records']))
    raw = encode(payload)
    manifest['content_sha256'] = hashlib.sha256(raw).hexdigest()
    revised = review_dataset(encode(manifest), raw, asof=asof)
    forecast = replace(forecast, dataset_sha256=revised.content_sha256,
                       dataset_manifest_sha256=revised.manifest_sha256)
    assert assess_observation_window(revised, forecast, asof=asof)['status'] == 'CONTRADICTORY'


def test_issue_time_input_and_evaluation_clock_cannot_leak():
    data = review(*fixture())
    forecast, _ = bound_forecast(data)
    with pytest.raises(ForecastEvidenceRefused, match='source-bound'):
        assess_observation_window(data, replace(forecast, reference_price=120), asof=ASOF)
    with pytest.raises(ForecastEvidenceRefused, match='precedes forecast'):
        assess_observation_window(data, forecast,
                                  asof=datetime(2026, 10, 16, 19, tzinfo=UTC))


def test_all_six_states_remain_distinct_in_source_cohort_summary():
    data = review(*fixture())
    forecast, _ = bound_forecast(data)
    base = assess_observation_window(data, forecast, asof=ASOF)
    states = ('COMPLETE', 'IMMATURE', 'PARTIAL', 'MISSING', 'CONTRADICTORY', 'UNVERIFIED')
    rows = [{**base, 'forecast_id': f'case-{index}', 'status': state}
            for index, state in enumerate(states)]
    summary = summarize_observation_windows(rows)
    assert summary['statuses'] == dict.fromkeys(sorted(states), 1)
    assert summary['source_cohorts'][0]['statuses'] == dict.fromkeys(sorted(states), 1)
    assert summary['authoritative_scored_n'] == 0
