import json

import pytest

from scripts.observation_runtime.r7e47u_fixture_boundary import (
    FixtureBoundary,
    FixtureRefused,
    MarketSnapshot,
)


def raw(**changes):
    record = {
        "provider": "fixture",
        "symbol": "BTC/USD",
        "timestamp_ms": 1790000000000,
        "price": 65000.0,
        "volume": 125.0,
    }
    record.update(changes)
    return json.dumps(record).encode("utf-8")


def test_valid_snapshot():
    boundary = FixtureBoundary("fixture", 2)
    result = boundary.ingest(raw())
    assert type(result) is MarketSnapshot
    assert result.symbol == "BTC/USD"
    assert boundary.attempted == 1


@pytest.mark.parametrize("provider,budget", [
    ("", 1),
    ("BAD PROVIDER", 1),
    ("fixture", 0),
    ("fixture", True),
    ("fixture", 10001),
])
def test_invalid_admission(provider, budget):
    with pytest.raises(FixtureRefused):
        FixtureBoundary(provider, budget)


@pytest.mark.parametrize("payload", [
    b"",
    b"not-json",
    b"[]",
    b'{"provider":"fixture"}',
    b'{"provider":"fixture","symbol":"BTC","timestamp_ms":1,"price":1,"volume":1,"extra":1}',
    b'{"provider":"fixture","symbol":"BTC","timestamp_ms":1,"price":NaN,"volume":1}',
    b"x" * 4097,
])
def test_malformed_payloads(payload):
    with pytest.raises(FixtureRefused):
        FixtureBoundary("fixture", 1).ingest(payload)


@pytest.mark.parametrize("changes", [
    {"provider": "other"},
    {"symbol": ""},
    {"symbol": "btc usd"},
    {"timestamp_ms": True},
    {"timestamp_ms": -1},
    {"price": 0},
    {"price": -1},
    {"price": True},
    {"volume": -1},
    {"volume": False},
])
def test_invalid_market_fields(changes):
    with pytest.raises(FixtureRefused):
        FixtureBoundary("fixture", 1).ingest(raw(**changes))


def test_no_callable_execution():
    boundary = FixtureBoundary("fixture", 1)
    executed = []

    def callback():
        executed.append(True)
        return raw()

    with pytest.raises(FixtureRefused):
        boundary.ingest(callback)
    assert executed == []


def test_failed_valid_size_attempt_consumes_budget():
    boundary = FixtureBoundary("fixture", 1)
    with pytest.raises(FixtureRefused):
        boundary.ingest(b"invalid")
    with pytest.raises(FixtureRefused):
        boundary.ingest(raw())
    assert boundary.attempted == 1


def test_stop_refuses_future_ingest():
    boundary = FixtureBoundary("fixture", 1)
    boundary.stop()
    with pytest.raises(FixtureRefused):
        boundary.ingest(raw())