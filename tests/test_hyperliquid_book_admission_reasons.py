"""Offline-only Hyperliquid first-gate refusal classification.

The established provider parser must remain fail-closed while exposing a
bounded, safe reason code for a future separate read-only diagnostic.
"""
import copy

import pytest

from app.adapters.hyperliquid import (
    HyperliquidPublicBookAdmissionRefused,
    _paper_book_admission_reason,
    _paper_execution_observation,
)


def good():
    metadata = [
        {"universe": [{"name": "ETH", "szDecimals": 4, "maxLeverage": 50}]},
        [{"markPx": "2000.2", "oraclePx": "2000.3", "funding": "0.00001"}],
    ]
    book = {
        "coin": "ETH", "time": 100000,
        "levels": [
            [{"px": "2000", "sz": "1", "n": 2}],
            [{"px": "2001", "sz": "1.5", "n": 1}],
        ],
    }
    return metadata, book


@pytest.mark.parametrize("start,observed,book_at", [
    (99999, 100000, 100000),          # zero age
    (99999, 100001, 100000),          # ordinary fresh
    (90000, 100000, 95000),          # exact 10-sec request / 5-sec book
])
def test_valid_first_gate_and_execution_facts_unchanged(start, observed, book_at):
    metadata, book = good()
    book["time"] = book_at
    before = copy.deepcopy((metadata, book))
    assert _paper_book_admission_reason("ETH", metadata, book, start, observed) is None
    row = _paper_execution_observation("ETH", metadata, book, start, observed)
    assert row["market_book_validated"] is True
    assert row["bid"] == "2000" and row["ask"] == "2001"
    assert row["startup_authorized"] is False
    assert row["financial_execution_authorized"] is False
    assert row["historical_settlement_oracle"] is None
    assert row["fee_schedule"] is None
    assert (metadata, book) == before


@pytest.mark.parametrize("damage,code", [
    ("wrong_symbol", "SYMBOL_NOT_ALLOWLISTED"),
    ("bool_start", "OBSERVATION_CLOCK_TYPE"),
    ("string_observed", "OBSERVATION_CLOCK_TYPE"),
    ("time_reversed", "OBSERVATION_CLOCK_REVERSED"),
    ("request_exceeded", "OBSERVATION_DURATION_EXCEEDED"),
    ("metadata_missing", "METADATA_ENVELOPE"),
    ("metadata_extra", "METADATA_ENVELOPE"),
    ("metadata_tuple", "METADATA_ENVELOPE"),
    ("metadata_part_type", "METADATA_PART_TYPES"),
    ("context_part_type", "METADATA_PART_TYPES"),
    ("book_missing", "BOOK_ENVELOPE"),
    ("book_extra", "BOOK_ENVELOPE"),
    ("book_wrong_type", "BOOK_ENVELOPE"),
    ("book_coin", "BOOK_COIN_MISMATCH"),
    ("book_time_bool", "BOOK_TIMESTAMP_TYPE"),
    ("book_time_float", "BOOK_TIMESTAMP_TYPE"),
    ("book_time_future", "BOOK_TIMESTAMP_FUTURE"),
    ("book_time_stale", "BOOK_TIMESTAMP_STALE"),
])
def test_exact_safe_admission_reason_preserves_refusal(damage, code):
    metadata, book = good()
    symbol, started, observed = "ETH", 99999, 100001
    if damage == "wrong_symbol":
        symbol = "NOT_ALLOWED_SECRET_STRING"
    elif damage == "bool_start":
        started = True
    elif damage == "string_observed":
        observed = "SECRET_TIME"
    elif damage == "time_reversed":
        started = 100002
    elif damage == "request_exceeded":
        started = 90000
    elif damage == "metadata_missing":
        metadata.pop()
    elif damage == "metadata_extra":
        metadata.append([])
    elif damage == "metadata_tuple":
        metadata = tuple(metadata)
    elif damage == "metadata_part_type":
        metadata[0] = []
    elif damage == "context_part_type":
        metadata[1] = {}
    elif damage == "book_missing":
        book.pop("levels")
    elif damage == "book_extra":
        book["unknown_provider_field"] = "NOT_TO_LEAK"
    elif damage == "book_wrong_type":
        book = []
    elif damage == "book_coin":
        book["coin"] = "BTC"
    elif damage == "book_time_bool":
        book["time"] = True
    elif damage == "book_time_float":
        book["time"] = 100000.0
    elif damage == "book_time_future":
        book["time"] = observed + 1
    elif damage == "book_time_stale":
        book["time"] = observed - 5001
    snapshot = copy.deepcopy((metadata, book))
    assert _paper_book_admission_reason(symbol, metadata, book, started, observed) == code
    with pytest.raises(HyperliquidPublicBookAdmissionRefused) as caught:
        _paper_execution_observation(symbol, metadata, book, started, observed)
    assert isinstance(caught.value, ValueError)
    assert caught.value.reason_code == code
    assert str(caught.value) == "Fresh exact Hyperliquid book/metadata evidence required"
    assert "SECRET" not in repr(caught.value)
    assert (metadata, book) == snapshot


@pytest.mark.parametrize("damage", [
    "crossed", "missing_context_oracle", "bad_instrument", "empty_side",
])
def test_later_strict_validation_not_downgraded_to_first_gate(damage):
    meta, book = good()
    if damage == "crossed":
        book["levels"][0][0]["px"] = "2002"
    elif damage == "missing_context_oracle":
        meta[1][0].pop("oraclePx")
    elif damage == "bad_instrument":
        meta[0]["universe"][0]["szDecimals"] = 99
    elif damage == "empty_side":
        book["levels"][1] = []
    assert _paper_book_admission_reason("ETH", meta, book, 99999, 100001) is None
    with pytest.raises(ValueError) as caught:
        _paper_execution_observation("ETH", meta, book, 99999, 100001)
    assert not isinstance(caught.value, HyperliquidPublicBookAdmissionRefused)


def test_fixed_reason_code_can_be_recorded_without_raw_market_payload():
    meta, book = good()
    book["time"] = 100002
    with pytest.raises(HyperliquidPublicBookAdmissionRefused) as caught:
        _paper_execution_observation("ETH", meta, book, 99999, 100001)
    evidence = {"symbol": "ETH", "status": "REFUSED",
                "reason_code": caught.value.reason_code,
                "provider_payload_retained": False, "financial_startup_authorized": False}
    assert evidence == {
        "symbol": "ETH", "status": "REFUSED",
        "reason_code": "BOOK_TIMESTAMP_FUTURE",
        "provider_payload_retained": False, "financial_startup_authorized": False,
    }
