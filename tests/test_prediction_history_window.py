"""Requested-window context must not inflate synthetic reclaim eligibility."""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from app.api import prediction as api
from app.prediction import prediction_paper_automation as automation
from app.prediction.paper_engine import evaluate_pre_event_repricing
from test_prediction_paper_automation import _market

NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)


def book():
    side = {'bids': [{'price_dollars': '.40', 'quantity_contracts': '100'}],
            'asks': [{'price_dollars': '.42', 'quantity_contracts': '100'}],
            'best_bid_dollars': '.40', 'best_ask_dollars': '.42', 'spread_dollars': '.02'}
    return {'yes': side, 'no': side}


def candles(start, end):
    rows = [{'end_period_ts': end-60*(6-i),
             'yes_bid': {'close_dollars': '.40', 'high_dollars': '.43'},
             'yes_ask': {'close_dollars': '.42', 'low_dollars': '.40'}} for i in range(6)]
    return [{'end_period_ts': start-60, 'yes_bid': {'close_dollars': '.40', 'high_dollars': '.70'},
             'yes_ask': {'close_dollars': '.42', 'low_dollars': '.40'}}, *rows]


def fake_providers(monkeypatch):
    async def market(*a, **k): return {'market': _market(NOW)}
    async def orderbook(*a, **k): return {'orderbook': book()}
    async def history(**kwargs): return {'candlesticks': candles(kwargs['start_ts'], kwargs['end_ts'])}
    for module in (api, automation):
        monkeypatch.setattr(module.kalshi_public, 'get_market', market)
        monkeypatch.setattr(module.kalshi_public, 'get_orderbook', orderbook)
        monkeypatch.setattr(module.kalshi_public, 'get_candlesticks', history)


@pytest.mark.parametrize('caller', ['api', 'scanner'])
def test_pre_window_peak_cannot_make_candidate_eligible(monkeypatch, caller):
    fake_providers(monkeypatch)
    if caller == 'api':
        class Clock:
            @staticmethod
            def now(tz): return NOW
        monkeypatch.setattr(api, 'datetime', Clock)
        result = asyncio.run(api._build_prediction_paper_evaluation(
            ticker='KXTEST-A', side='YES', quantity=Decimal(10), depth=20, history_minutes=180))
    else:
        values = asyncio.run(automation.PredictionPaperAutomation()._evaluate_market(_market(NOW), 'fixture', NOW))
        result = next(row for row in values if row['side'] == 'YES')
    assert result['eligible'] is False
    assert result['history']['context_bars_excluded'] == 1
    assert result['history']['usable_bars'] == 6
    assert result['history']['requested_start_ts'] == int(NOW.timestamp())-180*60
    assert result['history']['requested_end_ts'] == int(NOW.timestamp())
    assert result['history']['availability_verified'] is False



def scoped(rows, start, end):
    return evaluate_pre_event_repricing(market=_market(NOW), orderbook=book(), candles=rows,
        side='YES', quantity=Decimal(10), now=NOW, history_start_ts=start, history_end_ts=end)


def valid_rows():
    end = int(NOW.timestamp())
    return [{'end_period_ts': end-60*(5-i),
             'yes_bid': {'close_dollars': '.40', 'high_dollars': '.60'},
             'yes_ask': {'close_dollars': '.42', 'low_dollars': '.40'}} for i in range(6)]


@pytest.mark.parametrize('fault', ['missing-start', 'missing-end', 'boolean', 'string', 'reversed', 'future'])
def test_invalid_requested_window_cannot_fall_back_to_full_history(fault):
    end = int(NOW.timestamp())
    start = end-600
    if fault == 'missing-start': start = None
    if fault == 'missing-end': end = None
    if fault == 'boolean': start = True
    if fault == 'string': end = str(end)
    if fault == 'reversed': start, end = end, start
    if fault == 'future': end += 1
    result = scoped(valid_rows(), start, end)
    assert result['eligible'] is False
    assert 'MISSING_OR_INVALID_HISTORY_WINDOW' in result['rejection_reasons']
    assert result['history']['usable_bars'] == 0
    assert result['history']['window_status'] == 'REFUSED'


def test_requested_window_has_explicit_inclusive_endpoints():
    rows = valid_rows()
    result = scoped(rows, rows[0]['end_period_ts'], rows[-1]['end_period_ts'])
    assert result['eligible'] is True
    assert result['history']['usable_bars'] == 6
    assert result['history']['context_bars_excluded'] == 0
    assert result['history']['window_status'] == 'APPLIED'
    assert result['history']['availability_verified'] is False


def test_unspecified_pure_research_scope_is_labeled_not_invented():
    result = scoped(valid_rows(), None, None)
    assert result['history']['window_status'] == 'UNSPECIFIED'
    assert result['history']['requested_start_ts'] is None
    assert result['history']['availability_verified'] is False


def test_bar_after_requested_end_refuses_instead_of_silent_drop():
    end = int(NOW.timestamp())
    result = scoped(valid_rows(), end-600, end-1)
    assert result['eligible'] is False
    assert 'AFTER_REQUESTED_HISTORY_WINDOW' in result['rejection_reasons']
    assert result['history']['usable_bars'] == 0


def test_context_only_history_cannot_supply_minimum_history():
    end = int(NOW.timestamp())
    rows = valid_rows()
    # Keep a valid past request while every supplied bar predates its start.
    for row in rows:
        row['end_period_ts'] -= 1000
    start = end-600
    result = scoped(rows, start, end)
    assert result['eligible'] is False
    assert result['history']['context_bars_excluded'] == 6
    assert result['history']['usable_bars'] == 0
    assert 'INSUFFICIENT_PRE_EVENT_HISTORY' in result['rejection_reasons']


def test_one_context_bar_does_not_complete_four_bar_window():
    end = int(NOW.timestamp())
    start = end-600
    rows = candles(start, end)[:5]
    result = scoped(rows, start, end)
    assert result['history']['supplied_bars'] == 5
    assert result['history']['usable_bars'] == 4
    assert result['eligible'] is False
