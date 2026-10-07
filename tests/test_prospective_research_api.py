from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.prospective_research import router
from app.investment.etf_local_research import local_etf_report
from app.investment.bars import OhlcvBar


def test_compound_endpoint_and_report_page():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post(
            "/api/investments/prospective/compound",
            json={
                "starting_capital": 100,
                "contribution": 0,
                "years": 1,
                "price_growth": -0.1,
            },
        )
        assert response.status_code == 200
        assert round(response.json()["total_wealth"], 2) == 90
        assert client.get("/api/investments/prospective/view").status_code == 200
        assert (
            client.post(
                "/api/investments/prospective/compound",
                json={
                    "starting_capital": 100,
                    "contribution": 0,
                    "years": 1,
                    "price_growth": -0.1,
                    "contributions_per_year": 999,
                },
            ).status_code
            == 422
        )


def test_local_etf_data_preserves_missing_distributions_and_expenses():
    bars = [
        OhlcvBar("2026-01-01", close=100, adjusted_close=100),
        OhlcvBar("2026-01-02", close=95, adjusted_close=96),
    ]
    report = local_etf_report({}, lambda _: bars, symbols=["ETF"])[0]
    assert report["return_components"]["TOTAL_RETURN"] < 0
    assert report["return_components"]["DISTRIBUTION_RETURN"] is None
    assert report["metrics"]["expense_ratio"]["status"] == "UNKNOWN"
