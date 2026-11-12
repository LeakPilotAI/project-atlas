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
                           "bid_shares": 2, "ask_shares": 3, "timestamp": now.isoformat(),
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


def test_rejected_wide_quote_isolated_from_fresh_other_symbol():
    """A bad PLTR quote cannot disable a valid INTC quote or enable PLTR."""
    import json

    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    feed = IEXFeed(["PLTR", "INTC"], clock=lambda: now.timestamp())
    feed.receive('[{"T":"success","msg":"authenticated"}]')
    feed.receive('[{"T":"subscription","quotes":["PLTR","INTC"]}]')
    stamp = now.isoformat().replace("+00:00", "Z")
    def quote(symbol, bid=100, ask=100.02):
        return {"T": "q", "S": symbol, "bp": bid, "ap": ask,
                "bs": 1, "as": 2, "bx": "V", "ax": "V",
                "c": ["R"], "z": "C", "t": stamp}

    feed.receive(json.dumps([quote("PLTR"), quote("INTC")]))
    adapter = PersonalPaperIEXProvider(feed)
    assert adapter.read_iex_quote("PLTR")["state"] == "FRESH"
    assert adapter.read_iex_quote("INTC")["state"] == "FRESH"

    # This 1.96% spread is rejected, deleting only PLTR's cached quote.
    feed.receive(json.dumps([quote("PLTR", bid=100, ask=102)]))
    assert feed.quote_messages_rejected["PLTR"] == 1
    assert feed.snapshot()["error"] is None
    assert adapter.read_iex_quote("INTC")["state"] == "FRESH"
    with pytest.raises(ValueError, match="IEX_QUOTE_NOT_FRESH"):
        adapter.read_iex_quote("PLTR")

    # Subsequent valid PLTR provider evidence is required for readmission.
    feed.receive(json.dumps([quote("PLTR", bid=100.01, ask=100.03)]))
    assert adapter.read_iex_quote("PLTR")["state"] == "FRESH"
    feed.disconnect("IEX_TRANSPORT_UNAVAILABLE")
    with pytest.raises(ValueError, match="AUTHENTICATED_IEX_FEED_UNAVAILABLE"):
        adapter.read_iex_quote("INTC")


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


def test_feed_adapter_rejects_generation_rotation_during_snapshot():
    feed, now = _feed()
    feed.authenticated = True
    feed.subscribed = True
    feed.connection = "CONNECTED"
    feed.quotes["MSFT"] = {"symbol": "MSFT", "bid": "399.99", "ask": "400.01",
                           "bid_shares": 2, "ask_shares": 3, "timestamp": now.isoformat(),
                           "source_timestamp": now.timestamp(), "generation": feed.generation}
    original = feed.snapshot
    def rotating_snapshot():
        view = original()
        feed.generation += 1
        return view
    feed.snapshot = rotating_snapshot
    with pytest.raises(ValueError, match="IEX_QUOTE_GENERATION_INVALID"):
        PersonalPaperIEXProvider(feed).read_iex_quote("MSFT")
