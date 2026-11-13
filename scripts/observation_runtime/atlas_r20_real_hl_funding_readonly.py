"""Bounded read-only, actual public Hyperliquid completed-hour funding audit.

Uses the *original* strict HyperliquidAdapter funding parser. Never assumes
hourly fundingRate is settlement oracle. It does not create accounts, publisher
acceptance, invoices, orders, source rights, or durable financial effects.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time

import httpx
from app.adapters.hyperliquid import _paper_funding_observation

SCHEMA = "ATLAS_R20_REAL_PUBLIC_HL_COMPLETED_HOURS_READONLY_V1"
URL = "https://api.hyperliquid.xyz/info"
SYMBOLS = ("BTC", "ETH", "SOL")
HOUR_MS = 3_600_000
MAX_ROWS = 4
MAX_BYTES = 60_000


def finished_hours(*, now_ms: int, hours: int):
    if (type(now_ms) is not int or now_ms < 0
            or type(hours) is not int or not 1 <= hours <= MAX_ROWS):
        raise ValueError("HL_READONLY_BOUNDED_WHOLE_HOURS_REQUIRED")
    # Exclude the last hour: publication timing/funding lags could be ongoing.
    latest_completed_hour = (now_ms // HOUR_MS - 1) * HOUR_MS
    return (latest_completed_hour - (hours - 1) * HOUR_MS,
            latest_completed_hour + HOUR_MS)


def normalize(*, symbol, rows, start_ms, end_ms, started_ms, observed_ms):
    if symbol not in SYMBOLS:
        raise ValueError("HL_BOUNDED_MARKET_SCOPE_REQUIRED")
    parsed = _paper_funding_observation(
        symbol, rows, start_ms, end_ms, started_ms, observed_ms,
    )
    if (parsed["symbol"] != symbol
            or parsed["rate_history_complete"] is not True
            or parsed["settlement_evidence_complete"] is not False
            or parsed["financial_execution_authorized"] is not False
            or parsed["startup_authorized"] is not False
            or any(row["settlement_oracle"] is not None
                   for row in parsed["records"])):
        raise ValueError("HL_NO_HISTORICAL_ORACLE_MUST_REMAIN_UNAVAILABLE")
    # Hash only original source content for later independent readback;
    # never print raw trade/book payloads or any user credentials.
    source_hash = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema": SCHEMA,
        "symbol": symbol,
        "hours": len(parsed["records"]),
        "start_inclusive_ms": start_ms,
        "end_exclusive_ms": end_ms,
        "original_raw_funding_sha256": source_hash,
        "max_provider_publication_delay_ms": max(
            row["publication_delay_ms"] for row in parsed["records"]),
        "rate_history_complete": True,
        "historical_consensus_oracle_accepted": False,
        "historical_fee_schedule_accepted": False,
        "source_rights_accepted": False,
        "paper_funding_settlement_authorized": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }


def acquire(*, hours=3, client=None, clock_ms=None):
    now = clock_ms or (lambda: time.time_ns() // 1_000_000)
    start_ms, end_ms = finished_hours(now_ms=now(), hours=hours)
    reports = []
    own = client is None
    if own:
        client = httpx.Client(
            timeout=httpx.Timeout(7.0, connect=4.0),
            follow_redirects=False, trust_env=False,
        )
    try:
        for symbol in SYMBOLS:
            body = {
                "type": "fundingHistory", "coin": symbol,
                "startTime": start_ms, "endTime": end_ms - 1,
            }
            begun = now()
            response = client.post(URL, json=body)
            received = now()
            if (response.status_code != 200
                    or str(response.url) != URL
                    or len(response.content) > MAX_BYTES
                    or not 0 <= received - begun <= 10_000):
                raise ValueError("HL_PUBLIC_FUNDING_RECEIPT_REFUSED")
            rows = response.json()
            reports.append(normalize(
                symbol=symbol, rows=rows,
                start_ms=start_ms, end_ms=end_ms,
                started_ms=begun, observed_ms=received,
            ))
        return {
            "schema": SCHEMA,
            "status": "PUBLIC_HOURLY_RATES_ONLY_NOT_FINANCIAL_SETTLEMENT",
            "symbol_count": len(reports),
            "hours_per_symbol": hours,
            "reports": reports,
            "historical_consensus_oracle_accepted": False,
            "historical_fee_schedule_accepted": False,
            "source_rights_accepted": False,
            "paper_funding_settlement_authorized": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }
    finally:
        if own:
            client.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-public-completed-hours", action="store_true")
    parser.add_argument("--hours", type=int, default=3)
    args = parser.parse_args(argv)
    if not args.read_public_completed_hours:
        parser.error("Read-only explicit public funding observation required")
    try:
        print(json.dumps(acquire(hours=args.hours), sort_keys=True))
        return 0
    except (ValueError, TypeError, KeyError, OSError, httpx.HTTPError):
        print(json.dumps({
            "schema": SCHEMA, "status": "PUBLIC_HOURLY_SOURCE_REFUSED",
            "paper_funding_settlement_authorized": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
