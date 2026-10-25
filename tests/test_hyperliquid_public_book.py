"""Documented public info shapes; no provider connection or authority install."""
import copy

import pytest
from app.adapters.hyperliquid import (
    HyperliquidAdapter,
    _paper_execution_observation,
    _paper_funding_observation,
)


def inputs():
    return ([{"universe": [{"name": "BTC", "szDecimals": 5, "maxLeverage": 50, "marginTableId": 56}],
              "marginTables": [[56, {"marginTiers": [{"lowerBound": "0", "maxLeverage": 50}]}]]},
             [{"markPx": "100.5", "oraclePx": "100.4", "funding": "0.0000125"}]],
            {"coin": "BTC", "time": 100000, "levels": [[{"px": "100", "sz": "1.25", "n": 2}],
                                                        [{"px": "101", "sz": "2.5", "n": 1}]]})


def test_book_is_executable_price_observation_not_authority_or_settlement():
    metadata, book = inputs()
    before = copy.deepcopy((metadata, book))
    result = _paper_execution_observation("BTC", metadata, book, 99999, 100001)
    assert result["bid"] == "100" and result["ask"] == "101" and result["mark"] == "100.5"
    assert result["funding_settlement"] is None and result["fee_schedule"] is None
    assert not result["financial_execution_authorized"] and not result["startup_authorized"]
    assert (metadata, book) == before


@pytest.mark.parametrize("damage", ["mids", "stale", "future", "wrong-coin", "empty", "crossed",
    "duplicate", "nonfinite", "no-oracle", "delisted", "misaligned", "clock"])
def test_missing_or_conflicting_book_evidence_refuses(damage):
    meta, book = inputs()
    observed = 100001
    if damage == "mids": book = {"BTC": "100"}
    elif damage == "stale": book["time"] = 1
    elif damage == "future": book["time"] = 100002
    elif damage == "wrong-coin": book["coin"] = "ETH"
    elif damage == "empty": book["levels"][0] = []
    elif damage == "crossed": book["levels"][0][0]["px"] = "102"
    elif damage == "duplicate": book["levels"][0].append(copy.deepcopy(book["levels"][0][0]))
    elif damage == "nonfinite": book["levels"][0][0]["sz"] = "NaN"
    elif damage == "no-oracle": meta[1][0].pop("oraclePx")
    elif damage == "delisted": meta[0]["universe"][0]["isDelisted"] = True
    elif damage == "misaligned": meta[1].append(meta[1][0])
    else: observed = 99998
    with pytest.raises(ValueError): _paper_execution_observation("BTC", meta, book, 99999, observed)


@pytest.mark.asyncio
async def test_read_method_default_refuses_without_client_and_gate(monkeypatch):
    adapter = HyperliquidAdapter()
    calls = []
    async def forbidden(body): calls.append(body)
    monkeypatch.setattr(adapter, "_post", forbidden)
    with pytest.raises(ValueError): await adapter.paper_execution_observation("BTC", clock_ms=lambda: 100001)
    assert not calls


@pytest.mark.asyncio
async def test_fixed_info_requests_preserve_public_observation_boundary(monkeypatch):
    from app.adapters import hyperliquid_gate_registry
    adapter = HyperliquidAdapter()
    adapter._client = object()
    calls, payloads = [], list(inputs())
    async def fixture_post(body):
        calls.append(body)
        return payloads.pop(0)
    monkeypatch.setattr(adapter, "_post", fixture_post)
    monkeypatch.setattr(hyperliquid_gate_registry, "require_gate", lambda: object())
    result = await adapter.paper_execution_observation("BTC", clock_ms=lambda: 100001)
    assert calls == [{"type": "metaAndAssetCtxs"}, {"type": "l2Book", "coin": "BTC"}]
    assert result["bid_size"] == "1.25" and not result["financial_execution_authorized"]


@pytest.mark.parametrize("damage", [None, "missing", "duplicate", "wrong-symbol", "nonfinite", "wrong-interval", "future"])
def test_hourly_funding_history_never_supplies_missing_oracle_or_zero(damage):
    rows = [{"coin": "BTC", "time": hour * 3600000, "fundingRate": "0.0001", "premium": "0.0008"} for hour in (1, 2)]
    observed = 10800000
    if damage == "missing": rows.pop()
    elif damage == "duplicate": rows[1] = rows[0]
    elif damage == "wrong-symbol": rows[0]["coin"] = "ETH"
    elif damage == "nonfinite": rows[0]["fundingRate"] = "NaN"
    elif damage == "wrong-interval": rows[1]["time"] += 1000
    elif damage == "future": observed = 1
    if damage:
        with pytest.raises(ValueError): _paper_funding_observation("BTC", rows, 3600000, 10800000, observed, observed)
    else:
        result = _paper_funding_observation("BTC", rows, 3600000, 10800000, observed, observed)
        assert result["rate_history_complete"] and not result["settlement_evidence_complete"]
        assert all(r["settlement_oracle"] is None for r in result["records"])
        assert not result["financial_execution_authorized"]
