"""Bollinger Band squeeze detection for Project Atlas.

Squeeze = BB width inside (or near) Keltner / ATR channel width.
Release = first expansion bar in direction of break.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from app.analytics.atr_breakout import atr_wilder, _ema


@dataclass
class SqueezeSignal:
    symbol: str = ""
    squeeze_on: bool = False
    squeeze_off: bool = False  # just released this bar
    direction: str = "none"  # long | short | none (bias on release)
    bb_mid: float = 0.0
    bb_upper: float = 0.0
    bb_lower: float = 0.0
    bb_width: float = 0.0
    kc_upper: float = 0.0
    kc_lower: float = 0.0
    kc_width: float = 0.0
    width_ratio: float = 0.0  # bb_width / kc_width (<1 ≈ squeeze)
    atr: float = 0.0
    price: float = 0.0
    momentum: float = 0.0  # simple close vs mid
    reasons: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


def _sma(values: Sequence[float], period: int) -> list[float]:
    out: list[float] = []
    for i in range(len(values)):
        if i + 1 < period:
            out.append(sum(values[: i + 1]) / (i + 1))
        else:
            window = values[i + 1 - period : i + 1]
            out.append(sum(window) / period)
    return out


def _stdev(values: Sequence[float], period: int) -> list[float]:
    out: list[float] = []
    for i in range(len(values)):
        if i + 1 < 2:
            out.append(0.0)
            continue
        p = min(period, i + 1)
        window = [float(x) for x in values[i + 1 - p : i + 1]]
        mean = sum(window) / len(window)
        var = sum((x - mean) ** 2 for x in window) / len(window)
        out.append(var ** 0.5)
    return out


def evaluate_squeeze(
    closes: Sequence[float],
    highs: Optional[Sequence[float]] = None,
    lows: Optional[Sequence[float]] = None,
    *,
    symbol: str = "",
    bb_period: int = 20,
    bb_std: float = 2.0,
    kc_ema_period: int = 20,
    kc_atr_period: int = 14,
    kc_mult: float = 1.5,
    prev_squeeze_on: Optional[bool] = None,
) -> SqueezeSignal:
    """
    Detect Bollinger squeeze vs Keltner (ATR) channel.

    squeeze_on  → BB fully inside KC (compression)
    squeeze_off → was on, now off (release) — use momentum for bias
    """
    closes_f = [float(c) for c in closes if c is not None]
    if len(closes_f) < max(bb_period, kc_ema_period, kc_atr_period) + 2:
        return SqueezeSignal(symbol=symbol, reasons=["insufficient bars"])

    price = closes_f[-1]
    mid_series = _sma(closes_f, bb_period)
    std_series = _stdev(closes_f, bb_period)
    mid = mid_series[-1]
    std = std_series[-1]
    bb_upper = mid + bb_std * std
    bb_lower = mid - bb_std * std
    bb_width = bb_upper - bb_lower

    ema = _ema(closes_f, kc_ema_period)
    kc_mid = ema[-1] if ema else mid
    atr = atr_wilder(closes_f, highs, lows, period=kc_atr_period) or 0.0
    kc_upper = kc_mid + kc_mult * atr
    kc_lower = kc_mid - kc_mult * atr
    kc_width = kc_upper - kc_lower

    width_ratio = (bb_width / kc_width) if kc_width > 1e-12 else 1.0
    squeeze_on = bb_upper < kc_upper and bb_lower > kc_lower

    # Historical squeeze one bar ago (approx using prior closes)
    prev_on = prev_squeeze_on
    if prev_on is None and len(closes_f) > bb_period + 3:
        prev = evaluate_squeeze(
            closes_f[:-1],
            highs[:-1] if highs is not None else None,
            lows[:-1] if lows is not None else None,
            symbol=symbol,
            bb_period=bb_period,
            bb_std=bb_std,
            kc_ema_period=kc_ema_period,
            kc_atr_period=kc_atr_period,
            kc_mult=kc_mult,
            prev_squeeze_on=False,  # stop recursion depth
        )
        prev_on = prev.squeeze_on

    squeeze_off = bool(prev_on) and not squeeze_on

    momentum = price - mid
    direction = "none"
    reasons: list[str] = []

    if squeeze_on:
        reasons.append(
            f"Squeeze ON (BB inside KC, width_ratio={width_ratio:.3f})"
        )
    elif squeeze_off:
        direction = "long" if momentum > 0 else "short"
        reasons.append(
            f"Squeeze RELEASE → bias {direction.upper()} (mom={momentum:.6g})"
        )
    else:
        reasons.append(f"No squeeze (width_ratio={width_ratio:.3f})")

    return SqueezeSignal(
        symbol=symbol,
        squeeze_on=squeeze_on,
        squeeze_off=squeeze_off,
        direction=direction,
        bb_mid=round(mid, 8),
        bb_upper=round(bb_upper, 8),
        bb_lower=round(bb_lower, 8),
        bb_width=round(bb_width, 8),
        kc_upper=round(kc_upper, 8),
        kc_lower=round(kc_lower, 8),
        kc_width=round(kc_width, 8),
        width_ratio=round(width_ratio, 4),
        atr=round(atr, 8),
        price=round(price, 8),
        momentum=round(momentum, 8),
        reasons=reasons,
        details={
            "bb_period": bb_period,
            "bb_std": bb_std,
            "kc_mult": kc_mult,
        },
    )


def signal_from_candles(
    candles: Sequence[dict[str, Any]],
    *,
    symbol: str = "",
) -> SqueezeSignal:
    closes: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    for c in candles:
        try:
            closes.append(float(c.get("close", c.get("c", 0)) or 0))
            highs.append(float(c.get("high", c.get("h", 0)) or 0))
            lows.append(float(c.get("low", c.get("l", 0)) or 0))
        except (TypeError, ValueError):
            continue
    if not closes:
        return SqueezeSignal(symbol=symbol, reasons=["empty candles"])
    if not any(highs) or not any(lows):
        return evaluate_squeeze(closes, symbol=symbol)
    return evaluate_squeeze(closes, highs, lows, symbol=symbol)