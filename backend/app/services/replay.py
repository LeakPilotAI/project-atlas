from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

from app.analytics.anomaly import detect_anomalies, AnomalySignal
from app.analytics.decision_engine import decide_direction, TradeDecision
from app.analytics.regime import detect_regime
from app.core.logging import get_logger

logger = get_logger("replay")


@dataclass
class ReplayStep:
    index: int
    timestamp: datetime
    price: float
    volume: float
    regime: str
    anomalies: List[AnomalySignal] = field(default_factory=list)
    decision: Optional[TradeDecision] = None
    notes: str = ""


@dataclass
class ReplayResult:
    symbol: str
    interval: str
    total_bars: int
    steps: List[ReplayStep] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


def run_replay(
    symbol: str,
    candles_5m: List[dict],
    candles_15m: List[dict],
    start_index: int = 40,
    max_steps: int = 80,
) -> ReplayResult:
    """
    Walk through historical candles and record what the system would have done.
    """
    result = ReplayResult(
        symbol=symbol,
        interval="5m",
        total_bars=len(candles_5m),
    )

    if len(candles_5m) < start_index + 10:
        result.summary = {"error": "Not enough candles for replay"}
        return result

    anomaly_count = 0
    long_count = 0
    short_count = 0

    end = min(len(candles_5m) - 1, start_index + max_steps)

    for i in range(start_index, end):
        window_5m = candles_5m[max(0, i - 40) : i + 1]
        # Approximate 15m alignment
        idx_15 = min(i // 3, len(candles_15m) - 1)
        window_15m = candles_15m[max(0, idx_15 - 20) : idx_15 + 1]

        if len(window_5m) < 20 or len(window_15m) < 12:
            continue

        closes_5m = [c["close"] for c in window_5m]
        highs_5m = [c["high"] for c in window_5m]
        lows_5m = [c["low"] for c in window_5m]
        volumes_5m = [c["volume"] for c in window_5m]

        closes_15m = [c["close"] for c in window_15m]
        highs_15m = [c["high"] for c in window_15m]
        lows_15m = [c["low"] for c in window_15m]
        volumes_15m = [c["volume"] for c in window_15m]

        current = window_5m[-1]
        price = current["close"]
        volume = current["volume"]
        ts = datetime.utcfromtimestamp(current["open_time"] / 1000)

        # Regime
        regime_info = detect_regime(closes_5m, highs_5m, lows_5m)

        # Anomaly detection on price/volume history
        price_history = closes_5m
        volume_history = volumes_5m
        anomalies = detect_anomalies(
            symbol=symbol,
            price=price,
            volume_24h=volume * 288,  # rough 24h estimate from 5m
            open_interest=0.0,
            price_history=price_history,
            volume_history=volume_history,
        )
        if anomalies:
            anomaly_count += len(anomalies)

        # Decision
        decision = decide_direction(
            symbol=symbol,
            closes_5m=closes_5m,
            highs_5m=highs_5m,
            lows_5m=lows_5m,
            volumes_5m=volumes_5m,
            closes_15m=closes_15m,
            highs_15m=highs_15m,
            lows_15m=lows_15m,
            volumes_15m=volumes_15m,
            entry_price=price,
            profile_name="balanced",
        )

        if decision.recommendation == "LONG":
            long_count += 1
        elif decision.recommendation == "SHORT":
            short_count += 1

        step = ReplayStep(
            index=i,
            timestamp=ts,
            price=price,
            volume=volume,
            regime=regime_info.regime,
            anomalies=anomalies,
            decision=decision if decision.recommendation != "NONE" else None,
            notes=decision.reason if decision.recommendation != "NONE" else "",
        )
        result.steps.append(step)

    result.summary = {
        "bars_processed": len(result.steps),
        "anomalies_found": anomaly_count,
        "long_signals": long_count,
        "short_signals": short_count,
        "start_index": start_index,
        "end_index": end,
    }

    logger.info(
        "Replay completed",
        symbol=symbol,
        steps=len(result.steps),
        longs=long_count,
        shorts=short_count,
        anomalies=anomaly_count,
    )
    return result