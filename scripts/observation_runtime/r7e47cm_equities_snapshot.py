"""Validate caller-supplied equity minute candles using Atlas's existing calendar."""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite

from app.investment.offline_research import (
    ET,
    aware,
    equity_session,
    symbol_identity,
    validated_candles,
)
from app.investment.offline_research import (
    ResearchInputRefused as SnapshotRefused,
)


def build_snapshot(symbol, candles, *, now=None, max_age_seconds=180):
    now = aware(now if now is not None else datetime.now(timezone.utc), "current time")
    if type(max_age_seconds) not in (int, float) or not isfinite(max_age_seconds) or max_age_seconds <= 0:
        raise SnapshotRefused("Invalid freshness threshold")
    rows = validated_candles(symbol, candles, now=now)
    latest = rows[-1]
    timestamp = latest["timestamp"]
    age = (now - timestamp).total_seconds()
    if age > max_age_seconds:
        raise SnapshotRefused("Latest candle is stale")
    session = equity_session(timestamp)
    if session == "CLOSED" or equity_session(now) != session or now.astimezone(ET).date() != timestamp.astimezone(ET).date():
        raise SnapshotRefused("Current/candle market session mismatch")
    return {"symbol": symbol_identity(symbol), "price": latest["Close"],
            "candle_volume": latest["Volume"], "timestamp": timestamp.isoformat(),
            "age_seconds": round(age, 2), "session": session, "freshness": "FRESH",
            "source": "CALLER_SUPPLIED_CANDLES"}
