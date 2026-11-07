"""Existing IEX feed adapter tests; synthetic cache is not live authentication."""
from datetime import UTC, datetime

import pytest

from app.investment.alpaca_iex import IEXFeed
from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
from app.services.personal_paper_price_evidence import validate_stock_iex_quote


def _feed():
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    feed = IEXFeed(["MSFT"], clock=lambda: now.timestamp())
    return feed, now


def test_existing_feed_adapter_refuses_disconnected_and_stale():
    feed, now = _feed()
    adapter = PersonalPaperIEXProvider(feed)
    with pytest.raises(ValueError, match="AUTHENTICATED_IEX_FEED_UNAVAILABLE"):
        adapter.read_iex_quote("MSFT")
    feed.authenticated = True
    feed.subscribed = True
    feed.connection = "CONNECTED"
    with pytest.raises(ValueError, match="IEX_QUOTE_NOT_FRESH"):
        adapter.read_iex_quote("MSFT")


def test_existing_feed_adapter_maps_fresh_snapshot_without_fill_authority():
    feed, now = _feed()
    feed.authenticated = True
    feed.subscribed = True
    feed.connection = "CONNECTED"
    feed.quotes["MSFT"] = {"symbol": "MSFT", "bid": "399.99", "ask": "400.01",
                           "bid_lots": 2, "ask_lots": 3, "timestamp": now.isoformat(),
                           "source_timestamp": now.timestamp(), "generation": feed.generation}
    adapter = PersonalPaperIEXProvider(feed)
    quote = adapter.read_iex_quote("MSFT")
    evidence = validate_stock_iex_quote(quote, symbol="MSFT", now=now)
    assert evidence["paper_fill_authorized"] is False
    assert evidence["ask"] == "400.01"
    with pytest.raises(ValueError, match="IEX_SYMBOL_NOT_SUBSCRIBED"):
        adapter.read_iex_quote("AVGO")
    feed.generation += 1
    with pytest.raises(ValueError, match="IEX_QUOTE_NOT_FRESH"):
        adapter.read_iex_quote("MSFT")


def test_combined_forward_session_requires_existing_provider_and_operator(tmp_path):
    from app.services.personal_paper_price_evidence import (
        PriceEvidenceRejected, inspect_forward_paper_session_under_lease,
    )
    feed, now = _feed()
    with pytest.raises(PriceEvidenceRejected, match="FORWARD_SESSION_DEPENDENCIES_REQUIRED"):
        inspect_forward_paper_session_under_lease(
            installation=None, request={"action": "AUTO_PAPER"}, components=(),
            provider=PersonalPaperIEXProvider(feed), symbol="MSFT", now=now,
            journal_path=tmp_path / "missing.jsonl", account_id="forward")
    with pytest.raises(PriceEvidenceRejected, match="FORWARD_SESSION_DEPENDENCIES_REQUIRED"):
        inspect_forward_paper_session_under_lease(
            installation=object(), request={"action": "READ_ONLY"}, components=(),
            provider=PersonalPaperIEXProvider(feed), symbol="MSFT", now=now,
            journal_path=tmp_path / "missing.jsonl", account_id="forward")
