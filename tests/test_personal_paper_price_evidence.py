from datetime import UTC, datetime, timedelta

import pytest
from app.services.personal_paper_price_evidence import (
    PriceEvidenceRejected,
    preview_quality_dips_execution,
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

def test_missing_timestamp_basis_is_not_accepted():
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    quote = _quote(now)
    quote.pop("timestamp_basis")
    with pytest.raises(PriceEvidenceRejected, match="UNTRUSTED_TIMESTAMP_BASIS"):
        validate_stock_iex_quote(quote, symbol="MSFT", now=now)


def test_strategy_quote_preview_retains_strategy_blockers_even_with_fresh_quote():
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    observation = {
        "strategy": "QUALITY_DIPS_V3", "symbol": "MSFT", "observation_id": "sample-1",
        "blockers": ["QUALITY_DIPS_RESEARCH_STALE"],
        "strategy_result": {"entry_ladder": {"ready": True}},
        "paper_execution_eligible": False,
    }
    preview = preview_quality_dips_execution(observation, _quote(now), now=now)
    assert preview["quote_evidence"]["ask"] == "400.01"
    assert "QUALITY_DIPS_RESEARCH_STALE" in preview["blockers"]
    assert preview["paper_fill_authorized"] is False


def test_strategy_quote_preview_rejects_stale_quote_without_filling():
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    observation = {
        "strategy": "QUALITY_DIPS_V3", "symbol": "MSFT", "observation_id": "sample-2",
        "blockers": [], "strategy_result": {"entry_ladder": {"ready": True}},
        "paper_execution_eligible": False,
    }
    quote = _quote(now)
    quote["timestamp"] = (now - timedelta(seconds=30)).isoformat()
    preview = preview_quality_dips_execution(observation, quote, now=now)
    assert "PROVIDER_QUOTE_STALE_OR_FUTURE" in preview["blockers"]
    assert preview["quote_evidence"] is None
    assert preview["paper_execution_eligible"] is False

@pytest.mark.parametrize("ladder", [None, [], "ready", True, {"ready": 1}, {"ready": "yes"}])
def test_preview_malformed_ladder_fails_closed_without_crash(ladder):
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    observation = {
        "strategy": "QUALITY_DIPS_V3", "symbol": "MSFT", "blockers": [],
        "strategy_result": {"entry_ladder": ladder}, "paper_execution_eligible": True,
    }
    result = preview_quality_dips_execution(observation, _quote(now), now=now)
    assert "QUALITY_DIPS_ENTRY_LADDER_NOT_READY" in result["blockers"]
    assert result["paper_fill_authorized"] is False


@pytest.mark.parametrize("blockers", [None, "BLOCKED", {"x": True}, [None], [""], [1]])
def test_preview_rejects_malformed_blockers(blockers):
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    observation = {
        "strategy": "QUALITY_DIPS_V3", "symbol": "MSFT", "blockers": blockers,
        "strategy_result": {"entry_ladder": {"ready": True}},
        "paper_execution_eligible": True,
    }
    with pytest.raises(PriceEvidenceRejected, match="INVALID_STRATEGY_BLOCKERS"):
        preview_quality_dips_execution(observation, _quote(now), now=now)


def test_stock_execution_side_uses_adverse_quote_side_without_filling():
    from app.services.personal_paper_price_evidence import preview_stock_execution_side
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    evidence = validate_stock_iex_quote(_quote(now), symbol="MSFT", now=now)
    buy = preview_stock_execution_side(evidence, side="BUY", quantity="2")
    sell = preview_stock_execution_side(evidence, side="SELL", quantity="2")
    assert buy["reference_price"] == "400.01"
    assert sell["reference_price"] == "399.99"
    assert buy["reference_notional"] == "800.02"
    assert not buy["paper_fill_authorized"] and not sell["live_order_authorized"]


@pytest.mark.parametrize("side,quantity", [("SHORT", "1"), ("BUY", "0"), ("SELL", "NaN"), ("BUY", "Infinity"), ("BUY", "bad")])
def test_stock_execution_side_refuses_invalid_requests(side, quantity):
    from app.services.personal_paper_price_evidence import preview_stock_execution_side
    now = datetime(2026, 11, 6, 20, tzinfo=UTC)
    evidence = validate_stock_iex_quote(_quote(now), symbol="MSFT", now=now)
    with pytest.raises(PriceEvidenceRejected):
        preview_stock_execution_side(evidence, side=side, quantity=quantity)
