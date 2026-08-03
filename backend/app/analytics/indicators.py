from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass
class IndicatorResult:
    symbol: str
    price: float
    ema_9: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    ema_200: Optional[float] = None
    rsi_14: Optional[float] = None
    atr_14: Optional[float] = None
    volume_sma_20: Optional[float] = None
    relative_volume: Optional[float] = None
    volatility: Optional[float] = None
    zscore_price: Optional[float] = None


def ema(series: list[float], period: int) -> Optional[float]:
    if len(series) < period:
        return None
    weights = np.exp(np.linspace(-1.0, 0.0, period))
    weights /= weights.sum()
    return float(np.convolve(series[-period:], weights, mode="valid")[-1])


def rsi(closes: list[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    return float(np.mean(trs[-period:]))


def relative_volume(current_volume: float, volume_history: list[float], period: int = 20) -> Optional[float]:
    if len(volume_history) < period:
        return None
    avg = np.mean(volume_history[-period:])
    if avg == 0:
        return None
    return float(current_volume / avg)


def zscore(series: list[float], period: int = 20) -> Optional[float]:
    if len(series) < period:
        return None
    window = series[-period:]
    mean = np.mean(window)
    std = np.std(window)
    if std == 0:
        return 0.0
    return float((series[-1] - mean) / std)


def calculate_basic_indicators(
    symbol: str,
    closes: list[float],
    volumes: list[float],
    highs: Optional[list[float]] = None,
    lows: Optional[list[float]] = None,
) -> IndicatorResult:
    """
    Calculate a core set of indicators from price/volume history.
    For now we accept simple lists. Later we will feed real candle data.
    """
    price = closes[-1] if closes else 0.0

    result = IndicatorResult(
        symbol=symbol,
        price=price,
        ema_9=ema(closes, 9),
        ema_20=ema(closes, 20),
        ema_50=ema(closes, 50),
        ema_200=ema(closes, 200),
        rsi_14=rsi(closes, 14),
        relative_volume=relative_volume(volumes[-1], volumes, 20) if volumes else None,
        zscore_price=zscore(closes, 20),
    )

    if highs and lows and len(highs) == len(closes) and len(lows) == len(closes):
        result.atr_14 = atr(highs, lows, closes, 14)

    if len(closes) >= 20:
        result.volatility = float(np.std(closes[-20:]) / np.mean(closes[-20:]) * 100)

    return result