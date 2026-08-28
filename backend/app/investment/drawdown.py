"""Historical drawdown from available bars. Never claims a short window is complete."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from app.investment.bars import OhlcvBar

# Trading days. 252 is a convention for "about a year", not a complete history.
BARS_PER_YEAR = 252
MIN_BARS_FOR_PERCENTILE = 60
MIN_BARS_FOR_52W = 60
MIN_BARS_FOR_VOL = 20


@dataclass
class DrawdownReport:
    current_drawdown: Optional[float] = None
    drawdown_52w: Optional[float] = None
    high_available: Optional[float] = None
    high_available_date: Optional[str] = None
    high_52w: Optional[float] = None
    high_52w_date: Optional[str] = None
    max_drawdown: Optional[float] = None
    drawdown_percentile: Optional[float] = None
    coverage_bars: int = 0
    coverage_label: str = "no price history"
    recovery_days_median: Optional[float] = None
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "current_drawdown": self.current_drawdown,
            "drawdown_52w": self.drawdown_52w,
            "high_available": self.high_available,
            "high_available_date": self.high_available_date,
            "high_52w": self.high_52w,
            "high_52w_date": self.high_52w_date,
            "max_drawdown": self.max_drawdown,
            "drawdown_percentile": self.drawdown_percentile,
            "coverage_bars": self.coverage_bars,
            "coverage_label": self.coverage_label,
            "recovery_days_median": self.recovery_days_median,
            "notes": list(self.notes),
        }


def bar_price(bar: OhlcvBar) -> Optional[float]:
    for v in (bar.adjusted_close, bar.close):
        if v is None:
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if x > 0:
            return x
    return None


def closes_from_bars(bars: Sequence[OhlcvBar]) -> List[Tuple[str, float]]:
    rows: List[Tuple[str, float]] = []
    for b in bars:
        px = bar_price(b)
        if px is None or not b.session_date:
            continue
        rows.append((str(b.session_date)[:10], px))
    rows.sort(key=lambda r: r[0])
    return rows


def coverage_label(n: int) -> str:
    if n <= 0:
        return "no price history"
    years = n / float(BARS_PER_YEAR)
    if n < MIN_BARS_FOR_PERCENTILE:
        return f"{n} trading days (insufficient for drawdown percentile)"
    if n < BARS_PER_YEAR:
        return (
            f"{n} trading days (~{years:.1f} year; shorter than 52 weeks; "
            "incomplete for cycle-scale claims)"
        )
    if n < BARS_PER_YEAR * 3:
        return (
            f"{n} trading days (~{years:.1f} years; 52-week window available; "
            "incomplete for decade-scale / full-cycle claims)"
        )
    return (
        f"{n} trading days (~{years:.1f} years; still a sample, not an all-time market history)"
    )


def _percentile_rank(sample: Sequence[float], value: float) -> float:
    """Percent of sample that is *greater* than value.

    For drawdowns (negative), a deep current dd ranks high: more days were shallower.
    """
    if not sample:
        return 0.0
    n = len(sample)
    shallower = sum(1 for x in sample if x > value + 1e-15)
    return 100.0 * shallower / n


def _running_drawdowns(prices: Sequence[float]) -> Tuple[List[float], float]:
    peak = prices[0]
    dds: List[float] = []
    max_dd = 0.0
    for p in prices:
        if p > peak:
            peak = p
        dd = p / peak - 1.0
        dds.append(dd)
        if dd < max_dd:
            max_dd = dd
    return dds, max_dd


def _median(xs: Sequence[float]) -> Optional[float]:
    if not xs:
        return None
    s = sorted(xs)
    m = len(s) // 2
    if len(s) % 2:
        return float(s[m])
    return (s[m - 1] + s[m]) / 2.0


def _recovery_days(prices: Sequence[float]) -> Optional[float]:
    if len(prices) < 3:
        return None
    peak = prices[0]
    trough_i = 0
    trough_p = prices[0]
    in_dd = False
    recoveries: List[float] = []
    for i, p in enumerate(prices):
        if p >= peak - 1e-12:
            if in_dd and i > trough_i:
                recoveries.append(float(i - trough_i))
            in_dd = False
            peak = p
            trough_i = i
            trough_p = p
        else:
            in_dd = True
            if p < trough_p:
                trough_p = p
                trough_i = i
    return _median(recoveries)


def analyze_drawdown(
    bars: Sequence[OhlcvBar],
    *,
    current_price: Optional[float] = None,
) -> DrawdownReport:
    """Drawdown vs highest available close in the provided sample.

    Does not treat 252 days as a complete historical record.
    """
    series = closes_from_bars(bars)
    notes: List[str] = []
    n = len(series)
    label = coverage_label(n)
    if n == 0:
        notes.append("no usable historical closes")
        return DrawdownReport(coverage_bars=0, coverage_label=label, notes=notes)

    dates = [d for d, _ in series]
    prices = [p for _, p in series]
    high = max(prices)
    high_i = prices.index(high)
    last = prices[-1]
    now = last
    if current_price is not None:
        try:
            cp = float(current_price)
            if cp > 0:
                now = cp
        except (TypeError, ValueError):
            notes.append("current_price unusable; using last bar close")

    current_dd = now / high - 1.0
    running, max_dd = _running_drawdowns(prices)
    # If current quote is below last close, fold it into current_dd only (do not invent a bar).
    if now < last:
        notes.append("current price below last close; current drawdown uses the quote vs sample high")

    window = series[-BARS_PER_YEAR:] if n >= MIN_BARS_FOR_52W else series
    if n < BARS_PER_YEAR:
        notes.append("52-week high is the high of the available window, not a full 52-week record")
    w_prices = [p for _, p in window]
    w_dates = [d for d, _ in window]
    high_52 = max(w_prices)
    high_52_i = w_prices.index(high_52)
    dd_52 = now / high_52 - 1.0

    percentile: Optional[float] = None
    if n < MIN_BARS_FOR_PERCENTILE:
        notes.append(
            f"historical drawdown percentile UNKNOWN ({n} < {MIN_BARS_FOR_PERCENTILE} bars)"
        )
    else:
        # Percentile of *current* drawdown vs daily running-peak drawdowns in-sample.
        # A unique shallow dip at the end of a pure uptrend can rank high; magnitude still matters.
        percentile = _percentile_rank(running, current_dd)
        notes.append(
            "drawdown percentile is sample-relative (share of days with a shallower running-peak "
            "drawdown). It is not a full-cycle or generational claim."
        )

    rec = _recovery_days(prices)
    if rec is None:
        notes.append("no completed peak-to-trough recoveries in the sample")

    return DrawdownReport(
        current_drawdown=current_dd,
        drawdown_52w=dd_52,
        high_available=high,
        high_available_date=dates[high_i],
        high_52w=high_52,
        high_52w_date=w_dates[high_52_i],
        max_drawdown=max_dd,
        drawdown_percentile=percentile,
        coverage_bars=n,
        coverage_label=label,
        recovery_days_median=rec,
        notes=notes,
    )


def return_volatility(bars: Sequence[OhlcvBar]) -> Optional[float]:
    """Annualized stdev of daily close-to-close returns. None if history is too short."""
    series = closes_from_bars(bars)
    if len(series) < MIN_BARS_FOR_VOL:
        return None
    prices = [p for _, p in series]
    rets: List[float] = []
    for i in range(1, len(prices)):
        if prices[i - 1] > 0:
            rets.append(prices[i] / prices[i - 1] - 1.0)
    if len(rets) < MIN_BARS_FOR_VOL - 1:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return (var ** 0.5) * (BARS_PER_YEAR ** 0.5)
