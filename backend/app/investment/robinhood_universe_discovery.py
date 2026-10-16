"""Read-only Robinhood universe discovery sources.

This deliberately does not pretend the Stock Token catalog equals Robinhood
Financial's full US brokerage universe.  It is one official, unauthenticated
Robinhood discovery surface that can feed the durable coverage registry without
brokerage credentials or order capabilities.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.request import Request, urlopen

from app.investment.robinhood_universe_registry import upsert_discovery

RHJ_ASSETS_URL = "https://api.robinhood.com/rhj/assets"
DEFAULT_TIMEOUT_SEC = 8.0


def _get_assets(timeout: float) -> dict[str, Any]:
    req = Request(
        RHJ_ASSETS_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "ProjectAtlas/robinhood-universe read-only discovery",
        },
        method="GET",
    )
    with urlopen(req, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS host
        data = json.loads(response.read().decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _tradable(capabilities: Any) -> bool:
    if not isinstance(capabilities, dict):
        return False
    for session in capabilities.values():
        if not isinstance(session, dict):
            continue
        if any(str(v or "").upper() == "TRADING_STATUS_TRADABLE" for v in session.values()):
            return True
    return False


def rows_from_rhj_assets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for asset in payload.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        symbol = str(asset.get("tokenSymbol") or "").upper().strip()
        if not symbol:
            continue
        active = str(asset.get("status") or "").upper() == "ASSET_STATUS_ACTIVE"
        tradable = active and _tradable(asset.get("tradingCapabilities"))
        name = str(asset.get("tokenName") or "").replace(" • Robinhood Token", "").strip()
        rows.append(
            {
                "symbol": symbol,
                "name": name or None,
                "listing_state": "TRADABLE" if tradable else ("ANNOUNCED" if active else "UNKNOWN"),
                "tradable": tradable,
                "research_lane": "UNCLASSIFIED",
                "instrument_type": "EQUITY_REFERENCE",
                "source_reference": RHJ_ASSETS_URL,
            }
        )
    return rows


async def sync_official_rhj_assets(*, timeout_sec: float = DEFAULT_TIMEOUT_SEC) -> dict[str, Any]:
    payload = await asyncio.wait_for(
        asyncio.to_thread(_get_assets, float(timeout_sec)),
        timeout=float(timeout_sec) + 1.0,
    )
    rows = rows_from_rhj_assets(payload)
    result = await asyncio.to_thread(
        upsert_discovery,
        rows,
        source="robinhood_official_rhj_assets",
    )
    return {
        **result,
        "source_rows": len(rows),
        "coverage_scope": "OFFICIAL_ROBINHOOD_STOCK_TOKEN_ASSETS_NOT_FULL_US_BROKERAGE_UNIVERSE",
        "execution": "RESEARCH_ONLY_MANUAL",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
