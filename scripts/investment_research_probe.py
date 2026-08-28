#!/usr/bin/env python3
"""Live research probe for Phase 3. Not used by CI. Not a recommendation."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.investment.enums import AssetType  # noqa: E402
from app.investment.ingest import InvestmentIngest  # noqa: E402
from app.investment.research import InvestmentResearch, format_research_text  # noqa: E402
from app.investment.research_store import append_research  # noqa: E402
from app.investment.universe import InvestmentUniverse, UniverseEntry  # noqa: E402


def _sample_universe() -> InvestmentUniverse:
    return InvestmentUniverse(
        [
            UniverseEntry(symbol="SPY", name="SPDR S&P 500 ETF Trust", asset_type=AssetType.ETF),
            UniverseEntry(symbol="XLK", name="Technology Select Sector SPDR Fund", asset_type=AssetType.SECTOR_ETF),
            UniverseEntry(symbol="JNJ", name="Johnson & Johnson", asset_type=AssetType.STOCK),
        ]
    )


async def main() -> int:
    data_root = ROOT / "backend" / "data" / "investment"
    hist = data_root / "history"
    hist.mkdir(parents=True, exist_ok=True)
    ing = InvestmentIngest(
        universe=_sample_universe(),
        history_root=hist,
        snapshot_path=data_root / "snapshots.jsonl",
        persist=True,
    )
    snaps = await ing.ingest_universe(history_period="1y")
    eng = InvestmentResearch()
    records = eng.score_many(snaps, history_root=hist)
    opp_path = data_root / "opportunities.jsonl"
    for rec in records:
        append_research(rec, path=opp_path)
        print(format_research_text(rec))
        print("\n" + ("-" * 72) + "\n")
    return 0 if records else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
