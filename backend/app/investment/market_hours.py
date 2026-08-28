"""US equity session clock. Closed is not the same as system offline."""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Optional

from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
OPEN = time(9, 30)
CLOSE = time(16, 0)


def session_status(now: Optional[datetime] = None, *, system_ok: bool = True) -> str:
    """MARKET_OPEN · MARKET_CLOSED · SYSTEM_OFFLINE."""
    if not system_ok:
        return "SYSTEM_OFFLINE"
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local = now.astimezone(ET)
    if local.weekday() >= 5:
        return "MARKET_CLOSED"
    t = local.timetz().replace(tzinfo=None)
    if OPEN <= t < CLOSE:
        return "MARKET_OPEN"
    return "MARKET_CLOSED"


def is_market_open(now: Optional[datetime] = None, *, system_ok: bool = True) -> bool:
    return session_status(now, system_ok=system_ok) == "MARKET_OPEN"
