"""Read-only Robinhood equity quote references for Quality Dips.

Uses unauthenticated/public Robinhood market-data surfaces only. No account access,
no order placement, and no brokerage mutation. The preferred RHJ endpoint exposes
raw underlying-equity bid/ask with a generated timestamp; when available, Atlas
uses the ask for manual buy-limit monitoring and the bid/ask midpoint for display.
The legacy public quote endpoint is a fallback/reference only because it can stop
updating after extended hours.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RHJ_PRICE_URL = "https://api.robinhood.com/rhj/prices/{symbol}"
CLASSIC_QUOTE_URL = "https://api.robinhood.com/quotes/{symbol}/"
DEFAULT_TIMEOUT_SEC = 5.0


def _float(v: Any) -> float | None:
    try:
        x = float(v)
        return x if x == x and x > 0 else None
    except (TypeError, ValueError):
        return None


def _parse_ts(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _get_json(url: str, timeout: float) -> dict[str, Any]:
    req = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ProjectAtlas/quality-dips read-only market data",
        },
        method="GET",
    )
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed HTTPS hosts above
        body = resp.read().decode("utf-8")
    data = json.loads(body)
    return data if isinstance(data, dict) else {}


class RobinhoodEquityQuoteClient:
    def __init__(self, *, timeout_sec: float = DEFAULT_TIMEOUT_SEC) -> None:
        self.timeout_sec = float(timeout_sec)

    async def get_quote(self, symbol: str) -> dict[str, Any]:
        symbol = str(symbol or "").upper().strip()
        if not symbol:
            return self._missing(symbol, "EMPTY_SYMBOL", "empty symbol")

        notes: list[str] = []
        try:
            payload = await asyncio.wait_for(
                asyncio.to_thread(_get_json, RHJ_PRICE_URL.format(symbol=symbol), self.timeout_sec),
                timeout=self.timeout_sec + 1.0,
            )
            parsed = self._parse_rhj(symbol, payload)
            if parsed is not None:
                return parsed
            notes.append("rhj:no_quote")
        except (HTTPError, URLError, TimeoutError, asyncio.TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            notes.append(f"rhj:{type(exc).__name__}")
        except Exception as exc:
            notes.append(f"rhj:{type(exc).__name__}")

        try:
            payload = await asyncio.wait_for(
                asyncio.to_thread(_get_json, CLASSIC_QUOTE_URL.format(symbol=symbol), self.timeout_sec),
                timeout=self.timeout_sec + 1.0,
            )
            parsed = self._parse_classic(symbol, payload)
            if parsed is not None:
                parsed["provider_notes"] = notes
                return parsed
            notes.append("classic:no_quote")
        except (HTTPError, URLError, TimeoutError, asyncio.TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            notes.append(f"classic:{type(exc).__name__}")
        except Exception as exc:
            notes.append(f"classic:{type(exc).__name__}")

        return self._missing(symbol, "UNAVAILABLE", ", ".join(notes) or "Robinhood quote unavailable")

    @staticmethod
    def _parse_rhj(symbol: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        rows = payload.get("quotes")
        if not isinstance(rows, list) or not rows:
            return None
        row = next((x for x in rows if isinstance(x, dict) and str(x.get("tokenSymbol") or "").upper() == symbol), None)
        if row is None:
            row = next((x for x in rows if isinstance(x, dict)), None)
        if not isinstance(row, dict):
            return None
        bid = _float(row.get("bid"))
        ask = _float(row.get("ask"))
        ts = _parse_ts(row.get("generatedAt"))
        if bid is None and ask is None:
            return None
        display = (bid + ask) / 2.0 if bid is not None and ask is not None else (ask or bid)
        return {
            "symbol": symbol,
            "price": display,
            "display_price": display,
            "bid": bid,
            "ask": ask,
            "trigger_price": ask or display,
            "source": "robinhood_underlying_bid_ask",
            "session": "ROBINHOOD_MARKET_DATA",
            "effective_timestamp": ts.isoformat() if ts else None,
            "generated_at": ts.isoformat() if ts else None,
            "provider_notes": [],
            "raw_kind": "RHJ_UNDERLYING_BID_ASK",
        }

    @staticmethod
    def _parse_classic(symbol: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        regular = _float(payload.get("last_trade_price"))
        extended = _float(payload.get("last_extended_hours_trade_price"))
        price = extended or regular
        ts = _parse_ts(payload.get("updated_at"))
        if price is None:
            return None
        return {
            "symbol": symbol,
            "price": price,
            "display_price": price,
            "bid": _float(payload.get("bid_price")),
            "ask": _float(payload.get("ask_price")),
            "trigger_price": _float(payload.get("ask_price")) or price,
            "source": "robinhood_public_quote",
            "session": "ROBINHOOD_PUBLIC_REFERENCE",
            "effective_timestamp": ts.isoformat() if ts else None,
            "generated_at": ts.isoformat() if ts else None,
            "provider_notes": [],
            "raw_kind": "CLASSIC_PUBLIC_QUOTE",
        }

    @staticmethod
    def _missing(symbol: str, code: str, message: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "price": None,
            "display_price": None,
            "bid": None,
            "ask": None,
            "trigger_price": None,
            "source": "robinhood",
            "session": "UNKNOWN",
            "effective_timestamp": None,
            "generated_at": None,
            "provider_notes": [message[:180]],
            "raw_kind": "MISSING",
            "error": {"code": code, "message": message[:180]},
        }


robinhood_equity_quote_client = RobinhoodEquityQuoteClient()
