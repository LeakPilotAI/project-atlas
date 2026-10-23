"""Independent local clock inspection is never publication attestation."""

import hashlib
import json
from datetime import UTC, datetime

import pytest
from app.backtest.forecast_chronology_audit import _clock, audit_declared_chronology
from app.backtest.forecast_dataset import review_dataset
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_outcomes import append_outcome
from app.backtest.forecast_report import ForecastHistory
from test_afi_dataset_integrity import encode, fixture
from test_afi_outcomes import CORRECTED, RESOLVED, append, changed_review, setup

ASOF = datetime(2026, 10, 20, 3, tzinfo=UTC)


def test_declared_clocks_are_retrospective_not_witnessed(tmp_path):
    review, _, path, output = setup(tmp_path)
    first_path, first = append(output, path, review, outcome_asof=RESOLVED)
    corrected = changed_review(review)
    second_path, second = append(output, path, review, corrected, outcome_asof=CORRECTED,
                                 history=[(first_path, review)],
                                 expected_head=first['artifact_sha256'])
    entry = ForecastHistory(path, review, ((first_path, review), (second_path, corrected)),
                            second['artifact_sha256'])
    result = audit_declared_chronology([entry], evidence_asof=ASOF)
    case = result['cases'][0]
    assert case['history_n'] == 2
    assert case['reasons'] == ['RETROSPECTIVE_FORECAST_REVIEW',
                               'REVIEW_POSTDATES_OUTCOME_CUTOFF']
    assert not result['independent_attestation'] and not case['provider_publication_witnessed']
    assert not case['local_receipt_time_bound'] and result['authoritative_scored_n'] == 0
    assert _clock('2026-10-19T12:00:00Z') == _clock('2026-10-19T12:00:00+00:00')


def test_backdated_correction_is_explicitly_unverified(tmp_path):
    review, _, path, output = setup(tmp_path)
    first_path, first = append_outcome(output, path, review, review, evidence_asof=ASOF,
                                       outcome_asof=datetime(2026, 10, 19, 1, tzinfo=UTC))
    revised = changed_review(review)
    manifest, payload = json.loads(revised.manifest_bytes), json.loads(revised.payload_bytes)
    payload['records'][-1]['available_at'] = '2026-10-19T00:30:00+00:00'
    raw = encode(payload)
    manifest['content_sha256'] = hashlib.sha256(raw).hexdigest()
    revised = review_dataset(encode(manifest), raw, asof=ASOF)
    second_path, second = append_outcome(output, path, review, revised,
                                         evidence_asof=ASOF, outcome_asof=CORRECTED,
                                         history=((first_path, review),),
                                         expected_head=first['artifact_sha256'])
    entry = ForecastHistory(path, review, ((first_path, review), (second_path, revised)),
                            second['artifact_sha256'])
    case = audit_declared_chronology([entry], evidence_asof=ASOF)['cases'][0]
    assert 'CORRECTION_CLAIMED_AVAILABLE_BEFORE_PRIOR_OUTCOME' in case['reasons']
    assert case['declared_clock_consistency'] == 'UNVERIFIED'
    assert case['authoritative_scored_n'] == 0


def test_multiple_corrections_keep_one_forecast_and_ordered_lineage(tmp_path):
    review, _, path, output = setup(tmp_path)
    first_path, first = append_outcome(output, path, review, review, evidence_asof=ASOF,
                                       outcome_asof=datetime(2026, 10, 19, 1, tzinfo=UTC))
    second_review = changed_review(review)
    second_path, second = append_outcome(output, path, review, second_review,
                                         evidence_asof=ASOF, outcome_asof=CORRECTED,
                                         history=((first_path, review),),
                                         expected_head=first['artifact_sha256'])
    manifest, payload = json.loads(second_review.manifest_bytes), json.loads(second_review.payload_bytes)
    payload['records'].append({**payload['records'][-1], 'record_id': 'corrected-v3',
                               'revision': 'v3', 'raw_price': 156, 'value': 156,
                               'available_at': '2026-10-20T00:30:00+00:00'})
    raw = encode(payload)
    manifest.update(version='v3', acquired_at='2026-10-20T00:30:00+00:00',
                    generated_at='2026-10-20T00:30:00+00:00',
                    record_count=len(payload['records']),
                    content_sha256=hashlib.sha256(raw).hexdigest())
    third_review = review_dataset(encode(manifest), raw, asof=ASOF)
    third_path, third = append_outcome(output, path, review, third_review,
                                       evidence_asof=ASOF,
                                       outcome_asof=datetime(2026, 10, 20, 1, tzinfo=UTC),
                                       history=((first_path, review), (second_path, second_review)),
                                       expected_head=second['artifact_sha256'])
    entry = ForecastHistory(path, review,
                            ((first_path, review), (second_path, second_review),
                             (third_path, third_review)), third['artifact_sha256'])
    case = audit_declared_chronology([entry], evidence_asof=ASOF)['cases'][0]
    assert case['history_n'] == 3 and case['declared_clock_consistency'] == 'UNVERIFIED'
    assert case['reasons'] == ['RETROSPECTIVE_FORECAST_REVIEW']
    assert case['authoritative_scored_n'] == 0


@pytest.mark.parametrize('field,value', [
    ('available_at', None),
    ('available_at', '2026-10-15T20:00:00+00:00'),
    ('available_at', '2026-10-21T20:00:00+00:00'),
])
def test_missing_before_observation_or_future_publication_refuses(field, value):
    manifest, payload = fixture()
    if value is None:
        del payload['records'][0][field]
    else:
        payload['records'][0][field] = value
    raw = encode(payload)
    manifest['content_sha256'] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ForecastEvidenceRefused):
        review_dataset(encode(manifest), raw, asof=ASOF)


def test_duplicate_or_cross_cohort_history_refuses(tmp_path):
    review, _, path, output = setup(tmp_path)
    entry = ForecastHistory(path, review)
    with pytest.raises(ForecastEvidenceRefused, match='Duplicate chronology'):
        audit_declared_chronology([entry, entry], evidence_asof=ASOF)
    wrong = changed_review(review, wrong_source=True)
    first_path, first = append(output, path, review, outcome_asof=RESOLVED)
    with pytest.raises(ForecastEvidenceRefused):
        audit_declared_chronology([ForecastHistory(path, wrong, ((first_path, review),),
            first['artifact_sha256'])], evidence_asof=ASOF)
