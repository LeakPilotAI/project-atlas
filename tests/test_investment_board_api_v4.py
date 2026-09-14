from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _quote(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "price": 300.0,
        "display_price": 300.0,
        "source": "yfinance_1m",
        "session": "REGULAR",
        "market_state": "REGULAR",
        "effective_timestamp": "2026-09-13T20:00:00+00:00",
        "retrieved_at": "2026-09-13T20:01:00+00:00",
        "age_sec": 60.0,
        "quality": "LIVE",
        "fresh_for_display": True,
        "tradable_for_ladder": True,
        "is_live": True,
        "error": None,
    }


def test_quality_dips_api_is_mounted_under_investment_domain(monkeypatch):
    async def fake_get_many(symbols, **kwargs):
        return {symbol: _quote(symbol) for symbol in symbols}

    monkeypatch.setattr("app.api.investment_board.quality_dip_quote_service.get_many", fake_get_many)
    r = client.get("/api/investments/quality-dips")
    assert r.status_code == 200
    data = r.json()
    assert data["domain"] == "EQUITY_INVESTMENT"
    assert data["execution"] == "MANUAL_ONLY"
    assert "board" in data
    assert "counts" in data
    assert data["quote_health"]["source"] == "yfinance_1m+quote_fields"
    assert "yfinance_intraday_quote_overlay" in data["source"]
    assert data["accumulation_alerts"]["monitor_interval_sec"] == 30
    assert data["accumulation_alerts"]["levels"] == ["L1", "L2", "L3", "L4"]
    assert "pending_dm" in data["accumulation_alerts"]
    assert data["accumulation_alerts"]["broker_execution"] is False


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
    assert "DIP LEVEL HIT — CHECK ROBINHOOD" in text
    assert "NEXT DIP LEVEL" in text
    assert "DISCORD DM PENDING" in text
    assert "L1-L4" in text
    assert "NO BROKER ORDERS" in text
