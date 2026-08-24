"""Technical indicators for Atlas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass
class IndicatorResult:
    rsi: Optional[float] = None
    ema9: Optional[float] = None
    ema21: Optional[float] = None
    sma20: Optional[float] = None
    volume_spike: Optional[float] = None
    atr: Optional[float] = None


def _ema(values: Sequence[float], period: int) -> Optional[float]:
    if not values or len(values) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return float(ema)


def _sma(values: Sequence[float], period: int) -> Optional[float]:
    if not values or len(values) < period:
        return None
    return float(sum(values[-period:]) / period)


def _rsi(closes: Sequence[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for i in range(-period, 0):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def atr_proxy(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> Optional[float]:
    """Average True Range proxy from high/low/close series."""
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        # Fallback: use close-to-close range if HL not available
        if len(closes) < period + 1:
            return None
        ranges = [abs(closes[i] - closes[i - 1]) for i in range(-period, 0)]
        return float(sum(ranges) / period)

    trs: list[float] = []
    for i in range(n - period, n):
        if i <= 0:
            continue
        high = float(highs[i])
        low = float(lows[i])
        prev_close = float(closes[i - 1])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    if not trs:
        return None
    return float(sum(trs[-period:]) / min(period, len(trs)))


def atr_from_closes(closes: Sequence[float], period: int = 14) -> Optional[float]:
    """ATR-style volatility when only closes exist."""
    if len(closes) < period + 1:
        return None
    ranges = [abs(closes[i] - closes[i - 1]) for i in range(-period, 0)]
    return float(sum(ranges) / period)


def volume_spike_ratio(volumes: Sequence[float], lookback: int = 20) -> Optional[float]:
    if len(volumes) < lookback:
        return None
    window = [float(v) for v in volumes[-lookback:]]
    last = window[-1]
    avg = sum(window[:-1]) / max(1, lookback - 1)
    if avg <= 0:
        return None
    return last / avg


def compute_indicators(
    closes: Sequence[float],
    volumes: Optional[Sequence[float]] = None,
    highs: Optional[Sequence[float]] = None,
    lows: Optional[Sequence[float]] = None,
) -> IndicatorResult:
    volumes = volumes or []
    spike = volume_spike_ratio(volumes) if volumes else None

    atr = None
    if highs is not None and lows is not None:
        atr = atr_proxy(highs, lows, closes)
    if atr is None:
        atr = atr_from_closes(closes)

    return IndicatorResult(
        rsi=_rsi(closes),
        ema9=_ema(closes, 9),
        ema21=_ema(closes, 21),
        sma20=_sma(closes, 20),
        volume_spike=spike,
        atr=atr,
    )


# Aliases older modules may import
def rsi(closes: Sequence[float], period: int = 14) -> Optional[float]:
    return _rsi(closes, period)


def ema(values: Sequence[float], period: int) -> Optional[float]:
    return _ema(values, period)


def sma(values: Sequence[float], period: int) -> Optional[float]:
    return _sma(values, period)