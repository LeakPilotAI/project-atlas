#!/usr/bin/env python3
"""Live Yahoo probe for Phase 2 investment data. Not used by CI. Not scoring."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.investment.enums import AssetType  # noqa: E402
from app.investment.ingest import InvestmentIngest  # noqa: E402
from app.investment.quality_report import summarize_snapshots  # noqa: E402
from app.investment.universe import InvestmentUniverse, UniverseEntry  # noqa: E402


def _sample_universe() -> InvestmentUniverse:
    # Tiny representative mix — not a recommendation list, not a hardcoded engine universe.
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
    print(summarize_snapshots(snaps))
    print("")
    for s in snaps:
        px = s.price
        pe = s.valuation.get("pe")
        rev = s.fundamentals.get("revenue")
        print(
            f"{s.asset.symbol:6} price={px.value} q={px.quality.value} src={px.source} "
            f"pe={getattr(pe, 'value', None)} pe_q={getattr(getattr(pe, 'quality', None), 'value', None)} "
            f"rev={getattr(rev, 'value', None)} fails={len(s.failures)} bars={s.history_rows_stored}"
        )
        if s.price.retrieved_at:
            print(f"       retrieved_at={s.price.retrieved_at.isoformat()} "
                  f"effective={s.price.effective_timestamp}")
    return 0 if snaps else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
