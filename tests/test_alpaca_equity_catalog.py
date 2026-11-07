import pytest
from scripts.observation_runtime.alpaca_equity_catalog import summarize_catalog


def test_broad_catalog_remains_readonly_and_not_robinhood_proof():
    result = summarize_catalog([{"class": "us_equity", "symbol": "MSFT", "status": "active", "tradable": True},
                                {"class": "us_equity", "symbol": "SPY", "status": "inactive", "tradable": False}])
    assert result["catalog_records"] == 2
    assert result["provider_active_tradable_records"] == 1
    assert not result["robinhood_us_brokerage_coverage_verified"]
    assert not result["paper_execution_authorized"]


@pytest.mark.parametrize("payload", [{"assets": []}, [{"class": "crypto", "symbol": "BTC"}],
                                      [{"class": "us_equity", "symbol": "A"}] * 2])
def test_refuse_wrong_catalog(payload):
    with pytest.raises(ValueError):
        summarize_catalog(payload)


def test_durable_provider_scope_and_rotating_batches():
    from scripts.observation_runtime.alpaca_equity_catalog import inventory_snapshot, rotating_batch
    payload = [{"class": "us_equity", "symbol": s, "status": "active", "tradable": True} for s in ("C", "A", "B")]
    snapshot = inventory_snapshot(payload, captured_at="2026-11-07T00:00:00+00:00")
    assert rotating_batch(snapshot, offset=0, limit=2) == ["A", "B"]
    assert rotating_batch(snapshot, offset=2, limit=2) == ["C", "A"]
    assert not snapshot["paper_execution_authorized"]
    snapshot["rows"][0]["symbol"] = "FAKE"
    with pytest.raises(ValueError, match="DIGEST"):
        rotating_batch(snapshot, offset=0)


def test_research_batch_rejects_arbitrary_paths():
    from scripts.observation_runtime.alpaca_equity_catalog import next_research_batch
    with pytest.raises(ValueError, match="PATH_REFUSED"):
        next_research_batch("somewhere.json", "cursor.json")


def test_broad_market_routes_all_equity_strategies_not_perps():
    from scripts.observation_runtime.alpaca_equity_catalog import research_route_plan
    batch = {"schema": "ATLAS_ALPACA_RESEARCH_BATCH_V1", "market": "US_EQUITY",
             "paper_execution_authorized": False, "hyperliquid_perpetuals_included": False,
             "symbols": ["MSFT", "SPY"]}
    plan = research_route_plan(batch, known_etf_symbols=("SPY",))
    assert len(plan["routes"]) == 2
    assert plan["routes"][0]["asset_type"] == "UNCLASSIFIED_EQUITY"
    assert plan["routes"][1]["asset_type"] == "ETF"
    assert "LONG_TERM_INVESTMENT" in plan["routes"][0]["research_lanes"]
    assert "DAY_TRADE_RESEARCH" in plan["routes"][0]["research_lanes"]
    assert not plan["hyperliquid_perpetuals_included"]
    assert all(not r["paper_eligible"] for r in plan["routes"])
    batch["hyperliquid_perpetuals_included"] = True
    with pytest.raises(ValueError, match="SCOPE"):
        research_route_plan(batch)


def test_completion_rejects_missing_receipts_without_cursor_write():
    from scripts.observation_runtime.alpaca_equity_catalog import complete_research_batch
    batch = {"schema": "ATLAS_ALPACA_RESEARCH_BATCH_V1", "offset": 0, "next_offset": 2,
             "symbols": ["A", "AA"], "paper_execution_authorized": False,
             "hyperliquid_perpetuals_included": False}
    from scripts.observation_runtime.alpaca_equity_catalog import REPO
    cursor = REPO / "logs" / "research" / "alpaca_equity_cursor.json"
    with pytest.raises(ValueError, match="INCOMPLETE"):
        complete_research_batch(batch, [{"symbol": "A", "status": "RESEARCH_COMPLETE", "paper_eligible": False}], cursor)
