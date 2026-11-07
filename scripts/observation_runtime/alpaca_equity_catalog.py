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


def next_research_batch(inventory_path, cursor_path, *, limit=4, commit=False):
    """Read-only planning by default; explicit cursor-only progression on request.

    No research providers or financial journals are invoked here. A changed
    catalog digest resets the cursor rather than silently skipping instruments.
    """
    inventory_path, cursor_path = Path(inventory_path), Path(cursor_path)
    if inventory_path != REPO / "logs" / "research" / "alpaca_equity_inventory.json":
        raise ValueError("ALPACA_INVENTORY_PATH_REFUSED")
    if cursor_path != REPO / "logs" / "research" / "alpaca_equity_cursor.json":
        raise ValueError("ALPACA_CURSOR_PATH_REFUSED")
    if type(commit) is not bool or type(limit) is not int or not 1 <= limit <= 8:
        raise ValueError("ALPACA_BATCH_POLICY")
    snapshot = json.loads(inventory_path.read_text(encoding="utf-8"))
    prior = json.loads(cursor_path.read_text(encoding="utf-8")) if cursor_path.is_file() else {}
    if type(prior) is not dict or prior.get("schema", "ATLAS_ALPACA_RESEARCH_CURSOR_V1") != "ATLAS_ALPACA_RESEARCH_CURSOR_V1":
        raise ValueError("ALPACA_CURSOR_SCHEMA")
    if prior.get("inventory_sha256") != snapshot.get("sha256"):
        offset = 0
    else:
        offset = prior.get("offset", 0)
    batch = rotating_batch(snapshot, offset=offset, limit=limit)
    result = {"schema": "ATLAS_ALPACA_RESEARCH_BATCH_V1", "inventory_sha256": snapshot["sha256"],
              "offset": offset, "symbols": batch, "next_offset": offset + len(batch),
              "market": "US_EQUITY", "strategy_scope": "RESEARCH_CANDIDATES_ONLY",
              "hyperliquid_perpetuals_included": False,
              "paper_execution_authorized": False, "live_order_authorized": False}
    if commit and batch:
        cursor_path.parent.mkdir(parents=True, exist_ok=True)
        temp = cursor_path.with_suffix(".pending")
        with temp.open("x", encoding="utf-8") as handle:
            json.dump({"schema": "ATLAS_ALPACA_RESEARCH_CURSOR_V1", "inventory_sha256": snapshot["sha256"],
                       "offset": result["next_offset"]}, handle, sort_keys=True)
        os.replace(temp, cursor_path)
    return result


def research_route_plan(batch, *, known_etf_symbols=()):
    """Plan broad-market research without promoting any symbol to trading.

    Equity/ETF ambiguity remains UNKNOWN unless an independently supplied ETF
    classification exists. Hyperliquid is never part of this planner.
    """
    if (type(batch) is not dict or batch.get("schema") != "ATLAS_ALPACA_RESEARCH_BATCH_V1"
            or batch.get("market") != "US_EQUITY"
            or batch.get("paper_execution_authorized") is not False
            or batch.get("hyperliquid_perpetuals_included") is not False):
        raise ValueError("RESEARCH_ROUTE_SCOPE_REFUSED")
    symbols = batch.get("symbols")
    if type(symbols) is not list or len(symbols) > 8 or any(
            type(s) is not str or re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", s) is None
            for s in symbols) or len(symbols) != len(set(symbols)):
        raise ValueError("RESEARCH_ROUTE_SYMBOLS_REFUSED")
    etfs = set(known_etf_symbols)
    return {"schema": "ATLAS_BROAD_MARKET_RESEARCH_ROUTE_V1",
            "source": "ALPACA_US_EQUITY_ASSETS", "market": "US_EQUITY",
            "routes": [{"symbol": symbol, "asset_type": "ETF" if symbol in etfs else "UNCLASSIFIED_EQUITY",
                        "research_lanes": ["QUALITY_DIPS", "LONG_TERM_INVESTMENT", "DAY_TRADE_RESEARCH"],
                        "scoring_status": "NOT_EVALUATED", "paper_eligible": False}
                       for symbol in symbols],
            "hyperliquid_perpetuals_included": False,
            "paper_execution_authorized": False, "live_order_authorized": False}


