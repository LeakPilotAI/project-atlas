"""Point-in-time exit replay for Atlas V6 research challengers.

Replays persisted PAPER mark events chronologically. Candidate exits are evaluated
only after their threshold is observed in the event stream. Final MFE/MAE values
are never used to manufacture an earlier fill. Research-only; production unchanged.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, Optional, Sequence

from app.services.paper_journal import JOURNAL_PATH, iter_jsonl
from app.services.paper_validation import metrics, uncertainty

CANDIDATES = {
    "capture_0_5r": 0.5,
    "capture_1_0r": 1.0,
    "capture_1_5r": 1.5,
}


def _num(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _event_r(open_row: Dict[str, Any], mark_row: Dict[str, Any]) -> Optional[float]:
    """Compute contemporaneous gross R from the persisted mark, never final MFE."""
    direct = _num(mark_row.get("unrealized_r"))
    if direct is not None:
        return direct
    mark = _num(mark_row.get("mark"))
    entry = _num(open_row.get("actual_entry_price"))
    risk = _num(open_row.get("risk_price"))
    if mark is None or entry is None or risk is None or risk <= 0:
        return None
    side = str(open_row.get("side") or "").upper()
    if side == "LONG":
        return (mark - entry) / risk
    if side == "SHORT":
        return (entry - mark) / risk
    return None


def _cost_r(open_row: Dict[str, Any]) -> float:
    """Approximate configured round-trip fees+slippage in R using entry/risk geometry."""
    entry = _num(open_row.get("actual_entry_price"))
    risk = _num(open_row.get("risk_price"))
    if entry is None or risk is None or risk <= 0:
        return 0.0
    fees = max(0.0, _num(open_row.get("fees_bps")) or 0.0)
    slip = max(0.0, _num(open_row.get("slippage_bps")) or 0.0)
    return 2.0 * (fees + slip) / 10000.0 * abs(entry) / risk


def replay_exit_candidates(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    opens: Dict[str, Dict[str, Any]] = {}
    closes: Dict[str, Dict[str, Any]] = {}
    marks: Dict[str, list[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        tid = str(row.get("trade_id") or "")
        if not tid or str(row.get("trade_type") or "PAPER").upper() != "PAPER":
            continue
        event = str(row.get("event") or "").lower()
        if event == "open":
            opens[tid] = row
        elif event == "mark":
            marks[tid].append(row)
        elif event == "close":
            closes[tid] = row

    baseline_rows = [closes[tid] for tid in closes if tid in opens]
    result: Dict[str, Any] = {}
    for name, threshold in CANDIDATES.items():
        simulated: list[Dict[str, Any]] = []
        triggered = 0
        path_eligible = 0
        for tid, close in closes.items():
            opened = opens.get(tid)
            if opened is None:
                continue
            ordered_marks = sorted(marks.get(tid, []), key=lambda r: str(r.get("timestamp") or ""))
            usable = [(m, _event_r(opened, m)) for m in ordered_marks]
            usable = [(m, r) for m, r in usable if r is not None]
            if usable:
                path_eligible += 1
            hit = next(((m, r) for m, r in usable if r >= threshold), None)
            if hit is not None:
                triggered += 1
                net = threshold - _cost_r(opened)
                simulated.append({**close, "net_pnl_r": net, "R_multiple": net, "exit_reason": f"V6_REPLAY_{name}", "replay_exit_timestamp": hit[0].get("timestamp")})
            else:
                simulated.append(dict(close))
        result[name] = {
            "threshold_r": threshold,
            "path_eligible": path_eligible,
            "triggered": triggered,
            "trigger_rate_of_closed": round(triggered / len(baseline_rows), 6) if baseline_rows else 0.0,
            "metrics": metrics(simulated),
            "uncertainty": uncertainty(simulated),
            "prospective_validated": False,
            "promoted": False,
        }

    return {
        "ok": True,
        "title": "ATLAS V6 POINT-IN-TIME EXIT REPLAY",
        "mode": "RESEARCH_ONLY_EVENT_REPLAY",
        "closed_with_open": len(baseline_rows),
        "baseline": {**metrics(baseline_rows), "uncertainty": uncertainty(baseline_rows)},
        "candidates": result,
        "uses_final_mfe_to_trigger": False,
        "chronological_mark_events_only": True,
        "production_strategy_modified": False,
        "automatic_promotion": False,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
        "limitations": [
            "A candidate can trigger only when a persisted mark event proves the threshold was observed.",
            "Sparse mark persistence can miss intrainterval threshold touches, so replay is conservative/incomplete.",
            "Configured fees/slippage are converted to R from entry/risk geometry; this is research accounting, not a venue fill claim.",
        ],
    }


def exit_replay_report(*, journal_path=JOURNAL_PATH, rows: Optional[Iterable[Dict[str, Any]]] = None) -> Dict[str, Any]:
    data = list(rows) if rows is not None else iter_jsonl(journal_path)
    return replay_exit_candidates(data)
