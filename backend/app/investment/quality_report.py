"""Research diagnostic: freshness of price / fundamentals / valuation."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, List

from app.investment.enums import DataQuality
from app.investment.snapshot import InvestmentSnapshot


def summarize_snapshots(snaps: Iterable[InvestmentSnapshot]) -> str:
    snaps = list(snaps)
    price_c: Counter[str] = Counter()
    fund_c: Counter[str] = Counter()
    val_c: Counter[str] = Counter()
    errors = 0
    for s in snaps:
        price_c[_q(s.price.quality)] += 1
        for mv in s.fundamentals.values():
            fund_c[_q(mv.quality)] += 1
        for mv in s.valuation.values():
            val_c[_q(mv.quality)] += 1
        errors += len(s.failures)

    def line(title: str, c: Counter[str], n: int) -> List[str]:
        return [
            f"{title}:",
            f"  Fresh `{c.get('FRESH', 0)}`",
            f"  Stale `{c.get('STALE', 0)}`",
            f"  Missing `{c.get('MISSING', 0)}`",
            f"  Conflicting `{c.get('CONFLICTING', 0)}`",
            f"  Unknown `{c.get('UNKNOWN', 0)}`",
        ]

    lines = [
        "**INVESTMENT DATA QUALITY**",
        f"Assets requested: `{len(snaps)}`",
        "",
        *line("Price", price_c, len(snaps)),
        "",
        *line("Fundamentals", fund_c, sum(fund_c.values())),
        "",
        *line("Valuation", val_c, sum(val_c.values())),
        "",
        f"Provider errors: `{errors}`",
        "",
        "_Phase 2 data only. No recommendations._",
    ]
    return "\n".join(lines)


def _q(q: DataQuality | str) -> str:
    return q.value if isinstance(q, DataQuality) else str(q)