def complete_research_batch(batch, results, cursor_path):
    """Advance the research cursor only for a complete, successful batch.

    Results are research receipts, never trading authorizations. Failed symbols
    remain pending for the next attempt. An already advanced cursor is refused.
    """
    cursor_path = Path(cursor_path)
    if cursor_path != REPO / "logs" / "research" / "alpaca_equity_cursor.json":
        raise ValueError("RESEARCH_COMPLETION_CURSOR_PATH_REFUSED")
    if (type(batch) is not dict or batch.get("schema") != "ATLAS_ALPACA_RESEARCH_BATCH_V1"
            or batch.get("paper_execution_authorized") is not False
            or batch.get("hyperliquid_perpetuals_included") is not False
            or type(results) is not list):
        raise ValueError("RESEARCH_COMPLETION_SCOPE_REFUSED")
    symbols = batch.get("symbols")
    if (type(symbols) is not list or not symbols or len(symbols) > 8
            or len(symbols) != len(set(symbols))
            or type(batch.get("offset")) is not int or batch["offset"] < 0
            or batch.get("next_offset") != batch["offset"] + len(symbols)):
        raise ValueError("RESEARCH_COMPLETION_BATCH_REFUSED")
    if (len(results) != len(symbols)
            or any(type(r) is not dict or r.get("symbol") != symbol
                   or r.get("status") != "RESEARCH_COMPLETE"
                   or r.get("paper_eligible") is not False
                   for symbol, r in zip(symbols, results, strict=True))):
        raise ValueError("RESEARCH_COMPLETION_INCOMPLETE")
    inventory_path = REPO / "logs" / "research" / "alpaca_equity_inventory.json"
    snapshot = json.loads(inventory_path.read_text(encoding="utf-8"))
    expected = rotating_batch(snapshot, offset=batch["offset"], limit=len(symbols))
    if snapshot.get("sha256") != batch.get("inventory_sha256") or expected != symbols:
        raise ValueError("RESEARCH_COMPLETION_INVENTORY_CHANGED")
    prior = json.loads(cursor_path.read_text(encoding="utf-8")) if cursor_path.is_file() else {}
    if (type(prior) is not dict or prior.get("schema", "ATLAS_ALPACA_RESEARCH_CURSOR_V1") != "ATLAS_ALPACA_RESEARCH_CURSOR_V1"
            or (prior.get("offset", 0) if prior.get("inventory_sha256") == batch["inventory_sha256"] else 0) != batch["offset"]):
        raise ValueError("RESEARCH_COMPLETION_CURSOR_CHANGED")
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    temp = cursor_path.with_suffix(".pending")
    with temp.open("x", encoding="utf-8") as handle:
        json.dump({"schema": "ATLAS_ALPACA_RESEARCH_CURSOR_V1",
                   "inventory_sha256": batch["inventory_sha256"],
                   "offset": batch["next_offset"]}, handle, sort_keys=True)
    os.replace(temp, cursor_path)
    return {"completed": len(symbols), "next_offset": batch["next_offset"],
            "paper_execution_authorized": False, "live_order_authorized": False}


def score_research_bundle(*, symbol, data):
    """Score genuine provider-shaped data in memory with existing Atlas engine.

    No persisted snapshots, Robinhood token registry mutations or PAPER writes.
    """
    from app.investment.enums import AssetType
    from app.investment.research import InvestmentResearch
    from app.investment.snapshot import snapshot_from_parts
    from app.investment.universe import UniverseEntry
    from app.investment.robinhood_discovery_research import classify_lane
    if (type(symbol) is not str or re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", symbol) is None
            or type(data) is not dict or data.get("paper_eligible") is not False
            or type(data.get("asset")) is not dict or data["asset"].get("symbol") != symbol
            or data["asset"].get("class") != "us_equity"
            or not data.get("receipts") or not data.get("bars")
            or not isinstance(data.get("fundamentals"), dict)
            or not isinstance(data.get("valuation"), dict)):
        raise ValueError("BROAD_RESEARCH_SCORE_INPUT_REFUSED")
    entry = UniverseEntry(symbol=symbol, asset_type=AssetType.UNKNOWN,
                          groups=["alpaca_provider_scoped_research"])
    snap = snapshot_from_parts(entry, price=data["price"],
                               fundamentals=data["fundamentals"],
                               valuation=data["valuation"], latest_bar=data["bars"][-1])
    record = InvestmentResearch().score_snapshot(snap, tuple(data["bars"]))
    lane, reason = classify_lane(record)
    return {"symbol": symbol, "status": "RESEARCH_SCORED",
            "research_lane": lane, "reason": reason,
            "evidence_quality": record.evidence_quality.value,
            "thesis": record.thesis.value,
            "opportunity_score": record.opportunity_score,
            "provider_receipt_count": len(data["receipts"]),
            "paper_eligible": False, "live_order_authorized": False}


def run_bounded_provider_research(*, contact, limit=1, provider=None):
    """Explicit, non-autostart diagnostic research; no financial mutation.

    Uses the existing authenticated SEC/Alpaca research bundle. A provider
    failure refuses cursor advancement; no success is fabricated.
    """
    if type(limit) is not int or not 1 <= limit <= 2:
        raise ValueError("RESEARCH_WORKER_BUDGET_REFUSED")
    from scripts.observation_runtime.qd_free_research_acquisition import inspect_free_research
    provider = inspect_free_research if provider is None else provider
    root = REPO / "logs" / "research"
    batch = next_research_batch(root / "alpaca_equity_inventory.json",
                                root / "alpaca_equity_cursor.json", limit=limit)
    plan = research_route_plan(batch)
    outcomes = []
    for route in plan["routes"]:
        symbol = route["symbol"]
        try:
            result = provider(symbol=symbol, contact=contact,
                              credentials_path=REPO / "config/alpaca.env")
            if (type(result) is not dict or result.get("symbol") != symbol
                    or result.get("paper_fill_authorized") is not False
                    or result.get("live_order_authorized") is not False
                    or result.get("provider_receipt_count", 0) < 1):
                raise ValueError("RESEARCH_PROVIDER_RECEIPT_REFUSED")
            outcomes.append({"symbol": symbol, "status": "RESEARCH_COMPLETE",
                             "provider_receipt_count": result["provider_receipt_count"],
                             "paper_eligible": False})
        except (ValueError, OSError, KeyError, TypeError) as exc:
            outcomes.append({"symbol": symbol, "status": "RESEARCH_BLOCKED",
                             "reason": type(exc).__name__, "paper_eligible": False})
            break
    complete = len(outcomes) == len(batch["symbols"]) and all(
        row["status"] == "RESEARCH_COMPLETE" for row in outcomes)
    # Acquisition is not strategy scoring. Never skip a symbol just because
    # provider diagnostics returned receipts: a later scoring stage must own
    # the final research-completion and cursor-advance decision.
    return {"schema": "ATLAS_BROAD_PROVIDER_RESEARCH_DIAGNOSTIC_V1",
            "outcomes": outcomes, "batch_complete": complete,
            "cursor_advanced": False, "strategy_scoring_complete": False,
            "paper_execution_authorized": False, "live_order_authorized": False}


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
