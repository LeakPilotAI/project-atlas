from datetime import UTC, datetime, timedelta

import pytest
from app.services.personal_paper_price_evidence import (
    PriceEvidenceRejected,
    validate_stock_iex_quote,
)


def _quote(now):
    return {
        "symbol": "MSFT", "state": "FRESH", "bid": "399.99", "ask": "400.01",
        "bid_lots": 2, "ask_lots": 3, "timestamp": now.isoformat(),
        "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP",
    }


def test_fresh_provider_bid_ask_validates_without_authorizing_execution():
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    result = validate_stock_iex_quote(_quote(now), symbol="MSFT", now=now)
    assert result["ask"] == "400.01"
    assert result["paper_fill_authorized"] is False
    assert result["live_order_authorized"] is False


@pytest.mark.parametrize("mutation", [
    {"state": "STALE"}, {"symbol": "SPY"}, {"bid": "NaN"},
    {"ask": "390"}, {"bid_lots": 0}, {"timestamp_basis": "REST_REQUEST_START"},
    {"timestamp": "2026-11-06T20:00:00"}, {"timestamp": "not a timestamp"},
])
def test_rejects_bad_evidence(mutation):
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    quote = _quote(now)
    quote.update(mutation)
    with pytest.raises(PriceEvidenceRejected):
        validate_stock_iex_quote(quote, symbol="MSFT", now=now)


def test_rejects_stale_future_and_wide_spread():
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    for mutation in (
        {"timestamp": (now - timedelta(seconds=16)).isoformat()},
        {"timestamp": (now + timedelta(seconds=1)).isoformat()},
        {"bid": "390"},
    ):
        quote = _quote(now)
        quote.update(mutation)
        with pytest.raises(PriceEvidenceRejected):
            validate_stock_iex_quote(quote, symbol="MSFT", now=now)