from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.prediction.kalshi_public import KalshiPublicMarketClient, normalize_market
import app.api.prediction as prediction_api


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "backend" / "app" / "prediction" / "kalshi_public.py"


def sample_market():
    return {
        "ticker": "KXTEST-26OCT02-Y",
        "event_ticker": "KXTEST-26OCT02",
        "market_type": "binary",
        "title": "Will the test condition resolve yes?",
        "subtitle": "Test market",
        "yes_sub_title": "Yes",
        "no_sub_title": "No",
        "status": "open",
        "yes_bid_dollars": "0.4100",
        "yes_ask_dollars": "0.4300",
        "no_bid_dollars": "0.5700",
        "no_ask_dollars": "0.5900",
        "last_price_dollars": "0.4200",
        "previous_price_dollars": "0.4000",
        "volume_fp": "125.50",
        "volume_24h_fp": "50.25",
        "open_interest_fp": "88.00",
        "liquidity_dollars": "512.3400",
        "created_time": "2026-10-01T00:00:00Z",
        "updated_time": "2026-10-02T00:00:00Z",
        "open_time": "2026-10-01T00:00:00Z",
        "close_time": "2026-10-03T00:00:00Z",
        "rules_primary": "Resolves yes if the stated condition occurs.",
        "rules_secondary": "",
        "exchange_index": 0,
        "is_provisional": False,
    }


def test_normalize_market_preserves_public_fixed_point_fields():
    row = normalize_market(sample_market())
    assert row["provider"] == "kalshi"
    assert row["ticker"] == "KXTEST-26OCT02-Y"
    assert row["prices"]["yes_bid_dollars"] == "0.4100"
    assert row["prices"]["yes_ask_dollars"] == "0.4300"
    assert row["prices"]["yes_mid_dollars"] == "0.4200"
    assert row["activity"]["volume_contracts"] == "125.50"
    assert row["activity"]["liquidity_dollars"] == "512.3400"
    assert row["rules"]["primary"].startswith("Resolves yes")


def test_public_client_market_discovery_is_bounded_and_normalized(monkeypatch):
    client = KalshiPublicMarketClient()
    captured = {}

    async def fake_request(path, *, params=None):
        captured["path"] = path
        captured["params"] = dict(params or {})
        return {"markets": [sample_market()], "cursor": "NEXT"}

    monkeypatch.setattr(client, "_request", fake_request)
    payload = asyncio.run(
        client.get_markets(
            status="open",
            limit=999,
            series_ticker="KXTEST",
            event_ticker=None,
        )
    )

    assert captured["path"] == "/markets"
    assert captured["params"]["status"] == "open"
    assert captured["params"]["limit"] == 200
    assert captured["params"]["series_ticker"] == "KXTEST"
    assert payload["count"] == 1
    assert payload["cursor"] == "NEXT"
    assert payload["mode"] == "RESEARCH_ONLY"
    assert payload["execution"] == "DISABLED"
    assert payload["live_capital_allowed"] is False
    assert payload["automatic_real_money_execution"] is False


def test_prediction_status_is_explicitly_research_only():
    payload = TestClient(app).get("/api/prediction/status").json()
    assert payload["provider"] == "kalshi"
    assert payload["provider_mode"] == "PUBLIC_MARKET_DATA_ONLY"
    assert payload["paper_ledger"] is False
    assert payload["authenticated_provider_access"] is False
    assert payload["order_submission"] is False
    assert payload["portfolio_access"] is False
    assert payload["live_execution"] is False
    assert payload["live_capital_allowed"] is False
    assert payload["automatic_real_money_execution"] is False


def test_prediction_markets_route_uses_read_only_provider(monkeypatch):
    async def fake_markets(**kwargs):
        return {
            "provider": "kalshi",
            "mode": "RESEARCH_ONLY",
            "execution": "DISABLED",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "count": 1,
            "cursor": None,
            "filters": kwargs,
            "markets": [normalize_market(sample_market())],
        }

    monkeypatch.setattr(prediction_api.kalshi_public, "get_markets", fake_markets)
    response = TestClient(app).get(
        "/api/prediction/markets?status=open&limit=8&series_ticker=kxtest"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["filters"]["series_ticker"] == "KXTEST"
    assert payload["markets"][0]["ticker"] == "KXTEST-26OCT02-Y"


def test_prediction_market_detail_route_is_read_only(monkeypatch):
    async def fake_market(ticker):
        assert ticker == "KXTEST-26OCT02-Y"
        return {
            "provider": "kalshi",
            "mode": "RESEARCH_ONLY",
            "execution": "DISABLED",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "market": normalize_market(sample_market()),
        }

    monkeypatch.setattr(prediction_api.kalshi_public, "get_market", fake_market)
    response = TestClient(app).get("/api/prediction/markets/kxtest-26oct02-y")
    assert response.status_code == 200
    assert response.json()["market"]["ticker"] == "KXTEST-26OCT02-Y"


def test_prediction_routes_reject_invalid_status_and_ticker():
    client = TestClient(app)
    assert client.get("/api/prediction/markets?status=trading").status_code == 400
    assert client.get("/api/prediction/markets/not%20safe").status_code == 400


def test_prediction_phase_one_contains_no_authenticated_or_order_surface():
    source = SOURCE.read_text(encoding="utf-8")
    assert "KALSHI-ACCESS-KEY" not in source
    assert "/orders" not in source
    assert "/portfolio" not in source

    for route in app.routes:
        path = getattr(route, "path", "")
        if path.startswith("/api/prediction"):
            methods = set(getattr(route, "methods", set()) or set())
            assert methods <= {"GET", "HEAD"}
