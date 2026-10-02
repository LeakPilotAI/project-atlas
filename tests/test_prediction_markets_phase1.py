from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.prediction.kalshi_public import (
    KalshiPublicMarketClient,
    PredictionProviderError,
    normalize_candlestick,
    normalize_market,
    normalize_orderbook,
)
from app.prediction.policy import is_multivariate_market, policy_snapshot
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
        "occurrence_datetime": "2026-10-03T00:00:00Z",
        "rules_primary": "Resolves yes if the stated condition occurs.",
        "rules_secondary": "",
        "exchange_index": 0,
        "is_provisional": False,
        "mve_collection_ticker": "",
        "mve_selected_legs": [],
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
    assert row["market_structure"]["single_market"] is True
    assert row["market_structure"]["multivariate"] is False
    assert row["timing"]["occurrence_datetime"] == "2026-10-03T00:00:00Z"


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
    assert captured["params"]["mve_filter"] == "exclude"
    assert payload["count"] == 1
    assert payload["cursor"] == "NEXT"
    assert payload["mode"] == "RESEARCH_ONLY"
    assert payload["execution"] == "DISABLED"
    assert payload["live_capital_allowed"] is False
    assert payload["automatic_real_money_execution"] is False
    assert payload["filters"]["mve_filter"] == "exclude"
    assert payload["policy"]["combos_allowed"] is False
    assert payload["policy"]["parlays_allowed"] is False
    assert payload["policy"]["stacking_allowed"] is False
    assert payload["policy"]["max_concurrent_prediction_positions"] == 1


def test_prediction_status_is_explicitly_research_only():
    payload = TestClient(app).get("/api/prediction/status").json()
    assert payload["provider"] == "kalshi"
    assert payload["provider_mode"] == "PUBLIC_MARKET_DATA_ONLY"
    assert payload["paper_ledger"] is False
    assert payload["executable_orderbook"] is True
    assert payload["historical_pre_event_prices"] is True
    assert payload["authenticated_provider_access"] is False
    assert payload["order_submission"] is False
    assert payload["portfolio_access"] is False
    assert payload["live_execution"] is False
    assert payload["live_capital_allowed"] is False
    assert payload["automatic_real_money_execution"] is False
    policy = payload["strategy_policy"]
    assert policy["single_market_only"] is True
    assert policy["max_concurrent_prediction_positions"] == 1
    assert policy["combos_allowed"] is False
    assert policy["parlays_allowed"] is False
    assert policy["multivariate_allowed"] is False
    assert policy["stacking_allowed"] is False
    assert policy["pre_event_only"] is True
    assert policy["must_exit_before_event_start"] is True
    assert policy["hold_through_event_start"] is False
    assert policy["hold_to_settlement"] is False


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


def test_multivariate_market_detection_uses_provider_metadata():
    single = sample_market()
    assert is_multivariate_market(single) is False

    combo = sample_market()
    combo["mve_collection_ticker"] = "KXMVE-COLLECTION"
    assert is_multivariate_market(combo) is True

    combo2 = sample_market()
    combo2["mve_selected_legs"] = [{"market_ticker": "LEG-1", "side": "yes"}]
    assert is_multivariate_market(combo2) is True


def test_market_discovery_drops_combo_rows_even_if_provider_returns_them(monkeypatch):
    client = KalshiPublicMarketClient()
    combo = sample_market()
    combo["ticker"] = "KXMVE-BLOCKED"
    combo["mve_collection_ticker"] = "KXMVE-COLLECTION"
    combo["mve_selected_legs"] = [{"market_ticker": "LEG-1", "side": "yes"}]

    async def fake_request(path, *, params=None):
        assert params["mve_filter"] == "exclude"
        return {"markets": [combo, sample_market()], "cursor": None}

    monkeypatch.setattr(client, "_request", fake_request)
    payload = asyncio.run(client.get_markets(status="open", limit=5))
    assert payload["count"] == 1
    assert payload["provider_rows_blocked_by_single_market_policy"] == 1
    assert payload["markets"][0]["ticker"] == "KXTEST-26OCT02-Y"


