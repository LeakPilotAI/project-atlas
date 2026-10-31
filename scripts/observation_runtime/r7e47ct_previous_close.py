"""Extract prior regular-session close from timestamped daily candles."""

from __future__ import annotations

from datetime import datetime
from math import isfinite
from zoneinfo import ZoneInfo

from app.investment.offline_research import previous_session

EASTERN = ZoneInfo("America/New_York")


class PreviousCloseRefused(ValueError):
    pass


def extract_previous_close(daily_frame, *, observation_time):
    if not isinstance(observation_time, datetime):
        raise PreviousCloseRefused("Invalid observation time")

    if observation_time.tzinfo is None:
        raise PreviousCloseRefused("Observation time must be timezone-aware")

    if daily_frame is None or not hasattr(daily_frame, "iterrows"):
        raise PreviousCloseRefused("Expected a daily DataFrame")

    if getattr(daily_frame, "empty", True):
        raise PreviousCloseRefused("Daily history is empty")

    if "Close" not in daily_frame.columns:
        raise PreviousCloseRefused("Daily close column missing")

    current_date = observation_time.astimezone(EASTERN).date()
    expected_date = previous_session(current_date)
    candidates = []

    for index, row in daily_frame.iterrows():
        if not hasattr(index, "to_pydatetime"):
            continue

        timestamp = index.to_pydatetime()

        if timestamp.tzinfo is None:
            raise PreviousCloseRefused(
                "Daily history timestamps must be timezone-aware"
            )

        session_date = timestamp.astimezone(EASTERN).date()

        if session_date >= current_date:
            continue

        if session_date != expected_date:
            continue

        try:
            if isinstance(row["Close"], bool):
                raise PreviousCloseRefused("Invalid prior close")
            close = float(row["Close"])
        except (TypeError, ValueError, OverflowError):
            continue

        if not isfinite(close) or close <= 0:
            continue

        candidates.append((session_date, close))

    if not candidates:
        raise PreviousCloseRefused(
            "No prior regular-session closing price available"
        )

    if len(candidates) != 1:
        raise PreviousCloseRefused("Ambiguous duplicate previous-session close")

    session_date, close = max(
        candidates,
        key=lambda item: item[0],
    )

    return {
        "previous_close": close,
        "previous_session_date": session_date.isoformat(),
        "source": "CALLER_SUPPLIED_DAILY_HISTORY",
    }
