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
    args = p.parse_args()
    try:
        if not 1 <= args.seconds <= 60:
            raise IEXRefused("IEX_PROBE_DURATION_REFUSED")
        credentials = Credentials.load(REPO / "config/alpaca.env")
        result = asyncio.run(
            IEXFeed(["MSFT", "SPY"]).run(credentials, seconds=args.seconds)
        )
        print(json.dumps(result, sort_keys=True))
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
