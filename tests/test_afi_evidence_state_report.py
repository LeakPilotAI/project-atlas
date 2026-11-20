"""V2 companion export leaves retained V1 accountability bytes unchanged."""
import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from app.backtest.forecast_artifacts import publish_forecast
from app.backtest.forecast_baselines import fit_baseline
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_evidence_state_report import (
    build_evidence_state_report,
    publish_evidence_state_report,
    render_evidence_state_report,
)
from app.backtest.forecast_report import (
    ForecastHistory,
    browser_export,
    build_accountability_report,
    render_accountability_report,
    run_bundle,
)
from app.backtest.forecast_source import create_source_review
from test_afi_accountability_report import bundle_fixture, save, setup
from test_afi_baselines import ASOF, ASSET
from test_afi_outcomes import CORRECTED, RESOLVED, append, changed_review
from test_afi_source_binding import source


def test_companion_pending_and_resolved_exports_are_deterministic(tmp_path):
    review, _, forecast_path, output = setup(tmp_path)
    pending = ForecastHistory(forecast_path, review)
    base = build_accountability_report([pending], evidence_asof=ASOF)
    old_html = render_accountability_report(base).encode()
    old_browser = browser_export(base).encode()
    companion = build_evidence_state_report([pending], evidence_asof=ASOF)
    assert companion['schema'] == 'AFI_EVIDENCE_STATE_REPORT_V2'
    assert companion['source_report_sha256'] == base['report_sha256']
    assert companion['cases'][0]['outcome_status'] == 'FORECAST_ONLY'
    assert companion['cases'][0]['window']['status'] in {'MISSING', 'PARTIAL', 'COMPLETE'}
    assert companion['cases'][0]['diagnostic_scored_n'] == 0
    first = publish_evidence_state_report(output, [pending], evidence_asof=ASOF)
    second = publish_evidence_state_report(output, [pending], evidence_asof=ASOF)
    assert first == second
    assert json.loads((output/first['report']).read_bytes()) == companion
    assert '<script' not in (output/first['dashboard']).read_text(encoding='utf-8').lower()
    assert render_accountability_report(base).encode() == old_html
    assert browser_export(base).encode() == old_browser
    assert hashlib.sha256((output/first['report']).read_bytes()).hexdigest() == first['report'].split('.')[0]

    path, record = append(output, forecast_path, review, outcome_asof=RESOLVED)
    resolved = ForecastHistory(forecast_path, review, ((path, review),), record['artifact_sha256'])
    after = build_evidence_state_report([resolved], evidence_asof=ASOF)
    assert after['cases'][0]['window']['status'] == 'COMPLETE'
    assert after['cases'][0]['outcome_status'] == 'RESOLVED'
    assert after['cases'][0]['diagnostic_scored_n'] == 0
    assert after['cases'][0]['publication_order_status'] == 'UNVERIFIED_REVIEW_POSTDATES_OUTCOME'
    assert after['cases'][0]['diagnostic_exclusion_reason'] == 'PUBLICATION_ORDER_UNVERIFIED'
    assert after['authoritative_scored_n'] == 0


def test_companion_tampering_refuses_even_if_self_hashed(tmp_path):
    review, _, forecast_path, _ = setup(tmp_path)
    entries = [ForecastHistory(forecast_path, review)]
    report = build_evidence_state_report(entries, evidence_asof=ASOF)
    changed = deepcopy(report)
    changed['cases'][0]['window']['status'] = 'UNVERIFIED'
    with pytest.raises(ForecastEvidenceRefused, match='source histories'):
        render_evidence_state_report(changed, entries, evidence_asof=ASOF)


def test_bundle_opt_in_adds_only_v2_files_and_preserves_v1_bytes(tmp_path):
    _review, _forecast, output, bundle = bundle_fixture(tmp_path)
    save(tmp_path, bundle)
    original = run_bundle(bundle_root=tmp_path, bundle_name='bundle.json', output_root=output)
    v1 = {key: (output/original[key]).read_bytes()
          for key in ('report', 'dashboard', 'browser_export')}
    opted = run_bundle(bundle_root=tmp_path, bundle_name='bundle.json', output_root=output,
                       evidence_states=True)
    assert 'evidence_states' not in original
    assert {key: (output/opted[key]).read_bytes()
            for key in ('report', 'dashboard', 'browser_export')} == v1
    companion = json.loads((output/opted['evidence_states']['report']).read_bytes())
    assert companion['schema'] == 'AFI_EVIDENCE_STATE_REPORT_V2'
    assert companion['source_report_bytes_sha256'] == hashlib.sha256(v1['report']).hexdigest()
    assert companion['authoritative_scored_n'] == 0


