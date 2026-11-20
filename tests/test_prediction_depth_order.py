"""Synthetic depth cannot hide inverted executable level ordering."""
from decimal import Decimal

import pytest
from app.prediction.paper_engine import walk_executable_depth


@pytest.mark.parametrize('side', ['YES', 'NO'])
@pytest.mark.parametrize('action', ['BUY', 'SELL'])
def test_inverted_consumed_depth_refuses_fill(side, action):
    prices = ['.60', '.40'] if action == 'BUY' else ['.40', '.60']
    levels = [{'price_dollars': p, 'quantity_contracts': '5'} for p in prices]
    book = {side.lower(): {'asks' if action == 'BUY' else 'bids': levels}}
    result = walk_executable_depth(book, side=side, action=action, quantity=Decimal(10))
    assert not result['fillable']
    assert result['reason'] == 'NON_MONOTONIC_EXECUTABLE_DEPTH'


@pytest.mark.parametrize('action', ['BUY', 'SELL'])
def test_sorted_depth_retains_weighted_fill(action):
    prices = ['.40', '.60'] if action == 'BUY' else ['.60', '.40']
    levels = [{'price_dollars': p, 'quantity_contracts': '5'} for p in prices]
    result = walk_executable_depth({'yes': {'asks' if action == 'BUY' else 'bids': levels}},
                                side='YES', action=action, quantity=Decimal(10))
    assert result['fillable']
    assert Decimal(result['vwap_dollars']) == Decimal('.50')
    assert Decimal(result['depth_slippage_dollars_per_contract']) == Decimal('.10')
