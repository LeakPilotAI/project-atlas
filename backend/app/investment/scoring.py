"""Ordinal 0–100 research scores. Not probabilities. No ML. No threshold optimizer.

Correlation groups
------------------
Valuation is ONE component. Inside it, related multiples are averaged *within*
a group before groups are averaged:

  earnings_multiple : pe, forward_pe, earnings_yield
  sales_multiple    : ps
  book_multiple     : pb
  cashflow_multiple : fcf_yield, price_to_fcf, ev_ebitda

P/E and earnings yield are not two full weights. Price/FCF and FCF yield are not
two full weights.

Fundamentals are split so cash flow, profitability, and balance sheet are
separate top-level components (they can diverge). Growth is a top-level
component that stays None without a fundamentals time series — it is omitted
from the weighted average, not scored as 0.

Current valuation bands are rule-of-thumb ordinals, **not** historical
percentiles. Historical valuation context is UNKNOWN unless a valuation
history exists (Phase 2 does not store one).
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from app.investment.drawdown import DrawdownReport
from app.investment.enums import DataQuality, EvidenceQuality, ThesisState
from app.investment.models import MeasuredValue
from app.investment.research_models import ComponentScores

# Renormalized over whichever components are present.
SCORE_WEIGHTS: Dict[str, float] = {
    "valuation": 0.22,
    "fundamentals": 0.12,
    "cash_flow": 0.12,
    "balance_sheet": 0.10,
    "growth": 0.08,
    "drawdown": 0.14,
    "thesis_integrity": 0.12,
    "risk": 0.06,
    "evidence_quality": 0.04,
}

CORRELATION_GROUPS: Dict[str, Tuple[str, ...]] = {
    "earnings_multiple": ("pe", "forward_pe", "earnings_yield"),
    "sales_multiple": ("ps",),
    "book_multiple": ("pb",),
    "cashflow_multiple": ("fcf_yield", "price_to_fcf", "ev_ebitda"),
}

THESIS_POINTS = {
    ThesisState.STRONG: 90,
    ThesisState.INTACT: 75,
    ThesisState.UNDER_PRESSURE: 45,
    ThesisState.DAMAGED: 22,
    ThesisState.BROKEN: 5,
    ThesisState.UNKNOWN: None,
}

EVIDENCE_POINTS = {
    EvidenceQuality.HIGH: 88,
    EvidenceQuality.MEDIUM: 70,
    EvidenceQuality.LOW: 40,
    EvidenceQuality.INSUFFICIENT: 12,
    EvidenceQuality.UNKNOWN: None,
}


def _clip_int(x: float) -> int:
    return int(round(max(0.0, min(100.0, x))))


def _usable(mv: Optional[MeasuredValue]) -> Optional[float]:
    if mv is None or not mv.is_usable():
        return None
    try:
        return float(mv.value)
    except (TypeError, ValueError):
        return None


def _mean(xs: Iterable[float]) -> Optional[float]:
    vals = [float(x) for x in xs]
    if not vals:
        return None
    return sum(vals) / len(vals)


def pe_band(pe: float) -> int:
    """Lower multiple → higher score. Negative PE is not a cheapness signal."""
    if pe <= 0:
        return 25
    if pe < 10:
        return 90
    if pe < 15:
        return 80
    if pe < 22:
        return 65
    if pe < 30:
        return 45
    if pe < 45:
        return 30
    return 15


def yield_band(y: float) -> int:
    if y >= 0.10:
        return 92
    if y >= 0.07:
        return 84
    if y >= 0.05:
        return 74
    if y >= 0.03:
        return 60
    if y >= 0.015:
        return 45
    if y >= 0:
        return 28
    return 18


def ps_band(ps: float) -> int:
    if ps <= 0:
        return 25
    if ps < 1:
        return 88
    if ps < 2:
        return 75
    if ps < 4:
        return 58
    if ps < 8:
        return 40
    return 22


def pb_band(pb: float) -> int:
    if pb <= 0:
        return 25
    if pb < 1:
        return 88
    if pb < 2:
        return 75
    if pb < 4:
        return 55
    if pb < 8:
        return 35
    return 20


def ev_band(ev: float) -> int:
    if ev <= 0:
        return 25
    if ev < 8:
        return 88
    if ev < 12:
        return 75
    if ev < 18:
        return 58
    if ev < 25:
        return 40
    return 22


def _metric_ordinal(name: str, value: float) -> int:
    if name in {"pe", "forward_pe"}:
        return pe_band(value)
    if name in {"earnings_yield", "fcf_yield"}:
        return yield_band(value)
    if name == "price_to_fcf":
        return pe_band(value)
    if name == "ps":
        return ps_band(value)
    if name == "pb":
        return pb_band(value)
    if name == "ev_ebitda":
        return ev_band(value)
    return 50


def score_valuation(valuation: Mapping[str, MeasuredValue]) -> Tuple[Optional[int], List[str]]:
    notes: List[str] = []
    group_scores: List[float] = []
    for gname, keys in CORRELATION_GROUPS.items():
        inner: List[float] = []
        used: List[str] = []
        for k in keys:
            v = _usable(valuation.get(k))
            if v is None:
                continue
            inner.append(float(_metric_ordinal(k, v)))
            used.append(k)
        if not inner:
            continue
        group_scores.append(sum(inner) / len(inner))
        if len(used) > 1:
            notes.append(f"{gname} averaged {', '.join(used)} (not full separate weights)")
    if not group_scores:
        notes.append("current valuation missing; historical valuation context UNKNOWN")
        return None, notes
    notes.append(
        "valuation score uses current-multiple bands, not historical percentiles "
        "(no valuation time series in Phase 2 storage)"
    )
    notes.append("a low multiple is not automatically undervaluation")
    return _clip_int(sum(group_scores) / len(group_scores)), notes


def score_profitability(funds: Mapping[str, MeasuredValue]) -> Tuple[Optional[int], List[str]]:
    notes: List[str] = []
    earnings = _usable(funds.get("earnings"))
    eps = _usable(funds.get("eps"))
    net_m = _usable(funds.get("net_margin"))
    op_m = _usable(funds.get("operating_margin"))
    gross_m = _usable(funds.get("gross_margin"))
    parts: List[float] = []

    signs = [x for x in (earnings, eps) if x is not None]
    if signs:
        if all(x > 0 for x in signs):
            parts.append(80.0)
            notes.append("earnings/EPS positive")
        elif any(x > 0 for x in signs) and any(x <= 0 for x in signs):
            parts.append(45.0)
            notes.append("mixed earnings sign")
        else:
            parts.append(15.0)
            notes.append("earnings not profitable on available figures")

    for name, m in (("net", net_m), ("operating", op_m), ("gross", gross_m)):
        if m is None:
            continue
        if m >= 0.20:
            parts.append(90.0)
        elif m >= 0.10:
            parts.append(80.0)
        elif m >= 0.05:
            parts.append(68.0)
        elif m >= 0:
            parts.append(50.0)
        else:
            parts.append(18.0)
            notes.append(f"{name} margin negative")

    if not parts:
        notes.append("profitability UNKNOWN (insufficient fields)")
        return None, notes
    return _clip_int(sum(parts) / len(parts)), notes


def score_cash_flow(funds: Mapping[str, MeasuredValue]) -> Tuple[Optional[int], List[str]]:
    notes: List[str] = []
    fcf = _usable(funds.get("free_cash_flow"))
    ocf = _usable(funds.get("operating_cash_flow"))
    rev = _usable(funds.get("revenue"))
    parts: List[float] = []
    if fcf is not None:
        if fcf > 0:
            parts.append(82.0)
            notes.append("free cash flow positive")
        else:
            parts.append(18.0)
            notes.append("free cash flow not positive")
        if rev and rev > 0:
            margin = fcf / rev
            if margin >= 0.10:
                parts.append(90.0)
            elif margin >= 0.05:
                parts.append(75.0)
            elif margin >= 0:
                parts.append(55.0)
            else:
                parts.append(20.0)
    if ocf is not None:
        parts.append(80.0 if ocf > 0 else 20.0)
        if ocf <= 0:
            notes.append("operating cash flow not positive")
    if not parts:
        notes.append("cash-flow quality UNKNOWN")
        return None, notes
    return _clip_int(sum(parts) / len(parts)), notes


def score_balance_sheet(funds: Mapping[str, MeasuredValue]) -> Tuple[Optional[int], List[str]]:
    notes: List[str] = []
    cash = _usable(funds.get("cash"))
    debt = _usable(funds.get("total_debt"))
    mcap = _usable(funds.get("market_cap"))
    parts: List[float] = []
    if cash is not None and debt is not None:
        if cash >= debt:
            parts.append(88.0)
            notes.append("net cash (cash >= total debt)")
        elif cash > 0 and debt / max(cash, 1e-9) <= 2:
            parts.append(68.0)
            notes.append("moderate leverage vs cash")
        elif cash > 0 and debt / max(cash, 1e-9) <= 4:
            parts.append(45.0)
            notes.append("elevated leverage vs cash")
        else:
            parts.append(18.0)
            notes.append("high leverage vs cash")
    if debt is not None and mcap is not None and mcap > 0:
        ratio = debt / mcap
        if ratio < 0.15:
            parts.append(85.0)
        elif ratio < 0.35:
            parts.append(70.0)
        elif ratio < 0.60:
            parts.append(50.0)
        elif ratio < 0.90:
            parts.append(30.0)
        else:
            parts.append(12.0)
            notes.append("debt large vs market cap")
    if cash is not None and debt is None:
        parts.append(70.0 if cash > 0 else 40.0)
        notes.append("debt missing; cash-only view")
    if debt is not None and cash is None:
        parts.append(40.0)
        notes.append("cash missing; debt-only view")
    if not parts:
        notes.append("balance sheet UNKNOWN")
        return None, notes
    return _clip_int(sum(parts) / len(parts)), notes


def score_growth(_funds: Mapping[str, MeasuredValue]) -> Tuple[Optional[int], List[str]]:
    return None, [
        "growth UNKNOWN: Phase 2 stores one fundamentals snapshot, not a statement history"
    ]


def score_drawdown_context(dd: DrawdownReport) -> Tuple[Optional[int], List[str]]:
    """Larger drawdowns score higher as *context*, not as a buy signal.

    Classification (not this number) decides whether the dip is usable.
    """
    notes: List[str] = []
    if dd.current_drawdown is None:
        notes.append("drawdown context UNKNOWN (no history/high)")
        return None, notes
    mag = -float(dd.current_drawdown)
    if mag < 0.03:
        base = 12
    elif mag < 0.08:
        base = 28
    elif mag < 0.15:
        base = 45
    elif mag < 0.25:
        base = 62
    elif mag < 0.35:
        base = 74
    elif mag < 0.50:
        base = 84
    else:
        base = 92
    if dd.drawdown_percentile is not None and dd.drawdown_percentile >= 85 and mag >= 0.15:
        base = min(95, base + 5)
        notes.append("in-sample drawdown percentile is elevated (sample-relative)")
    notes.append(
        f"current drawdown {dd.current_drawdown:.1%} from highest available "
        f"({dd.coverage_label})"
    )
    notes.append("drawdown context is not a 'buy the dip' recommendation")
    return _clip_int(base), notes


def score_thesis(state: ThesisState) -> Optional[int]:
    v = THESIS_POINTS.get(state)
    return None if v is None else int(v)


def score_evidence(state: EvidenceQuality) -> Optional[int]:
    v = EVIDENCE_POINTS.get(state)
    return None if v is None else int(v)


def combine_components(c: ComponentScores) -> Optional[int]:
    """Weighted mean of *present* components. Missing is omitted, not zeroed.

    Light haircut when very few pillars exist, so a single lucky number cannot
    look like a complete research score.
    """
    present = c.present()
    if not present:
        return None
    wsum = 0.0
    acc = 0.0
    for k, v in present.items():
        w = SCORE_WEIGHTS.get(k)
        if not w:
            continue
        acc += v * w
        wsum += w
    if wsum <= 0:
        return None
    raw = acc / wsum
    n = len(present)
    if n <= 2:
        raw *= 0.70
    elif n <= 4:
        raw *= 0.88
    return _clip_int(raw)


def conflicting_in(mvs: Iterable[MeasuredValue]) -> bool:
    for mv in mvs:
        q = mv.quality
        if q is DataQuality.CONFLICTING or (isinstance(q, str) and q == "CONFLICTING"):
            return True
    return False
