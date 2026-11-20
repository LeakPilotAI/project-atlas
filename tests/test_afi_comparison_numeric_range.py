"""Actual dataset/model comparisons must not emit nonfinite normalized errors."""
import hashlib
import json
import math

import pytest
from app.backtest.forecast_comparison import compare_forecasts
from app.backtest.forecast_dataset import review_dataset
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from test_afi_baselines import ASOF, fit, history
from test_afi_dataset_integrity import encode


def entry(point, actual):
    original = history()
    manifest = json.loads(original.manifest_bytes)
    payload = json.loads(original.payload_bytes)
    for record in payload['records']:
        record['value'] = record['raw_price'] = actual if record['observed_at'].startswith('2026-10-02T') else point
    raw = encode(payload)
    manifest['content_sha256'] = hashlib.sha256(raw).hexdigest()
    reviewed = review_dataset(encode(manifest),raw,asof=ASOF)
    return reviewed,fit(reviewed)


@pytest.mark.parametrize('point,actual,expected', [(1e307,1e306,900),(1e-308,1e308,100)])
def test_finite_relative_error_survives_intermediate_product_overflow(point,actual,expected):
    report = compare_forecasts([entry(point,actual)],evidence_asof=ASOF)
    value = report['rows'][0]['relative_error_percent']
    assert math.isfinite(value) and value == pytest.approx(expected)
    json.dumps(report,allow_nan=False)


def test_truly_unrepresentable_relative_error_refuses():
    with pytest.raises(ForecastEvidenceRefused,match='numeric range'):
        compare_forecasts([entry(1e308,1e-308)],evidence_asof=ASOF)


def test_endpoint_drift_normalized_change_recovers_finite_percentage():
    original = history()
    manifest = json.loads(original.manifest_bytes)
    payload = json.loads(original.payload_bytes)
    for i,record in enumerate(payload['records']):
        value = 4e307+max(0,min(i-17,4))*1.5e307
        record['value'] = record['raw_price'] = value
    raw = encode(payload)
    manifest['content_sha256'] = hashlib.sha256(raw).hexdigest()
    reviewed = review_dataset(encode(manifest),raw,asof=ASOF)
    report = compare_forecasts([(reviewed,fit(reviewed,method='ENDPOINT_DRIFT'))],evidence_asof=ASOF)
    assert report['rows'][0]['implied_change_percent'] == pytest.approx(15)
    json.dumps(report,allow_nan=False)


def test_ordinary_comparison_arithmetic_retains_exact_values():
    reviewed = history()
    row = compare_forecasts([(reviewed,fit(reviewed))],evidence_asof=ASOF)['rows'][0]
    assert row['point'] == row['reference'] == 121
    assert row['actual'] == 123 and row['absolute_error'] == 2
    assert row['relative_error_percent'] == 200/123
    assert row['implied_change_percent'] == 0


def test_dashboard_refuses_unrepresentable_errors_instead_of_infinity_text():
    from app.backtest.forecast_dashboard import render_dashboard

    with pytest.raises(ForecastEvidenceRefused,match='numeric range'):
        render_dashboard([entry(1e308,1e-308)],evidence_asof=ASOF)
