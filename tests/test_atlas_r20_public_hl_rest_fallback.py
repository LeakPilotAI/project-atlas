"""Original R20 public REST fallback cadence: source data is never financial authority."""
import asyncio
import copy
import json

import pytest

from scripts.observation_runtime.atlas_r20_public_hl_rest_fallback import (
    SCHEMA,
    SYMBOLS,
    URL,
    _read_response,
    observe,
    validate_cycle,
)

NOW = 1_800_000_000_000


def provider(*, stamp=NOW - 200):
    metadata = [
        {"universe": [
            {"name": symbol, "szDecimals": 5, "maxLeverage": 50}
            for symbol in SYMBOLS
        ]},
        [{"markPx": "100.5", "oraclePx": "100.4", "funding": "0.00001"}
         for _ in SYMBOLS],
    ]
    books = {
        symbol: {
            "coin": symbol, "time": stamp,
            "levels": [
                [{"px": "100", "sz": "2", "n": 1}],
                [{"px": "101", "sz": "3", "n": 2}],
            ],
        } for symbol in SYMBOLS
    }
    return metadata, books


def test_original_three_symbol_parser_still_refuses_financial_authority():
    metadata, books = provider()
    rows = validate_cycle(
        metadata=metadata, books=books,
        started_ms=NOW - 100, observed_ms=NOW
    )
    assert set(rows) == set(SYMBOLS)
    assert all(item["source_age_ms"] == 200 for item in rows.values())
    assert all(len(item["source_digest"]) == 64 for item in rows.values())
    assert all("fee" not in item and "authorized" not in item for item in rows.values())


@pytest.mark.parametrize("mutation", [
    "missing_book", "foreign_coin", "stale", "future", "crossed", "no_oracle",
    "bad_metadata", "nan", "missing_depth", "too_long", "reversed_clock",
])
def test_bad_current_cut_never_passes(mutation):
    metadata, books = provider()
    started, observed = NOW - 100, NOW
    if mutation == "missing_book":
        del books["SOL"]
    elif mutation == "foreign_coin":
        books["ETH"]["coin"] = "BTC"
    elif mutation == "stale":
        books["BTC"]["time"] -= 10_000
    elif mutation == "future":
        books["SOL"]["time"] += 800
    elif mutation == "crossed":
        books["ETH"]["levels"][0][0]["px"] = "101"
    elif mutation == "no_oracle":
        metadata[1][0].pop("oraclePx")
    elif mutation == "bad_metadata":
        metadata = []
    elif mutation == "nan":
        books["BTC"]["levels"][0][0]["sz"] = "NaN"
    elif mutation == "missing_depth":
        books["SOL"]["levels"][1] = []
    elif mutation == "too_long":
        observed += 6_000
    else:
        observed = started - 1
    with pytest.raises(ValueError):
        validate_cycle(metadata=metadata, books=books,
                       started_ms=started, observed_ms=observed)


@pytest.mark.parametrize("cycles,interval", [
    (0, 4), (1, 4), (7, 4), (True, 4), (3.5, 4),
    (4, 0), (4, 2), (4, 7), (4, False),
])
def test_cadence_is_explicit_and_bounded(cycles, interval):
    with pytest.raises(ValueError):
        asyncio.run(observe(cycles=cycles, interval_seconds=interval))


class Response:
    def __init__(self, data, *, status=200, url=URL):
        self.status_code, self.url = status, url
        self._data = data
        self.content = json.dumps(data).encode()
    def json(self):
        return copy.deepcopy(self._data)


@pytest.mark.parametrize("fault", ["http_status", "redirect", "empty"])
def test_public_response_refuses_bad_transport(fault):
    response = Response({}, status=503 if fault == "http_status" else 200,
                        url="https://example.org/info" if fault == "redirect" else URL)
    if fault == "empty":
        response.content = b""
    with pytest.raises(ValueError):
        _read_response(response)


def test_public_reader_attempts_no_more_than_four_per_cycle():
    class Clock:
        def __init__(self):
            self.elapsed = 0.0
        def steady(self):
            return self.elapsed
        def now_ms(self):
            return NOW + int(self.elapsed * 1000)
        async def sleep(self, seconds):
            self.elapsed += seconds

    class Client:
        def __init__(self, clock):
            self.clock, self.calls = clock, []
        async def post(self, url, json):
            assert url == URL
            self.calls.append(json)
            meta, books = provider(stamp=self.clock.now_ms() - 200)
            data = meta if json["type"] == "metaAndAssetCtxs" else books[json["coin"]]
            return Response(data)

    clock = Clock()
    client = Client(clock)
    report = asyncio.run(observe(
        cycles=3, interval_seconds=4, client=client,
        wall_ms=clock.now_ms, monotonic=clock.steady, sleeper=clock.sleep
    ))
    assert report["schema"] == SCHEMA
    assert report["cycles"] == 3
    assert report["public_info_http_attempts"] == 12
    assert len(client.calls) == 12
    assert [row["type"] for row in client.calls].count("metaAndAssetCtxs") == 3
    assert all(sum(row.get("coin") == symbol for row in client.calls) == 3
               for symbol in SYMBOLS)
    assert report["max_observed_book_source_age_ms"] == 200
    for label in (
        "provider_entitlement_accepted", "financial_source_issuer_accepted",
        "financial_clock_accepted", "historical_consensus_settlement_oracle_accepted",
        "account_specific_fee_schedule_accepted", "extended_soak_accepted",
        "paper_startup_authorized", "live_trading_authorized",
    ):
        assert report[label] is False
