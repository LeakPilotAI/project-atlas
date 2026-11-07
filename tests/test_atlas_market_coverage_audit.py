from scripts.observation_runtime.atlas_market_coverage_audit import audit_coverage


def test_coverage_is_not_paper_authority():
    result = audit_coverage({"assets": [{"symbol": "MSFT", "asset_type": "STOCK"}, {"symbol": "SPY", "asset_type": "ETF"}]},
                            {"symbols": {"MSFT": {"research_lane": "QUALITY_DIPS"}, "ETH": {"research_lane": "UNCLASSIFIED"}}})
    assert result["configured_active_symbol_count"] == 2
    assert result["robinhood_discovery_symbol_count"] == 2
    assert result["configured_symbols_missing_from_discovery"] == 1
    assert not result["all_robinhood_markets_covered"]
    assert not result["paper_execution_eligible_from_discovery"]


def test_empty_inputs_do_not_invent_market_coverage():
    result = audit_coverage({}, {})
    assert result["configured_active_symbol_count"] == 0
    assert result["robinhood_discovery_symbol_count"] == 0
    assert not result["robinhood_us_brokerage_universe_complete"]