def test_market_detail_hard_blocks_multivariate_market(monkeypatch):
    client = KalshiPublicMarketClient()
    combo = sample_market()
    combo["mve_collection_ticker"] = "KXMVE-COLLECTION"

    async def fake_request(path, *, params=None):
        return {"market": combo}

    monkeypatch.setattr(client, "_request", fake_request)
    try:
        asyncio.run(client.get_market("KXMVE-BLOCKED"))
    except PredictionProviderError as exc:
        assert "single-market policy" in str(exc)
    else:
        raise AssertionError("combo market detail must be blocked")


def test_permanent_prediction_policy_is_single_market_pre_event_only():
    policy = policy_snapshot()
    assert policy["single_market_only"] is True
    assert policy["max_concurrent_prediction_positions"] == 1
    assert policy["combos_allowed"] is False
    assert policy["parlays_allowed"] is False
    assert policy["multivariate_allowed"] is False
    assert policy["stacking_allowed"] is False
    assert policy["pre_event_only"] is True
    assert policy["must_exit_before_event_start"] is True
    assert policy["hold_through_event_start"] is False
    assert policy["hold_to_settlement"] is False
    assert policy["live_execution"] is False


def test_orderbook_normalization_derives_executable_asks_from_opposite_bids():
    book = normalize_orderbook(
        {
            "orderbook_fp": {
                "yes_dollars": [["0.4200", "40.00"], ["0.4000", "10.00"]],
                "no_dollars": [["0.5600", "30.00"], ["0.5400", "20.00"]],
            }
        }
    )
    assert book["yes"]["best_bid_dollars"] == "0.4200"
    assert book["yes"]["best_ask_dollars"] == "0.4400"
    assert book["yes"]["spread_dollars"] == "0.0200"
    assert book["yes"]["asks"][0]["quantity_contracts"] == "30.00"
    assert book["no"]["best_bid_dollars"] == "0.5600"
    assert book["no"]["best_ask_dollars"] == "0.5800"
    assert book["no"]["spread_dollars"] == "0.0200"


def test_public_orderbook_read_is_single_market_and_depth_bounded(monkeypatch):
    client = KalshiPublicMarketClient()
    calls = []

    async def fake_request(path, *, params=None):
        calls.append((path, dict(params or {})))
        if path.endswith("/orderbook"):
            return {
                "orderbook_fp": {
                    "yes_dollars": [["0.4100", "25.00"]],
                    "no_dollars": [["0.5700", "30.00"]],
                }
            }
        return {"market": sample_market()}

    monkeypatch.setattr(client, "_request", fake_request)
    payload = asyncio.run(client.get_orderbook("KXTEST-26OCT02-Y", depth=999))
    assert calls[0][0] == "/markets/KXTEST-26OCT02-Y"
    assert calls[1] == ("/markets/KXTEST-26OCT02-Y/orderbook", {"depth": 100})
    assert payload["depth"] == 100
    assert payload["orderbook"]["yes"]["best_bid_dollars"] == "0.4100"
    assert payload["orderbook"]["yes"]["best_ask_dollars"] == "0.4300"
    assert payload["orderbook"]["yes"]["asks"][0]["quantity_contracts"] == "30.00"
    assert payload["execution"] == "DISABLED"
    assert payload["live_capital_allowed"] is False


def test_candlestick_normalization_preserves_bid_ask_and_activity():
    row = normalize_candlestick(
        {
            "end_period_ts": 123,
            "yes_bid": {
                "open_dollars": "0.4000",
                "low_dollars": "0.3900",
                "high_dollars": "0.4300",
                "close_dollars": "0.4200",
            },
            "yes_ask": {
                "open_dollars": "0.4300",
                "low_dollars": "0.4200",
                "high_dollars": "0.4500",
                "close_dollars": "0.4400",
            },
            "price": {
                "open_dollars": "0.4100",
                "low_dollars": "0.4000",
                "high_dollars": "0.4400",
                "close_dollars": "0.4300",
                "mean_dollars": "0.4250",
                "previous_dollars": "0.4050",
                "min_dollars": "0.4000",
                "max_dollars": "0.4400",
            },
            "volume_fp": "19.50",
            "open_interest_fp": "88.00",
        }
    )
    assert row["end_period_ts"] == 123
    assert row["yes_bid"]["close_dollars"] == "0.4200"
    assert row["yes_ask"]["close_dollars"] == "0.4400"
    assert row["price"]["mean_dollars"] == "0.4250"
    assert row["volume_contracts"] == "19.50"
    assert row["open_interest_contracts"] == "88.00"


