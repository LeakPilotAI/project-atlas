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
