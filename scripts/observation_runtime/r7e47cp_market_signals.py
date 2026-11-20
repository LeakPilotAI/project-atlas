"""Offline descriptive equity signals; no forecast, order or provider access."""
from __future__ import annotations

from datetime import datetime

from app.investment.offline_research import (
    ET,
    close_reference,
    comparable_volume,
    equity_session,
    validated_candles,
)

from scripts.observation_runtime.r7e47cm_equities_snapshot import build_snapshot


def analyze_market(symbol, candles, previous_close, *, now, historical_candles=None,
                   minimum_baseline_sessions=5, max_age_seconds=180):
    snapshot = build_snapshot(symbol, candles, now=now, max_age_seconds=max_age_seconds)
    latest = datetime.fromisoformat(snapshot["timestamp"])
    reference, reference_status, reference_date = close_reference(previous_close, observation_time=latest)
    rows = validated_candles(symbol, candles, now=now)
    today = latest.astimezone(ET).date()
    day_rows = [r for r in rows if r["timestamp"].astimezone(ET).date() == today]
    pre = [r for r in day_rows if equity_session(r["timestamp"]) == "PRE_MARKET"]
    regular = [r for r in day_rows if equity_session(r["timestamp"]) == "REGULAR"]
    same = [r for r in day_rows if equity_session(r["timestamp"]) == snapshot["session"]]
    momentum = None if len(same) < 2 else round((same[-1]["Close"] / same[0]["Close"] - 1) * 100, 3)
    history = [r for r in rows if r["timestamp"].astimezone(ET).date() < today]
    if historical_candles is not None:
        extra = validated_candles(symbol, historical_candles, now=now)
        if any(r["timestamp"].astimezone(ET).date() >= today for r in extra):
            from app.investment.offline_research import ResearchInputRefused
            raise ResearchInputRefused("Historical baseline must precede observation date")
        history = validated_candles(symbol, history + extra, now=now)
    volume = {"relative_volume": None, "relative_volume_status": "BASELINE_REQUIRED",
              "baseline_sessions": 0, "baseline_minimum_sessions": minimum_baseline_sessions,
              "baseline_mean_volume": None, "volume_window_completed_minutes": 0}
    if history:
        volume = comparable_volume(history + day_rows, latest, minimum_sessions=minimum_baseline_sessions)
    elif type(minimum_baseline_sessions) is not int or not 2 <= minimum_baseline_sessions <= 60:
        from app.investment.offline_research import ResearchInputRefused
        raise ResearchInputRefused("Invalid baseline sufficiency threshold")
    return {**snapshot, "previous_close": reference, "previous_close_status": reference_status,
            "previous_session_date": reference_date,
            "change_from_previous_close_percent": round((snapshot["price"] / reference - 1) * 100, 3),
            "premarket_gap_percent": round((pre[-1]["Close"] / reference - 1) * 100, 3) if pre else None,
            "premarket_volume": sum(r["Volume"] for r in pre),
            "regular_volume": sum(r["Volume"] for r in regular),
            "session_momentum_percent": momentum,
            "session_candle_count": len(same), "volume_coverage": "OBSERVED_BARS_ONLY",
            **volume, "research_only": True, "trading_enabled": False,
            "execution_authority": False, "network_authorized": False}
