"""Bounded Alpaca US equity/ETF catalog discovery, research-only.

Alpaca asset eligibility is not evidence of Robinhood availability or PAPER
execution authority. Never calls a trading endpoint that submits orders.
"""
import json
import hashlib
import os
import re
from datetime import UTC, datetime
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


def normalize_inventory(payload):
    """Stable provider-scoped research universe, never Robinhood/PAPER approval."""
    summarize_catalog(payload)
    rows = []
    for asset in payload:
        symbol = asset["symbol"]
        if (asset.get("status") != "active" or asset.get("tradable") is not True
                or re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", symbol) is None):
            continue
        rows.append({"symbol": symbol, "provider_asset_id": str(asset.get("id") or ""),
                     "exchange": str(asset.get("exchange") or ""),
                     "asset_class": "us_equity", "provider_tradable": True})
    rows.sort(key=lambda x: x["symbol"])
    if len({x["symbol"] for x in rows}) != len(rows):
        raise ValueError("ALPACA_INVENTORY_DUPLICATE")
    return rows


def inventory_snapshot(payload, *, captured_at):
    rows = normalize_inventory(payload)
    if type(captured_at) is not str or not captured_at.endswith("+00:00"):
        raise ValueError("ALPACA_INVENTORY_UTC_REQUIRED")
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"schema": "ATLAS_ALPACA_EQUITY_RESEARCH_INVENTORY_V1",
            "source": "ALPACA_US_EQUITY_ASSETS", "captured_at": captured_at,
            "sha256": digest, "rows": rows,
            "robinhood_brokerage_verified": False,
            "paper_execution_authorized": False, "live_order_authorized": False}


def rotating_batch(snapshot, *, offset, limit=8):
    if (type(snapshot) is not dict or snapshot.get("schema") != "ATLAS_ALPACA_EQUITY_RESEARCH_INVENTORY_V1"
            or snapshot.get("paper_execution_authorized") is not False
            or snapshot.get("robinhood_brokerage_verified") is not False
            or type(offset) is not int or offset < 0
            or type(limit) is not int or not 1 <= limit <= 8):
        raise ValueError("ALPACA_INVENTORY_RESEARCH_SCOPE")
    rows = snapshot.get("rows")
    if type(rows) is not list or not rows:
        return []
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != snapshot.get("sha256"):
        raise ValueError("ALPACA_INVENTORY_DIGEST_CHANGED")
    start = offset % len(rows)
    return [rows[(start + i) % len(rows)]["symbol"] for i in range(min(limit, len(rows)))]


def acquire_catalog(credentials_path, *, inventory_path=None):
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
    payload = json.loads(raw)
    result = summarize_catalog(payload)
    if inventory_path is not None:
        inventory_path = Path(inventory_path)
        if inventory_path != REPO / "logs" / "research" / "alpaca_equity_inventory.json":
            raise ValueError("ALPACA_INVENTORY_PATH_REFUSED")
        snapshot = inventory_snapshot(payload, captured_at=datetime.now(UTC).isoformat())
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        temp = inventory_path.with_suffix(".pending")
        with temp.open("x", encoding="utf-8") as handle:
            json.dump(snapshot, handle, separators=(",", ":"))
        os.replace(temp, inventory_path)
        result["research_inventory_rows"] = len(snapshot["rows"])
        result["research_inventory_sha256"] = snapshot["sha256"]
    return result


def main():
    try:
        result = acquire_catalog(REPO / "config/alpaca.env", inventory_path=REPO / "logs" / "research" / "alpaca_equity_inventory.json")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {"schema": "ATLAS_ALPACA_EQUITY_CATALOG_AUDIT_V1", "status": "REFUSED",
                  "paper_execution_authorized": False, "live_order_authorized": False}
        print(json.dumps(result, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
