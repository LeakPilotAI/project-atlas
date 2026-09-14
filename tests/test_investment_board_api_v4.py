from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _quote(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "price": 300.0,
        "source": "yfinance",
        "session": "REGULAR",
        "market_state": "CLOSED",
        "effective_timestamp": "2026-09-13T20:00:00+00:00",
        "retrieved_at": "2026-09-13T20:01:00+00:00",
        "age_sec": 60.0,
        "quality": "FRESH",
        "fresh_for_display": True,
        "error": None,
    }


def test_quality_dips_api_is_mounted_under_investment_domain(monkeypatch):
    async def fake_get_many(symbols):
        return {symbol: _quote(symbol) for symbol in symbols}

    monkeypatch.setattr("app.api.investment_board.quality_dip_quote_service.get_many", fake_get_many)
    r = client.get("/api/investments/quality-dips")
    assert r.status_code == 200
    data = r.json()
    assert data["domain"] == "EQUITY_INVESTMENT"
    assert data["execution"] == "MANUAL_ONLY"
    assert "board" in data
    assert "counts" in data
    assert data["quote_health"]["source"] == "yfinance"
    assert "yfinance_quote_overlay" in data["source"]
    assert data["accumulation_alerts"]["monitor_interval_sec"] == 60
    assert data["accumulation_alerts"]["levels"] == ["L1", "L2", "L3", "L4"]
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
    assert "LATEST QUOTE" in text
    assert "research snapshot" in text
    assert "quote_quality" in text
    assert "quote_session" in text
    assert "AUTO DIP ALERT LADDER" in text
    assert "L1-L4" in text
    assert "does not place" not in text or "manually" in text
