import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest

from scripts import kalshi_forward_quote_observer as observer
from app.prediction.kalshi_public import normalize_market


def market(now, age_hours=1):
    return normalize_market({
        'ticker': 'KXTEST-NEW', 'event_ticker': 'KXTEST-E', 'market_type': 'binary',
        'status': 'open', 'title': 'Test', 'yes_bid_dollars': '0.40',
        'yes_ask_dollars': '0.42', 'no_bid_dollars': '0.58', 'no_ask_dollars': '0.60',
        'volume_fp': '500', 'volume_24h_fp': '500', 'open_interest_fp': '300',
        'occurrence_datetime': (now + timedelta(hours=3)).isoformat(),
        'created_time': (now - timedelta(hours=age_hours)).isoformat(),
        'open_time': (now - timedelta(minutes=45)).isoformat(),
        'is_provisional': False, 'mve_collection_ticker': '', 'mve_selected_legs': [],
    })


def test_writes_only_new_listing_read_only_quote(tmp_path, monkeypatch):
    now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
    async def markets(**kwargs):
        return {'markets': [market(now, 1), market(now, 72)]}
    calls = []
    async def book(ticker, **kwargs):
        calls.append(ticker)
        return {'orderbook': {'yes': {'bids': [{'price_dollars': '0.40', 'quantity_contracts': '5'}],
                                          'asks': [{'price_dollars': '0.42', 'quantity_contracts': '5'}]},
                              'no': {'bids': [{'price_dollars': '0.58', 'quantity_contracts': '5'}],
                                     'asks': [{'price_dollars': '0.60', 'quantity_contracts': '5'}]}}}
    monkeypatch.setattr(observer.kalshi_public, 'get_markets', markets)
    monkeypatch.setattr(observer.kalshi_public, 'get_orderbook', book)
    path = tmp_path / 'quotes.jsonl'
    result = asyncio.run(observer.collect(path=path, now=now))
    assert result['records_written'] == 1
    assert calls == ['KXTEST-NEW']
    row = json.loads(path.read_text().strip())
    assert row['sides']['YES']['buy_vwap'] == '0.42'
    assert row['sides']['NO']['sell_vwap'] == '0.58'
    assert row['orders_placed'] == row['paper_trades_opened'] == 0
    assert result['unattended_paper_authorized'] is False


def test_paginated_discovery_finds_fresh_listing_after_old_first_page(tmp_path, monkeypatch):
    now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
    cursors = []
    async def markets(**kwargs):
        cursors.append(kwargs.get('cursor'))
        if kwargs.get('cursor') is None:
            old = market(now, 72)
            old['ticker'] = 'KXTEST-OLD'
            return {'markets': [old], 'cursor': 'next'}
        return {'markets': [market(now, 1)], 'cursor': ''}
    async def book(ticker, **kwargs):
        return {'orderbook': {'yes': {'bids': [{'price_dollars': '0.40', 'quantity_contracts': '5'}],
                                          'asks': [{'price_dollars': '0.42', 'quantity_contracts': '5'}]},
                              'no': {'bids': [{'price_dollars': '0.58', 'quantity_contracts': '5'}],
                                     'asks': [{'price_dollars': '0.60', 'quantity_contracts': '5'}]}}}
    monkeypatch.setattr(observer.kalshi_public, 'get_markets', markets)
    monkeypatch.setattr(observer.kalshi_public, 'get_orderbook', book)
    result = asyncio.run(observer.collect(path=tmp_path / 'quotes.jsonl', now=now))
    assert cursors == [None, 'next']
    assert result['pages_scanned'] == 2
    assert result['records_written'] == 1
    assert result['unique_markets_screened'] == 2


def test_fresh_low_activity_market_is_observed_but_not_entry_qualified(tmp_path, monkeypatch):
    now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
    fresh = market(now, 1)
    fresh['activity'] = {'volume_24h_contracts': '0', 'open_interest_contracts': '0'}
    async def markets(**kwargs):
        return {'markets': [fresh]}
    async def book(ticker, **kwargs):
        return {'orderbook': {'yes': {'bids': [{'price_dollars': '0.40', 'quantity_contracts': '5'}],
                                          'asks': [{'price_dollars': '0.42', 'quantity_contracts': '5'}]},
                              'no': {'bids': [{'price_dollars': '0.58', 'quantity_contracts': '5'}],
                                     'asks': [{'price_dollars': '0.60', 'quantity_contracts': '5'}]}}}
    monkeypatch.setattr(observer.kalshi_public, 'get_markets', markets)
    monkeypatch.setattr(observer.kalshi_public, 'get_orderbook', book)
    path = tmp_path / 'quotes.jsonl'
    result = asyncio.run(observer.collect(path=path, now=now))
    assert result['records_written'] == 1
    assert result['entry_gate_qualified_new_listings_seen'] == 0
    row = json.loads(path.read_text().strip())
    assert row['entry_gate_passed'] is False
    assert 'INSUFFICIENT_24H_VOLUME' in row['entry_gate_reasons']
    assert row['orders_placed'] == row['paper_trades_opened'] == 0


def test_no_eligible_market_writes_nothing(tmp_path, monkeypatch):
    now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
    async def markets(**kwargs):
        return {'markets': [market(now, 72)]}
    monkeypatch.setattr(observer.kalshi_public, 'get_markets', markets)
    path = tmp_path / 'quotes.jsonl'
    result = asyncio.run(observer.collect(path=path, now=now))
    assert result['records_written'] == 0
    assert not path.exists()


@pytest.mark.parametrize('quantity', [Decimal('NaN'), Decimal('Infinity'), Decimal('0'), Decimal('11')])
def test_invalid_quantity_refused(quantity):
    with pytest.raises(ValueError):
        asyncio.run(observer.collect(quantity=quantity))
