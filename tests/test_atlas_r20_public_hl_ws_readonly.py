"""Public Hyperliquid WS transport checks are NEVER financial source admission."""
import asyncio
import copy
import json

import pytest

from scripts.observation_runtime.atlas_r20_public_hl_ws_readonly import (
    SCHEMA,
    SYMBOLS,
    URL,
    observe,
    qualify_continuity,
    require_fast_five_level_book,
    validate_public_book,
)

NOW_MS = 1_800_000_000_000


def book(coin="BTC"):
    return {
        "channel": "l2Book",
        "data": {
            "coin": coin,
            "time": NOW_MS - 150,
            "levels": [
                [{"px": "110.0", "sz": "2.5", "n": 2},
                 {"px": "109.0", "sz": "1.0", "n": 1}],
                [{"px": "111.0", "sz": "1.5", "n": 1},
                 {"px": "112.0", "sz": "1.1", "n": 2}],
            ],
        },
    }


@pytest.mark.parametrize("coin", SYMBOLS)
def test_valid_book_structured_source_only(coin):
    receipt = validate_public_book(book(coin), observed_ms=NOW_MS)
    assert receipt["symbol"] == coin
    assert receipt["source_age_ms"] == 150
    assert receipt["bid_levels"] == receipt["ask_levels"] == 2
    assert "authorized" not in receipt


@pytest.mark.parametrize("change", [
    "missing_levels", "foreign_coin", "future", "stale", "crossed",
    "unordered_bids", "unordered_asks", "zero_size", "infinite_price",
    "negative_orders", "bool_time", "zero_depth", "bad_channel",
])
def test_refuses_inconsistent_public_book_not_fake_financial_proof(change):
    data = copy.deepcopy(book())
    x = data["data"]
    if change == "missing_levels":
        x.pop("levels")
    elif change == "foreign_coin":
        x["coin"] = "DOGE"
    elif change == "future":
        x["time"] = NOW_MS + 2500
    elif change == "stale":
        x["time"] = NOW_MS - 20_000
    elif change == "crossed":
        x["levels"][0][0]["px"] = "111.0"
    elif change == "unordered_bids":
        x["levels"][0][1]["px"] = "110.5"
    elif change == "unordered_asks":
        x["levels"][1][1]["px"] = "110.5"
    elif change == "zero_size":
        x["levels"][0][0]["sz"] = "0"
    elif change == "infinite_price":
        x["levels"][0][0]["px"] = "NaN"
    elif change == "negative_orders":
        x["levels"][0][0]["n"] = -1
    elif change == "bool_time":
        x["time"] = True
    elif change == "zero_depth":
        x["levels"][0] = []
    else:
        data["channel"] = "userFills"
    with pytest.raises(ValueError):
        validate_public_book(data, observed_ms=NOW_MS)


@pytest.mark.parametrize("seconds", [0, -1, 9, 31, 3.5, True])
def test_refuse_unbounded_websocket_observation(seconds):
    with pytest.raises(ValueError):
        asyncio.run(observe(seconds=seconds, connect=None))


@pytest.mark.parametrize("fast_books,ack_fast,passed", [
    (False, False, True), (True, True, True), (True, False, False),
])
def test_fake_websocket_round_trip_never_grants_paper(fast_books, ack_fast, passed):
    class Socket:
        def __init__(self):
            self.sent = []
            self.messages = [
                {"channel": "subscriptionResponse", "data": {
                    "method": "subscribe", "subscription": {
                        "type": "l2Book", "coin": coin,
                        **({"fast": True} if ack_fast else {})}}}
                for coin in SYMBOLS
            ]
            for index in range(40):
                for coin in SYMBOLS:
                    sample = book(coin)
                    sample["data"]["time"] = NOW_MS - 550 + index * 10
                    self.messages.append(sample)
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def send(self, message):
            self.sent.append(json.loads(message))
        async def recv(self):
            if self.messages:
                return json.dumps(self.messages.pop(0))
            raise TimeoutError

    class Clock:
        def __init__(self):
            self.now = 0
        def __call__(self):
            self.now += 0.1
            return self.now

    sock = Socket()
    report = asyncio.run(observe(
        seconds=10, fast_books=fast_books,
        connect=lambda url, **kwargs: sock,
        wall_ms=lambda: NOW_MS, monotonic=Clock()))
    assert len(sock.sent) == 3
    assert all(x["method"] == "subscribe" for x in sock.sent)
    assert all(x["subscription"].get("fast") is True for x in sock.sent) == fast_books
    assert report["fast_five_level_mode_requested"] is fast_books
    assert report["data_only_probe_passed"] is passed
    assert report["schema"] == SCHEMA
    assert report["endpoint"] == URL
    assert set(report["subscription_acknowledged"]) == (
        set(SYMBOLS) if passed else set()
    )
    if passed:
        assert all(report["valid_book_messages"][coin] >= 2 for coin in SYMBOLS)
    assert report["paper_startup_authorized"] is False
    assert report["live_trading_authorized"] is False
    assert report["provider_rights_verified"] is False
    assert report["historical_funding_oracle_verified"] is False


@pytest.mark.parametrize("change", ["interarrival", "end_window", "insufficient", "invalid"])
def test_sparse_or_incomplete_public_websocket_never_qualifies(change):
    counts = {symbol: 3 for symbol in SYMBOLS}
    gaps = {symbol: 0.8 for symbol in SYMBOLS}
    end = {symbol: 0.7 for symbol in SYMBOLS}
    invalid = 0
    if change == "interarrival":
        gaps["BTC"] = 10.344  # Genuine first public observation 2026-11-13
    elif change == "end_window":
        end["ETH"] = 5.01
    elif change == "insufficient":
        counts["SOL"] = 1
    else:
        invalid = 1
    assert qualify_continuity(
        subscribed=set(SYMBOLS), counts=counts, max_gap=gaps,
        last_message_gap=end, invalid=invalid, total=12,
    ) is False


@pytest.mark.parametrize("depth", [0, 6, 20, True, "5"])
def test_fast_depth_cannot_silently_accept_standard_or_malformed_book(depth):
    with pytest.raises(ValueError):
        require_fast_five_level_book({"bid_levels": depth, "ask_levels": 5})


def test_fast_depth_requires_maximum_five_levels_each_side():
    value = {"bid_levels": 5, "ask_levels": 3, "symbol": "BTC"}
    assert require_fast_five_level_book(value) is value