def test_multi_cohort_order_and_provenance_isolation(tmp_path):
    review, _, first, _ = setup(tmp_path)
    original_source = source()
    other_source = create_source_review(dict(original_source.source_files), release_id='fixture-v2')
    models = [fit_baseline(review, asset_id=ASSET,
                           issued_at=issued_at,
                           evidence_asof=ASOF, lookback=5, horizon=horizon,
                           source_review=source_review)
              for horizon, source_review, issued_at in [
                  ('1D', original_source, datetime(2026, 10, 17, 0, 1, tzinfo=UTC)),
                  ('5D', other_source, datetime(2026, 10, 18, 0, 1, tzinfo=UTC))]]
    paths = [publish_forecast(tmp_path/'forecasts', review, model,
                              evidence_asof=ASOF, source_review=source_review)
             for model, source_review in zip(models, (original_source, other_source))]
    entries = [ForecastHistory(first, review),
               ForecastHistory(paths[0], review, source_review=original_source),
               ForecastHistory(paths[1], review, source_review=other_source)]
    report = build_evidence_state_report(entries, evidence_asof=ASOF)
    reversed_report = build_evidence_state_report(list(reversed(entries)), evidence_asof=ASOF)
    assert report == reversed_report
    assert len(report['cases']) == 3
    assert [case['forecast_sha256'] for case in report['cases']] == sorted(
        case['forecast_sha256'] for case in report['cases'])
    assert len({(case['cohort']['horizon'], case['cohort']['release_source_sha256'])
                for case in report['cases']}) == 3
    assert len({case['window']['issued_at'] for case in report['cases']}) == 2
    assert all(case['authoritative_scored_n'] == 0 for case in report['cases'])
    assert all(case['diagnostic_scored_n'] == 0 for case in report['cases'])
    assert all(case['diagnostic_exclusion_reason'] for case in report['cases'])
    assert '<script' not in render_evidence_state_report(report, entries, evidence_asof=ASOF).lower()


def test_revision_history_is_reported_without_issue_time_lookahead(tmp_path):
    review, _, forecast_path, output = setup(tmp_path)
    resolved_path, resolved = append(output, forecast_path, review, outcome_asof=RESOLVED)
    corrected_review = changed_review(review)
    corrected_path, corrected = append(output, forecast_path, review, corrected_review,
                                       outcome_asof=CORRECTED,
                                       history=[(resolved_path, review)],
                                       expected_head=resolved['artifact_sha256'])
    entry = ForecastHistory(forecast_path, review,
                            ((resolved_path, review), (corrected_path, corrected_review)),
                            corrected['artifact_sha256'])
    case = build_evidence_state_report([entry], evidence_asof=ASOF)['cases'][0]
    assert case['revision']['latest_event'] == 'CORRECTION'
    assert case['revision']['correction_n'] == 1
    assert case['revision']['history_n'] == 2
    assert case['revision']['source_revision'] == 'v2'
    assert case['window']['issued_at'] < case['revision']['source_available_at']
    assert case['outcome_status'] == 'RESOLVED'
    assert case['diagnostic_exclusion_reason'] == 'PUBLICATION_ORDER_UNVERIFIED'
    assert case['authoritative_exclusion_reason'] == 'SYNTHETIC_UNAUTHENTICATED'
    with pytest.raises(ForecastEvidenceRefused):
        build_evidence_state_report([ForecastHistory(forecast_path, review,
                                    ((resolved_path, review), (corrected_path, review)),
                                    corrected['artifact_sha256'])], evidence_asof=ASOF)


def test_duplicate_and_source_substitution_refuse_before_export(tmp_path):
    review, _, forecast_path, output = setup(tmp_path)
    entry = ForecastHistory(forecast_path, review)
    with pytest.raises(ForecastEvidenceRefused, match='Repeated report forecast'):
        publish_evidence_state_report(output, [entry, entry], evidence_asof=ASOF)
    assert not list(output.iterdir())
    wrong = changed_review(review, wrong_source=True)
    path, record = append(output, forecast_path, review, outcome_asof=RESOLVED)
    with pytest.raises(ForecastEvidenceRefused):
        build_evidence_state_report([ForecastHistory(forecast_path, wrong,
                                    ((path, review),), record['artifact_sha256'])],
                                    evidence_asof=ASOF)
