"""Executable quote summaries must agree with their supplied depth."""
from copy import deepcopy
from decimal import Decimal

import pytest
from app.prediction.paper_engine import evaluate_pre_event_repricing
from test_prediction_history_time import NOW, history
from test_prediction_history_window import book
from test_prediction_paper_automation import _market


@pytest.mark.parametrize('side', ['YES', 'NO'])
@pytest.mark.parametrize('fault', ['crossed', 'negative_spread', 'wrong_spread', 'wrong_bid', 'wrong_ask', 'range'])
def test_contradictory_executable_quote_refuses_candidate(side, fault):
    data = deepcopy(book())
    row = data[side.lower()]
    if fault == 'crossed': row['best_bid_dollars'] = '.50'
    if fault == 'negative_spread': row['spread_dollars'] = '-.02'
    if fault == 'wrong_spread': row['spread_dollars'] = '.01'
    if fault == 'wrong_bid': row['best_bid_dollars'] = '.39'
    if fault == 'wrong_ask': row['best_ask_dollars'] = '.43'
    if fault == 'range': row['best_bid_dollars'] = '-.01'
    result = evaluate_pre_event_repricing(market=_market(NOW), orderbook=data,
              candles=history(), side=side, quantity=Decimal(10), now=NOW)
    assert not result['eligible']
    assert 'INCONSISTENT_EXECUTABLE_QUOTE' in result['rejection_reasons']
