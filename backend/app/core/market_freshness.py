"""Strict observation timestamps; receipt times never imply exchange event times."""

from datetime import datetime, timezone
from math import isfinite
from typing import Any

MAX_PRICE_AGE_SECONDS = 30.0


def observation_time(value: Any) -> datetime | None:
    try:
        stamp = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            return None
        return stamp.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def fresh_observation(value: Any, *, now: datetime | None = None,
                      max_age: float = MAX_PRICE_AGE_SECONDS) -> bool:
    stamp = observation_time(value)
    current = observation_time(now or datetime.now(timezone.utc))
    return bool(stamp is not None and current is not None
                and 0 <= (current - stamp).total_seconds() <= max_age)


def positive_price(value: Any) -> bool:
    try:
        return not isinstance(value, bool) and isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False
