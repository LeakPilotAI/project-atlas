"""Published NYSE cash-equity sessions, bounded to the verified 2026–2028 calendar.

Source: https://www.nyse.com/trade/hours-calendars (verified 2026-10-16).
No inferred holidays outside this horizon; unsupported dates fail closed.
Unscheduled exchange closures still require an operator calendar update.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
OPEN = time(9, 30)
CLOSE = time(16, 0)
CALENDAR_YEARS = frozenset({2026, 2027, 2028})
HOLIDAYS = frozenset(date.fromisoformat(day) for day in (
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
    "2028-01-17", "2028-02-21", "2028-04-14", "2028-05-29", "2028-06-19",
    "2028-07-04", "2028-09-04", "2028-11-23", "2028-12-25",
))
EARLY_CLOSES = frozenset(date.fromisoformat(day) for day in (
    "2026-11-27", "2026-12-24", "2027-11-26", "2028-07-03", "2028-11-24",
))


def _utc(now: Optional[datetime]) -> datetime:
    value = now or datetime.now(timezone.utc)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def session_bounds(now: Optional[datetime] = None) -> tuple[datetime, datetime] | None:
    day = _utc(now).astimezone(ET).date()
    if day.year not in CALENDAR_YEARS or day.weekday() >= 5 or day in HOLIDAYS:
        return None
    close = time(13) if day in EARLY_CLOSES else CLOSE
    return tuple(datetime.combine(day, t, ET).astimezone(timezone.utc) for t in (OPEN, close))


def session_status(now: Optional[datetime] = None, *, system_ok: bool = True) -> str:
    current = _utc(now)
    if not system_ok or current.astimezone(ET).year not in CALENDAR_YEARS:
        return "SYSTEM_OFFLINE"
    bounds = session_bounds(current)
    return "MARKET_OPEN" if bounds and bounds[0] <= current < bounds[1] else "MARKET_CLOSED"


def next_session_open(now: Optional[datetime] = None) -> datetime | None:
    current = _utc(now)
    day = current.astimezone(ET).date()
    if day.year not in CALENDAR_YEARS:
        return None
    for offset in range(370):
        candidate = datetime.combine(day + timedelta(days=offset), OPEN, ET).astimezone(timezone.utc)
        if candidate.astimezone(ET).year not in CALENDAR_YEARS:
            return None
        if candidate > current and session_bounds(candidate):
            return candidate
    return None


def next_scan_delay(now: datetime, *, open_seconds: float, closed_seconds: float,
                    system_ok: bool = True) -> float:
    current = _utc(now)
    if session_status(current, system_ok=system_ok) == "MARKET_OPEN":
        return max(60.0, float(open_seconds))
    opening = next_session_open(current)
    # Recheck clock/calendar at least once per minute when calendar/system is unavailable.
    if not opening or not system_ok:
        return 60.0
    return max(60.0, min(float(closed_seconds), (opening - current).total_seconds()))


def is_market_open(now: Optional[datetime] = None, *, system_ok: bool = True) -> bool:
    return session_status(now, system_ok=system_ok) == "MARKET_OPEN"
