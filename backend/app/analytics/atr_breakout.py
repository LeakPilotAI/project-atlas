"""ATR channel / Keltner-style breakout helpers for Project Atlas.

Uses close series (optional high/low) to build EMA ± k*ATR bands and
classify breakout state for perps and day-trade coaching.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence


@dataclass
class ATRChannelSignal:
    symbol: str = ""
    mid: float = 0.0
    upper: float = 0.0
    lower: float = 0.0
    atr: float = 0.0
    atr_pct: float = 0.0
    price: float = 0.0
    state: str = "inside"  # inside | break_up | break_down | near_upper | near_lower
    direction: str = "none"  # long | short | none
    k: float = 2.0
    stop_long: Optional[float] = None
    stop_short: Optional[float] = None
    tp1_long: Optional[float] = None
    tp2_long: Optional[float] = None
    tp1_short: Optional[float] = None
    tp2_short: Optional[float] = None
    reasons: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


def _ema(values: Sequence[float], period: int) -> list[float]:
    if not values or period < 1:
        return []
    k = 2.0 / (period + 1)
    out: list[float] = []
    ema_val = float(values[0])
    for v in values:
        ema_val = float(v) * k + ema_val * (1.0 - k)
        out.append(ema_val)
    return out


def true_range_series(
    closes: Sequence[float],
    highs: Optional[Sequence[float]] = None,
    lows: Optional[Sequence[float]] = None,
) -> list[float]:
    n = len(closes)
    if n < 2:
        return []
    use_hl = (
        highs is not None
        and lows is not None
        and len(highs) == n
        and len(lows) == n
    )
    trs: list[float] = []
    for i in range(1, n):
        c = float(closes[i])
        prev = float(closes[i - 1])
        if use_hl:
            h = float(highs[i])  # type: ignore[index]
            l = float(lows[i])  # type: ignore[index]
            tr = max(h - l, abs(h - prev), abs(l - prev))
        else:
            tr = abs(c - prev)
        trs.append(tr)
    return trs


def atr_wilder(
    closes: Sequence[float],
    highs: Optional[Sequence[float]] = None,
    lows: Optional[Sequence[float]] = None,
    period: int = 14,
) -> Optional[float]:
    """Wilder RMA of true range (classic ATR)."""
    trs = true_range_series(closes, highs, lows)
    if len(trs) < period:
        if not trs:
            return None
        return sum(trs) / len(trs)
    # Seed with SMA of first `period` TRs
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


def atr_channel(
    closes: Sequence[float],
    highs: Optional[Sequence[float]] = None,
    lows: Optional[Sequence[float]] = None,
    ema_period: int = 20,
    atr_period: int = 14,
    k: float = 2.0,
) -> tuple[float, float, float, float]:
    """
    Returns (mid, upper, lower, atr).
    mid = EMA(ema_period), bands = mid ± k*ATR.
    """
    closes_f = [float(c) for c in closes]
    if len(closes_f) < max(5, atr_period // 2):
        last = closes_f[-1] if closes_f else 0.0
        return last, last, last, 0.0

    ema = _ema(closes_f, ema_period)
    mid = ema[-1] if ema else closes_f[-1]
    atr = atr_wilder(closes_f, highs, lows, period=atr_period) or 0.0
    upper = mid + k * atr
    lower = mid - k * atr
    return mid, upper, lower, atr


def evaluate_atr_breakout(
    closes: Sequence[float],
    highs: Optional[Sequence[float]] = None,
    lows: Optional[Sequence[float]] = None,
    *,
    symbol: str = "",
    ema_period: int = 20,
    atr_period: int = 14,
    k: float = 2.0,
    stop_mult: float = 2.0,
    tp1_mult: float = 1.5,
    tp2_mult: float = 3.0,
    near_pct: float = 0.15,
    regime_name: Optional[str] = None,
) -> ATRChannelSignal:
    """
    Classify price vs ATR channel and suggest levels.

    state:
      break_up / break_down — close outside band
      near_upper / near_lower — within near_pct * ATR of band
      inside — neutral
    """
    closes_f = [float(c) for c in closes if c is not None]
    if not closes_f:
        return ATRChannelSignal(symbol=symbol, reasons=["no closes"])

    price = closes_f[-1]
    mid, upper, lower, atr = atr_channel(
        closes_f, highs, lows, ema_period=ema_period, atr_period=atr_period, k=k
    )
    atr_pct = (atr / price * 100.0) if price > 0 and atr > 0 else 0.0

    reasons: list[str] = []
    state = "inside"
    direction = "none"

    if atr <= 0:
        reasons.append("ATR unavailable")
        return ATRChannelSignal(
            symbol=symbol,
            mid=mid,
            upper=upper,
            lower=lower,
            atr=atr,
            atr_pct=atr_pct,
            price=price,
            state="inside",
            k=k,
            reasons=reasons,
        )

    # Breakout classification
    if price > upper:
        state = "break_up"
        direction = "long"
        reasons.append(f"Close above upper band ({upper:.6g})")
    elif price < lower:
        state = "break_down"
        direction = "short"
        reasons.append(f"Close below lower band ({lower:.6g})")
    elif price >= upper - near_pct * atr:
        state = "near_upper"
        reasons.append("Price near upper ATR band")
    elif price <= lower + near_pct * atr:
        state = "near_lower"
        reasons.append("Price near lower ATR band")
    else:
        reasons.append("Price inside ATR channel")

    # Regime filter notes (caller can hard-block)
    if regime_name:
        rn = regime_name.lower()
        if state == "break_up" and "trend_down" in rn:
            reasons.append("Counter-regime: break_up vs trend_down")
        if state == "break_down" and "trend_up" in rn:
            reasons.append("Counter-regime: break_down vs trend_up")
        if "range" in rn and state in ("break_up", "break_down"):
            reasons.append("Range regime — breakout less reliable")
        if "expansion" in rn:
            reasons.append("Vol expansion — widen risk / size down")

    stop_long = price - stop_mult * atr if direction == "long" else mid - stop_mult * atr
    stop_short = price + stop_mult * atr if direction == "short" else mid + stop_mult * atr
    tp1_long = price + tp1_mult * atr
    tp2_long = price + tp2_mult * atr
    tp1_short = price - tp1_mult * atr
    tp2_short = price - tp2_mult * atr

    return ATRChannelSignal(
        symbol=symbol,
        mid=round(mid, 8),
        upper=round(upper, 8),
        lower=round(lower, 8),
        atr=round(atr, 8),
        atr_pct=round(atr_pct, 4),
        price=round(price, 8),
        state=state,
        direction=direction,
        k=k,
        stop_long=round(stop_long, 8),
        stop_short=round(stop_short, 8),
        tp1_long=round(tp1_long, 8),
        tp2_long=round(tp2_long, 8),
        tp1_short=round(tp1_short, 8),
        tp2_short=round(tp2_short, 8),
        reasons=reasons,
        details={
            "ema_period": ema_period,
            "atr_period": atr_period,
            "stop_mult": stop_mult,
            "tp1_mult": tp1_mult,
            "tp2_mult": tp2_mult,
            "regime": regime_name,
        },
    )


def levels_from_atr(
    price: float,
    atr: float,
    *,
    side: str = "long",
    stop_mult: float = 2.0,
    tp1_mult: float = 1.5,
    tp2_mult: float = 3.0,
) -> dict[str, float]:
    """Simple stop/TP ladder from a known price + ATR (day-trade coach)."""
    if atr <= 0 or price <= 0:
        return {}
    side = side.lower()
    if side == "short":
        return {
            "stop": round(price + stop_mult * atr, 8),
            "tp1": round(price - tp1_mult * atr, 8),
            "tp2": round(price - tp2_mult * atr, 8),
            "risk": round(stop_mult * atr, 8),
        }
    return {
        "stop": round(price - stop_mult * atr, 8),
        "tp1": round(price + tp1_mult * atr, 8),
        "tp2": round(price + tp2_mult * atr, 8),
        "risk": round(stop_mult * atr, 8),
    }


def signal_from_candles(
    candles: Sequence[dict[str, Any]],
    *,
    symbol: str = "",
    k: float = 2.0,
    regime_name: Optional[str] = None,
) -> ATRChannelSignal:
    """Convenience: candle dicts with open/high/low/close or o/h/l/c."""
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
        return ATRChannelSignal(symbol=symbol, reasons=["empty candles"])
    # If highs/lows missing/zero, pass None so ATR falls back to close-to-close
    if not any(highs) or not any(lows):
        return evaluate_atr_breakout(
            closes, symbol=symbol, k=k, regime_name=regime_name
        )
    return evaluate_atr_breakout(
        closes,
        highs,
        lows,
        symbol=symbol,
        k=k,
        regime_name=regime_name,
    )