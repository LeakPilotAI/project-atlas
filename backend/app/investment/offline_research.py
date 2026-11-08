"""Pure, caller-supplied equity research validation; no I/O or execution authority.

Uses the existing bounded Atlas exchange calendar. This is not wired to a scanner,
provider, API, scheduler, PAPER engine or startup path.
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from math import isfinite

from app.investment.market_hours import CALENDAR_YEARS, ET, session_bounds


class ResearchInputRefused(ValueError):
    """Research evidence is invalid, inconsistent or outside the calendar horizon."""


def aware(value, field="timestamp"):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ResearchInputRefused(f"Invalid {field}") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ResearchInputRefused(f"Timezone-aware {field} required")
    return value.astimezone(UTC)


def symbol_identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,11}", value.strip().upper()):
        raise ResearchInputRefused("Invalid symbol")
    return value.strip().upper()


def number(value, field, *, zero=False):
    if isinstance(value, bool):
        raise ResearchInputRefused(f"Invalid {field}")
    try:
        n = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ResearchInputRefused(f"Invalid {field}") from exc
    if not isfinite(n) or (n < 0 if zero else n <= 0):
        raise ResearchInputRefused(f"Invalid {field}")
    return n


def equity_session(value):
    ts = aware(value)
    local = ts.astimezone(ET)
    if local.year not in CALENDAR_YEARS:
        raise ResearchInputRefused("Unsupported calendar year")
    bounds = session_bounds(ts)
    if not bounds:
        return "CLOSED"
    opening, closing = bounds
    if datetime.combine(local.date(), time(4), ET) <= ts < opening:
        return "PRE_MARKET"
    if opening <= ts < closing:
        return "REGULAR"
    if closing <= ts < datetime.combine(local.date(), time(20), ET):
        return "AFTER_HOURS"
    return "CLOSED"


def previous_session(day):
    if not isinstance(day, date) or day.year not in CALENDAR_YEARS:
        raise ResearchInputRefused("Unsupported reference calendar")
    for offset in range(1, 15):
        candidate = day - timedelta(days=offset)
        if candidate.year not in CALENDAR_YEARS:
            break
        if session_bounds(datetime.combine(candidate, time(12), ET)):
            return candidate
    raise ResearchInputRefused("Previous session unavailable in verified calendar")


def validated_candles(symbol, candles, *, now):
    symbol = symbol_identity(symbol)
    now = aware(now, "current time")
    if not isinstance(candles, (list, tuple)) or not 1 <= len(candles) <= 100000:
        raise ResearchInputRefused("Bounded candle records required")
    result, seen = [], set()
    for row in candles:
        if not isinstance(row, dict):
            raise ResearchInputRefused("Malformed candle")
        ts = aware(row.get("timestamp"))
        if ts > now:
            raise ResearchInputRefused("Future candle timestamp")
        if ts.second or ts.microsecond or ts in seen:
            raise ResearchInputRefused("Duplicate or non-minute candle timestamp")
        seen.add(ts)
        if "symbol" in row and symbol_identity(row["symbol"]) != symbol:
            raise ResearchInputRefused("Candle symbol mismatch")
        close = number(row.get("Close"), "candle close")
        # Validate the supplied decimal value before float rounding can erase a
        # fractional share or alias adjacent unsafe integers. Already rounded
        # upstream floating-point values cannot be reconstructed here.
        raw_volume = row.get("Volume")
        try:
            volume = Decimal(str(raw_volume))
        except (InvalidOperation, ValueError) as exc:
            raise ResearchInputRefused("Integral bounded share volume required") from exc
        if (isinstance(raw_volume, bool) or not volume.is_finite() or volume < 0
                or volume > 2**53 - 1 or volume != volume.to_integral_value()):
            raise ResearchInputRefused("Integral bounded share volume required")
        ohlc = {k: number(row[k], k) for k in ("Open", "High", "Low") if k in row}
        if "High" in ohlc and ohlc["High"] < max(close, ohlc.get("Open", close), ohlc.get("Low", close)):
            raise ResearchInputRefused("Conflicting candle high")
        if "Low" in ohlc and ohlc["Low"] > min(close, ohlc.get("Open", close), ohlc.get("High", close)):
            raise ResearchInputRefused("Conflicting candle low")
        if equity_session(ts) == "CLOSED":
            raise ResearchInputRefused("Candle outside supported market session")
        # Existing numeric values keep their byte-relevant int/float form. Only
        # nonnumeric representations accepted by number() need coercion.
        normalized_ohlc = {key: row[key] if type(row[key]) in (int, float) else value
                           for key, value in ohlc.items()}
        result.append({**row, **normalized_ohlc, "timestamp": ts, "Close": close, "Volume": int(volume)})
    return sorted(result, key=lambda r: r["timestamp"])


def close_reference(reference, *, observation_time):
    """Scalar compatibility is explicitly undated; structured references verify date."""
    if not isinstance(reference, dict):
        return number(reference, "Previous close"), "UNDATED_CALLER_REFERENCE", None
    price = number(reference.get("previous_close"), "Previous close")
    expected = previous_session(aware(observation_time).astimezone(ET).date())
    if reference.get("previous_session_date") != expected.isoformat():
        raise ResearchInputRefused("Previous close must be the immediately preceding session")
    source = reference.get("source")
    if not isinstance(source, str) or not source.strip() or source.upper() == "UNKNOWN":
        raise ResearchInputRefused("Previous close provenance missing")
    return price, "DATED_CALLER_REFERENCE", expected.isoformat()


def comparable_volume(candles, latest, *, minimum_sessions=5):
    """Same-session completed-minute windows only; no daily-volume proxy or imputation."""
    if type(minimum_sessions) is not int or not 2 <= minimum_sessions <= 60:
        raise ResearchInputRefused("Invalid baseline sufficiency threshold")
    local = latest.astimezone(ET)
    session = equity_session(latest)
    bounds = session_bounds(latest)
    start = 240 if session == "PRE_MARKET" else 570 if session == "REGULAR" else bounds[1].astimezone(ET).hour * 60 + bounds[1].astimezone(ET).minute
    stop = local.hour * 60 + local.minute  # current partial minute excluded
    expected = set(range(start, stop))
    by_day = {}
    for row in candles:
        ts = row["timestamp"].astimezone(ET)
        if equity_session(ts) != session or ts.date() > local.date():
            continue
        minute = ts.hour * 60 + ts.minute
        if minute in expected:
            by_day.setdefault(ts.date(), {})[minute] = row["Volume"]
    current = by_day.pop(local.date(), {})
    completed = [sum(v.values()) for _, v in sorted(by_day.items())
                 if set(v) == expected and expected]
    status = "CURRENT_WINDOW_INCOMPLETE" if not expected or set(current) != expected else "BASELINE_INSUFFICIENT"
    ratio = baseline = None
    if status != "CURRENT_WINDOW_INCOMPLETE" and len(completed) >= minimum_sessions:
        baseline = sum(completed) / len(completed)
        status = "ZERO_BASELINE" if baseline == 0 else "COMPARABLE_HISTORY"
        if baseline:
            ratio = round(sum(current.values()) / baseline, 6)
    return {"relative_volume": ratio, "relative_volume_status": status,
            "baseline_sessions": len(completed), "baseline_minimum_sessions": minimum_sessions,
            "baseline_mean_volume": baseline, "volume_window_completed_minutes": len(expected)}


def rank_research(signals):
    """Deterministic descriptive ordering, never a confidence or execution score."""
    if not isinstance(signals, (list, tuple)) or len(signals) > 1000:
        raise ResearchInputRefused("Bounded research candidates required")
    seen, valid = set(), []
    for row in signals:
        if not isinstance(row, dict) or row.get("research_only") is not True or row.get("trading_enabled") is not False:
            raise ResearchInputRefused("Research-only candidate required")
        symbol = symbol_identity(row.get("symbol"))
        if symbol in seen:
            raise ResearchInputRefused("Duplicate ranking symbol")
        seen.add(symbol)
        change = row.get("change_from_previous_close_percent")
        if type(change) not in (int, float) or not isfinite(change):
            raise ResearchInputRefused("Invalid observed change")
        gap = abs(change)
        valid.append((gap, symbol, row))
    return [{**row, "research_rank": i, "ranking_basis": "ABS_OBSERVED_CHANGE_THEN_SYMBOL"}
            for i, (_, _, row) in enumerate(sorted(valid, key=lambda r: (-r[0], r[1])), 1)]
