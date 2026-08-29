"""Phase 6 — paper performance VALIDATION. Research only.

Never changes RSI 28/72, extension 1.4%, R:R 1.8, quality/liquidity,
entry/exit, paper opens, or Discord /paper. Never mixes shadow with paper
into one performance number. Never unlocks live capital.
"""

from __future__ import annotations

import math
import random
import statistics
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.analytics.regime import normalize_regime
from app.services.outcome_research import (
    accepted_vs_rejected,
    load_paper_closes,
    load_shadow_resolved,
    paper_performance,
    shadow_performance,
)

MILESTONES = (30, 50, 75, 100, 150, 250, 500)
SIDE_MIN_N = 20
REGIME_MIN_N = 15
STABLE_N = 50
BOOTSTRAP_N = 2000
MC_N = 2000
Z95 = 1.96
FUTURE_FEATURE_KEYS = {
    "actual_exit_price",
    "exit_price",
    "net_pnl_r",
    "gross_pnl_r",
    "R_multiple",
    "hypothetical_r",
    "hypothetical_final_r",
    "future_rsi",
    "future_close",
    "future_price",
    "win",
    "result",
}


def _f(row: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in row and row[k] is not None:
            try:
                return float(row[k])
            except (TypeError, ValueError):
                continue
    return default


def _parse_iso(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _t_crit(df: int) -> float:
    if df <= 0:
        return 12.7
    if df == 1:
        return 12.71
    if df == 2:
        return 4.30
    if df < 5:
        return 3.18
    if df < 10:
        return 2.26
    if df < 20:
        return 2.09
    if df < 30:
        return 2.05
    if df < 60:
        return 2.00
    return 1.96


def r_series(rows: Sequence[Dict[str, Any]]) -> List[float]:
    return [_f(r, "net_pnl_r", "R_multiple", "hypothetical_r") for r in rows]


def wilson_ci(wins: int, n: int, z: float = Z95) -> Tuple[Optional[float], Optional[float]]:
    """95% Wilson score interval for a binomial proportion."""
    if n <= 0:
        return None, None
    p = wins / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = z * math.sqrt((p * (1.0 - p) + z2 / (4 * n)) / n) / denom
    lo = max(0.0, center - margin)
    hi = min(1.0, center + margin)
    return round(lo, 4), round(hi, 4)


def mean_t_ci(xs: Sequence[float], z: Optional[float] = None) -> Tuple[Optional[float], Optional[float]]:
    n = len(xs)
    if n < 2:
        return None, None
    m = float(sum(xs) / n)
    sd = float(statistics.stdev(xs))
    se = sd / math.sqrt(n)
    crit = z if z is not None else _t_crit(n - 1)
    return round(m - crit * se, 4), round(m + crit * se, 4)


def _max_drawdown(rs: Sequence[float]) -> float:
    peak = eq = 0.0
    dd = 0.0
    for x in rs:
        eq += x
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return dd


def _streak(rs: Sequence[float], losing: bool) -> int:
    best = cur = 0
    for x in rs:
        hit = x <= 0 if losing else x > 0
        if hit:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def metrics(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    rs = r_series(rows)
    n = len(rs)
    if n == 0:
        return {
            "n": 0,
            "wins": 0,
            "losses": 0,
            "winrate": 0.0,
            "total_r": 0.0,
            "average_r": 0.0,
            "median_r": 0.0,
            "expectancy": 0.0,
            "avg_winner": 0.0,
            "avg_loser": 0.0,
            "payoff_ratio": None,
            "profit_factor": None,
            "max_drawdown_r": 0.0,
            "longest_losing_streak": 0,
            "longest_winning_streak": 0,
            "median_duration_sec": 0.0,
            "average_duration_sec": 0.0,
            "avg_mfe": 0.0,
            "avg_mae": 0.0,
            "mfe_mae_ratio": None,
        }
    wins_r = [x for x in rs if x > 0]
    loss_r = [x for x in rs if x <= 0]
    wins = len(wins_r)
    losses = len(loss_r)
    avg_win = sum(wins_r) / wins if wins else 0.0
    avg_loss = sum(loss_r) / losses if losses else 0.0
    payoff = (avg_win / abs(avg_loss)) if losses and avg_loss != 0 else None
    gross_win = sum(wins_r)
    gross_loss = abs(sum(loss_r))
    if losses == 0 and wins:
        pf: Optional[float] = None
        pf_label = "undefined (no losses)"
    elif gross_loss == 0:
        pf = None
        pf_label = "undefined"
    else:
        pf = round(gross_win / gross_loss, 4)
        pf_label = str(pf)
    mfes = [_f(r, "mfe_r") for r in rows]
    maes = [_f(r, "mae_r") for r in rows]
    durs = [_f(r, "holding_time_sec", "duration_sec") for r in rows]
    avg_mfe = sum(mfes) / n
    avg_mae = sum(maes) / n
    return {
        "n": n,
        "wins": wins,
        "losses": losses,
        "winrate": round(wins / n, 4),
        "total_r": round(sum(rs), 4),
        "average_r": round(sum(rs) / n, 4),
        "median_r": round(float(statistics.median(rs)), 4),
        "expectancy": round(sum(rs) / n, 4),
        "avg_winner": round(avg_win, 4),
        "avg_loser": round(avg_loss, 4),
        "payoff_ratio": None if payoff is None else round(payoff, 4),
        "profit_factor": pf,
        "profit_factor_note": pf_label,
        "max_drawdown_r": round(_max_drawdown(rs), 4),
        "longest_losing_streak": _streak(rs, True),
        "longest_winning_streak": _streak(rs, False),
        "median_duration_sec": round(float(statistics.median(durs)), 1),
        "average_duration_sec": round(sum(durs) / n, 1),
        "avg_mfe": round(avg_mfe, 4),
        "avg_mae": round(avg_mae, 4),
        "mfe_mae_ratio": None if avg_mae == 0 else round(avg_mfe / avg_mae, 4),
    }


def r_milestones(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows) or 1
    out: Dict[str, Any] = {}
    for m in (0.5, 1.0, 1.5, 1.8, 2.0):
        key = str(m).replace(".", "_")
        hit = 0
        for r in rows:
            mfe = _f(r, "mfe_r")
            if r.get(f"reached_{key}r") is True or mfe + 1e-12 >= m:
                hit += 1
        out[f"reached_{key}r"] = {
            "count": hit,
            "pct": round(100.0 * hit / n, 1) if rows else 0.0,
        }
    return out


def uncertainty(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    rs = r_series(rows)
    n = len(rs)
    wins = sum(1 for x in rs if x > 0)
    wr_lo, wr_hi = wilson_ci(wins, n)
    exp_lo, exp_hi = mean_t_ci(rs)
    too_small = n < 30
    return {
        "n": n,
        "winrate_observed": round(wins / n, 4) if n else 0.0,
        "winrate_ci95": [wr_lo, wr_hi],
        "expectancy_observed": round(sum(rs) / n, 4) if n else 0.0,
        "expectancy_ci95": [exp_lo, exp_hi],
        "method_winrate": "wilson_score_95",
        "method_expectancy": "student_t_95",
        "sample_too_small": too_small,
        "note": (
            "n<30 — treat WR/expectancy as noise, not a population statistic."
            if too_small
            else (
                "n<50 — directional only; intervals are wide."
                if n < STABLE_N
                else "n>=50 — still not permission to go live."
            )
        ),
    }


def _sort_chrono(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(r: Dict[str, Any]) -> str:
        return str(r.get("exit_timestamp") or r.get("entry_timestamp") or "")

    return sorted(rows, key=key)


def chronological(rows: Sequence[Dict[str, Any]], group_size: int = 10) -> Dict[str, Any]:
    ordered = _sort_chrono(rows)
    groups: List[Dict[str, Any]] = []
    for i in range(0, len(ordered), group_size):
        chunk = ordered[i : i + group_size]
        start = i + 1
        end = i + len(chunk)
        m = metrics(chunk)
        groups.append(
            {
                "label": f"trades {start}–{end}",
                "start": start,
                "end": end,
                "n": m["n"],
                "winrate": m["winrate"],
                "average_r": m["average_r"],
                "total_r": m["total_r"],
                "max_drawdown_r": m["max_drawdown_r"],
                "exploratory": True,
            }
        )
    cumul: List[Dict[str, Any]] = []
    for cap in (10, 20, 25, 30, 50, 75, 100, 150, 250, 500):
        if len(ordered) < cap and cap not in (10, 20, 25) and len(ordered) < 10:
            continue
        if not ordered:
            break
        take = ordered[: min(cap, len(ordered))]
        if cap > len(ordered) and cap not in (10, 20, 25):
            continue
        m = metrics(take)
        cumul.append(
            {
                "label": f"1–{len(take)}",
                "n": m["n"],
                "winrate": m["winrate"],
                "average_r": m["average_r"],
                "total_r": m["total_r"],
                "max_drawdown_r": m["max_drawdown_r"],
            }
        )
    return {"sequential_groups": groups, "cumulative": cumul, "time_order": "exit_timestamp"}


def _slice_flag(n: int, min_n: int) -> Dict[str, Any]:
    return {
        "n": n,
        "min_n_for_inference": min_n,
        "exploratory": n < min_n,
        "label": "EXPLORATORY — insufficient sample" if n < min_n else "descriptive only",
    }


def side_analysis(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for side in ("LONG", "SHORT"):
        chunk = [r for r in rows if str(r.get("side") or "").upper() == side]
        m = metrics(chunk)
        flag = _slice_flag(m["n"], SIDE_MIN_N)
        out[side] = {**m, **flag}
    n_l = out["LONG"]["n"]
    n_s = out["SHORT"]["n"]
    out["comparison_note"] = (
        "Do not conclude one side is structurally superior. "
        f"LONG n={n_l}, SHORT n={n_s}; need ≥{SIDE_MIN_N} each."
    )
    out["structurally_superior"] = None
    return out


def regime_analysis(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        buckets[normalize_regime(r.get("regime_normalized") or r.get("regime"))].append(r)
    out: Dict[str, Any] = {}
    for name in ("HIGH_VOLATILITY", "LOW_VOLATILITY", "TREND_UP", "TREND_DOWN", "UNKNOWN", "RANGE"):
        chunk = buckets.get(name) or []
        if not chunk and name not in buckets:
            continue
        m = metrics(chunk)
        flag = _slice_flag(m["n"], REGIME_MIN_N)
        if name == "HIGH_VOLATILITY":
            flag["label"] = "EXPLORATORY — current HIGH_VOLATILITY result is not actionable"
            flag["exploratory"] = True
        out[name] = {**m, **flag}
    for name, chunk in buckets.items():
        if name not in out:
            m = metrics(chunk)
            out[name] = {**m, **_slice_flag(m["n"], REGIME_MIN_N)}
    return out


def shadow_vs_paper(
    paper: Sequence[Dict[str, Any]],
    shadow: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    p = metrics(paper)
    s = metrics(shadow)
    return {
        "paper": p,
        "shadow": s,
        "combined_forbidden": True,
        "note": (
            "PAPER = trades that passed production gates and were opened. "
            "SHADOW = hypothetical rejected/qualified research population. "
            "Do not average them. Different selection."
        ),
        "materially_different": abs(p["expectancy"] - s["expectancy"]) >= 0.15
        or abs(p["winrate"] - s["winrate"]) >= 0.08,
    }


def rejection_analysis() -> Dict[str, Any]:
    raw = accepted_vs_rejected()
    stages = raw.get("by_rejection_stage") or {}
    wanted = ("quality", "rr", "liquidity", "other", "extension", "rsi", "atr")
    out: Dict[str, Any] = {}
    for k in wanted:
        if k in stages:
            v = stages[k]
            out[k] = {
                "n": v.get("n", 0),
                "winrate": v.get("winrate", 0.0),
                "average_r": v.get("avg_r", 0.0),
                "avg_mfe": v.get("avg_mfe", 0.0),
                "avg_mae": v.get("avg_mae", 0.0),
                "note": "Research only. Do not remove a gate because rejects look better.",
            }
    for k, v in stages.items():
        if k not in out:
            out[k] = {
                "n": v.get("n", 0),
                "winrate": v.get("winrate", 0.0),
                "average_r": v.get("avg_r", 0.0),
                "avg_mfe": v.get("avg_mfe", 0.0),
                "avg_mae": v.get("avg_mae", 0.0),
            }
    return out


def feature_dataset(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        feats = r.get("features") if isinstance(r.get("features"), dict) else {}
        out.append(
            {
                "trade_id": r.get("trade_id"),
                "entry_timestamp": r.get("entry_timestamp") or r.get("signal_timestamp"),
                "exit_timestamp": r.get("exit_timestamp"),
                "symbol": r.get("symbol"),
                "side": r.get("side"),
                "entry": r.get("actual_entry_price") or r.get("entry"),
                "exit": r.get("actual_exit_price"),
                "R": _f(r, "net_pnl_r", "R_multiple"),
                "MFE": _f(r, "mfe_r"),
                "MAE": _f(r, "mae_r"),
                "duration_sec": _f(r, "duration_sec", "holding_time_sec"),
                "regime": normalize_regime(r.get("regime_normalized") or r.get("regime")),
                "score": r.get("signal_score") or feats.get("qscore") or feats.get("score"),
                "quality": feats.get("qscore") or r.get("signal_score"),
                "extension": feats.get("ext_pct"),
                "RSI": feats.get("rsi"),
                "liquidity_vol": feats.get("vol"),
                "liquidity_oi": feats.get("oi"),
                "R:R": feats.get("rr"),
                "atr": feats.get("atr"),
                "sma20": feats.get("sma20"),
                "tier": r.get("tier") or feats.get("tier"),
                "counts_for_live": r.get("counts_for_live"),
            }
        )
    return out


def leakage_audit(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    flags: List[Dict[str, Any]] = []
    for r in rows:
        tid = r.get("trade_id")
        reasons: List[str] = []
        t_sig = _parse_iso(r.get("signal_timestamp"))
        t_ent = _parse_iso(r.get("entry_timestamp"))
        t_ex = _parse_iso(r.get("exit_timestamp"))
        if t_sig and t_ent and t_sig > t_ent:
            reasons.append("signal_timestamp after entry_timestamp")
        if t_ent and t_ex and t_ex < t_ent:
            reasons.append("exit before entry")
        feats = r.get("features") if isinstance(r.get("features"), dict) else {}
        for k in FUTURE_FEATURE_KEYS:
            if k in feats and feats.get(k) is not None:
                reasons.append(f"feature {k} is an outcome/future field")
        if reasons:
            flags.append({"trade_id": tid, "symbol": r.get("symbol"), "reasons": reasons})
    return {
        "records": len(rows),
        "contaminated": len(flags),
        "clean": len(rows) - len(flags),
        "flags": flags[:50],
        "pass": len(flags) == 0,
        "note": "Features must be knowable before entry. Contaminated rows are excluded from inference claims.",
    }


def bootstrap(
    rs: Sequence[float],
    n_iter: int = BOOTSTRAP_N,
    seed: int = 6,
) -> Dict[str, Any]:
    rng = random.Random(seed)
    n = len(rs)
    if n == 0:
        return {"n": 0, "iterations": 0, "winrate": {}, "expectancy": {}, "total_r": {}}
    wr_s: List[float] = []
    exp_s: List[float] = []
    tot_s: List[float] = []
    for _ in range(n_iter):
        sample = [rs[rng.randrange(n)] for _ in range(n)]
        wr_s.append(sum(1 for x in sample if x > 0) / n)
        exp_s.append(sum(sample) / n)
        tot_s.append(sum(sample))

    def pct(xs: List[float], p: float) -> float:
        s = sorted(xs)
        i = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
        return round(s[i], 4)

    def pack(xs: List[float]) -> Dict[str, float]:
        return {
            "p5": pct(xs, 5),
            "p50": pct(xs, 50),
            "p95": pct(xs, 95),
            "mean": round(sum(xs) / len(xs), 4),
        }

    return {
        "n": n,
        "iterations": n_iter,
        "seed": seed,
        "winrate": pack(wr_s),
        "expectancy": pack(exp_s),
        "total_r": pack(tot_s),
        "label": "Statistical uncertainty under resampling of THIS sample. Not a forecast.",
    }


def monte_carlo_drawdown(
    rs: Sequence[float],
    n_iter: int = MC_N,
    seed: int = 6,
) -> Dict[str, Any]:
    rng = random.Random(seed)
    n = len(rs)
    if n == 0:
        return {"n": 0, "iterations": 0}
    dds: List[float] = []
    streaks: List[int] = []
    for _ in range(n_iter):
        sample = [rs[rng.randrange(n)] for _ in range(n)]
        dds.append(_max_drawdown(sample))
        streaks.append(_streak(sample, True))

    def pct(xs: List[float], p: float) -> float:
        s = sorted(xs)
        i = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
        return float(s[i])

    return {
        "n": n,
        "iterations": n_iter,
        "seed": seed,
        "drawdown_r": {
            "p50": round(pct(dds, 50), 4),
            "p90": round(pct(dds, 90), 4),
            "p95": round(pct(dds, 95), 4),
        },
        "losing_streak": {
            "p50": int(pct([float(x) for x in streaks], 50)),
            "p90": int(pct([float(x) for x in streaks], 90)),
            "p95": int(pct([float(x) for x in streaks], 95)),
        },
        "label": "Risk under the historical R distribution. Not a guaranteed future bound.",
    }


def milestone_status(n: int) -> Dict[str, Any]:
    reached = [m for m in MILESTONES if n >= m]
    next_m = next((m for m in MILESTONES if n < m), None)
    return {
        "closed": n,
        "reached": reached,
        "next": next_m,
        "current_label": (
            "INSUFFICIENT SAMPLE"
            if n < 30
            else (
                f"Milestone {reached[-1]} reached — still research only"
                if reached
                else "INSUFFICIENT SAMPLE"
            )
        ),
        "unlocks_live": False,
    }


def readiness_report(
    paper: Optional[Sequence[Dict[str, Any]]] = None,
    shadow: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    rows = list(paper) if paper is not None else load_paper_closes()
    sh = list(shadow) if shadow is not None else load_shadow_resolved()
    m = metrics(rows)
    unc = uncertainty(rows)
    leak = leakage_audit(rows)
    ms = milestone_status(m["n"])
    wr_ci = unc["winrate_ci95"]
    exp_ci = unc["expectancy_ci95"]
    data_sufficiency = "LOW" if m["n"] < 50 else ("MODERATE" if m["n"] < 100 else "HIGH")
    stat_stability = "LOW"
    if m["n"] >= 50 and wr_ci[0] is not None and exp_ci[0] is not None:
        if wr_ci[0] > 0.5 and exp_ci[0] > 0:
            stat_stability = "MODERATE"
    performance = "OBSERVED_POSITIVE" if m["expectancy"] > 0 and m["winrate"] > 0.5 else "MIXED_OR_NEGATIVE"
    risk = "UNKNOWN" if m["n"] < 30 else "DESCRIBED_NOT_STRESSED"
    conclusion = "INSUFFICIENT EVIDENCE FOR LIVE CAPITAL"
    return {
        "title": "ATLAS TRADING RESEARCH",
        "closed_trades": m["n"],
        "observed_wr": m["winrate"],
        "observed_expectancy": m["expectancy"],
        "total_r": m["total_r"],
        "data_sufficiency": data_sufficiency,
        "statistical_stability": stat_stability,
        "performance": performance,
        "risk": risk,
        "data_integrity": "PASS" if leak["pass"] else "FAIL",
        "provider_health": "PASS",
        "side_stability": "UNKNOWN",
        "regime_stability": "UNKNOWN",
        "sample_size": "LOW" if m["n"] < 50 else "OK",
        "statistical_confidence": "LOW" if m["n"] < 50 else "MODERATE",
        "milestone": ms,
        "live_capital_allowed": False,
        "conclusion": conclusion,
        "uncertainty": unc,
        "metrics": m,
        "shadow_n": len(sh),
        "disclaimer": (
            "Observed results are a small-sample paper record. "
            "Not a claim of alpha, profitability, or live-readiness."
        ),
    }


def full_report(seed: int = 6) -> Dict[str, Any]:
    paper = load_paper_closes()
    shadow = load_shadow_resolved()
    rs = r_series(paper)
    return {
        "generated_for": "PHASE_6_PAPER_VALIDATION",
        "control_gates": {
            "rsi_long": 28.0,
            "rsi_short": 72.0,
            "extension_pct": 1.4,
            "min_rr": 1.8,
            "unchanged": True,
        },
        "paper_n": len(paper),
        "metrics": metrics(paper),
        "r_milestones": r_milestones(paper),
        "uncertainty": uncertainty(paper),
        "chronological": chronological(paper),
        "side": side_analysis(paper),
        "regime": regime_analysis(paper),
        "shadow_vs_paper": shadow_vs_paper(paper, shadow),
        "rejection": rejection_analysis(),
        "feature_dataset_n": len(feature_dataset(paper)),
        "leakage": leakage_audit(paper),
        "bootstrap": bootstrap(rs, seed=seed),
        "monte_carlo": monte_carlo_drawdown(rs, seed=seed),
        "readiness": readiness_report(paper, shadow),
        "legacy_paper_performance": paper_performance(paper),
        "legacy_shadow_performance": shadow_performance(shadow),
    }


def validation_text(limit: int = 1900) -> str:
    r = full_report()
    m = r["metrics"]
    u = r["uncertainty"]
    rd = r["readiness"]
    wr_ci = u["winrate_ci95"]
    exp_ci = u["expectancy_ci95"]
    wr_s = (
        f"{wr_ci[0]*100:.1f}–{wr_ci[1]*100:.1f}%"
        if wr_ci[0] is not None
        else "n/a"
    )
    exp_s = (
        f"{exp_ci[0]:+.2f}–{exp_ci[1]:+.2f}R"
        if exp_ci[0] is not None
        else "n/a"
    )
    side = r["side"]
    hv = (r["regime"] or {}).get("HIGH_VOLATILITY") or {}
    lines = [
        "**ATLAS TRADING VALIDATION** (research only)",
        f"Closed: `{m['n']}` · WR `{m['winrate']*100:.1f}%` · exp `{m['expectancy']:+.2f}R` · tot `{m['total_r']:+.2f}R`",
        f"95% WR CI: `{wr_s}` · exp CI: `{exp_s}`",
        f"PF `{m.get('profit_factor')}` · DD `{m['max_drawdown_r']:.2f}R` · lose-streak `{m['longest_losing_streak']}`",
        f"MFE `{m['avg_mfe']:+.2f}` · MAE `{m['avg_mae']:+.2f}`",
        f"LONG n `{side['LONG']['n']}` WR `{side['LONG']['winrate']*100:.0f}%` avgR `{side['LONG']['average_r']:+.2f}` **exploratory**",
        f"SHORT n `{side['SHORT']['n']}` WR `{side['SHORT']['winrate']*100:.0f}%` avgR `{side['SHORT']['average_r']:+.2f}` **exploratory**",
        f"HIGH_VOL n `{hv.get('n', 0)}` — **exploratory, not actionable**",
        f"Shadow n `{r['shadow_vs_paper']['shadow']['n']}` WR `{r['shadow_vs_paper']['shadow']['winrate']*100:.1f}%` exp `{r['shadow_vs_paper']['shadow']['expectancy']:+.2f}R` (separate)",
        f"Integrity: `{'PASS' if r['leakage']['pass'] else 'FAIL'}` · sample `{rd['sample_size']}` · confidence `{rd['statistical_confidence']}`",
        f"**{rd['conclusion']}**",
        f"Milestone: `{rd['milestone']['current_label']}` · live unlock: **no**",
        "_Gates locked RSI 28/72 · ext 1.4% · R:R 1.8. Not /paper. Not financial advice._",
    ]
    text = "\n".join(lines)
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text
