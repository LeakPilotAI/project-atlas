from copy import deepcopy

import pytest
from app.investment import quality_dips_v2_runtime as enrichment
from app.investment.quality_dips_v2_board import build_v2_projection
from app.services.quality_dips_research_only import project_explicit_research
from test_quality_dips_v2_board import _row


def row(symbol='MSFT', kind='STOCK'):
    result = _row()
    result.update(symbol=symbol, asset_type=kind)
    return result


def forbid(*args, **kwargs):
    raise AssertionError('legacy stored evidence must not be read')


def test_explicit_projection_preserves_existing_scoring_and_source_bytes(monkeypatch):
    monkeypatch.setattr(enrichment, 'load_bars', forbid)
    rows = [row(), row('SPY', 'ETF')]
    original = deepcopy(rows)
    result = project_explicit_research(rows)
    assert {x['symbol'] for x in result} == {'MSFT', 'SPY'}
    for item in result:
        source = next(r for r in rows if r['symbol'] == item['symbol'])
        assert item['quality_dips_v2'] == build_v2_projection(source)
        assert item['quality_dips_v2']['automatic_real_money_execution'] is False
    assert rows == original


def test_missing_explicit_inputs_never_read_legacy_history_or_cache(monkeypatch):
    monkeypatch.setattr(enrichment, 'load_bars', forbid)
    import builtins
    original_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.endswith('quality_dips_v2_target_cache'):
            forbid()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', guarded)
    source = row()
    source.pop('trend')
    source.pop('valuation_sources')
    projected = project_explicit_research([source])[0]['quality_dips_v2']
    assert projected['valuation_source_count'] == 0
    assert not projected['entry_ladder']['ready']
    assert not projected['evidence_gate']['gate_passed']
    assert projected['missing_v2_evidence']


@pytest.mark.parametrize('rows', [[], [row()] * 51, [row(), row()],
    [row('msft')], [row('BTC', 'CRYPTO')], [None], [row('')]])
def test_ambiguous_or_unbounded_inputs_refuse(rows):
    with pytest.raises(ValueError):
        project_explicit_research(rows)


def test_no_historical_data_is_promoted_to_current():
    source = row()
    source['timestamp'] = '2020-01-01T00:00:00+00:00'
    source['trend']['as_of'] = source['timestamp']
    result = project_explicit_research([source])[0]
    assert result['research_timestamp'] == source['timestamp']
    assert result['quality_dips_v2']['trend']['as_of'] == source['timestamp']
    assert result['quote_bid'] is None
    assert result['quote_ask'] is None
