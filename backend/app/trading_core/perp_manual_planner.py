from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from .domains import require_hyperliquid_market
from .models import Side


@dataclass(frozen=True)
class ManualPerpPlan:
    symbol: str
    side: Side
    reference_price: float
    l1: float
    l2: float
    l3: float
    stop: float
    tp1: float
    tp2: float
    risk_per_unit: float
    target_rr: float
    note: str


def _positive(name: str, value: float) -> float:
    value = float(value)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def build_manual_perp_plan(
    *,
    symbol: str,
    side: Side,
    reference_price: float,
    volatility_pct: float,
    hyperliquid_symbols: Iterable[str],
    target_rr: float = 1.8,
) -> ManualPerpPlan:
    """Create a manual, layered limit plan for a verified Hyperliquid market.

    Pure research/planning function: it does not submit orders. Layer distances scale
    with observed volatility rather than using one fixed percentage across markets.
    """
    symbol = require_hyperliquid_market(symbol, hyperliquid_symbols)
    px = _positive("reference_price", reference_price)
    vol = _positive("volatility_pct", volatility_pct) / 100.0
    rr = _positive("target_rr", target_rr)

    # Conservative bounded spacing: avoid absurd ladders from noisy volatility inputs.
    step = min(max(vol * 0.35, 0.0025), 0.02)

    if side is Side.LONG:
        l1 = px * (1.0 - step)
        l2 = px * (1.0 - step * 2.0)
        l3 = px * (1.0 - step * 3.0)
        stop = px * (1.0 - step * 4.25)
        risk = l1 - stop
        tp1 = l1 + rr * risk
        tp2 = l1 + max(3.0, rr + 0.8) * risk
    elif side is Side.SHORT:
        l1 = px * (1.0 + step)
        l2 = px * (1.0 + step * 2.0)
        l3 = px * (1.0 + step * 3.0)
        stop = px * (1.0 + step * 4.25)
        risk = stop - l1
        tp1 = l1 - rr * risk
        tp2 = l1 - max(3.0, rr + 0.8) * risk
    else:
        raise ValueError(f"unsupported side: {side}")

    values: Tuple[float, ...] = (l1, l2, l3, stop, tp1, tp2, risk)
    if any(v <= 0 for v in values):
        raise ValueError("computed plan contains a non-positive price")

    return ManualPerpPlan(
        symbol=symbol,
        side=side,
        reference_price=px,
        l1=l1,
        l2=l2,
        l3=l3,
        stop=stop,
        tp1=tp1,
        tp2=tp2,
        risk_per_unit=risk,
        target_rr=rr,
        note=(
            "Manual-only Hyperliquid plan. Levels are planning references, not a "
            "guarantee of fill, profit, or recovery. Cancel/adjust if market structure changes."
        ),
    )
