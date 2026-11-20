"""Ambiguous research clocks and event timing cannot grant eligibility."""
from decimal import Decimal

import pytest
from app.prediction.paper_engine import (
    PredictionPaperError,
    evaluate_pre_event_repricing,
)
from test_prediction_history_time import NOW, history
from test_prediction_history_window import book
from test_prediction_paper_automation import _market


def evaluate(market, now=NOW):
    return evaluate_pre_event_repricing(market=market, orderbook=book(), candles=history(),
                                       side='YES', quantity=Decimal(10), now=now)


@pytest.mark.parametrize('timing', ['bad', ['bad'], 12, True])
def test_malformed_timing_is_reported_without_attribute_error(timing):
    market = _market(NOW)
    market['timing'] = timing
    result = evaluate(market)
    assert not result['eligible']
    assert 'MISSING_OCCURRENCE_DATETIME' in result['rejection_reasons']


def test_naive_event_clock_is_not_silently_assumed_utc():
    market = _market(NOW)
    market['timing']['occurrence_datetime'] = '2026-10-02T15:00:00'
    result = evaluate(market)
    assert not result['eligible']
    assert 'MISSING_OCCURRENCE_DATETIME' in result['rejection_reasons']


@pytest.mark.parametrize('now', [NOW.replace(tzinfo=None), '2026-10-02T12:00:00Z', False, 0])
def test_invalid_explicit_research_clock_is_refused_before_calculation(now):
    with pytest.raises(PredictionPaperError, match='aware research clock'):
        evaluate(_market(NOW), now)


def test_unrepresentable_flat_window_is_refused_without_overflow():
    market = _market(NOW)
    market['timing']['occurrence_datetime'] = '0001-01-01T00:00:00Z'
    result = evaluate(market)
    assert not result['eligible']
    assert 'MISSING_OCCURRENCE_DATETIME' in result['rejection_reasons']


@pytest.mark.parametrize('occurrence', ['2026-10-02T15:00:00Z', '2026-10-02T10:00:00-05:00'])
def test_explicit_z_and_offset_clocks_keep_valid_research(occurrence):
    market = _market(NOW)
    market['timing']['occurrence_datetime'] = occurrence
    assert evaluate(market)['eligible']
