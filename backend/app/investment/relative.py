"""Relative performance vs stored benchmark/sector bars. Never invents prints."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from app.investment.bars import OhlcvBar
from app.investment.enums import DataQuality


def _close(bar: Optional[OhlcvBar]) -> Optional[float]:
    if bar is None:
        return None
    for v in (bar.adjusted_close, bar.close):
        if v is None:
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if x > 0:
            return x
    return None


def period_return(bars: Sequence[OhlcvBar], sessions: int) -> Optional[float]:
    """Close-to-close return over `sessions` completed bars. None if history is short."""
    if sessions <= 0 or len(bars) < sessions + 1:
        return None
    last = _close(bars[-1])
    prev = _close(bars[-1 - sessions])
    if last is None or prev is None or prev <= 0:
        return None
    return last / prev - 1.0


def aligned_return(
    asset: Sequence[OhlcvBar],
    bench: Sequence[OhlcvBar],
    sessions: int,
) -> Optional[float]:
    """Asset return minus benchmark return over the same session count.

    Uses each series' own last N sessions (operator stores both). Does not
    invent missing dates. If either leg is missing, result is None.
    """
    a = period_return(asset, sessions)
    b = period_return(bench, sessions)
    if a is None or b is None:
        return None
    return a - b


@dataclass
class RelativeReport:
    asset: str = ""
    spy_symbol: str = ""
    qqq_symbol: str = ""
    sector_symbol: str = ""
    asset_1d: Optional[float] = None
    asset_5d: Optional[float] = None
    asset_20d: Optional[float] = None
    spy_1d: Optional[float] = None
    qqq_1d: Optional[float] = None
    sector_1d: Optional[float] = None
    vs_spy_1d: Optional[float] = None
    vs_qqq_1d: Optional[float] = None
    vs_sector_1d: Optional[float] = None
    vs_spy_5d: Optional[float] = None
    vs_qqq_5d: Optional[float] = None
    vs_sector_5d: Optional[float] = None
    quality: DataQuality = DataQuality.UNKNOWN
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {
            "asset": self.asset,
            "spy_symbol": self.spy_symbol,
            "qqq_symbol": self.qqq_symbol,
            "sector_symbol": self.sector_symbol,
            "asset_1d": self.asset_1d,
            "asset_5d": self.asset_5d,
            "asset_20d": self.asset_20d,
            "spy_1d": self.spy_1d,
            "qqq_1d": self.qqq_1d,
            "sector_1d": self.sector_1d,
            "vs_spy_1d": self.vs_spy_1d,
            "vs_qqq_1d": self.vs_qqq_1d,
            "vs_sector_1d": self.vs_sector_1d,
            "vs_spy_5d": self.vs_spy_5d,
            "vs_qqq_5d": self.vs_qqq_5d,
            "vs_sector_5d": self.vs_sector_5d,
            "quality": self.quality.value,
            "notes": list(self.notes),
        }


def relative_report(
    *,
    symbol: str,
    asset_bars: Sequence[OhlcvBar],
    spy_bars: Sequence[OhlcvBar] = (),
    qqq_bars: Sequence[OhlcvBar] = (),
    sector_bars: Sequence[OhlcvBar] = (),
    spy_symbol: str = "",
    qqq_symbol: str = "",
    sector_symbol: str = "",
) -> RelativeReport:
    notes: List[str] = []
    rep = RelativeReport(
        asset=symbol,
        spy_symbol=spy_symbol,
        qqq_symbol=qqq_symbol,
        sector_symbol=sector_symbol,
    )
    rep.asset_1d = period_return(asset_bars, 1)
    rep.asset_5d = period_return(asset_bars, 5)
    rep.asset_20d = period_return(asset_bars, 20)
    if spy_bars:
        rep.spy_1d = period_return(spy_bars, 1)
        rep.vs_spy_1d = aligned_return(asset_bars, spy_bars, 1)
        rep.vs_spy_5d = aligned_return(asset_bars, spy_bars, 5)
    else:
        notes.append("SPY bars missing — market-relative UNKNOWN")
    if qqq_bars:
        rep.qqq_1d = period_return(qqq_bars, 1)
        rep.vs_qqq_1d = aligned_return(asset_bars, qqq_bars, 1)
        rep.vs_qqq_5d = aligned_return(asset_bars, qqq_bars, 5)
    else:
        notes.append("QQQ bars missing — growth-relative UNKNOWN")
    if sector_bars:
        rep.sector_1d = period_return(sector_bars, 1)
        rep.vs_sector_1d = aligned_return(asset_bars, sector_bars, 1)
        rep.vs_sector_5d = aligned_return(asset_bars, sector_bars, 5)
    else:
        notes.append("sector ETF bars missing — sector-relative UNKNOWN")

    present = [rep.vs_spy_1d, rep.vs_qqq_1d, rep.vs_sector_1d]
    if all(v is None for v in present):
        rep.quality = DataQuality.MISSING
    elif any(v is None for v in present):
        rep.quality = DataQuality.UNKNOWN
    else:
        rep.quality = DataQuality.FRESH
    if rep.asset_1d is None:
        notes.append("asset 1D return UNKNOWN")
        if rep.quality is DataQuality.FRESH:
            rep.quality = DataQuality.UNKNOWN
    rep.notes = notes
    return rep
