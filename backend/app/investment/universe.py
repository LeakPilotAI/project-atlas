"""Configurable investment universe. Engine does not depend on any ticker."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from app.investment.enums import AssetType
from app.investment.storage import PACKAGE_UNIVERSE_EXAMPLE, UNIVERSE_PATH, ensure_dirs

VALID_TYPES = {t.value for t in AssetType}


@dataclass
class UniverseEntry:
    symbol: str
    name: str = ""
    asset_type: AssetType = AssetType.UNKNOWN
    exchange: str = ""
    currency: str = "USD"
    sector: str = ""
    industry: str = ""
    active: bool = True
    groups: List[str] = field(default_factory=list)
    sector_etf: str = ""

    def __post_init__(self) -> None:
        self.symbol = str(self.symbol or "").upper().strip()


class InvestmentUniverse:
    def __init__(
        self,
        entries: Optional[List[UniverseEntry]] = None,
        *,
        sector_benchmarks: Optional[Dict[str, str]] = None,
        broad_benchmarks: Optional[Dict[str, str]] = None,
    ) -> None:
        self._by_symbol: Dict[str, UniverseEntry] = {}
        self.sector_benchmarks: Dict[str, str] = {
            str(k): str(v).upper() for k, v in (sector_benchmarks or {}).items() if v
        }
        self.broad_benchmarks: Dict[str, str] = {
            str(k): str(v).upper() for k, v in (broad_benchmarks or {}).items() if v
        }
        for e in entries or []:
            if e.symbol:
                self._by_symbol[e.symbol] = e

    def __len__(self) -> int:
        return len(self._by_symbol)

    def __iter__(self) -> Iterator[UniverseEntry]:
        return iter(self._by_symbol.values())

    def get(self, symbol: str) -> Optional[UniverseEntry]:
        return self._by_symbol.get(str(symbol or "").upper().strip())

    def symbols(self, *, active_only: bool = True) -> List[str]:
        out = []
        for e in self._by_symbol.values():
            if active_only and not e.active:
                continue
            out.append(e.symbol)
        return sorted(out)

    def add(self, entry: UniverseEntry) -> None:
        if not entry.symbol:
            return
        self._by_symbol[entry.symbol] = entry

    def by_group(self, group: str) -> List[UniverseEntry]:
        g = str(group or "").lower()
        return [e for e in self._by_symbol.values() if e.active and g in {x.lower() for x in e.groups}]

    def sector_etf_for(self, entry: UniverseEntry) -> str:
        if entry.sector_etf:
            return entry.sector_etf.upper()
        return self.sector_benchmarks.get(entry.sector, "")

    def spy_symbol(self) -> str:
        return self.broad_benchmarks.get("market") or self.broad_benchmarks.get("spy") or ""

    def qqq_symbol(self) -> str:
        return self.broad_benchmarks.get("growth") or self.broad_benchmarks.get("qqq") or ""

    def scan_order(self) -> List[UniverseEntry]:
        """Benchmarks first so relative comparisons have bars in the same cycle."""
        active = [e for e in self._by_symbol.values() if e.active]

        def rank(e: UniverseEntry) -> int:
            g = {x.lower() for x in e.groups}
            if "benchmark" in g:
                return 0
            if e.symbol in set(self.sector_benchmarks.values()) | set(self.broad_benchmarks.values()):
                return 1
            if "major" in g:
                return 2
            return 3

        return sorted(active, key=lambda e: (rank(e), e.symbol))


def _parse_type(raw: str) -> AssetType:
    s = str(raw or "UNKNOWN").upper().strip()
    if s in VALID_TYPES:
        return AssetType(s)
    return AssetType.UNKNOWN


def _entries_from_payload(data: object) -> List[UniverseEntry]:
    raw_list = data.get("assets") if isinstance(data, dict) else data
    if not isinstance(raw_list, list):
        return []
    entries: List[UniverseEntry] = []
    for row in raw_list:
        if not isinstance(row, dict) or not row.get("symbol"):
            continue
        entries.append(
            UniverseEntry(
                symbol=str(row["symbol"]),
                name=str(row.get("name") or ""),
                asset_type=_parse_type(str(row.get("asset_type") or "")),
                exchange=str(row.get("exchange") or ""),
                currency=str(row.get("currency") or "USD"),
                sector=str(row.get("sector") or ""),
                industry=str(row.get("industry") or ""),
                active=bool(row.get("active", True)),
                groups=[str(x) for x in (row.get("groups") or []) if x],
                sector_etf=str(row.get("sector_etf") or ""),
            )
        )
    return entries


def _from_payload(data: object) -> InvestmentUniverse:
    entries = _entries_from_payload(data)
    sector = {}
    broad = {}
    if isinstance(data, dict):
        sector = data.get("sector_benchmarks") or {}
        broad = data.get("broad_benchmarks") or {}
        if not isinstance(sector, dict):
            sector = {}
        if not isinstance(broad, dict):
            broad = {}
    return InvestmentUniverse(entries, sector_benchmarks=sector, broad_benchmarks=broad)


def load_universe(path: Optional[Path] = None) -> InvestmentUniverse:
    """Load operator universe. Missing/empty file → empty universe. No compiled tickers."""
    ensure_dirs()
    p = path or UNIVERSE_PATH
    if not p.exists():
        return InvestmentUniverse([])
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return InvestmentUniverse([])
    return _from_payload(data)


def load_example_universe() -> InvestmentUniverse:
    """Tracked representative sample (stocks, ETFs, index, sector ETFs). Not recommendations."""
    p = PACKAGE_UNIVERSE_EXAMPLE
    if not p.exists():
        return InvestmentUniverse([])
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return InvestmentUniverse([])
    return _from_payload(data)
