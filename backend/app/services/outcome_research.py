"""Outcome collection / research aggregations. Never changes production gates."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.analytics.regime import normalize_regime

R_MILESTONES = (0.5, 1.0, 1.5, 1.8, 2.0)


def _parse_iso(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _f(row: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in row and row[k] is not None:
            try:
                return float(row[k])
            except (TypeError, ValueError):
                continue
    return default


def _median(xs: List[float]) -> float:
    if not xs:
        return 0.0
    return float(statistics.median(xs))


def _max_drawdown(equity: List[float]) -> float:
    peak = 0.0
    dd = 0.0
    for x in equity:
        peak = max(peak, x)
        dd = max(dd, peak - x)
    return dd


def _longest_losing_streak(rs: List[float]) -> int:
    best = cur = 0
    for r in rs:
        if r <= 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _bucket_stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "wins": 0,
            "losses": 0,
            "winrate": 0.0,
            "avg_r": 0.0,
            "median_r": 0.0,
            "total_r": 0.0,
            "avg_mfe": 0.0,
            "avg_mae": 0.0,
            "avg_duration_sec": 0.0,
            "median_duration_sec": 0.0,
        }
    rs = [_f(r, "net_pnl_r", "R_multiple", "hypothetical_r", "hypothetical_final_r") for r in rows]
    mfes = [_f(r, "mfe_r") for r in rows]
    maes = [_f(r, "mae_r") for r in rows]
    durs = [_f(r, "holding_time_sec", "duration_sec") for r in rows]
    wins = sum(1 for x in rs if x > 0)
    losses = sum(1 for x in rs if x <= 0)
    n = len(rows)
    return {
        "n": n,
        "wins": wins,
        "losses": losses,
        "winrate": round(wins / n, 4) if n else 0.0,
        "avg_r": round(sum(rs) / n, 4) if n else 0.0,
        "median_r": round(_median(rs), 4),
        "total_r": round(sum(rs), 4),
        "avg_mfe": round(sum(mfes) / n, 4) if n else 0.0,
        "avg_mae": round(sum(maes) / n, 4) if n else 0.0,
        "avg_duration_sec": round(sum(durs) / n, 1) if n else 0.0,
        "median_duration_sec": round(_median(durs), 1),
    }


def _milestones(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows) or 1
    out: Dict[str, Any] = {}
    for m in R_MILESTONES:
        key = str(m).replace(".", "_")
        hit = 0
        for r in rows:
            mfe = _f(r, "mfe_r")
            flagged = r.get(f"reached_{key}r")
            if flagged is True or mfe + 1e-12 >= m:
                hit += 1
        out[f"reached_{key}r"] = {"count": hit, "pct": round(100.0 * hit / n, 1) if rows else 0.0}
    return out


def load_paper_closes(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    from app.services.paper_journal import JOURNAL_PATH

    p = path or JOURNAL_PATH
    if not p.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("event") != "close":
                    continue
                if str(row.get("trade_type") or "PAPER").upper() != "PAPER":
                    continue
                rows.append(row)
    except Exception:
        return rows
    return rows


def load_shadow_resolved(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    from app.services.shadow_research import CANDIDATES_PATH

    p = path or CANDIDATES_PATH
    if not p.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if str(row.get("trade_type") or "").upper() != "SHADOW":
                    continue
                if row.get("event") == "resolved" or row.get("lifecycle") == "RESOLVED":
                    rows.append(row)
    except Exception:
        return rows
    return rows


def paper_performance(closes: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    rows = closes if closes is not None else load_paper_closes()
    base = _bucket_stats(rows)
    rs: List[float] = []
    equity: List[float] = []
    eq = 0.0
    for r in rows:
        x = _f(r, "net_pnl_r", "R_multiple")
        rs.append(x)
        eq += x
        equity.append(eq)
    n = base["n"]
    wr = base["winrate"]
    avg = base["avg_r"]
    # Expectancy = E[R] = avg R. Also p*avg_win - (1-p)*avg_loss if mixed.
    expectancy = avg
    dd = _max_drawdown(equity)
    streak = _longest_losing_streak(rs)
    by_side: Dict[str, Any] = {}
    for side in ("LONG", "SHORT"):
        by_side[side] = _bucket_stats([r for r in rows if str(r.get("side") or "").upper() == side])
    by_regime: Dict[str, Any] = defaultdict(list)
    for r in rows:
        rg = normalize_regime(r.get("regime_normalized") or r.get("regime"))
        by_regime[rg].append(r)
    regime_out = {k: _bucket_stats(v) for k, v in sorted(by_regime.items())}
    by_symbol: Dict[str, Any] = defaultdict(list)
    for r in rows:
        by_symbol[str(r.get("symbol") or "?").upper()].append(r)
    symbol_out = {k: _bucket_stats(v) for k, v in sorted(by_symbol.items())}
    live_rows = [r for r in rows if r.get("counts_for_live")]
    return {
        **base,
        "expectancy": round(expectancy, 4),
        "max_drawdown_r": round(dd, 4),
        "longest_losing_streak": streak,
        "milestones": _milestones(rows),
        "by_side": by_side,
        "by_regime": regime_out,
        "by_symbol": symbol_out,
        "live": _bucket_stats(live_rows),
        "sample_size": n,
        "uncertainty": (
            "n<30 — treat as noise"
            if n < 30
            else ("n<50 — directional only" if n < 50 else "n>=50 — mechanical gate possible")
        ),
        "live_ready_mechanical": False,
    }


def shadow_performance(resolved: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    rows = resolved if resolved is not None else load_shadow_resolved()
    base = _bucket_stats(rows)
    by_stage: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        stage = str(
            r.get("rejection_stage")
            or (r.get("failed_gates") or ["other"])[0]
            or r.get("reject_status")
            or "other"
        ).lower()
        if "ext" in stage:
            key = "extension"
        elif "rsi" in stage:
            key = "rsi"
        elif "quality" in stage or "score" in stage:
            key = "quality"
        elif "rr" in stage or "risk" in stage:
            key = "rr"
        elif "liq" in stage or "thin" in stage or "junk" in stage:
            key = "liquidity"
        elif "atr" in stage:
            key = "atr"
        else:
            key = "other"
        by_stage[key].append(r)
    by_regime_rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_regime_rows[normalize_regime(r.get("regime_normalized") or r.get("regime"))].append(r)
    return {
        **base,
        "milestones": _milestones(rows),
        "by_rejection_stage": {k: _bucket_stats(v) for k, v in sorted(by_stage.items())},
        "by_side": {
            "LONG": _bucket_stats([r for r in rows if str(r.get("side") or "").upper() == "LONG"]),
            "SHORT": _bucket_stats([r for r in rows if str(r.get("side") or "").upper() == "SHORT"]),
        },
        "by_regime": {k: _bucket_stats(v) for k, v in sorted(by_regime_rows.items())},
    }


def accepted_vs_rejected() -> Dict[str, Any]:
    paper = load_paper_closes()
    shadow = load_shadow_resolved()
    rejected = [
        r
        for r in shadow
        if not r.get("qualified") and str(r.get("status") or "").upper() != "QUALIFIED"
    ]
    sh = shadow_performance(shadow)
    return {
        "paper_qualified": _bucket_stats(paper),
        "shadow_rejected": _bucket_stats(rejected or shadow),
        "shadow_all_resolved": _bucket_stats(shadow),
        "by_rejection_stage": sh.get("by_rejection_stage") or {},
        "note": "Research only. Not permission to loosen gates.",
    }


def paper_text(open_n: int = 0, readiness: Optional[Dict[str, Any]] = None) -> str:
    p = paper_performance()
    side = p["by_side"]
    lines = [
        "**ATLAS PAPER PERFORMANCE**",
        f"Open: `{open_n}`",
        f"Closed: `{p['n']}`",
        f"Win/Loss: `{p['wins']}` / `{p['losses']}`",
        f"Win Rate: `{p['winrate'] * 100:.1f}%`",
        f"Total R: `{p['total_r']:+.2f}`",
        f"Average R: `{p['avg_r']:+.2f}`",
        f"Expectancy: `{p['expectancy']:+.2f}`",
        f"Average MFE: `{p['avg_mfe']:+.2f}`",
        f"Average MAE: `{p['avg_mae']:+.2f}`",
        f"Max Drawdown: `{p['max_drawdown_r']:.2f}R`",
        f"Longest Losing Streak: `{p['longest_losing_streak']}`",
        f"Median Duration: `{p['median_duration_sec']:.0f}s`",
        "",
        "**BY SIDE**",
        f"LONG: n `{side['LONG']['n']}` WR `{side['LONG']['winrate']*100:.0f}%` "
        f"avgR `{side['LONG']['avg_r']:+.2f}` tot `{side['LONG']['total_r']:+.2f}` "
        f"MFE `{side['LONG']['avg_mfe']:+.2f}` MAE `{side['LONG']['avg_mae']:+.2f}`",
        f"SHORT: n `{side['SHORT']['n']}` WR `{side['SHORT']['winrate']*100:.0f}%` "
        f"avgR `{side['SHORT']['avg_r']:+.2f}` tot `{side['SHORT']['total_r']:+.2f}` "
        f"MFE `{side['SHORT']['avg_mfe']:+.2f}` MAE `{side['SHORT']['avg_mae']:+.2f}`",
        "",
        "**BY REGIME**",
    ]
    if p["by_regime"]:
        for k, v in p["by_regime"].items():
            lines.append(
                f"`{k}` n `{v['n']}` WR `{v['winrate']*100:.0f}%` avgR `{v['avg_r']:+.2f}` tot `{v['total_r']:+.2f}`"
            )
    else:
        lines.append("_No closed trades yet._")
    if readiness:
        lines.append("")
        lines.append(f"Readiness: {readiness.get('message', 'n/a')}")
        lines.append(f"Sample: `{p['uncertainty']}`")
    lines.append("_Paper only. Shadow excluded. Not financial advice._")
    text = "\n".join(lines)
    if len(text) > 1900:
        text = text[:1900] + "…"
    return text


def rejection_text() -> str:
    cmp_ = accepted_vs_rejected()
    stages = cmp_.get("by_rejection_stage") or {}
    order = ("extension", "rsi", "quality", "rr", "liquidity", "atr", "other")
    lines = ["**REJECTION ANALYSIS** (shadow hypotheticals)"]
    for k in order:
        if k not in stages:
            continue
        v = stages[k]
        lines.append(
            f"{k}: `{v['n']}` candidates · WR `{v['winrate']*100:.0f}%` · avgR `{v['avg_r']:+.2f}`"
        )
    if len(lines) == 1:
        lines.append("_No resolved shadow candidates yet._")
    return "\n".join(lines)
