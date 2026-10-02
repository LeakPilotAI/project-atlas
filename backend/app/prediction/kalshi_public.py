"""Read-only Kalshi public market-data client for Atlas prediction research.

Kalshi's public Trade API exposes unauthenticated market-data reads.  Atlas uses
only those public GET surfaces in this module.  There are deliberately no API-key
fields, authenticated portfolio calls, order methods, or write endpoints.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
ALLOWED_STATUSES = {"unopened", "open", "paused", "closed", "settled"}


class PredictionProviderError(RuntimeError):
    """Raised when a read-only prediction-market provider request fails."""


def _fixed(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        return format(Decimal(str(value)), "f")
    except (InvalidOperation, ValueError, TypeError):
        return None


def _midpoint(bid: Any, ask: Any) -> str | None:
    try:
        b = Decimal(str(bid))
        a = Decimal(str(ask))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if b < 0 or a < 0 or a < b:
        return None
    return format((a + b) / Decimal("2"), "f")


def normalize_market(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize public Kalshi market metadata without inventing missing values."""
    yes_bid = _fixed(row.get("yes_bid_dollars"))
    yes_ask = _fixed(row.get("yes_ask_dollars"))
    return {
        "provider": "kalshi",
        "ticker": str(row.get("ticker") or ""),
        "event_ticker": str(row.get("event_ticker") or ""),
        "market_type": str(row.get("market_type") or ""),
        "title": str(row.get("title") or ""),
        "subtitle": str(row.get("subtitle") or ""),
        "yes_sub_title": str(row.get("yes_sub_title") or ""),
        "no_sub_title": str(row.get("no_sub_title") or ""),
        "status": str(row.get("status") or ""),
        "result": str(row.get("result") or "") or None,
        "prices": {
            "yes_bid_dollars": yes_bid,
            "yes_ask_dollars": yes_ask,
            "yes_mid_dollars": _midpoint(yes_bid, yes_ask),
            "no_bid_dollars": _fixed(row.get("no_bid_dollars")),
            "no_ask_dollars": _fixed(row.get("no_ask_dollars")),
            "last_dollars": _fixed(row.get("last_price_dollars")),
            "previous_dollars": _fixed(row.get("previous_price_dollars")),
        },
        "activity": {
            "volume_contracts": _fixed(row.get("volume_fp")),
            "volume_24h_contracts": _fixed(row.get("volume_24h_fp")),
            "open_interest_contracts": _fixed(row.get("open_interest_fp")),
            "liquidity_dollars": _fixed(row.get("liquidity_dollars")),
        },
        "timing": {
            "created_time": row.get("created_time"),
            "updated_time": row.get("updated_time"),
            "open_time": row.get("open_time"),
            "close_time": row.get("close_time"),
            "expected_expiration_time": row.get("expected_expiration_time"),
            "expiration_time": row.get("expiration_time"),
            "settlement_ts": row.get("settlement_ts"),
        },
        "settlement": {
            "can_close_early": row.get("can_close_early"),
            "early_close_condition": row.get("early_close_condition"),
            "expiration_value": row.get("expiration_value"),
            "settlement_value_dollars": _fixed(row.get("settlement_value_dollars")),
        },
        "rules": {
            "primary": row.get("rules_primary"),
            "secondary": row.get("rules_secondary"),
        },
        "exchange_index": row.get("exchange_index"),
        "is_provisional": row.get("is_provisional"),
    }


class KalshiPublicMarketClient:
    """Bounded unauthenticated GET-only market discovery client."""

    async def _request(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=BASE_URL,
                timeout=httpx.Timeout(8.0, connect=4.0),
                headers={"Accept": "application/json", "User-Agent": "Project-Atlas/0.1 read-only"},
            ) as client:
                response = await client.get(path, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PredictionProviderError("Kalshi public market-data request failed") from exc
        if not isinstance(payload, dict):
            raise PredictionProviderError("Kalshi public market-data response was not an object")
        return payload

    async def get_markets(
        self,
        *,
        status: str = "open",
        limit: int = 50,
        cursor: str | None = None,
        series_ticker: str | None = None,
        event_ticker: str | None = None,
    ) -> dict[str, Any]:
        clean_status = str(status or "").lower().strip()
        if clean_status and clean_status not in ALLOWED_STATUSES:
            raise ValueError("unsupported Kalshi market status")
        params: dict[str, Any] = {"limit": max(1, min(int(limit), 200))}
        if clean_status:
            params["status"] = clean_status
        if cursor:
            params["cursor"] = cursor
        if series_ticker:
            params["series_ticker"] = series_ticker
        if event_ticker:
            params["event_ticker"] = event_ticker

        payload = await self._request("/markets", params=params)
        rows = payload.get("markets")
        markets = [normalize_market(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        return {
            "provider": "kalshi",
            "provider_endpoint": "/markets",
            "mode": "RESEARCH_ONLY",
            "authentication": "NOT_REQUIRED_FOR_PUBLIC_MARKET_DATA",
            "execution": "DISABLED",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "count": len(markets),
            "cursor": str(payload.get("cursor") or "") or None,
            "filters": {
                "status": clean_status or None,
                "limit": params["limit"],
                "series_ticker": series_ticker,
                "event_ticker": event_ticker,
            },
            "markets": markets,
        }

    async def get_market(self, ticker: str) -> dict[str, Any]:
        payload = await self._request(f"/markets/{ticker}")
        row = payload.get("market")
        if not isinstance(row, dict):
            raise PredictionProviderError("Kalshi market response did not contain a market")
        return {
            "provider": "kalshi",
            "provider_endpoint": "/markets/{ticker}",
            "mode": "RESEARCH_ONLY",
            "authentication": "NOT_REQUIRED_FOR_PUBLIC_MARKET_DATA",
            "execution": "DISABLED",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "market": normalize_market(row),
        }


kalshi_public = KalshiPublicMarketClient()
