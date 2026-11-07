"""Explicit bounded real IEX observation, never a trading or startup service.

Requires an already-enrolled diagnostic watermark; this CLI cannot create it.
Only the authenticated feed callback may advance it. No financial writer.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.investment.alpaca_iex import Credentials, IEXFeed, IEXRefused
from scripts.observation_runtime.paper_readonly_watermark import ReadonlyIEXEventConsumer


def bounded_observation(*, symbol: str, seconds: int, watermark: Path,
                        credentials_path: Path, feed_factory=IEXFeed):
    if (type(symbol) is not str or not symbol.isascii() or not symbol.isalpha()
            or not symbol.isupper() or len(symbol) > 8
            or type(seconds) is not int or not 1 <= seconds <= 60):
        raise ValueError("IEX_WATERMARKED_PROBE_ARGUMENTS_REFUSED")
    # Read-only, explicit local path; enrollment must already exist.
    credentials = Credentials.load(credentials_path)
    with ReadonlyIEXEventConsumer(path=watermark, symbol=symbol) as consumer:
        result = asyncio.run(feed_factory([symbol]).run(
            credentials, seconds=seconds, max_reconnects=0,
            on_fresh_quote=consumer.on_fresh_quote))
        return {"schema": "ATLAS_IEX_WATERMARKED_READONLY_PROBE_V1",
                "authenticated": result["authenticated"],
                "subscribed": result["subscribed"],
                "connection_closed": result["result"]["connection"] == "DISCONNECTED",
                "accepted_events": consumer.accepted,
                "paper_fill_authorized": False, "live_order_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="MSFT")
    parser.add_argument("--seconds", type=int, default=10)
    parser.add_argument("--watermark", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = bounded_observation(symbol=args.symbol, seconds=args.seconds,
                                     watermark=args.watermark,
                                     credentials_path=REPO / "config/alpaca.env")
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, IEXRefused, OSError) as exc:
        # No raw exception: credentials and provider transport must not leak.
        print(json.dumps({"schema": "ATLAS_IEX_WATERMARKED_READONLY_PROBE_V1",
                          "status": "REFUSED", "reason": "PROBE_GATE_OR_PROVIDER_UNAVAILABLE",
                          "paper_fill_authorized": False, "live_order_authorized": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
