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


@pytest.mark.parametrize("location", [
    "mark", "oracle", "funding", "bid", "ask", "size",
])
def test_malformed_provider_decimal_refuses_through_sanitized_cli_path(location):
    from scripts.observation_runtime.atlas_r14_hyperliquid_public_book_probe import (
        safe_refusal_code,
    )
    metadata, book = inputs()
    if location == "mark":
        metadata[1][0]["markPx"] = "NOT_A_DECIMAL"
    elif location == "oracle":
        metadata[1][0]["oraclePx"] = "NOT_A_DECIMAL"
    elif location == "funding":
        metadata[1][0]["funding"] = "NOT_A_DECIMAL"
    elif location == "bid":
        book["levels"][0][0]["px"] = "NOT_A_DECIMAL"
    elif location == "ask":
        book["levels"][1][0]["px"] = "NOT_A_DECIMAL"
    else:
        book["levels"][0][0]["sz"] = "NOT_A_DECIMAL"
    with pytest.raises(ValueError) as caught:
        _paper_execution_observation("BTC", metadata, book, 99999, 100001)
    assert type(caught.value) is ValueError
    assert "NOT_A_DECIMAL" not in str(caught.value)
    assert safe_refusal_code(caught.value) == "HL_SOURCE_OR_DATA_VALIDATION_REFUSED"


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
    cache = adapter.paper_source_snapshot()
    retained = cache["facts"]["books"]["BTC"]
    assert retained["parsed"] == result
    assert retained["metadata"][0]["universe"] == [
        {"name": "BTC", "szDecimals": 5, "maxLeverage": 50, "marginTableId": 56}]
    assert _paper_execution_observation(
        "BTC", retained["metadata"], retained["book"],
        result["request_started_ms"], result["observed_at_ms"]) == result


@pytest.mark.parametrize("damage", [None, "missing", "duplicate", "wrong-symbol", "nonfinite", "wrong-interval", "future"])
def test_hourly_funding_history_never_supplies_missing_oracle_or_zero(damage):
    rows = [{"coin": "BTC", "time": hour * 3600000, "fundingRate": "0.0001", "premium": "0.0008"} for hour in (1, 2)]
    observed = 10800000
    if damage == "missing": rows.pop()
    elif damage == "duplicate": rows[1] = rows[0]
    elif damage == "wrong-symbol": rows[0]["coin"] = "ETH"
    elif damage == "nonfinite": rows[0]["fundingRate"] = "NaN"
    elif damage == "wrong-interval": rows[1]["time"] += 30001  # Outside bounded 30-second publication window
    elif damage == "future": observed = 1
    if damage:
        with pytest.raises(ValueError): _paper_funding_observation("BTC", rows, 3600000, 10800000, observed, observed)
    else:
        result = _paper_funding_observation("BTC", rows, 3600000, 10800000, observed, observed)
        assert result["rate_history_complete"] and not result["settlement_evidence_complete"]
        assert all(r["settlement_oracle"] is None for r in result["records"])
        assert not result["financial_execution_authorized"]


def test_inclusive_provider_window_preserves_raw_and_returns_latest_requested():
 from app.adapters.hyperliquid import candle_window
 raw=[{'t':i,'o':'10','h':'11','l':'9','c':'10.5','v':'20','n':3} for i in range(97)]
 before=copy.deepcopy(raw)
 result=candle_window(raw,96)
 assert len(result)==96 and result[0]['time']==1 and result[-1]['time']==96
 assert raw==before


@pytest.mark.asyncio
@pytest.mark.parametrize('raw,expected',[
    ({'time':1000},[]),
    ({'time':1000,'fundingRate':'Infinity'},[]),
    ({'time':1000,'fundingRate':0,'funding_rate':'0.01'},[]),
    ({'time':1000,'fundingRate':0},[0.0]),
])
async def test_research_funding_requires_explicit_finite_unambiguous_rate(monkeypatch,raw,expected):
    adapter=HyperliquidAdapter()
    async def reply(_request):return [copy.deepcopy(raw)]
    monkeypatch.setattr(adapter,'_post',reply)
    result=await adapter.get_funding_history('BTC')
    assert [row['funding_rate'] for row in result]==expected


def test_large_original_hyperliquid_universe_compacts_without_changing_executable_facts():
    import json
    from app.adapters.hyperliquid import _verified_compact_paper_metadata
    metadata, book = inputs()
    original = copy.deepcopy((metadata, book))
    for i in range(235):
        metadata[0]["universe"].append({
            "name": f"SYNTHETIC_EXTRA_{i}", "szDecimals": 5,
            "maxLeverage": 50, "marginTableId": 56,
        })
        metadata[1].append({
            "markPx": "100.5", "oraclePx": "100.4", "funding": "0.0000125",
        })
    accepted = _paper_execution_observation(
        "BTC", metadata, book, 99999, 100001)
    compact = _verified_compact_paper_metadata(
        "BTC", metadata, book, 99999, 100001, accepted)
    assert _paper_execution_observation(
        "BTC", compact, book, 99999, 100001) == accepted
    assert compact[0]["universe"] == [original[0][0]["universe"][0]]
    assert compact[1] == [original[0][1][0]]
    assert compact[0]["marginTables"] == original[0][0]["marginTables"]
    assert len(json.dumps(compact).encode()) * 10 < len(
        json.dumps(metadata).encode())
    # This test grants no source issuer, original oracle, broker access, or fill.
    assert accepted["financial_execution_authorized"] is False
    assert accepted["funding_settlement"] is None
    assert accepted["startup_authorized"] is False


def test_compact_metadata_never_adopts_foreign_or_modified_instrument():
    from app.adapters.hyperliquid import _verified_compact_paper_metadata
    meta, book = inputs()
    accepted = _paper_execution_observation(
        "BTC", meta, book, 99999, 100001)
    with pytest.raises(ValueError):
        _verified_compact_paper_metadata(
            "ETH", meta, book, 99999, 100001, accepted)
    meta[0]["universe"][0]["maxLeverage"] = 2
    with pytest.raises(ValueError, match="CHANGED_ORIGINAL_EXECUTION_FACTS"):
        _verified_compact_paper_metadata(
            "BTC", meta, book, 99999, 100001, accepted)
