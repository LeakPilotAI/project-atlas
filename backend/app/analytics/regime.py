from dataclasses import dataclass
from typing import List, Optional
import numpy as np


@dataclass
class MarketRegime:
    regime: str                  # trending | ranging | high_vol | low_vol
    trend_strength: float        # 0–100
    volatility: float            # annualized-ish %
    direction: str               # up | down | sideways
    confidence: float            # 0–100
    notes: str = ""


def detect_regime(
    closes: List[float],
    highs: List[float],
    lows: List[float],
    lookback: int = 30,
) -> MarketRegime:
    if len(closes) < lookback:
        return MarketRegime(
            regime="ranging",
            trend_strength=0.0,
            volatility=0.0,
            direction="sideways",
            confidence=0.0,
            notes="Insufficient data",
        )

    c = np.array(closes[-lookback:])
    h = np.array(highs[-lookback:])
    l = np.array(lows[-lookback:])

    # --- Volatility (simple ATR-style) ---
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    atr = float(np.mean(tr)) if len(tr) > 0 else 0.0
    volatility_pct = (atr / c[-1]) * 100 if c[-1] > 0 else 0.0

    # --- Trend strength via linear regression slope ---
    x = np.arange(len(c))
    slope, intercept = np.polyfit(x, c, 1)
    # Normalize slope by price
    norm_slope = (slope / c[-1]) * 100 if c[-1] > 0 else 0.0

    # R-squared for trend confidence
    y_pred = slope * x + intercept
    ss_res = np.sum((c - y_pred) ** 2)
    ss_tot = np.sum((c - np.mean(c)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    abs_slope = abs(norm_slope)
    trend_strength = min(100.0, abs_slope * 40 + r2 * 40)

    # Direction
    if norm_slope > 0.08:
        direction = "up"
    elif norm_slope < -0.08:
        direction = "down"
    else:
        direction = "sideways"

    # Regime classification
    if volatility_pct >= 4.5:
        regime = "high_vol"
    elif volatility_pct <= 1.2:
        regime = "low_vol"
    elif trend_strength >= 55 and direction != "sideways":
        regime = "trending"
    else:
        regime = "ranging"

    confidence = min(95.0, 40 + r2 * 40 + min(volatility_pct * 3, 20))

    notes = f"slope={norm_slope:.3f} | ATR%={volatility_pct:.2f} | R²={r2:.2f}"

    return MarketRegime(
        regime=regime,
        trend_strength=round(trend_strength, 1),
        volatility=round(volatility_pct, 2),
        direction=direction,
        confidence=round(confidence, 1),
        notes=notes,
    )