def test_public_candlestick_read_is_bounded_and_single_market(monkeypatch):
    client = KalshiPublicMarketClient()
    calls = []

    async def fake_request(path, *, params=None):
        calls.append((path, dict(params or {})))
        if path.endswith("/candlesticks"):
            return {
                "ticker": "KXTEST-26OCT02-Y",
                "candlesticks": [
                    {
                        "end_period_ts": 200,
                        "yes_bid": {"close_dollars": "0.4300"},
                        "yes_ask": {"close_dollars": "0.4500"},
                        "price": {"close_dollars": "0.4400"},
                        "volume_fp": "2.00",
                        "open_interest_fp": "5.00",
                    },
                    {
                        "end_period_ts": 100,
                        "yes_bid": {"close_dollars": "0.4100"},
                        "yes_ask": {"close_dollars": "0.4300"},
                        "price": {"close_dollars": "0.4200"},
                        "volume_fp": "1.00",
                        "open_interest_fp": "4.00",
                    },
                ],
            }
        return {"market": sample_market()}

    monkeypatch.setattr(client, "_request", fake_request)
    start = 1_700_000_000
    end = start + 60 * 60 * 24
    payload = asyncio.run(
        client.get_candlesticks(
            series_ticker="KXTEST",
            ticker="KXTEST-26OCT02-Y",
            start_ts=start,
            end_ts=end,
            period_interval=60,
            include_latest_before_start=True,
        )
    )
    assert calls[0][0] == "/markets/KXTEST-26OCT02-Y"
    assert calls[1][0] == "/series/KXTEST/markets/KXTEST-26OCT02-Y/candlesticks"
    assert calls[1][1]["period_interval"] == 60
    assert calls[1][1]["include_latest_before_start"] is True
    assert payload["count"] == 2
    assert [row["end_period_ts"] for row in payload["candlesticks"]] == [100, 200]
    assert payload["candlesticks"][0]["yes_ask"]["close_dollars"] == "0.4300"


def test_public_candlestick_read_rejects_unbounded_window():
    client = KalshiPublicMarketClient()
    start = 1_700_000_000
    try:
        asyncio.run(
            client.get_candlesticks(
                series_ticker="KXTEST",
                ticker="KXTEST-26OCT02-Y",
                start_ts=start,
                end_ts=start + (60 * 60 * 1001),
                period_interval=60,
            )
        )
    except ValueError as exc:
        assert "bounded window" in str(exc)
    else:
        raise AssertionError("oversized candlestick range must be rejected")


def test_prediction_orderbook_route_uses_read_only_provider(monkeypatch):
    async def fake_orderbook(ticker, *, depth=20):
        return {
            "provider": "kalshi",
            "mode": "RESEARCH_ONLY",
            "execution": "DISABLED",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "ticker": ticker,
            "depth": depth,
            "orderbook": {"yes": {"best_bid_dollars": "0.4100", "best_ask_dollars": "0.4300"}},
        }

    monkeypatch.setattr(prediction_api.kalshi_public, "get_orderbook", fake_orderbook)
    response = TestClient(app).get("/api/prediction/markets/KXTEST-26OCT02-Y/orderbook?depth=25")
    assert response.status_code == 200
    payload = response.json()
    assert payload["depth"] == 25
    assert payload["orderbook"]["yes"]["best_ask_dollars"] == "0.4300"


def test_prediction_candlestick_route_uses_read_only_provider(monkeypatch):
    async def fake_candles(**kwargs):
        return {
            "provider": "kalshi",
            "mode": "RESEARCH_ONLY",
            "execution": "DISABLED",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "series_ticker": kwargs["series_ticker"],
            "ticker": kwargs["ticker"],
            "period_interval_minutes": kwargs["period_interval"],
            "count": 1,
            "candlesticks": [{"end_period_ts": kwargs["end_ts"], "yes_bid": {}, "yes_ask": {}}],
        }

    monkeypatch.setattr(prediction_api.kalshi_public, "get_candlesticks", fake_candles)
    response = TestClient(app).get(
        "/api/prediction/markets/KXTEST-26OCT02-Y/candlesticks"
        "?series_ticker=KXTEST&start_ts=1700000000&end_ts=1700003600&period_interval=60"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["series_ticker"] == "KXTEST"
    assert payload["ticker"] == "KXTEST-26OCT02-Y"
    assert payload["count"] == 1


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
