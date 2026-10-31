"""Explicit current research must not renew, invent or mislabel valuations."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from app.investment.quality_dips_v2_board import build_v2_projection
from app.investment.quality_dips_v2_valuation import build_normalization_window
from app.services.quality_dips_research_only import project_explicit_research
from test_quality_dips_v2_board import _row

NOW = datetime(2026, 10, 29, 14, tzinfo=UTC)


def current_row():
    row = _row()
    row['asset_type'] = 'STOCK'
    row['timestamp'] = row['trend']['as_of'] = NOW.isoformat()
    for source in row['valuation_sources']:
        source['as_of'] = NOW.isoformat()
    return row


@pytest.mark.parametrize('bad', [True, False, float('inf'), float('-inf'), float('nan'), 'Infinity', 'NaN', 10**400])
def test_invalid_value_cannot_complete_three_estimates(bad):
    sources = current_row()['valuation_sources']
    sources[0]['value'] = bad
    window = build_normalization_window(sources)
    assert not window['complete'] and window['source_count'] == 2
    assert all(window[k] is None for k in ('conservative', 'base', 'optimistic'))


@pytest.mark.parametrize('stamp', [None, '', 'bad', '2026-10-29T13:00:00', '2026-10-30',
    (NOW-timedelta(days=7, microseconds=1)).isoformat()])
def test_one_stale_undated_or_future_estimate_blocks_current_window(stamp):
    row = current_row()
    row['valuation_sources'][0]['as_of'] = stamp
    # A forged precomputed value must not bypass insufficient original sources.
    row['normalization_value'] = {'conservative': 1000, 'base': 2000, 'optimistic': 3000}
    row['valuation_window'] = dict(row['normalization_value'])
    original = deepcopy(row)
    result = project_explicit_research([row], now=NOW)[0]['quality_dips_v2']
    assert result['valuation_source_count'] == 2
    assert not result['entry_ladder']['ready'] and not result['evidence_gate']['gate_passed']
    assert not result['quality_dips_v3']['entry_ladder']['ready']
    assert all(value is None for value in result['normalization_value'].values())
    assert row == original


def test_ttl_boundary_and_day_precision_preserve_original_math():
    sources = current_row()['valuation_sources']
    sources[0]['as_of'] = (NOW-timedelta(days=7)).isoformat()
    sources[1]['as_of'] = '2026-10-29'
    window = build_normalization_window(sources, now=NOW)
    assert window['complete']
    assert [window[k] for k in ('conservative', 'base', 'optimistic')] == [130, 140, 150]
    assert window['provenance'][0]['as_of'] == sources[0]['as_of']


def test_analyst_low_mean_high_are_not_three_independent_analysts_or_a_median():
    row = current_row()
    row.pop('valuation_sources')
    row['input_snapshot'] = {'valuation': {
        key: {'value': value, 'source': 'SYNTHETIC_CONSENSUS', 'availability': True,
              'quality': 'FRESH', 'effective_timestamp': NOW.isoformat()}
        for key, value in [('target_low_price', 110), ('target_mean_price', 135), ('target_high_price', 200)]}}
    result = project_explicit_research([row], now=NOW)[0]['quality_dips_v2']
    assert result['valuation_source_count'] == 3
    assert result['normalization_value'] == {'conservative': 110, 'base': 135, 'optimistic': 200}
    assert all(p['provenance'] == 'ANALYST_CONSENSUS' for p in result['valuation_provenance'])


@pytest.mark.parametrize('quality', ['STALE', 'CONFLICTING', 'UNKNOWN', 'MISSING'])
def test_recent_wrapper_does_not_override_provider_quality(quality):
    row = current_row()
    row.pop('valuation_sources')
    row['input_snapshot'] = {'valuation': {
        key: {'value': 150, 'availability': True, 'quality': quality, 'effective_timestamp': NOW.isoformat()}
        for key in ('target_low_price', 'target_mean_price', 'target_high_price')}}
    result = project_explicit_research([row], now=NOW)[0]['quality_dips_v2']
    assert result['valuation_source_count'] == 0 and not result['entry_ladder']['ready']


def test_accounting_ratios_guidance_and_eps_are_not_target_prices():
    row = current_row()
    row.pop('valuation_sources')
    row['input_snapshot'] = {'valuation': {key: {'value': 150, 'availability': True}
        for key in ('pe', 'pb', 'forward_pe', 'eps', 'revenue_guidance', 'book_value_per_share')}}
    result = project_explicit_research([row], now=NOW)[0]['quality_dips_v2']
    assert result['valuation_source_count'] == 0
    assert not result['entry_ladder']['ready']


@pytest.mark.parametrize('field,value', [('quality', 'CONFLICTING'), ('availability', False)])
def test_explicit_source_flags_are_not_erased(field, value):
    row = current_row()
    row['valuation_sources'][0][field] = value
    result = project_explicit_research([row], now=NOW)[0]['quality_dips_v2']
    assert result['valuation_source_count'] == 2 and not result['entry_ladder']['ready']


def test_contradictory_named_targets_are_not_silently_resorted():
    row = current_row()
    row.pop('valuation_sources')
    row['input_snapshot'] = {'valuation': {
        key: {'value': value, 'availability': True, 'effective_timestamp': NOW.isoformat()}
        for key,value in [('target_low_price', 200), ('target_mean_price', 135), ('target_high_price', 110)]}}
    result = project_explicit_research([row], now=NOW)[0]['quality_dips_v2']
    assert result['valuation_source_count'] == 0 and not result['entry_ladder']['ready']


def test_historical_display_compatible_but_not_current_acceptance():
    row = current_row()
    for source in row['valuation_sources']:
        source['as_of'] = '2020-01-01'
    assert build_normalization_window(row['valuation_sources'])['complete']
    assert not build_normalization_window(row['valuation_sources'], now=NOW)['complete']
    with pytest.raises(ValueError, match='EXPLICIT'):
        build_v2_projection(row, now=NOW)
    with pytest.raises(ValueError, match='AWARE'):
        build_normalization_window(row['valuation_sources'], now=NOW.replace(tzinfo=None))


def test_current_projection_restart_and_expiry_need_no_file_or_network(monkeypatch):
    import app.investment.quality_dips_v2_runtime as runtime

    def refuse(*args, **kwargs):
        raise AssertionError('legacy store/provider read prohibited')

    monkeypatch.setattr(runtime, 'load_bars', refuse)
    row = current_row()
    before = project_explicit_research([row], now=NOW)
    assert before == project_explicit_research([row], now=NOW)
    assert before[0]['quality_dips_v2']['entry_ladder']['ready']
    later = project_explicit_research([row], now=NOW+timedelta(days=8))
    assert not later[0]['quality_dips_v2']['entry_ladder']['ready']
