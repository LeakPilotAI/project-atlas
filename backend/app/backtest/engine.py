from dataclasses import dataclass
from typing import List, Optional
import numpy as np

from app.analytics.profiles import StrategyProfile, get_profile


@dataclass
class TradeDecision:
    recommendation: str
    confidence: float
    reason: str
    invalidation: Optional[float] = None
    risk_reward_note: str = ""
    suggested_rr: Optional[str] = None
    profile: str = "balanced"


def calculate_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes[-(period + 1) :])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def _score_direction(
    closes: List[float],
    highs: List[float],
    lows: List[float],
    volumes: List[float],
    entry_price: float,
    profile: StrategyProfile,
) -> tuple[float, float, list, list]:
    if len(closes) < 15:
        return 0, 0, [], []

    current = closes[-1]
    change_pct = ((current - entry_price) / entry_price) * 100
    recent_move = ((closes[-1] - closes[-6]) / closes[-6]) * 100 if len(closes) >= 6 else 0

    avg_vol = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
    recent_vol = np.mean(volumes[-3:]) if len(volumes) >= 3 else volumes[-1]
    rel_vol = recent_vol / avg_vol if avg_vol > 0 else 1.0

    higher_highs = highs[-1] > max(highs[-6:-1]) if len(highs) >= 6 else False
    lower_lows = lows[-1] < min(lows[-6:-1]) if len(lows) >= 6 else False
    rsi = calculate_rsi(closes, 14)

    long_score = 0.0
    long_reasons = []
    short_score = 0.0
    short_reasons = []

    # Volume
    if rel_vol >= profile.min_rel_volume:
        long_score += 22
        short_score += 22
        long_reasons.append(f"vol {rel_vol:.1f}x")
        short_reasons.append(f"vol {rel_vol:.1f}x")

    # Momentum / Mean reversion bias
    if profile.prefer_momentum:
        if change_pct >= profile.min_abs_change_pct:
            long_score += 24
            long_reasons.append(f"+{change_pct:.2f}%")
        if change_pct <= -profile.min_abs_change_pct:
            short_score += 24
            short_reasons.append(f"{change_pct:.2f}%")
        if recent_move > 0.7:
            long_score += 16
            long_reasons.append("momentum")
        if recent_move < -0.7:
            short_score += 16
            short_reasons.append("momentum")

    if profile.prefer_mean_reversion:
        # Prefer fading extremes
        if change_pct >= profile.min_abs_change_pct * 1.3:
            short_score += 26
            short_reasons.append(f"overextended +{change_pct:.2f}%")
        if change_pct <= -profile.min_abs_change_pct * 1.3:
            long_score += 26
            long_reasons.append(f"oversold {change_pct:.2f}%")

    if profile.prefer_breakout:
        if higher_highs and rel_vol >= profile.min_rel_volume:
            long_score += 20
            long_reasons.append("HH breakout")
        if lower_lows and rel_vol >= profile.min_rel_volume:
            short_score += 20
            short_reasons.append("LL breakdown")

    # Structure
    if higher_highs:
        long_score += 12
        long_reasons.append("HH structure")
    if lower_lows:
        short_score += 12
        short_reasons.append("LL structure")

    # RSI filter
    if rsi is not None:
        if 48 <= rsi <= 68:
            long_score += 10
            long_reasons.append(f"RSI {rsi:.0f}")
        if 32 <= rsi <= 52:
            short_score += 10
            short_reasons.append(f"RSI {rsi:.0f}")

    return long_score, short_score, long_reasons, short_reasons


def decide_direction(
    symbol: str,
    closes_5m: List[float],
    highs_5m: List[float],
    lows_5m: List[float],
    volumes_5m: List[float],
    closes_15m: List[float],
    highs_15m: List[float],
    lows_15m: List[float],
    volumes_15m: List[float],
    entry_price: float,
    profile_name: str = "balanced",
) -> TradeDecision:
    profile = get_profile(profile_name)

    if len(closes_5m) < 20 or len(closes_15m) < 12:
        return TradeDecision("NONE", 0, "Insufficient multi-timeframe data", profile=profile_name)

    l5, s5, lr5, sr5 = _score_direction(
        closes_5m, highs_5m, lows_5m, volumes_5m, entry_price, profile
    )
    l15, s15, lr15, sr15 = _score_direction(
        closes_15m, highs_15m, lows_15m, volumes_15m, entry_price, profile
    )

    long_score = l5 * 0.6 + l15 * 0.4
    short_score = s5 * 0.6 + s15 * 0.4

    long_aligned = l5 >= 40 and l15 >= 35
    short_aligned = s5 >= 40 and s15 >= 35

    current = closes_5m[-1]

    if long_aligned and long_score >= 58 and long_score > short_score + 10:
        invalidation = min(lows_5m[-10:]) * 0.995
        risk = abs(current - invalidation) / current * 100
        change_pct = abs((current - entry_price) / entry_price * 100)
        suggested_rr = f"~1:{max(1.6, round(change_pct / max(risk, 0.25), 1))}"
        reasons = list(dict.fromkeys(lr5 + lr15))
        return TradeDecision(
            recommendation="LONG",
            confidence=min(94.0, long_score + 12),
            reason=" | ".join(reasons),
            invalidation=invalidation,
            risk_reward_note=f"Invalidation ≈ ${invalidation:.4f}",
            suggested_rr=suggested_rr,
            profile=profile_name,
        )

    if short_aligned and short_score >= 58 and short_score > long_score + 10:
        invalidation = max(highs_5m[-10:]) * 1.005
        risk = abs(invalidation - current) / current * 100
        change_pct = abs((current - entry_price) / entry_price * 100)
        suggested_rr = f"~1:{max(1.6, round(change_pct / max(risk, 0.25), 1))}"
        reasons = list(dict.fromkeys(sr5 + sr15))
        return TradeDecision(
            recommendation="SHORT",
            confidence=min(94.0, short_score + 12),
            reason=" | ".join(reasons),
            invalidation=invalidation,
            risk_reward_note=f"Invalidation ≈ ${invalidation:.4f}",
            suggested_rr=suggested_rr,
            profile=profile_name,
        )

    return TradeDecision("NONE", 0, "No multi-timeframe agreement yet", profile=profile_name)