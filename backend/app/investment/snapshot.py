"""Normalized per-asset investment snapshot. Input to Phase 3 research/scoring."""

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


def _parse_dt(raw: object) -> Optional[datetime]:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def measured_from_dict(d: Optional[Dict[str, Any]]) -> MeasuredValue:
    if not d or not isinstance(d, dict):
        return MeasuredValue.unknown("none", "missing")
    q_raw = str(d.get("quality") or "UNKNOWN")
    try:
        q = DataQuality(q_raw)
    except ValueError:
        q = DataQuality.UNKNOWN
    return MeasuredValue(
        value=d.get("value"),
        source=str(d.get("source") or "none"),
        timestamp=_parse_dt(d.get("effective_timestamp") or d.get("timestamp")),
        retrieved_at=_parse_dt(d.get("retrieved_at")),
        effective_timestamp=_parse_dt(d.get("effective_timestamp") or d.get("timestamp")),
        quality=q,
        availability=bool(d.get("availability")),
        notes=str(d.get("notes") or ""),
    )


def snapshot_from_dict(d: Dict[str, Any]) -> Optional[InvestmentSnapshot]:
    if not d or not isinstance(d, dict):
        return None
    asset_d = d.get("asset") if isinstance(d.get("asset"), dict) else {}
    from app.investment.enums import AssetType
    from app.investment.universe import UniverseEntry

    try:
        at = AssetType(str(asset_d.get("asset_type") or "UNKNOWN"))
    except ValueError:
        at = AssetType.UNKNOWN
    entry = UniverseEntry(
        symbol=str(asset_d.get("symbol") or d.get("symbol") or ""),
        name=str(asset_d.get("name") or ""),
        asset_type=at,
        exchange=str(asset_d.get("exchange") or ""),
        currency=str(asset_d.get("currency") or "USD"),
        sector=str(asset_d.get("sector") or ""),
        industry=str(asset_d.get("industry") or ""),
        active=bool(asset_d.get("active", True)),
    )
    if not entry.symbol:
        return None
    funds = {k: measured_from_dict(v) for k, v in (d.get("fundamentals") or {}).items() if isinstance(v, dict)}
    val = {k: measured_from_dict(v) for k, v in (d.get("valuation") or {}).items() if isinstance(v, dict)}
    latest = None
    lb = d.get("latest_bar")
    if isinstance(lb, dict) and lb.get("date"):
        latest = OhlcvBar(
            session_date=str(lb.get("date")),
            open=lb.get("open"),
            high=lb.get("high"),
            low=lb.get("low"),
            close=lb.get("close"),
            volume=lb.get("volume"),
            adjusted_close=lb.get("adjusted_close"),
            source=str(lb.get("source") or ""),
        )
    snap = snapshot_from_parts(
        entry,
        price=measured_from_dict(d.get("price") if isinstance(d.get("price"), dict) else None),
        fundamentals=funds,
        valuation=val,
        latest_bar=latest,
        failures=list(d.get("failures") or []),
        history_rows_stored=int(d.get("history_rows_stored") or 0),
    )
    ra = _parse_dt(d.get("retrieved_at"))
    if ra:
        snap.retrieved_at = ra
    return snap


def save_latest_snapshot(snap: InvestmentSnapshot, root: Optional[Path] = None) -> None:
    from app.investment.storage import LATEST_DIR

    ensure_dirs()
    base = root or LATEST_DIR
    base.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch for ch in snap.asset.symbol.upper() if ch.isalnum() or ch in ".-^")
    (base / f"{safe}.json").write_text(json.dumps(snap.as_dict(), default=str), encoding="utf-8")


def load_latest_snapshot(symbol: str, root: Optional[Path] = None) -> Optional[InvestmentSnapshot]:
    from app.investment.storage import LATEST_DIR

    base = root or LATEST_DIR
    safe = "".join(ch for ch in str(symbol or "").upper() if ch.isalnum() or ch in ".-^")
    p = base / f"{safe}.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return snapshot_from_dict(data)
