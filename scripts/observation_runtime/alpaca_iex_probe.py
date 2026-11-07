"""Explicit bounded data-only probe. No Atlas lifespan or financial-store imports."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.investment.alpaca_iex import Credentials, IEXFeed, IEXRefused


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seconds", type=int, default=20)
    p.add_argument("--symbols", nargs="+", default=["MSFT", "SPY"])
    args = p.parse_args()
    try:
        if not 1 <= args.seconds <= 60:
            raise IEXRefused("IEX_PROBE_DURATION_REFUSED")
        if (not 1 <= len(args.symbols) <= 10
                or len(set(args.symbols)) != len(args.symbols)):
            raise IEXRefused("IEX_PROBE_ROSTER_REFUSED")
        credentials = Credentials.load(REPO / "config/alpaca.env")
        result = asyncio.run(
            IEXFeed(args.symbols).run(credentials, seconds=args.seconds, max_reconnects=0)
        )
        # Never dump the raw feed, credentials, quote payloads or transport
        # details. Authentication and quote delivery are separate evidence.
        print(json.dumps({
            "schema": "ATLAS_IEX_BOUNDED_DATA_ONLY_PROBE_V1",
            "authenticated": result["authenticated"],
            "subscribed": result["subscribed"],
            "quote_count": result["quote_count"],
            "fresh_quote_observed_during_connection": result["fresh_quote_observed_during_connection"],
            "connection_closed": result["result"]["connection"] == "DISCONNECTED",
            "paper_fill_authorized": False,
            "live_order_authorized": False,
        }, sort_keys=True))
    except (IEXRefused, OSError):
        print(
            json.dumps(
                {"status": "REFUSED", "reason": "IEX_CONFIGURATION_OR_DATA_UNAVAILABLE"}
            )
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
