"""Buy-prep ranking for quality names. Research only — not a buy order.

Cannot detect a bottom. Scores still-falling risk and prints limits *below* last
so a dip that keeps dropping is scaled, not chased. Falling knives (deep
drawdown + still selling / weak thesis) are WAIT, not ACCUMULATE.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

PREPARE_OFF_HIGH = 0.08
PREPARE_1D = -0.03
PREPARE_5D = -0.05
WATCH_OFF_HIGH = 0.04
WATCH_1D = -0.015
MAJOR_OFF_HIGH = 0.25
TRAP_OFF_HIGH = 0.40
ACCUM_MAX_OFF_HIGH = 0.38
ACCUM_MAX_1D = -0.025

STAND_DOWN_THESIS = {"BROKEN", "DAMAGED"}
STAND_DOWN_MOVES = {"FUNDAMENTAL_BREAKDOWN", "THESIS_DETERIORATING"}
DUMPING_MOVES = {
    "ELEVATED_SELLING",
    "ABNORMAL_SELLING",
    "MAJOR_DISLOCATION",
    "EXTREME_DISLOCATION",
}
CALM_MOVES = {"NORMAL", "NORMAL_PULLBACK", "UNKNOWN"}
ACCUM_STATES = {"ACCUMULATION", "DEEP_VALUE", "GENERATIONAL_OPPORTUNITY"}
LADDER_PCTS = (0.03, 0.07, 0.12, 0.18)
LADDER_LABELS = (
    "T1 first scale — only if thesis still intact",
    "T2 if it keeps falling",
    "T3 cheaper — do not skip T1/T2",
    "T4 last tranche — size small, can still fail",
)

ACTION_RANK = {
    "ACCUMULATE": 0,
    "PREPARE": 1,
    "STAND_DOWN": 2,
    "WATCH": 3,
    "QUIET": 4,
}

DISCLAIMER = (
    "Research only. Not a brokerage order. Not a bottom call. "
    "A name 40%+ off a high can keep falling. You place any buy yourself."
)


def _frac(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> int:
    return int(max(lo, min(hi, round(x))))


def still_falling_score(
    *,
    thesis: str,
    move: str,
    off: float,
    r1: Optional[float],
    r5: Optional[float],
    vs_spy: Optional[float],
) -> int:
    """0–100. High = more likely still going down. Not a bottom detector."""
    s = 18.0
    if r1 is not None:
        if r1 <= -0.02:
            s += 10
        if r1 <= -0.04:
            s += 14
        if r1 <= -0.07:
            s += 12
        if r1 >= 0.01:
            s -= 10
    if r5 is not None:
        if r5 <= -0.05:
            s += 8
        if r5 <= -0.10:
            s += 10
        if r5 >= 0.03:
            s -= 6
    if vs_spy is not None:
        if vs_spy <= -0.04:
            s += 10
        if vs_spy <= -0.08:
            s += 10
    if move in DUMPING_MOVES:
        s += 16
    if move in STAND_DOWN_MOVES:
        s += 28
    if thesis == "UNDER_PRESSURE":
        s += 14
    if thesis in STAND_DOWN_THESIS:
        s += 40
    if off >= 0.40 and (r1 is None or r1 < 0):
        s += 16
    if off >= 0.50:
        s += 8
    return _clamp(s)


def quality_dip_score(
    *,
    thesis: str,
    move: str,
    off: float,
    r1: Optional[float],
    inv: str,
) -> int:
    """0–100. High = more like a quality pullback, not exit-liquidity."""
    s = 38.0
    if thesis == "STRONG":
        s += 24
    elif thesis == "INTACT":
        s += 10
    elif thesis == "UNDER_PRESSURE":
        s -= 18
    elif thesis in STAND_DOWN_THESIS:
        s -= 40
    if move in CALM_MOVES:
        s += 14
    if move in DUMPING_MOVES:
        s -= 16
    if 0.08 <= off <= 0.30:
        s += 10
    if off >= 0.45:
        s -= 16
    if r1 is not None and r1 >= 0:
        s += 10
    if inv in ACCUM_STATES and thesis == "STRONG":
        s += 6
    return _clamp(s)


def is_trap(
    *,
    thesis: str,
    move: str,
    off: float,
    r1: Optional[float],
    falling: int,
) -> bool:
    """Deep dump + still selling or weak thesis. ORCL/MSFT-style exit liquidity."""
    if thesis in STAND_DOWN_THESIS or move in STAND_DOWN_MOVES:
        return True
    if thesis == "UNDER_PRESSURE" and off >= 0.22:
        return True
    if off >= TRAP_OFF_HIGH and (r1 is None or r1 < 0):
        return True
    if move in DUMPING_MOVES and off >= 0.22:
        return True
    if falling >= 70:
        return True
    return False


def scale_ladder(price: Optional[float], *, stance: str) -> List[Dict[str, Any]]:
    if stance in ("DO_NOT_BUY", "WATCH") or not price or price <= 0:
        return []
    out: List[Dict[str, Any]] = []
    for pct, lab in zip(LADDER_PCTS, LADDER_LABELS):
        limit = round(float(price) * (1.0 - pct), 4)
        out.append(
            {
                "label": lab,
                "pct_below": round(pct * 100.0, 1),
                "limit": limit,
                "note": f"{pct * 100:.0f}% below last ${float(price):,.2f}",
            }
        )
    return out


def classify_buy_prep(
    *,
    thesis: Optional[str] = None,
    move_class: Optional[str] = None,
    investment_class: Optional[str] = None,
    drawdown: Optional[float] = None,
    ret_1d: Optional[float] = None,
    ret_5d: Optional[float] = None,
    vs_spy: Optional[float] = None,
    evidence: Optional[str] = None,
    price: Optional[float] = None,
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
    vs = _frac(vs_spy)
    px = _frac(price)
    off = abs(dd) if dd is not None else 0.0
    falling = still_falling_score(thesis=th, move=mv, off=off, r1=r1, r5=r5, vs_spy=vs)
    quality = quality_dip_score(thesis=th, move=mv, off=off, r1=r1, inv=inv)
    trap = is_trap(thesis=th, move=mv, off=off, r1=r1, falling=falling)

    def pack(action: str, stance: str, reason: str, notify: bool, priority: str = "NORMAL") -> Dict[str, Any]:
        return {
            "action": action,
            "stance": stance,
            "priority": priority,
            "reason": reason,
            "notify": notify,
            "bottom_risk": falling,
            "quality_score": quality,
            "trap": trap,
            "ladder": scale_ladder(px, stance=stance),
            "invalidation": (
                "Thesis breaks, or another 15%+ dump without a bounce. "
                "Limits are research levels, not orders."
            ),
        }

    if th in STAND_DOWN_THESIS or mv in STAND_DOWN_MOVES:
        return pack(
            "STAND_DOWN",
            "DO_NOT_BUY",
            "Thesis damaged — do not buy this dip. Not exit-liquidity.",
            False,
            "HIGH",
        )
    if ev in ("INSUFFICIENT",) and inv in ACCUM_STATES:
        return pack("WATCH", "WATCH", "Evidence thin — wait for a complete snapshot.", False)

    calm = mv in CALM_MOVES
    bounce = r1 is None or r1 >= ACCUM_MAX_1D
    in_dip_band = PREPARE_OFF_HIGH <= off < ACCUM_MAX_OFF_HIGH
    if (
        (not trap)
        and th == "STRONG"
        and calm
        and bounce
        and in_dip_band
        and quality >= 55
        and falling < 50
    ):
        why = f"Quality pullback {off * 100:.0f}% off high. Scale with limits below last — not a bottom."
        return pack("ACCUMULATE", "SCALE_SMALL", why, True, "HIGH")

    if trap or falling >= 55 or th == "UNDER_PRESSURE" or (off >= MAJOR_OFF_HIGH and (r1 is None or r1 < 0)):
        why = (
            f"WAIT for cheaper. Still-falling risk {falling}/100. "
            f"{off * 100:.0f}% off high is not a buy-the-ask. Use the ladder if you research a scale-in."
        )
        if off >= MAJOR_OFF_HIGH or mv in DUMPING_MOVES or trap:
            return pack("PREPARE", "WAIT_CHEAPER", why, True, "HIGH")
        return pack("PREPARE", "WAIT_CHEAPER", why, True, "NORMAL")

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
        return pack(
            "PREPARE",
            "WAIT_CHEAPER",
            " · ".join(bits) + " — quality name. Wait for cheaper prints. Not an order.",
            True,
        )
    soft = False
    sbits = []
    if off >= WATCH_OFF_HIGH:
        soft = True
        sbits.append(f"{off * 100:.0f}% off high")
    if r1 is not None and r1 <= WATCH_1D:
        soft = True
        sbits.append(f"1d {r1 * 100:.1f}%")
    if soft:
        return pack(
            "WATCH",
            "WATCH",
            " · ".join(sbits) + " — soft pullback, not a buy signal.",
            False,
        )
    return pack("QUIET", "WATCH", "No material dip on this scan.", False)


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
    vs = row.get("vs_spy")
    if vs is not None and abs(float(vs)) > 2:
        vs = float(vs) / 100.0
    return classify_buy_prep(
        thesis=row.get("thesis"),
        move_class=row.get("classification") or row.get("move_class"),
        investment_class=row.get("investment_class"),
        drawdown=dd if isinstance(dd, (int, float)) else None,
        ret_1d=r1 if isinstance(r1, (int, float)) else None,
        ret_5d=r5 if isinstance(r5, (int, float)) else None,
        vs_spy=vs if isinstance(vs, (int, float)) else None,
        evidence=row.get("evidence"),
        price=row.get("price"),
    )


def format_quality_dip_alert(row: Dict[str, Any], prep: Dict[str, Any]) -> str:
    sym = str(row.get("symbol") or "")
    name = str(row.get("name") or sym)
    action = prep.get("action") or "WATCH"
    stance = prep.get("stance") or action
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
    title = f"ATLAS QUALITY DIP — {stance} · {sym}"
    lines = [
        title,
        f"{name} ({sym})",
        f"Stance: {stance}  (board action {action})",
        f"Why: {prep.get('reason')}",
        f"Still-falling risk: {prep.get('bottom_risk')}/100  (not a bottom call)",
        f"Quality-dip score: {prep.get('quality_score')}/100",
        "",
        f"Price: {px_s}",
        f"Off high: {off_s}",
        f"1D: {r1_s}",
        f"5D: {r5_s}",
        f"vs SPY: {vs_s}",
        f"Thesis: {row.get('thesis') or 'UNKNOWN'}",
        f"Move class: {row.get('classification') or 'UNKNOWN'}",
        "",
        "RESEARCH LIMIT LADDER (you place these, Atlas does not):",
    ]
    ladder = prep.get("ladder") or []
    if not ladder:
        lines.append("• None — do not scale this name.")
    else:
        for t in ladder:
            lines.append(f"• {t['label']}: ${t['limit']:,.2f}  ({t['pct_below']:.0f}% below last)")
    lines += [
        "",
        f"Invalidation: {prep.get('invalidation')}",
        "",
        "WHAT TO DO:",
        "• Do not buy the ask on a name that is still dumping.",
        "• If you buy, use limits below last and leave dry powder for lower prints.",
        "• Size small. A 50% drawdown can become 70%.",
        "",
        DISCLAIMER,
    ]
    return "\n".join(lines)
