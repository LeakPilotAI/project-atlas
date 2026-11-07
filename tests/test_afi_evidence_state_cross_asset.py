"""Cross-asset and publication-order acceptance for offline V2 cases."""

import hashlib
import json
from datetime import UTC, date, datetime

import pytest
from app.backtest.forecast_artifacts import publish_forecast
from app.backtest.forecast_baselines import fit_baseline
from app.backtest.forecast_dataset import _close, review_dataset
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_evidence_state_report import build_evidence_state_report
from app.backtest.forecast_outcomes import append_outcome
from app.backtest.forecast_report import ForecastHistory
from app.backtest.forecast_source import create_source_review
from test_afi_dataset_integrity import encode, fixture
from test_afi_outcomes import changed_review, setup
from test_afi_source_binding import source

ASOF = datetime(2026, 10, 21, 12, tzinfo=UTC)


def cohort_review(asset_class, symbol, source_id):
    manifest, payload = fixture()
    asset_id = f'{asset_class}:{symbol}'
    asset = manifest['assets'][0]
    asset.update(asset_id=asset_id, asset_class=asset_class,
                 timezone='UTC' if asset_class == 'CRYPTO' else 'America/New_York',
                 calendar='CRYPTO_24_7' if asset_class == 'CRYPTO' else 'ATLAS_US_CASH_2026_2028')
    payload['universe'][0]['asset_id'] = asset_id
    days = [date(2026, 10, day) for day in range(14, 21)]
    closes = [close for day in days if (close := _close(day, asset)) is not None]
    payload['records'] = [dict(payload['records'][0], record_id=f'{source_id}-{index}',
                               asset_id=asset_id, source_id=source_id,
                               observed_at=close.isoformat(), available_at=close.isoformat(),
                               raw_price=100 + index, value=100 + index)
                          for index, close in enumerate(closes)]
    manifest.update(dataset_id=f'{asset_class}-{symbol}-{source_id}',
                    period_start=closes[0].isoformat(), period_end=closes[-1].isoformat(),
                    acquired_at=closes[-1].isoformat(), generated_at=closes[-1].isoformat(),
                    record_count=len(closes))
    manifest['source']['id'] = source_id
    raw = encode(payload)
    manifest['content_sha256'] = hashlib.sha256(raw).hexdigest()
    return review_dataset(encode(manifest), raw, asof=ASOF)


def make_case(root, asset_class, symbol, source_id, *, release=None, horizon='1D', resolved=False):
    review = cohort_review(asset_class, symbol, source_id)
    asset_id = f'{asset_class}:{symbol}'
    issued = datetime(2026, 10, 19, 20, 1, tzinfo=UTC)
    if asset_class == 'CRYPTO':
        issued = datetime(2026, 10, 19, 0, 1, tzinfo=UTC)
    model = fit_baseline(review, asset_id=asset_id, issued_at=issued,
                         evidence_asof=ASOF, lookback=2, horizon=horizon,
                         source_review=release)
    path = publish_forecast(root, review, model, evidence_asof=ASOF, source_review=release)
    if not resolved:
        return ForecastHistory(path, review, source_review=release)
    outcome_path, record = append_outcome(root, path, review, review, evidence_asof=ASOF,
                                          outcome_asof=ASOF, source_review=release)
    return ForecastHistory(path, review, ((outcome_path, review),),
                           record['artifact_sha256'], release)


