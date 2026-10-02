"""Read-only Kalshi public market-data client for Atlas prediction research.

Kalshi's public Trade API exposes unauthenticated market-data reads.  Atlas uses
only those public GET surfaces in this module.  There are deliberately no API-key
fields, authenticated portfolio calls, order methods, or write endpoints.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.prediction.policy import is_multivariate_market, policy_snapshot

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
ALLOWED_STATUSES = {"unopened", "open", "paused", "closed", "settled"}
ALLOWED_CANDLE_INTERVALS = {1, 60, 1440}
MAX_CANDLE_POINTS = 1000


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


def _spread(bid: Any, ask: Any) -> str | None:
    try:
        b = Decimal(str(bid))
        a = Decimal(str(ask))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if b < 0 or a < b:
        return None
    return format(a - b, "f")


def _complement(price: Any) -> str | None:
    try:
        p = Decimal(str(price))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if p < 0 or p > 1:
        return None
    return format(Decimal("1") - p, "f")


def _normalize_bid_levels(levels: Any) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    if not isinstance(levels, list):
        return cleaned
    for level in levels:
        if not isinstance(level, (list, tuple)) or len(level) < 2:
            continue
        price = _fixed(level[0])
        quantity = _fixed(level[1])
        if price is None or quantity is None:
            continue
        try:
            p = Decimal(price)
            q = Decimal(quantity)
        except InvalidOperation:
            continue
        if p < 0 or p > 1 or q < 0:
            continue
        cleaned.append({"price_dollars": price, "quantity_contracts": quantity})
    cleaned.sort(key=lambda row: Decimal(row["price_dollars"]), reverse=True)
    return cleaned


def _implied_ask_levels(opposite_bids: list[dict[str, str]]) -> list[dict[str, str]]:
    asks = []
    for row in opposite_bids:
        price = _complement(row.get("price_dollars"))
        if price is None:
            continue
        asks.append(
            {
                "price_dollars": price,
                "quantity_contracts": str(row.get("quantity_contracts") or "0"),
            }
        )
    asks.sort(key=lambda row: Decimal(row["price_dollars"]))
    return asks


def normalize_orderbook(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("orderbook_fp")
    raw = raw if isinstance(raw, dict) else {}
    yes_bids = _normalize_bid_levels(raw.get("yes_dollars"))
    no_bids = _normalize_bid_levels(raw.get("no_dollars"))
    yes_asks = _implied_ask_levels(no_bids)
    no_asks = _implied_ask_levels(yes_bids)

    best_yes_bid = yes_bids[0]["price_dollars"] if yes_bids else None
    best_yes_ask = yes_asks[0]["price_dollars"] if yes_asks else None
    best_no_bid = no_bids[0]["price_dollars"] if no_bids else None
    best_no_ask = no_asks[0]["price_dollars"] if no_asks else None

    return {
        "yes": {
            "bids": yes_bids,
            "asks": yes_asks,
            "best_bid_dollars": best_yes_bid,
            "best_ask_dollars": best_yes_ask,
            "spread_dollars": _spread(best_yes_bid, best_yes_ask),
        },
        "no": {
            "bids": no_bids,
            "asks": no_asks,
            "best_bid_dollars": best_no_bid,
            "best_ask_dollars": best_no_ask,
            "spread_dollars": _spread(best_no_bid, best_no_ask),
        },
        "derivation": (
            "Kalshi public orderbook returns YES and NO bids only. Atlas derives each side's "
            "ask from 1.0000 minus the opposite side bid at identical size."
        ),
    }


def _normalize_price_bar(value: Any) -> dict[str, str | None]:
    row = value if isinstance(value, dict) else {}
    return {
        "open_dollars": _fixed(row.get("open_dollars")),
        "low_dollars": _fixed(row.get("low_dollars")),
        "high_dollars": _fixed(row.get("high_dollars")),
        "close_dollars": _fixed(row.get("close_dollars")),
    }


def normalize_candlestick(row: dict[str, Any]) -> dict[str, Any]:
    price = row.get("price") if isinstance(row.get("price"), dict) else {}
    normalized_price = _normalize_price_bar(price)
    normalized_price.update(
        {
            "mean_dollars": _fixed(price.get("mean_dollars")),
            "previous_dollars": _fixed(price.get("previous_dollars")),
            "min_dollars": _fixed(price.get("min_dollars")),
            "max_dollars": _fixed(price.get("max_dollars")),
        }
    )
    return {
        "end_period_ts": int(row.get("end_period_ts") or 0),
        "yes_bid": _normalize_price_bar(row.get("yes_bid")),
        "yes_ask": _normalize_price_bar(row.get("yes_ask")),
        "price": normalized_price,
        "volume_contracts": _fixed(row.get("volume_fp")),
        "open_interest_contracts": _fixed(row.get("open_interest_fp")),
    }


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
            "occurrence_datetime": row.get("occurrence_datetime"),
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
        "market_structure": {
            "single_market": not is_multivariate_market(row),
            "multivariate": is_multivariate_market(row),
        },
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
        params: dict[str, Any] = {
            "limit": max(1, min(int(limit), 200)),
            # Permanent Atlas policy: provider-side combo exclusion.
            "mve_filter": "exclude",
        }
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
        raw_rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        # Defense in depth: even if provider filtering regresses, Atlas never surfaces
        # a multivariate/combo market into the prediction research lane.
        single_rows = [row for row in raw_rows if not is_multivariate_market(row)]
        markets = [normalize_market(row) for row in single_rows]
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
                "mve_filter": "exclude",
            },
            "policy": policy_snapshot(),
            "provider_rows_blocked_by_single_market_policy": len(raw_rows) - len(single_rows),
            "markets": markets,
        }

    async def get_market(self, ticker: str) -> dict[str, Any]:
        payload = await self._request(f"/markets/{ticker}")
        row = payload.get("market")
        if not isinstance(row, dict):
            raise PredictionProviderError("Kalshi market response did not contain a market")
        if is_multivariate_market(row):
            raise PredictionProviderError(
                "Kalshi market blocked by Atlas permanent single-market policy"
            )
        return {
            "provider": "kalshi",
            "provider_endpoint": "/markets/{ticker}",
            "mode": "RESEARCH_ONLY",
            "authentication": "NOT_REQUIRED_FOR_PUBLIC_MARKET_DATA",
            "execution": "DISABLED",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "policy": policy_snapshot(),
            "market": normalize_market(row),
        }


    async def get_orderbook(self, ticker: str, *, depth: int = 20) -> dict[str, Any]:
        """Return executable public depth for one permitted single market.

        The provider returns YES and NO bids. Atlas derives executable asks from the
        opposite-side bids and preserves quantities for realistic PAPER fill modeling.
        """
        clean_depth = max(0, min(int(depth), 100))
        market_payload = await self.get_market(ticker)
        payload = await self._request(
            f"/markets/{ticker}/orderbook",
            params={"depth": clean_depth},
        )
        return {
            "provider": "kalshi",
            "provider_endpoint": "/markets/{ticker}/orderbook",
            "mode": "RESEARCH_ONLY",
            "execution": "DISABLED",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "ticker": ticker,
            "depth": clean_depth,
            "policy": policy_snapshot(),
            "market": market_payload["market"],
            "orderbook": normalize_orderbook(payload),
        }

    async def get_candlesticks(
        self,
        *,
        series_ticker: str,
        ticker: str,
        start_ts: int,
        end_ts: int,
        period_interval: int = 60,
        include_latest_before_start: bool = False,
    ) -> dict[str, Any]:
        """Return bounded public price history for pre-event research."""
        interval = int(period_interval)
        if interval not in ALLOWED_CANDLE_INTERVALS:
            raise ValueError("unsupported Kalshi candlestick interval")
        start = int(start_ts)
        end = int(end_ts)
        if start <= 0 or end <= start:
            raise ValueError("invalid Kalshi candlestick time range")
        max_seconds = interval * 60 * MAX_CANDLE_POINTS
        if end - start > max_seconds:
            raise ValueError("Kalshi candlestick range exceeds Atlas bounded window")

        market_payload = await self.get_market(ticker)
        payload = await self._request(
            f"/series/{series_ticker}/markets/{ticker}/candlesticks",
            params={
                "start_ts": start,
                "end_ts": end,
                "period_interval": interval,
                "include_latest_before_start": bool(include_latest_before_start),
            },
        )
        rows = payload.get("candlesticks")
        candles = [
            normalize_candlestick(row)
            for row in rows
            if isinstance(row, dict)
        ] if isinstance(rows, list) else []
        candles.sort(key=lambda row: int(row.get("end_period_ts") or 0))
        return {
            "provider": "kalshi",
            "provider_endpoint": "/series/{series_ticker}/markets/{ticker}/candlesticks",
            "mode": "RESEARCH_ONLY",
            "execution": "DISABLED",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "series_ticker": series_ticker,
            "ticker": ticker,
            "period_interval_minutes": interval,
            "start_ts": start,
            "end_ts": end,
            "include_latest_before_start": bool(include_latest_before_start),
            "count": len(candles),
            "policy": policy_snapshot(),
            "market": market_payload["market"],
            "candlesticks": candles,
        }



kalshi_public = KalshiPublicMarketClient()
