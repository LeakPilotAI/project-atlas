"""Synthetic holdout and future intake declarations cannot grant authority."""

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from app.backtest.forecast_artifacts import publish_forecast
from app.backtest.forecast_baselines import fit_baseline
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_holdout_readiness import (
    prepare_holdout_readiness,
    validate_intake_declaration,
)
from app.backtest.forecast_outcomes import append_outcome
from app.backtest.forecast_report import ForecastHistory
from test_afi_accountability_report import setup
from test_afi_baselines import ASSET
from test_afi_source_binding import source

ASOF = datetime(2026, 10, 20, 2, tzinfo=UTC)
FREEZE = datetime(2026, 10, 19, 2, tzinfo=UTC)


def cases(tmp_path, *, selection_cutoff=None, holdout_issue=None, selection_history=True):
    review, _, first, output = setup(tmp_path)
    selection_cutoff = selection_cutoff or datetime(2026, 10, 19, 1, tzinfo=UTC)
    history, head = (), None
    if selection_history:
        path, record = append_outcome(output, first, review, review, evidence_asof=ASOF,
                                      outcome_asof=selection_cutoff)
        history, head = ((path, review),), record['artifact_sha256']
    selection = ForecastHistory(first, review, history, head)
    issue = holdout_issue or datetime(2026, 10, 19, 3, tzinfo=UTC)
    model = fit_baseline(review, asset_id=ASSET, issued_at=issue,
                         evidence_asof=ASOF, lookback=5)
    second = publish_forecast(first.parent, review, model, evidence_asof=ASOF)
    return selection, ForecastHistory(second, review)


def intake():
    return {"schema": "AFI_WITNESSED_SOURCE_INTAKE_V1", "provider_id": "synthetic-provider",
            "instrument_id": "CRYPTO:BTC-USD", "asset_class": "CRYPTO", "source_id": "fixture",
            "license_id": "SYNTHETIC_FIXTURE", "license_digest": "a" * 64,
            "permitted_uses": ["OFFLINE_RESEARCH"],
            "observed_at": "2026-10-18T00:00:00+00:00",
            "published_at": "2026-10-18T00:01:00+00:00",
            "witnessed_at": "2026-10-18T00:02:00+00:00",
            "witness_identity": "synthetic-claim-only", "witness_payload_digest": "b" * 64,
            "receipt_id": "synthetic-receipt", "payload_digest": "c" * 64,
            "revision_id": "synthetic-v1", "previous_revision_id": None,
            "correction_published_at": None, "retention_policy": "retain-original",
            "source_complete": True, "verification_status": "DECLARED_UNVERIFIED"}


def test_holdout_plan_is_reproducible_and_never_authoritative(tmp_path):
    selection, holdout = cases(tmp_path)
    first = prepare_holdout_readiness([selection], [holdout], frozen_at=FREEZE,
                                      evidence_asof=ASOF)
    second = prepare_holdout_readiness([selection], [holdout], frozen_at=FREEZE,
                                       evidence_asof=ASOF)
    assert first == second and first['selection_n'] == first['holdout_n'] == 1
    assert {case['partition'] for case in first['cases']} == {'SELECTION', 'HOLDOUT'}
    assert first['proposed_minimum_samples'] is None and not first['sample_minimum_approved']
    assert first['holdout_mature_n'] == 0
    assert first['selection_partition_sha256'] != first['holdout_partition_sha256']
    assert not first['holdout_independently_unseen'] and first['authoritative_scored_n'] == 0


@pytest.mark.parametrize('change', ['duplicate', 'late-selection', 'missing-label', 'early-holdout'])
def test_holdout_contamination_refuses(tmp_path, change):
    options = {}
    if change == 'late-selection':
        options['selection_cutoff'] = datetime(2026, 10, 19, 3, tzinfo=UTC)
    if change == 'missing-label':
        options['selection_history'] = False
    if change == 'early-holdout':
        options['holdout_issue'] = datetime(2026, 10, 18, 3, tzinfo=UTC)
    selection, holdout = cases(tmp_path, **options)
    if change == 'duplicate':
        holdout = selection
    with pytest.raises(ForecastEvidenceRefused):
        prepare_holdout_readiness([selection], [holdout], frozen_at=FREEZE,
                                  evidence_asof=ASOF)


def test_model_version_substitution_within_same_cohort_refuses(tmp_path):
    selection, holdout = cases(tmp_path)
    review = holdout.forecast_review
    release = source()
    model = fit_baseline(review, asset_id=ASSET,
                         issued_at=datetime(2026, 10, 19, 3, tzinfo=UTC),
                         evidence_asof=ASOF, lookback=5, source_review=release)
    path = publish_forecast(holdout.forecast_path.parent, review, model,
                            evidence_asof=ASOF, source_review=release)
    substituted = ForecastHistory(path, review, source_review=release)
    with pytest.raises(ForecastEvidenceRefused, match='substitution'):
        prepare_holdout_readiness([selection], [substituted], frozen_at=FREEZE,
                                  evidence_asof=ASOF)


def test_intake_declaration_is_structural_only():
    packet = intake()
    result = validate_intake_declaration(packet)
    assert result['status'] == 'PENDING_INDEPENDENT_AUTHENTICATION'
    assert not result['license_verified'] and not result['witness_verified']
    assert not result['authoritative_use_allowed']
    assert result == validate_intake_declaration(deepcopy(packet))


@pytest.mark.parametrize('change', ['no-witness', 'bad-license', 'future-witness',
                                     'before-observation', 'incomplete', 'correction-lineage',
                                     'false-authority'])
def test_invalid_intake_declaration_refuses(change):
    packet = intake()
    if change == 'no-witness':
        packet.pop('witness_payload_digest')
    if change == 'bad-license':
        packet['permitted_uses'] = ['LIVE_TRADING']
    if change == 'future-witness':
        packet['witnessed_at'] = '2026-10-17T00:00:00+00:00'
    if change == 'before-observation':
        packet['published_at'] = '2026-10-17T00:00:00+00:00'
    if change == 'incomplete':
        packet['source_complete'] = False
    if change == 'correction-lineage':
        packet['correction_published_at'] = packet['published_at']
    if change == 'false-authority':
        packet['verification_status'] = 'AUTHENTICATED'
    with pytest.raises(ForecastEvidenceRefused):
        validate_intake_declaration(packet)
