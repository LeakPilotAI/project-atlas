"""Public Hyperliquid REST relief during sparse WS gaps, never financial GO."""
from __future__ import annotations

from copy import deepcopy

import pytest
from app.adapters.hyperliquid import (
    HyperliquidAdapter,
    _paper_execution_observation,
)
from app.services.hyperliquid_public_rest_gap_monitor import (
    NO_AUTHORITY,
    PublicBookContinuityRefused,
    PublicRestGapMonitor,
)

STAMP = 100_000
NOW = 100_500
OLD_WS = 90_000


def cached_adapter(*, stamp=STAMP):
    adapter = HyperliquidAdapter()
    adapter._connected = True  # Test-only in-memory injection, never provider I/O.
    metadata = [
        {"universe": [{"name": "BTC", "maxLeverage": 50, "szDecimals": 5}]},
        [{"markPx": "100.4", "oraclePx": "100.3", "funding": "0.0001"}],
    ]
    book = {
        "coin": "BTC", "time": stamp,
        "levels": [
            [{"px": "100", "sz": "1.3", "n": 2}],
            [{"px": "101", "sz": "2.4", "n": 3}],
        ],
    }
    parsed = _paper_execution_observation("BTC", metadata, book, stamp + 50, stamp + 210)
    adapter._cache_paper("books", "BTC", {
        "parsed": parsed, "metadata": metadata, "book": book,
    })
    return adapter


def inspect(monitor, *, ws=OLD_WS, now=NOW):
    return monitor.inspect(
        symbol="BTC", last_ws_book_received_ms=ws, now_ms=now)


def test_original_book_can_predate_http_start_and_relieve_sparse_ws_for_research():
    adapter = cached_adapter()
    monitor = PublicRestGapMonitor(adapter=adapter)
    result = inspect(monitor)
    assert result["status"] == "FRESH_HTTP_BOOK_FOR_RESEARCH_ONLY_WS_GAP_UNRESOLVED"
    assert result["ws_gap_ms"] == 10_500
    assert result["http_book_age_ms"] == 500
    assert result["rest_public_book_for_research"] is True
    assert all(result[k] is False for k in NO_AUTHORITY)
    assert adapter.paper_source_snapshot()["facts"]["books"]["BTC"]["parsed"][
        "request_started_ms"] > result["http_book_timestamp_ms"]


def test_websocket_current_does_not_claim_continuity_or_touch_http_cache():
    monitor = PublicRestGapMonitor(adapter=HyperliquidAdapter())
    result = inspect(monitor, ws=95_000)
    assert result["status"] == "WS_WITHIN_GAP_WINDOW_NOT_ATTESTED_HERE"
    assert result["http_book_timestamp_ms"] is None
    assert not result["rest_public_book_for_research"]
    assert all(result[k] is False for k in NO_AUTHORITY)


def test_actual_parsed_cache_replay_cannot_claim_new_fresh_http_observation():
    adapter = cached_adapter()
    monitor = PublicRestGapMonitor(adapter=adapter)
    inspect(monitor)
    with pytest.raises(PublicBookContinuityRefused, match="REPLAY"):
        inspect(monitor, now=101_000)


def test_advancing_fresh_public_http_book_may_be_observed_again():
    adapter = cached_adapter()
    monitor = PublicRestGapMonitor(adapter=adapter)
    inspect(monitor)
    newer = cached_adapter(stamp=100_300).paper_source_snapshot()["facts"]["books"]["BTC"]
    newer["parsed"]["request_started_ms"] = 100_250
    newer["parsed"]["observed_at_ms"] = 100_420
    adapter._cache_paper("books", "BTC", newer)
    new = inspect(monitor, now=100_600)
    assert new["http_book_timestamp_ms"] == 100_300
    assert new["http_book_age_ms"] == 300
    assert all(new[k] is False for k in NO_AUTHORITY)


@pytest.mark.parametrize("mutation", [
    "fake_adapter", "no_connection", "missing_book", "wrong_provenance",
    "wrong_symbol", "financial_true", "start_true", "fake_fee",
    "fake_funding", "fake_settlement_oracle", "expired_at_now",
    "future_event", "zero_book_price", "crossed_book", "bad_size",
    "out_of_order_http_window", "wrong_original_timestamp",
])
def test_unsafe_source_or_owner_never_claims_valid_rest_research(mutation):
    adapter = cached_adapter()
    if mutation == "fake_adapter":
        with pytest.raises(PublicBookContinuityRefused):
            PublicRestGapMonitor(adapter=object())
        return
    if mutation == "no_connection":
        adapter._connected = False
    elif mutation == "missing_book":
        adapter._paper_cache["books"] = {}
    else:
        row = deepcopy(adapter._paper_cache["books"]["BTC"])
        parsed = row["parsed"]
        if mutation == "wrong_provenance":
            parsed["provider"] = "https://untrusted.example/info"
        elif mutation == "wrong_symbol":
            parsed["symbol"] = "ETH"
        elif mutation == "financial_true":
            parsed["financial_execution_authorized"] = True
        elif mutation == "start_true":
            parsed["startup_authorized"] = True
        elif mutation == "fake_fee":
            parsed["fee_schedule"] = {"approved": True}
        elif mutation == "fake_funding":
            parsed["funding_settlement"] = "0.02"
        elif mutation == "fake_settlement_oracle":
            parsed["historical_settlement_oracle"] = "100"
        elif mutation == "expired_at_now":
            parsed["book_timestamp_ms"] = 94_000
            row["book"]["time"] = 94_000
        elif mutation == "future_event":
            parsed["book_timestamp_ms"] = 102_000
            row["book"]["time"] = 102_000
        elif mutation == "zero_book_price":
            parsed["bid"] = "0"
        elif mutation == "crossed_book":
            parsed["bid"] = "102"
        elif mutation == "bad_size":
            parsed["ask_size"] = "NaN"
        elif mutation == "out_of_order_http_window":
            parsed["observed_at_ms"] = 100_000
        elif mutation == "wrong_original_timestamp":
            row["book"]["time"] += 1
        adapter._cache_paper("books", "BTC", row)
    with pytest.raises(PublicBookContinuityRefused):
        inspect(PublicRestGapMonitor(adapter=adapter))


@pytest.mark.parametrize("ws,now", [
    (100_501, 100_500), (-1, 100_500), (None, 100_500),
    (90_000, 0), (90_000, 100_500.0),
])
def test_invalid_gaps_or_clock_refuse(ws, now):
    monitor = PublicRestGapMonitor(adapter=cached_adapter())
    with pytest.raises(PublicBookContinuityRefused):
        inspect(monitor, ws=ws, now=now)


def test_rollback_refused_even_after_nonfinancial_ws_status():
    monitor = PublicRestGapMonitor(adapter=cached_adapter())
    inspect(monitor, ws=95_000)
    with pytest.raises(PublicBookContinuityRefused, match="CLOCK"):
        inspect(monitor, now=100_499)


def test_snapshot_mutated_during_verification_fails_closed(monkeypatch):
    adapter = cached_adapter()
    original = adapter.paper_source_snapshot
    attempts = 0

    def drifting():
        nonlocal attempts
        attempts += 1
        result = original()
        if attempts == 2:
            result["revision"] += 1
        return result
    monkeypatch.setattr(adapter, "paper_source_snapshot", drifting)
    with pytest.raises(PublicBookContinuityRefused, match="SOURCE_CHANGED"):
        inspect(PublicRestGapMonitor(adapter=adapter))
