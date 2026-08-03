from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import numpy as np


@dataclass
class AnomalySignal:
    symbol: str
    alert_type: str
    severity: str
    title: str
    message: str
    opportunity_score: float
    confidence_score: float
    risk_score: float
    price: float
    indicators: Dict = field(default_factory=dict)


def detect_anomalies(
    symbol: str,
    price: float = 0.0,
    volume_24h: float = 0.0,
    open_interest: float = 0.0,
    price_history: Optional[List[float]] = None,
    volume_history: Optional[List[float]] = None,
    **kwargs: Any,
) -> List[AnomalySignal]:
    """
    Stricter anomaly detection – only high-quality candidates become opportunities.
    Accepts extra kwargs so older call styles don't crash.
    """
    signals: List[AnomalySignal] = []

    price_history = price_history or []
    volume_history = volume_history or []

    if len(price_history) < 12 or price <= 0:
        return signals

    # Liquidity filter
    if volume_24h < 250_000:
        return signals

    closes = np.array(price_history[-30:])
    vols = np.array(volume_history[-30:]) if volume_history else np.array([volume_24h])

    mean_p = np.mean(closes[:-1])
    std_p = np.std(closes[:-1])
    zscore = (closes[-1] - mean_p) / std_p if std_p > 0 else 0.0

    avg_vol = np.mean(vols[:-1]) if len(vols) > 1 else float(vols[-1])
    rel_vol = float(vols[-1]) / avg_vol if avg_vol > 0 else 1.0

    change_pct = ((closes[-1] - closes[-6]) / closes[-6]) * 100 if len(closes) >= 6 else 0.0

    # Volume + Price anomaly
    if rel_vol >= 3.5 and abs(change_pct) >= 1.8:
        severity = "high" if rel_vol >= 5.0 or abs(change_pct) >= 3.5 else "medium"

        signals.append(
            AnomalySignal(
                symbol=symbol,
                alert_type="volume_price_anomaly",
                severity=severity,
                title=f"{symbol} Volume + Price Anomaly",
                message=(
                    f"Relative volume {rel_vol:.1f}x with {change_pct:+.2f}% move "
                    f"in the last few candles."
                ),
                opportunity_score=min(85.0, 40 + rel_vol * 6 + abs(change_pct) * 4),
                confidence_score=min(80.0, 45 + rel_vol * 5),
                risk_score=55.0,
                price=price,
                indicators={
                    "rel_vol": round(rel_vol, 2),
                    "change_pct": round(float(change_pct), 2),
                    "zscore": round(float(zscore), 2),
                },
            )
        )

    # Strong statistical outlier
    elif abs(zscore) >= 3.2 and rel_vol >= 2.0:
        signals.append(
            AnomalySignal(
                symbol=symbol,
                alert_type="price_zscore",
                severity="high" if abs(zscore) >= 4.0 else "medium",
                title=f"{symbol} Statistical Price Outlier",
                message=f"Price z-score = {zscore:.2f} with elevated volume ({rel_vol:.1f}x).",
                opportunity_score=min(80.0, 35 + abs(zscore) * 8),
                confidence_score=min(75.0, 40 + abs(zscore) * 6),
                risk_score=60.0,
                price=price,
                indicators={
                    "zscore": round(float(zscore), 2),
                    "rel_vol": round(rel_vol, 2),
                },
            )
        )

    return signals