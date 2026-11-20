"""Bounded Hyperliquid PUBLIC REST fallback research only, no financial authority.

The existing selected-source Hyperliquid parser validates the complete original
metadata/book envelope and provider freshness. This diagnostic neither creates
nor resets an old native budget, and never uses wallets/order endpoints. It
cannot certify continuous 24/7 operation from a short observation.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from hashlib import sha256

import httpx
from app.adapters.hyperliquid import _paper_execution_observation

SCHEMA = "ATLAS_R20_PUBLIC_HL_BOUNDED_REST_BOOK_FALLBACK_READONLY_V1"
URL = "https://api.hyperliquid.xyz/info"
SYMBOLS = ("BTC", "ETH", "SOL")
MAX_CYCLES = 6
MAX_RESPONSE_BYTES = 512_000
MIN_INTERVAL_SECONDS = 3
MAX_INTERVAL_SECONDS = 6


def _read_response(response):
    if (response.status_code != 200
            or str(response.url) != URL
            or not 0 < len(response.content) <= MAX_RESPONSE_BYTES):
        raise ValueError("HL_REST_BOUNDED_PUBLIC_PROVIDER_RESPONSE_REFUSED")
    return response.json()


def validate_cycle(*, metadata, books, started_ms, observed_ms):
    """Validate an original contemporaneous source cut, not a trading quote."""
    if (type(books) is not dict or set(books) != set(SYMBOLS)
            or type(started_ms) is not int or type(observed_ms) is not int
            or started_ms <= 0 or not 0 <= observed_ms - started_ms <= 5000):
        raise ValueError("HL_REST_BOUNDED_SOURCE_CUT_REFUSED")
    observations = {}
    for symbol in SYMBOLS:
        parsed = _paper_execution_observation(
            symbol, metadata, books[symbol], started_ms, observed_ms
        )
        if (parsed["market_book_validated"] is not True
                or parsed["financial_execution_authorized"] is not False
                or parsed["startup_authorized"] is not False
                or parsed["historical_settlement_oracle"] is not None
                or parsed["fee_schedule"] is not None):
            raise ValueError("HL_REST_PUBLIC_NOT_FINANCIAL_SETTLEMENT")
        observations[symbol] = {
            "timestamp_ms": parsed["book_timestamp_ms"],
            "source_age_ms": observed_ms - parsed["book_timestamp_ms"],
            "source_digest": sha256(
                json.dumps(books[symbol], sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        }
    return observations


async def _fetch(client, payload):
    response = await client.post(URL, json=payload)
    return _read_response(response)


async def observe(*, cycles=4, interval_seconds=4, client=None,
                  wall_ms=None, monotonic=None, sleeper=None):
    if (type(cycles) is not int or not 2 <= cycles <= MAX_CYCLES
            or type(interval_seconds) is not int
            or not MIN_INTERVAL_SECONDS <= interval_seconds <= MAX_INTERVAL_SECONDS):
        raise ValueError("HL_REST_BOUNDED_CADENCE_REQUIRED")
    now = wall_ms or (lambda: time.time_ns() // 1_000_000)
    steady = monotonic or time.monotonic
    pause = sleeper or asyncio.sleep
    own = client is None
    if own:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=3.0),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
            follow_redirects=False, trust_env=False,
        )
    begin = steady()
    reports = []
    try:
        for index in range(cycles):
            remaining = begin + index * interval_seconds - steady()
            if remaining > 0:
                await pause(remaining)
            if steady() - (begin + index * interval_seconds) > 1.0:
                raise ValueError("HL_REST_BOUNDED_SCHEDULE_SLIPPED")
            started_ms = now()
            started_steady = steady()
            inputs = [
                {"type": "metaAndAssetCtxs"},
                *({"type": "l2Book", "coin": symbol} for symbol in SYMBOLS),
            ]
            # Exactly four simultaneous public INFO requests per cycle.
            raw = await asyncio.gather(*(_fetch(client, item) for item in inputs))
            observed_ms = now()
            if (type(started_ms) is not int or type(observed_ms) is not int
                    or steady() - started_steady > 5.0):
                raise ValueError("HL_REST_BOUNDED_REQUEST_DEADLINE_REFUSED")
            books = dict(zip(SYMBOLS, raw[1:], strict=True))
            observations = validate_cycle(
                metadata=raw[0], books=books,
                started_ms=started_ms, observed_ms=observed_ms,
            )
            reports.append({
                "cycle_index": index,
                "request_elapsed_ms": observed_ms - started_ms,
                "max_source_age_ms": max(
                    item["source_age_ms"] for item in observations.values()
                ),
                "book_timestamps_ms": {
                    symbol: item["timestamp_ms"] for symbol, item in observations.items()
                },
                "original_provider_digests": {
                    symbol: item["source_digest"] for symbol, item in observations.items()
                },
                "accepted_symbols": list(SYMBOLS),
            })
        return {
            "schema": SCHEMA,
            "status": "BOUNDED_PUBLIC_REST_CADENCE_VERIFIED_DATA_ONLY",
            "cycles": cycles,
            "interval_seconds": interval_seconds,
            "public_info_http_attempts": cycles * (len(SYMBOLS) + 1),
            "reports": reports,
            "max_observed_book_source_age_ms": max(
                row["max_source_age_ms"] for row in reports
            ),
            "only_public_info_endpoints_used": True,
            "provider_entitlement_accepted": False,
            "financial_source_issuer_accepted": False,
            "financial_clock_accepted": False,
            "historical_consensus_settlement_oracle_accepted": False,
            "account_specific_fee_schedule_accepted": False,
            "extended_soak_accepted": False,
            "paper_startup_authorized": False,
            "live_trading_authorized": False,
        }
    finally:
        if own:
            await client.aclose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observe-public-readonly", action="store_true")
    parser.add_argument("--cycles", type=int, default=4)
    parser.add_argument("--interval", type=int, default=4)
    args = parser.parse_args(argv)
    if not args.observe_public_readonly:
        parser.error("Explicit bounded read-only public REST observation required")
    try:
        output = asyncio.run(observe(
            cycles=args.cycles, interval_seconds=args.interval
        ))
        print(json.dumps(output, sort_keys=True))
        return 0
    except (ValueError, TypeError, KeyError, OSError, httpx.HTTPError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "BOUNDED_PUBLIC_REST_SOURCE_REFUSED",
            "paper_startup_authorized": False,
            "live_trading_authorized": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
