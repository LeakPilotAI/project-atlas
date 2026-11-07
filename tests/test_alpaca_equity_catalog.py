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


def test_bounded_provider_worker_rejects_large_batch():
    from scripts.observation_runtime.alpaca_equity_catalog import run_bounded_provider_research
    with pytest.raises(ValueError, match="BUDGET"):
        run_bounded_provider_research(contact="not-configured", limit=9)


def test_worker_success_does_not_advance_before_strategy_scoring(tmp_path, monkeypatch):
    import json
    from scripts.observation_runtime import alpaca_equity_catalog as mod
    monkeypatch.setattr(mod, "REPO", tmp_path)
    root = tmp_path / "logs" / "research"
    root.mkdir(parents=True)
    snapshot = mod.inventory_snapshot([{"class": "us_equity", "symbol": s, "status": "active", "tradable": True}
                                       for s in ("MSFT", "AVGO")], captured_at="2026-11-07T00:00:00+00:00")
    (root / "alpaca_equity_inventory.json").write_text(json.dumps(snapshot), encoding="utf-8")
    called = []
    def provider(**kwargs):
        called.append(kwargs["symbol"])
        return {"symbol": kwargs["symbol"], "provider_receipt_count": 2,
                "paper_fill_authorized": False, "live_order_authorized": False}
    result = mod.run_bounded_provider_research(contact="test-contact", limit=2, provider=provider)
    assert result["batch_complete"] and not result["cursor_advanced"]
    assert called == ["AVGO", "MSFT"]
    assert not (root / "alpaca_equity_cursor.json").exists()
    assert not result["paper_execution_authorized"]


def test_worker_failed_provider_never_advances_cursor(tmp_path, monkeypatch):
    import json
    from scripts.observation_runtime import alpaca_equity_catalog as mod
    monkeypatch.setattr(mod, "REPO", tmp_path)
    root = tmp_path / "logs" / "research"
    root.mkdir(parents=True)
    snapshot = mod.inventory_snapshot([{"class": "us_equity", "symbol": "MSFT", "status": "active", "tradable": True}],
                                      captured_at="2026-11-07T00:00:00+00:00")
    (root / "alpaca_equity_inventory.json").write_text(json.dumps(snapshot), encoding="utf-8")
    def provider(**kwargs):
        raise ValueError("PROVIDER_DOWN")
    result = mod.run_bounded_provider_research(contact="test-contact", limit=1, provider=provider)
    assert not result["batch_complete"] and not result["cursor_advanced"]
    assert result["outcomes"][0]["status"] == "RESEARCH_BLOCKED"
    assert not (root / "alpaca_equity_cursor.json").exists()


def test_score_bundle_refuses_unverified_source():
    from scripts.observation_runtime.alpaca_equity_catalog import score_research_bundle
    with pytest.raises(ValueError, match="INPUT_REFUSED"):
        score_research_bundle(symbol="MSFT", data={"paper_eligible": True})


def test_scored_pipeline_success_and_failure_keep_cursor(tmp_path, monkeypatch):
    import json
    from scripts.observation_runtime import alpaca_equity_catalog as mod
    monkeypatch.setattr(mod, "REPO", tmp_path)
    root = tmp_path / "logs" / "research"
    root.mkdir(parents=True)
    snapshot = mod.inventory_snapshot([{"class": "us_equity", "symbol": s, "status": "active", "tradable": True}
                                       for s in ("MSFT", "AVGO")], captured_at="2026-11-07T00:00:00+00:00")
    (root / "alpaca_equity_inventory.json").write_text(json.dumps(snapshot), encoding="utf-8")
    def scorer(*, symbol, data):
        return {"symbol": symbol, "status": "RESEARCH_SCORED", "paper_eligible": False,
                "live_order_authorized": False, "research_lane": "FRONTIER_RESEARCH"}
    ok = mod.score_bounded_research_batch(limit=2, acquire=lambda symbol: {"symbol": symbol}, scorer=scorer)
    assert ok["scoring_complete"] and len(ok["results"]) == 2
    assert not ok["cursor_advanced"] and not (root / "alpaca_equity_cursor.json").exists()
    def fail(symbol):
        raise OSError("provider down")
    blocked = mod.score_bounded_research_batch(limit=2, acquire=fail, scorer=scorer)
    assert not blocked["scoring_complete"] and blocked["results"][0]["status"] == "RESEARCH_BLOCKED"
    assert not (root / "alpaca_equity_cursor.json").exists()
