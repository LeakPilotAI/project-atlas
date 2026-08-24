"""A+ setup decision engine for Hyperliquid perps.

Combines RSI, momentum, funding, regime, and ATR channel breakouts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SetupDecision:
    symbol: str
    recommendation: str  # LONG | SHORT | WAIT
    score: float
    confidence: float
    risk_score: float
    reasons: list[str] = field(default_factory=list)
    invalidation: Optional[str] = None
    direction: Optional[str] = None
    atr_state: Optional[str] = None
    stop: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None

    def __post_init__(self) -> None:
        if self.direction is None:
            self.direction = self.recommendation


def _rsi_from_closes(closes: list[float], period: int = 14) -> Optional[float]:
    if not closes or len(closes) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _pct_change(closes: list[float], bars: int) -> Optional[float]:
    if not closes or len(closes) < bars + 1:
        return None
    a = closes[-(bars + 1)]
    b = closes[-1]
    if a <= 0:
        return None
    return (b / a - 1.0) * 100.0


def evaluate_setup(
    symbol: str,
    price: float,
    volume_24h: float = 0.0,
    open_interest: float = 0.0,
    funding_rate: Optional[float] = None,
    indicators: Any = None,
    regime: Any = None,
    price_history: Optional[list[float]] = None,
    volume_history: Optional[list[float]] = None,
    funding_bias: Any = None,
    atr_signal: Any = None,
    **kwargs: Any,
) -> Optional[SetupDecision]:
    """
    Score a perp for LONG / SHORT / WAIT.

    Optional atr_signal: ATRChannelSignal from atr_breakout.evaluate_atr_breakout
    or signal_from_candles.
    """
    closes = list(price_history or [])
    volumes = list(volume_history or [])

    rsi = None
    if indicators is not None:
        rsi = getattr(indicators, "rsi", None)
        if rsi is None and isinstance(indicators, dict):
            rsi = indicators.get("rsi")
    if rsi is None:
        rsi = _rsi_from_closes(closes)

    regime_name = None
    regime_strength = 0.0
    vol_state = "normal"
    if regime is not None:
        regime_name = getattr(regime, "name", None) or getattr(regime, "regime", None)
        if regime_name is None and isinstance(regime, dict):
            regime_name = regime.get("name") or regime.get("regime")
        if regime_name is not None:
            regime_name = str(regime_name).lower()
        try:
            regime_strength = float(getattr(regime, "strength", 0) or 0)
        except (TypeError, ValueError):
            regime_strength = 0.0
        vol_state = str(getattr(regime, "vol_state", "normal") or "normal").lower()

    chg_5 = _pct_change(closes, 5)
    chg_20 = _pct_change(closes, 20)

    long_score = 0.0
    short_score = 0.0
    reasons: list[str] = []
    conf = 50.0

    # ── Liquidity ────────────────────────────────────────────────────
    if volume_24h >= 500_000:
        conf += 5
    elif volume_24h < 20_000:
        conf -= 8
        reasons.append("Thin 24h volume")

    if open_interest >= 100_000:
        conf += 3

    # ── RSI ──────────────────────────────────────────────────────────
    if rsi is not None:
        if rsi <= 25:
            long_score += 28
            reasons.append(f"RSI oversold ({rsi:.1f})")
            conf += 10
        elif rsi <= 35:
            long_score += 14
            reasons.append(f"RSI soft ({rsi:.1f})")
            conf += 4
        elif rsi >= 75:
            short_score += 28
            reasons.append(f"RSI overbought ({rsi:.1f})")
            conf += 10
        elif rsi >= 65:
            short_score += 14
            reasons.append(f"RSI elevated ({rsi:.1f})")
            conf += 4

    # ── Momentum ─────────────────────────────────────────────────────
    if chg_5 is not None:
        if chg_5 <= -6:
            long_score += 18
            reasons.append(f"Sharp 5-bar drop ({chg_5:.1f}%)")
            conf += 6
        elif chg_5 <= -3:
            long_score += 10
            reasons.append(f"5-bar weakness ({chg_5:.1f}%)")
        elif chg_5 >= 6:
            short_score += 18
            reasons.append(f"Sharp 5-bar spike ({chg_5:.1f}%)")
            conf += 6
        elif chg_5 >= 3:
            short_score += 10
            reasons.append(f"5-bar strength ({chg_5:.1f}%)")

    if chg_20 is not None:
        if chg_20 <= -12:
            long_score += 10
            reasons.append(f"Extended 20-bar drawdown ({chg_20:.1f}%)")
        elif chg_20 >= 12:
            short_score += 10
            reasons.append(f"Extended 20-bar run ({chg_20:.1f}%)")

    # ── Instant funding ──────────────────────────────────────────────
    if funding_rate is not None:
        fr = float(funding_rate)
        if fr >= 0.0003:
            short_score += 8
            reasons.append(f"Elevated positive funding ({fr:.5f})")
        elif fr <= -0.0003:
            long_score += 8
            reasons.append(f"Negative funding ({fr:.5f})")

    # ── Funding history bias ─────────────────────────────────────────
    if isinstance(funding_bias, dict):
        lean = str(funding_bias.get("lean") or "neutral").lower()
        try:
            delta = float(funding_bias.get("score_delta") or 0)
        except (TypeError, ValueError):
            delta = 0.0
        sum_rate = funding_bias.get("sum_rate")
        if lean == "long" and delta > 0:
            long_score += delta
            reasons.append(f"Funding history lean LONG (sum={sum_rate})")
            conf += 3
        elif lean == "short" and delta > 0:
            short_score += delta
            reasons.append(f"Funding history lean SHORT (sum={sum_rate})")
            conf += 3

    # ── Regime ───────────────────────────────────────────────────────
    if regime_name:
        if "trend_up" in regime_name or regime_name == "bull":
            long_score += 6 + min(6.0, regime_strength * 0.05)
            short_score -= 4
            reasons.append(f"Regime trend_up (str={regime_strength:.0f})")
        elif "trend_down" in regime_name or regime_name == "bear":
            short_score += 6 + min(6.0, regime_strength * 0.05)
            long_score -= 4
            reasons.append(f"Regime trend_down (str={regime_strength:.0f})")
        elif "range" in regime_name or "mean" in regime_name:
            conf += 2
            reasons.append("Regime range — favor RSI extremes only")
        elif "expansion" in regime_name:
            conf -= 4
            reasons.append("Vol expansion — size down / higher bar")

    if vol_state == "high":
        conf -= 3

    # ── ATR channel breakout ─────────────────────────────────────────
    atr_state = None
    stop = None
    tp1 = None
    tp2 = None

    if atr_signal is not None:
        atr_state = str(getattr(atr_signal, "state", None) or "")
        if not atr_state and isinstance(atr_signal, dict):
            atr_state = str(atr_signal.get("state") or "")

        atr_dir = str(getattr(atr_signal, "direction", None) or "")
        if not atr_dir and isinstance(atr_signal, dict):
            atr_dir = str(atr_signal.get("direction") or "")

        atr_val = getattr(atr_signal, "atr", None)
        if atr_val is None and isinstance(atr_signal, dict):
            atr_val = atr_signal.get("atr")
        try:
            atr_f = float(atr_val or 0)
        except (TypeError, ValueError):
            atr_f = 0.0

        upper = getattr(atr_signal, "upper", None)
        lower = getattr(atr_signal, "lower", None)
        if isinstance(atr_signal, dict):
            upper = upper if upper is not None else atr_signal.get("upper")
            lower = lower if lower is not None else atr_signal.get("lower")

        # Breakout alignment boosts
        if atr_state == "break_up":
            long_score += 16
            reasons.append(
                f"ATR breakout UP (upper={upper})"
                if upper is not None
                else "ATR breakout UP"
            )
            conf += 6
            if regime_name and "trend_up" in regime_name:
                long_score += 8
                conf += 4
                reasons.append("ATR break_up + trend_up alignment")
            if regime_name and "trend_down" in regime_name:
                long_score -= 10
                conf -= 5
                reasons.append("ATR break_up against trend_down — discounted")

        elif atr_state == "break_down":
            short_score += 16
            reasons.append(
                f"ATR breakout DOWN (lower={lower})"
                if lower is not None
                else "ATR breakout DOWN"
            )
            conf += 6
            if regime_name and "trend_down" in regime_name:
                short_score += 8
                conf += 4
                reasons.append("ATR break_down + trend_down alignment")
            if regime_name and "trend_up" in regime_name:
                short_score -= 10
                conf -= 5
                reasons.append("ATR break_down against trend_up — discounted")

        elif atr_state == "near_upper":
            short_score += 4
            reasons.append("Price near ATR upper band")
        elif atr_state == "near_lower":
            long_score += 4
            reasons.append("Price near ATR lower band")

        # Pull structured levels for embeds
        if atr_dir == "long" or atr_state == "break_up":
            stop = getattr(atr_signal, "stop_long", None)
            tp1 = getattr(atr_signal, "tp1_long", None)
            tp2 = getattr(atr_signal, "tp2_long", None)
            if isinstance(atr_signal, dict):
                stop = stop if stop is not None else atr_signal.get("stop_long")
                tp1 = tp1 if tp1 is not None else atr_signal.get("tp1_long")
                tp2 = tp2 if tp2 is not None else atr_signal.get("tp2_long")
        elif atr_dir == "short" or atr_state == "break_down":
            stop = getattr(atr_signal, "stop_short", None)
            tp1 = getattr(atr_signal, "tp1_short", None)
            tp2 = getattr(atr_signal, "tp2_short", None)
            if isinstance(atr_signal, dict):
                stop = stop if stop is not None else atr_signal.get("stop_short")
                tp1 = tp1 if tp1 is not None else atr_signal.get("tp1_short")
                tp2 = tp2 if tp2 is not None else atr_signal.get("tp2_short")

        if atr_f > 0 and price > 0:
            reasons.append(f"ATR={atr_f:.6g} ({atr_f / price * 100:.2f}%)")

    # ── Decision ─────────────────────────────────────────────────────
    recommendation = "WAIT"
    score = 0.0

    if long_score >= short_score and long_score >= 40:
        recommendation = "LONG"
        score = min(99.0, 55.0 + long_score * 0.5)
    elif short_score > long_score and short_score >= 40:
        recommendation = "SHORT"
        score = min(99.0, 55.0 + short_score * 0.5)
    else:
        recommendation = "WAIT"
        score = max(long_score, short_score)
        reasons.append("No A+ edge — stand down")

    conf = max(0.0, min(95.0, conf + min(long_score, short_score) * 0.15))
    risk = 40.0
    if volume_24h < 50_000:
        risk += 15
    if recommendation != "WAIT":
        risk += 5
    if vol_state == "high" or (regime_name and "expansion" in regime_name):
        risk += 10

    invalidation = None
    if recommendation == "LONG" and price > 0:
        if stop is not None:
            invalidation = f"Stop / invalidation ~{float(stop):.6g}"
        else:
            invalidation = f"Close breakdown ~{price * 0.985:.6g}"
    elif recommendation == "SHORT" and price > 0:
        if stop is not None:
            invalidation = f"Stop / invalidation ~{float(stop):.6g}"
        else:
            invalidation = f"Close breakout ~{price * 1.015:.6g}"

    return SetupDecision(
        symbol=symbol,
        recommendation=recommendation,
        score=round(score, 1),
        confidence=round(conf, 1),
        risk_score=round(risk, 1),
        reasons=reasons[:12],
        invalidation=invalidation,
        atr_state=atr_state or None,
        stop=float(stop) if stop is not None else None,
        tp1=float(tp1) if tp1 is not None else None,
        tp2=float(tp2) if tp2 is not None else None,
    )


def decide_direction(*args: Any, **kwargs: Any) -> Optional[SetupDecision]:
    """Back-compat alias used by opportunity_tracker."""
    return evaluate_setup(*args, **kwargs)