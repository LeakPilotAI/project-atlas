"""Look-ahead bias protection.

At timestamp T only information whose effective date is ≤ T may affect
score, classification, thesis, alert, or allocation.

Future prices are stored later by `outcomes.enrich_due_observations`,
which writes a *separate* append-only file and never mutates the original
observation. Enrichment is never imported by the scoring path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List

from app.investment.bars import OhlcvBar


def as_of_date(as_of: datetime) -> str:
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    return as_of.astimezone(timezone.utc).date().isoformat()


def filter_bars_as_of(bars: Iterable[OhlcvBar], as_of: datetime) -> List[OhlcvBar]:
    """Drop any bar whose session date is after T. Does not invent bars."""
    cutoff = as_of_date(as_of)
    out: List[OhlcvBar] = []
    for b in bars:
        d = str(getattr(b, "session_date", "") or "")
        if not d:
            continue
        if d > cutoff:
            continue
        out.append(b)
    return out


def assert_no_future_bars(bars: Iterable[OhlcvBar], as_of: datetime) -> None:
    cutoff = as_of_date(as_of)
    future = [b.session_date for b in bars if b.session_date and b.session_date > cutoff]
    if future:
        raise RuntimeError(
            f"look-ahead violation: {len(future)} bars after {cutoff} (e.g. {future[0]})"
        )
