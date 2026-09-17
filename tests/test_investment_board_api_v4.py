from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class FakeLadderStore:
    """API tests must never mutate backend/data/investment runtime state."""
    def sync(self, rows):
        return []
    def overlay(self, rows):
        out = []
        for row in rows:
            copy = dict(row)
            copy["accumulation_ladder"] = None
            copy["accumulation_status"] = {"state": "WAITING_FOR_FRESH_QUOTE" if copy.get("stance") == "ACCUMULATE" else "NOT_ACCUMULATING", "next_level": None, "pending_dm": 0}
            out.append(copy)
        return out


def _quote(symbol: str) -> dict:
    return {"symbol": symbol, "price": 300.0, "display_price": 300.0, "trigger_price": 300.05, "bid": 299.95, "ask": 300.05, "source": "robinhood_underlying_bid_ask", "session": "ROBINHOOD_MARKET_DATA", "market_state": "REGULAR", "effective_timestamp": "2026-09-13T20:00:00+00:00", "retrieved_at": "2026-09-13T20:01:00+00:00", "age_sec": 60.0, "quality": "LIVE", "fresh_for_display": True, "tradable_for_ladder": True, "is_live": True, "error": None}


def test_quality_dips_api_is_mounted_under_investment_domain(monkeypatch):
    async def fake_get_many(symbols, **kwargs):
        return {symbol: _quote(symbol) for symbol in symbols}
    async def fake_refresh_many(symbols):
        return None

    monkeypatch.setattr("app.api.investment_board.quality_dip_quote_service.get_many", fake_get_many)
    monkeypatch.setattr("app.api.investment_board.quality_dips_v2_target_cache.refresh_many", fake_refresh_many)
    monkeypatch.setattr("app.api.investment_board.accumulation_ladder_store", FakeLadderStore())
    r = client.get("/api/investments/quality-dips")
    assert r.status_code == 200
    data = r.json()
    assert data["domain"] == "EQUITY_INVESTMENT"
    assert data["execution"] == "MANUAL_ONLY"
    assert "board" in data
    assert "counts" in data
    assert data["quote_health"]["source"] == "robinhood_underlying+yfinance_fallback"
    assert "robinhood" in data["source"]
    assert data["accumulation_alerts"]["monitor_interval_sec"] == 30
    assert data["accumulation_alerts"]["levels"] == ["L1", "L2", "L3", "L4"]
    assert data["accumulation_alerts"]["level_pcts"] == [3.0, 5.0, 8.0, 12.0]
    assert "pending_dm" in data["accumulation_alerts"]
    assert data["accumulation_alerts"]["broker_execution"] is False
    assert data["quality_dips_v2"]["operational_repair"] == "V2_1_RUNTIME_EVIDENCE"


def test_quality_dips_view_is_stock_only_and_has_no_perp_api_calls():
    r = client.get("/api/investments/quality-dips/view")
    assert r.status_code == 200
    text = r.text
    assert "Quality Dips / Robinhood" in text
    assert "EQUITY INVESTMENT" in text
    assert "/api/investments/quality-dips" in text
    assert "/api/perps/" not in text
    assert "Hyperliquid" not in text
    assert "LIVE SUPPORTED PRICE" in text
    assert "LAST SUPPORTED PRICE" in text
    assert "DIP LEVEL HIT" in text
    assert "CHECK ROBINHOOD" in text
    assert "NEXT DIP LEVEL" in text
    assert "DISCORD DM PENDING" in text
    assert "L1-L4" in text
    assert "NO BROKER ORDERS" in text
