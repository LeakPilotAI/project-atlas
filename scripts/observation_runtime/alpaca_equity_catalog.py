"""Bounded Alpaca US equity/ETF catalog discovery, research-only.

Alpaca asset eligibility is not evidence of Robinhood availability or PAPER
execution authority. Never calls a trading endpoint that submits orders.
"""
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
from app.investment.alpaca_iex import Credentials

URL = "https://paper-api.alpaca.markets/v2/assets?status=active&asset_class=us_equity"


def summarize_catalog(payload):
    if type(payload) is not list or len(payload) > 20000:
        raise ValueError("ALPACA_CATALOG_CAPACITY_OR_SHAPE")
    seen = set()
    types = {"ETF": 0, "STOCK_OR_OTHER_EQUITY": 0}
    for row in payload:
        if type(row) is not dict or row.get("class") != "us_equity":
            raise ValueError("ALPACA_CATALOG_ASSET_CLASS")
        symbol = row.get("symbol")
        if type(symbol) is not str or not symbol or len(symbol) > 20 or symbol in seen:
            raise ValueError("ALPACA_CATALOG_SYMBOL_DUPLICATE_OR_INVALID")
        seen.add(symbol)
        if row.get("status") == "active" and row.get("tradable") is True:
            types["ETF" if row.get("_asset_type") == "ETF" else "STOCK_OR_OTHER_EQUITY"] += 1
    return {"schema": "ATLAS_ALPACA_EQUITY_CATALOG_AUDIT_V1",
            "provider": "ALPACA_US_EQUITY_ASSETS", "catalog_records": len(payload),
            "provider_active_tradable_records": sum(types.values()),
            "provider_asset_class": "us_equity",
            "robinhood_us_brokerage_coverage_verified": False,
            "paper_execution_authorized": False, "live_order_authorized": False}


def acquire_catalog(credentials_path):
    credentials = Credentials.load(credentials_path)
    request = Request(URL, headers={"APCA-API-KEY-ID": credentials.key,
                                    "APCA-API-SECRET-KEY": credentials.secret,
                                    "Accept": "application/json"}, method="GET")
    with urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise ValueError("ALPACA_CATALOG_HTTP_REFUSED")
        raw = response.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("ALPACA_CATALOG_RESPONSE_TOO_LARGE")
    return summarize_catalog(json.loads(raw))


def main():
    try:
        result = acquire_catalog(REPO / "config/alpaca.env")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {"schema": "ATLAS_ALPACA_EQUITY_CATALOG_AUDIT_V1", "status": "REFUSED",
                  "paper_execution_authorized": False, "live_order_authorized": False}
        print(json.dumps(result, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
