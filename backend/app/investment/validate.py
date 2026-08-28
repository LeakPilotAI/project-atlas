"""Validate investment data. Flag issues. Never silently repair."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Set


class ValidationIssue:
    def __init__(self, code: str, message: str, field: str = "") -> None:
        self.code = code
        self.message = message
        self.field = field

    def as_dict(self) -> Dict[str, str]:
        return {"code": self.code, "field": self.field, "message": self.message}


# Fields that may legitimately be negative.
SIGNED_FUNDAMENTALS = {
    "earnings",
    "free_cash_flow",
    "operating_cash_flow",
    "net_income",
    "eps",
    "net_margin",
    "operating_margin",
    "gross_margin",
}

# Zero is unusual and should be flagged, not coerced.
SUSPICIOUS_ZERO_FIELDS = {
    "revenue",
    "market_cap",
    "shares_outstanding",
    "open",
    "high",
    "low",
    "close",
    "pe",
    "forward_pe",
    "ps",
    "pb",
}


def _f(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def validate_ohlc(
    *,
    session_date: Any,
    open_: Any,
    high: Any,
    low: Any,
    close: Any,
    volume: Any = None,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    if session_date is None:
        issues.append(ValidationIssue("INVALID_DATE", "date missing", "date"))
    else:
        try:
            if isinstance(session_date, datetime):
                session_date.date()
            elif isinstance(session_date, date):
                pass
            else:
                date.fromisoformat(str(session_date)[:10])
        except Exception:
            issues.append(ValidationIssue("INVALID_DATE", f"unparseable date {session_date}", "date"))

    o, h, l, c = _f(open_), _f(high), _f(low), _f(close)
    for name, val in (("open", o), ("high", h), ("low", l), ("close", c)):
        if val is None:
            issues.append(ValidationIssue("MISSING_OHLC", f"{name} missing", name))
        elif val < 0:
            issues.append(ValidationIssue("NEGATIVE_PRICE", f"{name}={val}", name))
        elif val == 0:
            issues.append(ValidationIssue("SUSPICIOUS_ZERO", f"{name} is zero", name))

    if None not in (o, h, l, c) and o is not None and h is not None and l is not None and c is not None:
        if h < l:
            issues.append(ValidationIssue("IMPOSSIBLE_OHLC", "high < low", "high"))
        if h < max(o, c) - 1e-12:
            issues.append(ValidationIssue("IMPOSSIBLE_OHLC", "high < max(open, close)", "high"))
        if l > min(o, c) + 1e-12:
            issues.append(ValidationIssue("IMPOSSIBLE_OHLC", "low > min(open, close)", "low"))

    vol = _f(volume) if volume is not None else None
    if vol is not None and vol < 0:
        issues.append(ValidationIssue("NEGATIVE_VOLUME", f"volume={vol}", "volume"))

    return issues


def validate_non_negative(name: str, value: Any, *, allow_missing: bool = True) -> List[ValidationIssue]:
    if value is None:
        return [] if allow_missing else [ValidationIssue("MISSING", f"{name} missing", name)]
    n = _f(value)
    if n is None:
        return [ValidationIssue("NON_NUMERIC", f"{name} not numeric", name)]
    issues: List[ValidationIssue] = []
    if n < 0 and name not in SIGNED_FUNDAMENTALS:
        issues.append(ValidationIssue("NEGATIVE_VALUE", f"{name}={n}", name))
    if n == 0 and name in SUSPICIOUS_ZERO_FIELDS:
        issues.append(ValidationIssue("SUSPICIOUS_ZERO", f"{name} is zero", name))
    return issues


def validate_shares(shares: Any) -> List[ValidationIssue]:
    n = _f(shares)
    if n is None:
        return []
    if n <= 0:
        return [ValidationIssue("INVALID_SHARES", f"shares_outstanding={n}", "shares_outstanding")]
    if n < 1000:
        return [ValidationIssue("SUSPICIOUS_SHARES", f"shares_outstanding={n} looks too small", "shares_outstanding")]
    return []


def validate_share_consistency(
    *,
    shares: Any,
    market_cap: Any,
    price: Any,
) -> List[ValidationIssue]:
    """Flag share counts that imply a wildly different price. Do not repair."""
    s, m, p = _f(shares), _f(market_cap), _f(price)
    if s is None or m is None or p is None:
        return []
    if s <= 0 or p <= 0 or m <= 0:
        return []
    implied = m / s
    if implied <= 0:
        return [ValidationIssue("INCONSISTENT_SHARES", "implied price non-positive", "shares_outstanding")]
    ratio = implied / p
    if ratio > 10 or ratio < 0.1:
        return [
            ValidationIssue(
                "INCONSISTENT_SHARES",
                f"implied price {implied:.4g} vs quoted {p:.4g}",
                "shares_outstanding",
            )
        ]
    return []


def find_duplicate_dates(dates: Sequence[str]) -> Set[str]:
    seen: Set[str] = set()
    dups: Set[str] = set()
    for d in dates:
        if d in seen:
            dups.add(d)
        seen.add(d)
    return dups
