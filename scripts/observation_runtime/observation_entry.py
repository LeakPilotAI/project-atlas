"""Standalone, deny-by-default observation entry point.

This entry point reports capabilities only. It does not initialize a
session, contact a provider, start Atlas, or authorize live execution.
"""
from __future__ import annotations

import argparse
import json


def capabilities() -> dict:
    return {
        "profile": "OBSERVATION_ONLY",
        "mode": "OFFLINE",
        "network_enabled": False,
        "live_provider_enabled": False,
        "paper_trading_enabled": False,
        "real_trading_enabled": False,
        "discord_enabled": False,
        "production_backend_enabled": False,
        "session_started": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline Atlas observation capability report"
    )
    operations = parser.add_mutually_exclusive_group(required=False)
    operations.add_argument(
        "--status",
        action="store_true",
        help="Print offline capability status",
    )
    operations.add_argument(
        "--synthetic-once",
        action="store_true",
        help="Run one development-only synthetic observation",
    )
    args = parser.parse_args(argv)

    if not args.status and not args.synthetic_once:
        parser.error("One permitted operation is required")

    if args.synthetic_once:
        from scripts.observation_runtime.r7e47at_offline_lifecycle import run_once

        result = run_once()
        if (
            result.get("mode") != "SYNTHETIC_OFFLINE"
            or result.get("network_enabled") is not False
            or result.get("trading_enabled") is not False
            or result.get("session_closed") is not True
            or result.get("final_event") != "GRACEFUL_SHUTDOWN"
        ):
            raise RuntimeError("Synthetic lifecycle failed closed")

        print(json.dumps(result, sort_keys=True))
        return 0

    print(json.dumps(capabilities(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
