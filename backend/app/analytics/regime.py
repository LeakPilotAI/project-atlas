"""Market regime detection for Project Atlas.

Labels:
  trend_up   — directional upside with strength
  trend_down — directional downside with strength
  range      — weak direction / chop
  expansion  — elevated volatility (risk override)

Used by evaluate_setup / scanner via detect_regime(closes) or
detect_regime(closes, highs=..., lows=...).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence


@dataclass
class RegimeResult:
    name: str  # trend_up | trend_down | range | expansion
    strength: float  # 0–100
    vol_state: str  # low | normal | high
    efficiency: float  # 0–1 Kaufman-style efficiency
    slope_fast: float  # short return %
    slope_slow: float  # longer return %
    atr_pct: Optional[float] = None
    details: dict[str, Any] | None = None

    # Back-compat aliases
    @property
    def regime(self) -> str:
        return self.name


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


def _pct(a: float, b: float) -> float:
    if a == 0:
        return 0.0
    return (b / a - 1.0) * 100.0


def _efficiency_ratio(closes: Sequence[float], window: int = 20) -> float:
    """Kaufman efficiency: |net move| / sum(|bar moves|). 1 = pure trend, ~0 = noise."""
    if len(closes) < window + 1:
        window = max(2, len(closes) - 1)
    if window < 2 or len(closes) < 2:
        return 0.0
    segment = [float(x) for x in closes[-(window + 1) :]]
    net = abs(segment[-1] - segment[0])
    path = 0.0
    for i in range(1, len(segment)):
        path += abs(segment[i] - segment[i - 1])
    if path <= 1e-12:
        return 0.0
    return max(0.0, min(1.0, net / path))


def _atr_proxy(
    closes: Sequence[float],
    highs: Optional[Sequence[float]] = None,
    lows: Optional[Sequence[float]] = None,
    period: int = 14,
) -> Optional[float]:
    """Average true-range style proxy. Falls back to close-to-close range if no H/L."""
    n = len(closes)
    if n < 2:
        return None
    period = min(period, n - 1)
    trs: list[float] = []
    for i in range(-period, 0):
        c = float(closes[i])
        prev = float(closes[i - 1])
        if highs is not None and lows is not None and len(highs) == n and len(lows) == n:
            h = float(highs[i])
            l = float(lows[i])
            tr = max(h - l, abs(h - prev), abs(l - prev))
        else:
            tr = abs(c - prev)
        trs.append(tr)
    if not trs:
        return None
    return sum(trs) / len(trs)


def _atr_percentile(
    closes: Sequence[float],
    atr: float,
    lookback: int = 60,
    highs: Optional[Sequence[float]] = None,
    lows: Optional[Sequence[float]] = None,
) -> Optional[float]:
    """Where current ATR sits vs recent ATR series (0–100)."""
    n = len(closes)
    if n < 20 or atr <= 0:
        return None
    lookback = min(lookback, n - 2)
    series: list[float] = []
    for end in range(n - lookback, n):
        sub_c = closes[: end + 1]
        sub_h = highs[: end + 1] if highs is not None else None
        sub_l = lows[: end + 1] if lows is not None else None
        a = _atr_proxy(sub_c, sub_h, sub_l, period=14)
        if a is not None:
            series.append(a)
    if len(series) < 5:
        return None
    below = sum(1 for x in series if x <= atr)
    return 100.0 * below / len(series)


def detect_regime(
    closes: Sequence[float],
    highs: Optional[Sequence[float]] = None,
    lows: Optional[Sequence[float]] = None,
    volumes: Optional[Sequence[float]] = None,  # reserved
    **kwargs: Any,
) -> RegimeResult:
    """
    Detect market regime from close series (optionally highs/lows).

    Returns RegimeResult with:
      name: trend_up | trend_down | range | expansion
      strength: 0–100
      vol_state: low | normal | high
    """
    closes_f = [float(c) for c in closes if c is not None]
    if len(closes_f) < 5:
        return RegimeResult(
            name="range",
            strength=0.0,
            vol_state="normal",
            efficiency=0.0,
            slope_fast=0.0,
            slope_slow=0.0,
            details={"reason": "insufficient_bars"},
        )

    ema_fast = _ema(closes_f, 9)
    ema_slow = _ema(closes_f, 21)
    last = closes_f[-1]
    e9 = ema_fast[-1] if ema_fast else last
    e21 = ema_slow[-1] if ema_slow else last

    slope_fast = _pct(closes_f[-min(6, len(closes_f))], last)
    slope_slow = _pct(closes_f[-min(21, len(closes_f))], last)
    efficiency = _efficiency_ratio(closes_f, window=min(20, len(closes_f) - 1))

    atr = _atr_proxy(closes_f, highs, lows, period=14)
    atr_pct = (atr / last * 100.0) if atr and last > 0 else None
    atr_rank = _atr_percentile(closes_f, atr, 60, highs, lows) if atr else None

    # Volatility state
    vol_state = "normal"
    if atr_rank is not None:
        if atr_rank >= 80:
            vol_state = "high"
        elif atr_rank <= 25:
            vol_state = "low"
    elif atr_pct is not None:
        if atr_pct >= 3.5:
            vol_state = "high"
        elif atr_pct <= 0.8:
            vol_state = "low"

    # Direction from EMA stack + slow slope
    bullish = e9 > e21 and slope_slow > 0.4
    bearish = e9 < e21 and slope_slow < -0.4

    # Strength: blend |slow slope|, efficiency, EMA separation
    ema_sep = abs(_pct(e21, e9)) if e21 else 0.0
    strength = min(
        100.0,
        abs(slope_slow) * 4.0 + efficiency * 40.0 + ema_sep * 3.0,
    )

    # Expansion overrides when vol is extreme (risk flag for decision engine)
    if vol_state == "high" and (atr_rank is not None and atr_rank >= 90 or (atr_pct or 0) >= 5.0):
        name = "expansion"
        # Keep directional hint in details
        bias = "up" if bullish or slope_slow > 0 else ("down" if bearish or slope_slow < 0 else "flat")
    elif bullish and strength >= 25 and efficiency >= 0.25:
        name = "trend_up"
    elif bearish and strength >= 25 and efficiency >= 0.25:
        name = "trend_down"
    elif bullish and strength >= 18:
        name = "trend_up"
    elif bearish and strength >= 18:
        name = "trend_down"
    else:
        name = "range"
        bias = "flat"

    if name != "expansion":
        bias = "up" if name == "trend_up" else ("down" if name == "trend_down" else "flat")

    return RegimeResult(
        name=name,
        strength=round(strength, 1),
        vol_state=vol_state,
        efficiency=round(efficiency, 3),
        slope_fast=round(slope_fast, 3),
        slope_slow=round(slope_slow, 3),
        atr_pct=round(atr_pct, 3) if atr_pct is not None else None,
        details={
            "ema9": round(e9, 8),
            "ema21": round(e21, 8),
            "atr_rank": round(atr_rank, 1) if atr_rank is not None else None,
            "bias": bias,
            "bars": len(closes_f),
        },
    )


# Convenience: string-only callers
def regime_name(closes: Sequence[float], **kwargs: Any) -> str:
    return detect_regime(closes, **kwargs).name


def normalize_regime(value: Any) -> str:
    """Map detector output / free text to research buckets. Does not change strategy."""
    if value is None:
        return "UNKNOWN"
    if isinstance(value, RegimeResult):
        if value.name == "expansion" or value.vol_state == "high":
            return "HIGH_VOLATILITY"
        if value.name == "range" and value.vol_state == "low":
            return "LOW_VOLATILITY"
        value = value.name
    s = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if not s or s in ("none", "n/a", "na"):
        return "UNKNOWN"
    mapping = {
        "trend_up": "TREND_UP",
        "trendup": "TREND_UP",
        "uptrend": "TREND_UP",
        "bull": "TREND_UP",
        "trend_down": "TREND_DOWN",
        "trenddown": "TREND_DOWN",
        "downtrend": "TREND_DOWN",
        "bear": "TREND_DOWN",
        "range": "RANGE",
        "ranging": "RANGE",
        "chop": "RANGE",
        "expansion": "HIGH_VOLATILITY",
        "high_volatility": "HIGH_VOLATILITY",
        "high_vol": "HIGH_VOLATILITY",
        "low_volatility": "LOW_VOLATILITY",
        "low_vol": "LOW_VOLATILITY",
        "unknown": "UNKNOWN",
    }
    if s in mapping:
        return mapping[s]
    su = s.upper()
    if su in {
        "TREND_UP",
        "TREND_DOWN",
        "RANGE",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "UNKNOWN",
    }:
        return su
    return "UNKNOWN"