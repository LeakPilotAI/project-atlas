"""Normalized per-asset investment snapshot. Scoring is Phase 3+."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.investment.bars import OhlcvBar
from app.investment.enums import DataQuality
from app.investment.models import InvestmentAsset, MeasuredValue
from app.investment.storage import SNAPSHOTS_PATH, ensure_dirs
from app.investment.universe import UniverseEntry
from app.investment.yfinance_client import utcnow


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


@dataclass
class InvestmentSnapshot:
    asset: InvestmentAsset
    retrieved_at: datetime
    price: MeasuredValue
    market_cap: MeasuredValue
    latest_bar: Optional[OhlcvBar] = None
    fundamentals: Dict[str, MeasuredValue] = field(default_factory=dict)
    valuation: Dict[str, MeasuredValue] = field(default_factory=dict)
    failures: List[Dict[str, Any]] = field(default_factory=list)
    history_rows_stored: int = 0

    def quality_counts(self, group: str) -> Dict[str, int]:
        items: List[MeasuredValue] = []
        if group == "price":
            items = [self.price]
        elif group == "fundamentals":
            items = list(self.fundamentals.values())
        elif group == "valuation":
            items = list(self.valuation.values())
        counts = {q.value: 0 for q in DataQuality}
        for mv in items:
            counts[mv.quality.value] = counts.get(mv.quality.value, 0) + 1
        return counts

    def as_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset.as_dict(),
            "retrieved_at": _iso(self.retrieved_at),
            "price": self.price.as_dict(),
            "market_cap": self.market_cap.as_dict(),
            "latest_bar": self.latest_bar.as_dict() if self.latest_bar else None,
            "fundamentals": {k: v.as_dict() for k, v in self.fundamentals.items()},
            "valuation": {k: v.as_dict() for k, v in self.valuation.items()},
            "failures": list(self.failures),
            "history_rows_stored": self.history_rows_stored,
        }


def snapshot_from_parts(
    entry: UniverseEntry,
    *,
    price: MeasuredValue,
    fundamentals: Dict[str, MeasuredValue],
    valuation: Dict[str, MeasuredValue],
    latest_bar: Optional[OhlcvBar] = None,
    failures: Optional[List[Dict[str, Any]]] = None,
    history_rows_stored: int = 0,
) -> InvestmentSnapshot:
    asset = InvestmentAsset(
        symbol=entry.symbol,
        asset_type=entry.asset_type,
        name=entry.name,
        sector=entry.sector,
        industry=entry.industry,
        exchange=entry.exchange,
        currency=entry.currency,
        price=price,
        market_cap=fundamentals.get("market_cap") or MeasuredValue.unknown("none"),
        data_timestamp=price.timestamp or utcnow(),
        active=entry.active,
    )
    return InvestmentSnapshot(
        asset=asset,
        retrieved_at=utcnow(),
        price=price,
        market_cap=asset.market_cap,
        latest_bar=latest_bar,
        fundamentals=fundamentals,
        valuation=valuation,
        failures=failures or [],
        history_rows_stored=history_rows_stored,
    )


def persist_snapshot(snap: InvestmentSnapshot, path: Optional[Path] = None) -> None:
    """Append a snapshot JSON line. Isolated from trading journals."""
    ensure_dirs()
    p = path or SNAPSHOTS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snap.as_dict(), default=str) + "\n")
