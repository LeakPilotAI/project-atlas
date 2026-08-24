"""Analytics package exports."""

from app.analytics.indicators import (
    IndicatorResult,
    atr_from_closes,
    atr_proxy,
    compute_indicators,
    ema,
    rsi,
    sma,
    volume_spike_ratio,
)
from app.analytics.regime import RegimeResult, detect_regime
from app.analytics.decision_engine import SetupDecision, decide_direction, evaluate_setup

__all__ = [
    "IndicatorResult",
    "atr_from_closes",
    "atr_proxy",
    "compute_indicators",
    "ema",
    "rsi",
    "sma",
    "volume_spike_ratio",
    "RegimeResult",
    "detect_regime",
    "SetupDecision",
    "decide_direction",
    "evaluate_setup",
]