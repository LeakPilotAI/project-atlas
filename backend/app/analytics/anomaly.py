"""
Project Atlas — anomaly detection + AnomalySignal model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, pstdev
from typing import Any, Optional


@dataclass
class AnomalySignal:
    symbol: str
    alert_type: str = "anomaly"
    severity: str = "medium"  # low | medium | high
    title: str = ""
    message: str = ""
    opportunity_score: Optional[float] = None
    confidence_score: Optional[float] = None
    risk_score: Optional[float] = None
    price: Optional[float] = None
    indicators: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0  # 0-100 anomaly strength


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _returns(prices: list[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(prices)):
        a, b = prices[i - 1], prices[i]
        if a > 0:
            out.append((b / a) - 1.0)
    return out


def detect_anomalies(
    symbol: str = "",
    price: float = 0.0,
    volume_24h: float = 0.0,
    open_interest: float = 0.0,
    price_history: Optional[list[float]] = None,
    volume_history: Optional[list[float]] = None,
    **kwargs: Any,
) -> list[AnomalySignal]:
    """
    Detect statistically unusual price/volume behavior vs recent history.

    Returns a list of AnomalySignal (may be empty).
    Primary score is on signal.score (0-100).
    """
    prices = list(price_history or [])
    volumes = list(volume_history or [])

    # Allow alternate positional-style misuse without crashing
    if not prices and isinstance(symbol, list):
        prices = list(symbol)
        symbol = kwargs.get("symbol_name", "UNKNOWN")

    if len(prices) < 12:
        return []

    signals: list[AnomalySignal] = []
    last = float(prices[-1])
    rets = _returns(prices)
    if len(rets) < 8:
        return []

    # --- Price z-score of latest return vs recent returns ---
    window = rets[-30:] if len(rets) >= 30 else rets
    mu = mean(window)
    try:
        sigma = pstdev(window) or 1e-9
    except Exception:
        sigma = 1e-9
    latest_ret = rets[-1]
    z = (latest_ret - mu) / sigma
    abs_z = abs(z)

    # --- Range expansion vs typical range ---
    recent = prices[-20:]
    high = max(recent)
    low = min(recent)
    rng = (high - low) / max(last, 1e-9)
    older = prices[-60:-20] if len(prices) >= 60 else prices[:-20] or prices
    older_rng = (max(older) - min(older)) / max(mean(older), 1e-9) if older else rng
    range_ratio = rng / max(older_rng, 1e-9)

    # --- Volume spike ---
    vol_score = 0.0
    vol_ratio = 1.0
    if len(volumes) >= 8:
        v_last = float(volumes[-1])
        v_avg = mean(float(x) for x in volumes[-11:-1]) or 1e-9
        vol_ratio = v_last / v_avg
        if vol_ratio >= 3.0:
            vol_score = 30.0
        elif vol_ratio >= 2.0:
            vol_score = 20.0
        elif vol_ratio >= 1.5:
            vol_score = 10.0

    # --- Composite anomaly score ---
    score = 0.0
    reasons: list[str] = []

    if abs_z >= 3.0:
        score += 45
        reasons.append(f"Extreme return z-score {z:+.2f}")
    elif abs_z >= 2.25:
        score += 32
        reasons.append(f"High return z-score {z:+.2f}")
    elif abs_z >= 1.75:
        score += 18
        reasons.append(f"Elevated return z-score {z:+.2f}")

    if range_ratio >= 2.0:
        score += 20
        reasons.append(f"Range expansion x{range_ratio:.1f}")
    elif range_ratio >= 1.5:
        score += 10
        reasons.append(f"Elevated range x{range_ratio:.1f}")

    score += vol_score
    if vol_score >= 20:
        reasons.append(f"Volume spike x{vol_ratio:.1f}")

    # Distance from local mean
    local = mean(prices[-15:])
    dist = abs(last - local) / max(local, 1e-9)
    if dist >= 0.04:
        score += 12
        reasons.append(f"Stretched vs local mean ({dist*100:.1f}%)")
    elif dist >= 0.025:
        score += 6

    score = _clamp(score)
    if score < 40 or not reasons:
        return []

    severity = "low"
    if score >= 80:
        severity = "high"
    elif score >= 60:
        severity = "medium"

    direction = "selloff" if latest_ret < 0 else "rally"
    title = f"{symbol} abnormal {direction}"
    message = (
        f"**{symbol}** anomaly score **{score:.0f}**\n"
        + "\n".join(f"• {r}" for r in reasons)
    )

    signals.append(
        AnomalySignal(
            symbol=symbol,
            alert_type="price_volume_anomaly",
            severity=severity,
            title=title,
            message=message,
            opportunity_score=score,
            confidence_score=_clamp(50 + abs_z * 10),
            risk_score=_clamp(40 + (20 if severity == "high" else 0)),
            price=price or last,
            score=score,
            indicators={
                "z_score": round(z, 3),
                "latest_return_pct": round(latest_ret * 100, 3),
                "range_ratio": round(range_ratio, 3),
                "volume_ratio": round(vol_ratio, 3),
                "reasons": reasons,
                "volume_24h": volume_24h,
                "open_interest": open_interest,
            },
        )
    )
    return signals