"""Buy-prep ranking for quality names. Research only — not a buy order."""

from __future__ import annotations

from typing import Any, Dict, Optional

# Momentary dip (prepare to review), not a crash.
PREPARE_OFF_HIGH = 0.08
PREPARE_1D = -0.03
PREPARE_5D = -0.05
WATCH_OFF_HIGH = 0.04
WATCH_1D = -0.015
MAJOR_OFF_HIGH = 0.25

STAND_DOWN_THESIS = {"BROKEN", "DAMAGED"}
STAND_DOWN_MOVES = {"FUNDAMENTAL_BREAKDOWN", "THESIS_DETERIORATING"}
ACCUM_STATES = {"ACCUMULATION", "DEEP_VALUE", "GENERATIONAL_OPPORTUNITY"}

ACTION_RANK = {
    "ACCUMULATE": 0,
    "PREPARE": 1,
    "STAND_DOWN": 2,
    "WATCH": 3,
    "QUIET": 4,
}

DISCLAIMER = (
    "Research only. Not a brokerage order. Not a guarantee the name recovers. "
    "You place any buy yourself."
)


def _frac(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def classify_buy_prep(
    *,
    thesis: Optional[str] = None,
    move_class: Optional[str] = None,
    investment_class: Optional[str] = None,
    drawdown: Optional[float] = None,
    ret_1d: Optional[float] = None,
    ret_5d: Optional[float] = None,
    evidence: Optional[str] = None,
) -> Dict[str, Any]:
    """Rank a quality-name snapshot for the dip board.

    drawdown / returns are fractions (0.12 = 12% off high, -0.03 = −3% 1d).
    """
    th = str(thesis or "UNKNOWN").upper()
    mv = str(move_class or "UNKNOWN").upper()
    inv = str(investment_class or "NO_ACTION").upper()
    ev = str(evidence or "UNKNOWN").upper()
    dd = _frac(drawdown)
    r1 = _frac(ret_1d)
    r5 = _frac(ret_5d)

    if th in STAND_DOWN_THESIS or mv in STAND_DOWN_MOVES:
        return {
            "action": "STAND_DOWN",
            "priority": "HIGH",
            "reason": "Thesis damaged — do not buy this dip.",
            "notify": False,
        }
    if ev in ("INSUFFICIENT",) and inv in ACCUM_STATES:
        return {
            "action": "WATCH",
            "priority": "NORMAL",
            "reason": "Evidence thin — wait for a complete snapshot.",
            "notify": False,
        }
    if inv in ACCUM_STATES:
        why = "Investment engine is in an accumulation state."
        if dd is not None:
            why = f"{abs(dd) * 100:.0f}% off high · accumulation state."
        return {
            "action": "ACCUMULATE",
            "priority": "HIGH",
            "reason": why,
            "notify": True,
        }
    off = abs(dd) if dd is not None else 0.0
    if off >= MAJOR_OFF_HIGH or mv in ("MAJOR_DISLOCATION", "EXTREME_DISLOCATION", "ABNORMAL_SELLING"):
        return {
            "action": "PREPARE",
            "priority": "HIGH",
            "reason": f"{off * 100:.0f}% off high — review for a scale-in, do not chase.",
            "notify": True,
        }
    dip = False
    bits = []
    if off >= PREPARE_OFF_HIGH:
        dip = True
        bits.append(f"{off * 100:.0f}% off high")
    if r1 is not None and r1 <= PREPARE_1D:
        dip = True
        bits.append(f"1d {r1 * 100:.1f}%")
    if r5 is not None and r5 <= PREPARE_5D:
        dip = True
        bits.append(f"5d {r5 * 100:.1f}%")
    if dip and th in ("STRONG", "INTACT", "UNDER_PRESSURE", "UNKNOWN"):
        return {
            "action": "PREPARE",
            "priority": "NORMAL",
            "reason": " · ".join(bits) + " — quality name, research a buy. Not an order.",
            "notify": True,
        }
    soft = False
    sbits = []
    if off >= WATCH_OFF_HIGH:
        soft = True
        sbits.append(f"{off * 100:.0f}% off high")
    if r1 is not None and r1 <= WATCH_1D:
        soft = True
        sbits.append(f"1d {r1 * 100:.1f}%")
    if soft:
        return {
            "action": "WATCH",
            "priority": "NORMAL",
            "reason": " · ".join(sbits) + " — soft pullback, not a buy signal.",
            "notify": False,
        }
    return {
        "action": "QUIET",
        "priority": "NORMAL",
        "reason": "No material dip on this scan.",
        "notify": False,
    }


def from_tape_row(row: Dict[str, Any]) -> Dict[str, Any]:
    dd = row.get("drawdown")
    if dd is None and row.get("pct_from_high") is not None:
        try:
            dd = float(row["pct_from_high"]) / 100.0
        except (TypeError, ValueError):
            dd = None
    r1 = row.get("ret_1d")
    if r1 is None and row.get("chg_1d") is not None:
        try:
            r1 = float(row["chg_1d"]) / 100.0
        except (TypeError, ValueError):
            r1 = None
    r5 = row.get("ret_5d")
    if r5 is None and row.get("chg_5d") is not None:
        try:
            r5 = float(row["chg_5d"]) / 100.0
        except (TypeError, ValueError):
            r5 = None
    return classify_buy_prep(
        thesis=row.get("thesis"),
        move_class=row.get("classification") or row.get("move_class"),
        investment_class=row.get("investment_class"),
        drawdown=dd if isinstance(dd, (int, float)) else None,
        ret_1d=r1 if isinstance(r1, (int, float)) else None,
        ret_5d=r5 if isinstance(r5, (int, float)) else None,
        evidence=row.get("evidence"),
    )


def format_quality_dip_alert(row: Dict[str, Any], prep: Dict[str, Any]) -> str:
    sym = str(row.get("symbol") or "")
    name = str(row.get("name") or sym)
    action = prep.get("action") or "WATCH"
    px = row.get("price")
    px_s = "UNKNOWN" if px is None else f"${float(px):,.2f}"
    off = row.get("pct_from_high")
    if off is None and row.get("drawdown") is not None:
        try:
            off = abs(float(row["drawdown"])) * 100.0
        except (TypeError, ValueError):
            off = None
    off_s = "UNKNOWN" if off is None else f"{float(off):.1f}%"
    r1 = row.get("ret_1d")
    r1_s = "UNKNOWN" if r1 is None else f"{float(r1) * 100:+.1f}%"
    r5 = row.get("ret_5d")
    r5_s = "UNKNOWN" if r5 is None else f"{float(r5) * 100:+.1f}%"
    vs = row.get("vs_spy")
    vs_s = "UNKNOWN" if vs is None else f"{float(vs) * 100:+.1f}%"
    title = f"ATLAS QUALITY DIP — {action} · {sym}"
    lines = [
        title,
        f"{name} ({sym})",
        f"Action: {action}",
        f"Why: {prep.get('reason')}",
        "",
        f"Price: {px_s}",
        f"Off high: {off_s}",
        f"1D: {r1_s}",
        f"5D: {r5_s}",
        f"vs SPY: {vs_s}",
        f"Thesis: {row.get('thesis') or 'UNKNOWN'}",
        f"Move class: {row.get('classification') or 'UNKNOWN'}",
        f"Investment class: {row.get('investment_class') or 'n/a'}",
        "",
        "WHAT TO DO:",
        "• Open the Quality Dip tab and read thesis + risks.",
        "• If you buy, you place the order. Atlas does not.",
        "• Size small. A dip can keep falling.",
        "",
        DISCLAIMER,
    ]
    return "\n".join(lines)
