#!/usr/bin/env python3
"""Manual investment scan. Not used by CI. Not a recommendation. No real orders."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.investment.scan import InvestmentScanner  # noqa: E402
from app.investment.scan_settings import ScanSettings  # noqa: E402
from app.investment.universe import InvestmentUniverse, UniverseEntry, load_universe  # noqa: E402
from app.investment.storage import bootstrap_universe_if_missing  # noqa: E402


def _universe(symbols: str | None) -> InvestmentUniverse | None:
    if not symbols:
        bootstrap_universe_if_missing()
        return None
    entries = [
        UniverseEntry(symbol=s.strip(), name=s.strip(), active=True)
        for s in symbols.split(",")
        if s.strip()
    ]
    return InvestmentUniverse(entries)


async def main() -> int:
    p = argparse.ArgumentParser(description="Run one Atlas investment research scan")
    p.add_argument("--symbols", default="", help="Comma-separated override (TEST/RESEARCH only)")
    p.add_argument("--no-notify", action="store_true")
    p.add_argument("--no-persist", action="store_true")
    args = p.parse_args()
    cfg = ScanSettings(
        enabled=True,
        notify_discord=not args.no_notify,
        persist=not args.no_persist,
        inter_symbol_delay_seconds=0.75,
        max_retries=2,
        retry_base_seconds=1.0,
    )
    scanner = InvestmentScanner(settings=cfg, universe=_universe(args.symbols) or load_universe())
    report = await scanner.run_once()
    print(report.dashboard)
    print(f"\nevaluated={report.evaluated} failed={report.failed} scan_id={report.scan_id}")
    return 0 if report.evaluated or report.universe == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
