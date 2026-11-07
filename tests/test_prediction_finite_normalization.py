"""Malformed public numeric inputs are absent, never executable depth."""
import pytest
from app.prediction.kalshi_public import (
    normalize_candlestick,
    normalize_market,
    normalize_orderbook,
)


@pytest.mark.parametrize('value', ['NaN', 'sNaN', 'Infinity', '-Infinity'])
@pytest.mark.parametrize('field', ['price', 'quantity'])
def test_nonfinite_depth_is_excluded_without_exception(value, field):
    level = [value, '10'] if field == 'price' else ['.50', value]
    result = normalize_orderbook({'orderbook_fp': {'yes_dollars': [level], 'no_dollars': []}})
    assert result['yes']['bids'] == []
    assert result['no']['asks'] == []
    assert result['yes']['best_bid_dollars'] is None


@pytest.mark.parametrize('value', ['NaN', 'sNaN', 'Infinity', '-Infinity'])
def test_nonfinite_market_and_candle_values_remain_missing(value):
    market = normalize_market({'yes_bid_dollars': value, 'yes_ask_dollars': value})
    assert market['prices']['yes_bid_dollars'] is None
    candle = normalize_candlestick({'end_period_ts': 1, 'yes_bid': {'close_dollars': value}})
    assert candle['yes_bid']['close_dollars'] is None


def test_zero_quantity_does_not_hide_valid_deeper_liquidity():
    result = normalize_orderbook({'orderbook_fp': {'yes_dollars': [['.60', '0'], ['.50', '10']]}})
    assert result['yes']['best_bid_dollars'] == '.50' or result['yes']['best_bid_dollars'] == '0.50'
    assert len(result['yes']['bids']) == 1


@pytest.mark.parametrize('valid_liquidity', [False, True])
def test_normalized_provider_depth_flows_into_research_without_nonfinite_liquidity(valid_liquidity):
    from decimal import Decimal

    from app.prediction.paper_engine import evaluate_pre_event_repricing
    from test_prediction_history_time import NOW, history
    from test_prediction_paper_automation import _market

    yes = [['NaN', '100'], ['.99', 'Infinity'], ['.90', '0']]
    no = [['.80', 'NaN']]
    if valid_liquidity:
        yes.append(['.40', '100'])
        no.append(['.58', '100'])
    normalized = normalize_orderbook({'orderbook_fp': {'yes_dollars': yes, 'no_dollars': no}})
    result = evaluate_pre_event_repricing(market=_market(NOW), orderbook=normalized,
                  candles=history(), side='YES', quantity=Decimal(10), now=NOW)
    assert result['eligible'] is valid_liquidity
    assert result['entry_fill']['fillable'] is valid_liquidity
