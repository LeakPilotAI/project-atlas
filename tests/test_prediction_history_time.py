"""No future or ambiguous candle clock can support synthetic eligibility."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from app.prediction.kalshi_public import PredictionProviderError, normalize_candlestick
from app.prediction.paper_engine import evaluate_pre_event_repricing
from test_prediction_paper_automation import _book, _market

NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)


def history():
    return [{'end_period_ts': int((NOW-timedelta(minutes=6-i)).timestamp()),
             'yes_bid': {'close_dollars': '0.50', 'high_dollars': '0.60'},
             'yes_ask': {'close_dollars': '0.52', 'low_dollars': '0.40'}} for i in range(6)]


def evaluate(rows, side='YES'):
    return evaluate_pre_event_repricing(market=_market(NOW), orderbook=_book(), candles=rows,
                                       side=side, quantity=Decimal(10), now=NOW)


@pytest.mark.parametrize('side', ['YES', 'NO'])
@pytest.mark.parametrize('fault', ['future', 'missing', 'bool', 'float', 'string', 'duplicate', 'reversed', 'zero', 'negative'])
def test_invalid_history_clock_cannot_support_eligibility(side, fault):
    rows = history()
    if fault == 'future': rows[-1]['end_period_ts'] = int(NOW.timestamp())+1
    if fault == 'missing': rows[0].pop('end_period_ts')
    if fault == 'bool': rows[0]['end_period_ts'] = True
    if fault == 'float': rows[0]['end_period_ts'] += .5
    if fault == 'string': rows[0]['end_period_ts'] = str(rows[0]['end_period_ts'])
    if fault == 'duplicate': rows[-1]['end_period_ts'] = rows[-2]['end_period_ts']
    if fault == 'reversed': rows.reverse()
    if fault == 'zero': rows[0]['end_period_ts'] = 0
    if fault == 'negative': rows[0]['end_period_ts'] = -1
    result = evaluate(rows, side)
    assert result['eligible'] is False
    assert any('HISTORY_TIMESTAMP' in reason for reason in result['rejection_reasons'])
    assert result['history']['usable_bars'] == 0
    assert result['projected']['net_repricing_pnl_dollars'] is None


def test_valid_ordered_history_keeps_existing_heuristic_result():
    result = evaluate(history())
    assert result['eligible'] is True
    assert result['history']['usable_bars'] == 6


@pytest.mark.parametrize('stamp', [None, True, 12.5, '123', 0, -1])
def test_provider_normalization_does_not_fabricate_integer_time(stamp):
    with pytest.raises(PredictionProviderError):
        normalize_candlestick({'end_period_ts': stamp})


def test_end_time_equal_to_research_cutoff_is_allowed_but_not_availability_proof():
    rows = history()
    rows[-1]['end_period_ts'] = int(NOW.timestamp())
    result = evaluate(rows)
    assert result['eligible'] is True
    assert result['history']['timestamp_status'] == 'EVENT_TIME_ORDER_ONLY'
    assert result['history']['availability_verified'] is False


def test_history_input_budget_refuses_without_silent_truncation():
    rows = [history()[0]]*10001
    result = evaluate(rows)
    assert result['eligible'] is False
    assert 'HISTORY_TIMESTAMP_INPUT_BUDGET' in result['rejection_reasons']
    assert result['history']['supplied_bars'] == 10001
    assert result['history']['usable_bars'] == 0
    assert len(rows) == 10001
