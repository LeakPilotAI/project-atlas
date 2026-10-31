from __future__ import annotations

from dataclasses import dataclass
from math import log10
from statistics import mean, pstdev
from typing import Any, Iterable, Sequence

from .models import Side


@dataclass(frozen=True)
class StructureSnapshot:
    side: Side | None
    confidence: float
    volatility_pct: float
    momentum_pct: float
    trend_pct: float
    reason: str


@dataclass(frozen=True)
class RankedPerpSetup:
    symbol: str
    side: Side
    score: float
    price: float
    volume_24h: float
    open_interest: float
    funding_rate: float | None
    volatility_pct: float
    momentum_pct: float
    trend_pct: float
    reason: str


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def analyze_candles(candles: Sequence[dict[str, Any]]) -> StructureSnapshot:
    closes = [float(c.get("close") or 0.0) for c in candles if float(c.get("close") or 0.0) > 0]
    if len(closes) < 20:
        return StructureSnapshot(None, 0.0, 0.0, 0.0, 0.0, "insufficient candle history")

    returns = [((closes[i] / closes[i - 1]) - 1.0) * 100.0 for i in range(1, len(closes)) if closes[i - 1] > 0]
    volatility = pstdev(returns[-20:]) if len(returns) >= 2 else 0.0
    momentum = ((closes[-1] / closes[-5]) - 1.0) * 100.0 if len(closes) >= 5 else 0.0
    fast = mean(closes[-5:])
    slow = mean(closes[-20:])
    trend = ((fast / slow) - 1.0) * 100.0 if slow > 0 else 0.0

    # Require momentum and local trend to agree. This is a discovery heuristic,
    # not a profitability claim or live-trading authorization.
    side: Side | None = None
    if trend >= 0.20 and momentum >= 0.10:
        side = Side.LONG
    elif trend <= -0.20 and momentum <= -0.10:
        side = Side.SHORT

    directional_strength = min(30.0, abs(trend) * 10.0 + abs(momentum) * 5.0)
    vol_quality = 15.0 if 0.15 <= volatility <= 2.5 else max(0.0, 15.0 - abs(volatility - 1.0) * 5.0)
    confidence = _clamp(45.0 + directional_strength + vol_quality, 0.0, 90.0) if side else 0.0
    reason = (
        f"5-bar momentum {momentum:+.2f}% · fast/slow trend {trend:+.2f}% · "
        f"20-bar return vol {volatility:.2f}%"
    )
    return StructureSnapshot(side, round(confidence, 2), round(volatility, 4), round(momentum, 4), round(trend, 4), reason)


def rank_setup(
    *,
    symbol: str,
    price: float,
    volume_24h: float,
    open_interest: float,
    funding_rate: float | None,
    structure: StructureSnapshot,
) -> RankedPerpSetup | None:
    if structure.side is None or price <= 0:
        return None

    # Liquidity/OI are capped log-scale quality terms so BTC-sized markets do not
    # completely swamp all other valid Hyperliquid markets.
    vol_score = _clamp((log10(max(volume_24h, 1.0)) - 5.0) * 7.0, 0.0, 22.0)
    oi_score = _clamp((log10(max(open_interest, 1.0)) - 4.5) * 7.0, 0.0, 18.0)
    structure_score = structure.confidence * 0.55

    funding_bonus = 0.0
    if funding_rate is not None:
        f = float(funding_rate)
        # Mildly reward setups that are not leaning into an obviously crowded side.
        if structure.side is Side.LONG and f <= 0:
            funding_bonus = min(5.0, abs(f) * 10000.0)
        elif structure.side is Side.SHORT and f >= 0:
            funding_bonus = min(5.0, abs(f) * 10000.0)
        elif abs(f) > 0.001:
            funding_bonus = -4.0

    score = _clamp(vol_score + oi_score + structure_score + funding_bonus, 0.0, 100.0)
    return RankedPerpSetup(
        symbol=str(symbol).upper(),
        side=structure.side,
        score=round(score, 2),
        price=float(price),
        volume_24h=float(volume_24h),
        open_interest=float(open_interest),
        funding_rate=None if funding_rate is None else float(funding_rate),
        volatility_pct=structure.volatility_pct,
        momentum_pct=structure.momentum_pct,
        trend_pct=structure.trend_pct,
        reason=structure.reason,
    )


def shortlist_markets(markets: Iterable[dict[str, Any]], *, limit: int = 10) -> list[dict[str, Any]]:
    rows = [dict(r) for r in markets if float(r.get("price") or 0.0) > 0]
    rows.sort(
        key=lambda r: (float(r.get("volume_24h") or 0.0), float(r.get("open_interest") or 0.0)),
        reverse=True,
    )
    return rows[: max(1, int(limit))]
