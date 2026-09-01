"""Thesis deterioration vs a prior snapshot. Current-only thesis stays in research.py."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.investment.enums import ThesisState
from app.investment.models import MeasuredValue


def _num(mv: Optional[MeasuredValue]) -> Optional[float]:
    if mv is None or not mv.is_usable():
        return None
    try:
        return float(mv.value)
    except (TypeError, ValueError):
        return None


def detect_deterioration(
    current: Dict[str, MeasuredValue],
    prior: Optional[Dict[str, MeasuredValue]],
) -> Tuple[bool, List[str]]:
    """True when the latest snapshot is materially worse than the previous stored snapshot.

    No prior → trend UNKNOWN (not deteriorating). Never invents a time series.
    """
    notes: List[str] = []
    if not prior:
        notes.append("no prior fundamentals snapshot — deterioration UNKNOWN")
        return False, notes

    flags: List[str] = []
    pairs = (
        ("earnings", 0.5, "earnings"),
        ("free_cash_flow", 0.5, "FCF"),
        ("operating_cash_flow", 0.5, "operating cash flow"),
        ("net_margin", 0.7, "net margin"),
        ("gross_margin", 0.85, "gross margin"),
    )
    for key, ratio, label in pairs:
        cur = _num(current.get(key))
        old = _num(prior.get(key))
        if cur is None or old is None:
            continue
        if old > 0 and cur < old * ratio:
            flags.append(f"{label} deteriorated vs prior snapshot")
        if old >= 0 and cur < 0:
            flags.append(f"{label} flipped negative vs prior snapshot")

    cur_debt = _num(current.get("total_debt"))
    old_debt = _num(prior.get("total_debt"))
    if cur_debt is not None and old_debt is not None and old_debt > 0 and cur_debt > old_debt * 1.5:
        flags.append("debt increased >50% vs prior snapshot")

    cur_cash = _num(current.get("cash"))
    old_cash = _num(prior.get("cash"))
    if cur_cash is not None and old_cash is not None and old_cash > 0 and cur_cash < old_cash * 0.6:
        flags.append("cash declined >40% vs prior snapshot")

    if flags:
        notes.extend(flags)
        return True, notes
    notes.append("no material deterioration vs prior snapshot")
    return False, notes


def apply_deterioration(thesis: ThesisState, deteriorating: bool) -> ThesisState:
    if not deteriorating:
        return thesis
    if thesis is ThesisState.BROKEN:
        return thesis
    if thesis is ThesisState.DAMAGED:
        return ThesisState.DAMAGED
    if thesis in (ThesisState.STRONG, ThesisState.INTACT):
        return ThesisState.UNDER_PRESSURE
    if thesis is ThesisState.UNKNOWN:
        return ThesisState.UNDER_PRESSURE
    return thesis