def test_equity_etf_crypto_symbols_sources_and_models_remain_separate(tmp_path):
    releases = [source(), create_source_review(dict(source().source_files), release_id='fixture-v2')]
    entries = []
    for asset_class in ('US_EQUITY', 'ETF', 'CRYPTO'):
        for symbol in ('SAME', 'SECOND'):
            entries.append(make_case(tmp_path, asset_class, symbol, 'fixture-a', resolved=True))
    entries.extend([
        make_case(tmp_path, 'US_EQUITY', 'SAME', 'fixture-b', resolved=True),
        make_case(tmp_path, 'US_EQUITY', 'SAME', 'fixture-a', release=releases[0], resolved=True),
        make_case(tmp_path, 'US_EQUITY', 'SAME', 'fixture-a', release=releases[1], resolved=True),
        make_case(tmp_path, 'US_EQUITY', 'SAME', 'fixture-a', horizon='5D'),
    ])
    report = build_evidence_state_report(entries, evidence_asof=ASOF)
    assert report == build_evidence_state_report(list(reversed(entries)), evidence_asof=ASOF)
    assert len(report['cases']) == 10
    assert {case['cohort']['asset_class'] for case in report['cases']} == {'US_EQUITY', 'ETF', 'CRYPTO'}
    assert {case['cohort']['source_id'] for case in report['cases']} == {'fixture-a', 'fixture-b'}
    same = [case for case in report['cases'] if case['cohort']['asset_id'] == 'US_EQUITY:SAME']
    assert len(same) == 5
    assert len({case['forecast_sha256'] for case in same}) == 5
    assert len({case['cohort']['model_version'] for case in same}) == 3
    assert {case['cohort']['horizon'] for case in same} == {'1D', '5D'}
    assert sum(case['diagnostic_scored_n'] for case in report['cases']) == 9
    assert all(case['authoritative_scored_n'] == 0 for case in report['cases'])
    assert all(case['authoritative_exclusion_reason'] == 'SYNTHETIC_UNAUTHENTICATED'
               for case in report['cases'])


def test_review_publication_after_outcome_cutoff_is_not_diagnostic_score(tmp_path):
    entry = make_case(tmp_path, 'US_EQUITY', 'SAME', 'fixture-a', resolved=True)
    record = json.loads(entry.history[0][0].read_bytes())
    assert record['status'] == 'RESOLVED'
    case = build_evidence_state_report([entry], evidence_asof=ASOF)['cases'][0]
    assert case['publication_order_status'] == 'CONSISTENT_DECLARED_TIMES'
    assert case['diagnostic_scored_n'] == 1
    with pytest.raises(ForecastEvidenceRefused):
        build_evidence_state_report([ForecastHistory(entry.forecast_path, entry.forecast_review,
            entry.history, 'a' * 64, entry.source_review)], evidence_asof=ASOF)


def test_backdated_correction_and_missing_publication_clock_refuse_promotion(tmp_path):
    review, _, forecast_path, output = setup(tmp_path)
    initial = datetime(2026, 10, 19, 1, tzinfo=UTC)
    first_path, first = append_outcome(output, forecast_path, review, review,
                                       evidence_asof=ASOF, outcome_asof=initial)
    revised = changed_review(review)
    manifest, payload = json.loads(revised.manifest_bytes), json.loads(revised.payload_bytes)
    payload['records'][-1]['available_at'] = '2026-10-19T00:30:00+00:00'
    raw = encode(payload)
    manifest['content_sha256'] = hashlib.sha256(raw).hexdigest()
    revised = review_dataset(encode(manifest), raw, asof=ASOF)
    second_path, second = append_outcome(output, forecast_path, review, revised,
                                         evidence_asof=ASOF,
                                         outcome_asof=datetime(2026, 10, 19, 13, tzinfo=UTC),
                                         history=((first_path, review),),
                                         expected_head=first['artifact_sha256'])
    case = build_evidence_state_report([ForecastHistory(forecast_path, review,
        ((first_path, review), (second_path, revised)), second['artifact_sha256'])],
        evidence_asof=ASOF)['cases'][0]
    assert case['revision']['latest_event'] == 'CORRECTION'
    assert case['publication_order_status'] == 'UNVERIFIED_BACKDATED_CORRECTION'
    assert case['diagnostic_scored_n'] == 0
    assert case['diagnostic_exclusion_reason'] == 'PUBLICATION_ORDER_UNVERIFIED'
    del payload['records'][-1]['available_at']
    raw = encode(payload)
    manifest['content_sha256'] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ForecastEvidenceRefused):
        review_dataset(encode(manifest), raw, asof=ASOF)
