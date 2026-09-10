from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_quality_dips_api_is_mounted_under_investment_domain():
    r = client.get("/api/investments/quality-dips")
    assert r.status_code == 200
    data = r.json()
    assert data["domain"] == "EQUITY_INVESTMENT"
    assert data["execution"] == "MANUAL_ONLY"
    assert "board" in data
    assert "counts" in data


def test_quality_dips_view_is_stock_only_and_has_no_perp_api_calls():
    r = client.get("/api/investments/quality-dips/view")
    assert r.status_code == 200
    text = r.text
    assert "Quality Dips / Robinhood" in text
    assert "EQUITY INVESTMENT" in text
    assert "/api/investments/quality-dips" in text
    assert "/api/perps/" not in text
    assert "Hyperliquid" not in text
    assert "Atlas places no" not in text or "No orders are placed" in text
