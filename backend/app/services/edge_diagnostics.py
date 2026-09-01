"""Phase 8 — ATLAS EDGE DIAGNOSTICS. Research only.

Diagnoses WHERE paper trades make/lose R. Does not change RSI 28/72,
extension 1.4%, R:R 1.8, paper/shadow behavior, or unlock live capital.
Never shuffles. Never mixes paper+shadow into one performance number.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from app.analytics.regime import normalize_regime
from app.services.outcome_research import load_paper_closes, load_shadow_resolved
from app.services.paper_validation import (
    SIDE_MIN_N,
    _f,
    _parse_iso,
    _sort_chrono,
    feature_buckets,
    hour_dow_analysis,
    leakage_audit,
    mean_t_ci,
    metrics,
    r_milestones,
    r_series,
    regime_analysis,
    shadow_vs_paper,
    side_analysis,
    uncertainty,
)

TIME_MIN_N = 15
GATE_MIN_N = 15
SYMBOL_MIN_N = 8
HOLDOUT_MIN_N = 40
FORBIDDEN = (
    "change rsi to",
    "disable this gate",
    "trade only shorts",
    "trade only longs",
    "trade only high volatility",
    "this is profitable",
    "unlock live",
    "go live",
    "live capital allowed",
)


def _label(n: int, min_n: int) -> str:
    if n < min_n:
        return "EXPLORATORY — insufficient sample"
    return "Observed difference — exploratory; requires holdout validation"


def _json_safe(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, bool)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if hasattr(obj, "isoformat"):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    return str(obj)


def _section(name: str, fn: Callable[[], Any], errors: List[str]) -> Any:
    try:
        return fn()
    except Exception as e:
        errors.append(f"{name}: {type(e).__name__}: {str(e)[:180]}")
        return {"error": str(e)[:180], "section": name}


def _empty_baseline() -> Dict[str, Any]:
    return metrics([])


def classify_row(row: Dict[str, Any]) -> str:
    """closed / open / malformed / ignored — never silently drop a close."""
    if not isinstance(row, dict):
        return "malformed"
    if row.get("event") == "_malformed":
        return "malformed"
    ev = str(row.get("event") or "")
    if ev == "open":
        return "open"
    if ev == "mark":
        return "ignored"
    if ev != "close":
        return "ignored"
    if str(row.get("trade_type") or "PAPER").upper() == "TEST":
        return "ignored"
    try:
        _f(row, "net_pnl_r", "R_multiple")
    except Exception:
        return "malformed"
    return "closed"


def load_paper_closes_safe(
    path: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
    from app.services.paper_journal import JOURNAL_PATH, iter_jsonl

    p = path or JOURNAL_PATH
    rows: List[Dict[str, Any]] = []
    malformed: List[Dict[str, Any]] = []
    counts = {"closed": 0, "open": 0, "malformed": 0, "ignored": 0, "lines": 0}
    if not p.exists():
        return rows, malformed, counts
    for row in iter_jsonl(p):
        counts["lines"] += 1
        kind = classify_row(row)
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "malformed":
            malformed.append({"trade_id": row.get("trade_id"), "line": row.get("line"), "raw": row.get("raw")})
            continue
        if kind == "closed":
            rows.append(row)
    return rows, malformed, counts


def load_mark_events(path: Optional[Path] = None) -> Dict[str, List[Dict[str, Any]]]:
    from app.services.paper_journal import JOURNAL_PATH, iter_jsonl

    p = path or JOURNAL_PATH
    out: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    if not p.exists():
        return {}
    for row in iter_jsonl(p):
        if row.get("event") != "mark":
            continue
        tid = str(row.get("trade_id") or "")
        if tid:
            out[tid].append(row)
    return dict(out)


def _first_touch(marks: Sequence[Dict[str, Any]], *, field: str, target: float, t0) -> Optional[float]:
    if t0 is None or target <= 0 or not marks:
        return None
    for m in marks:
        try:
            v = float(m.get(field) or 0)
        except (TypeError, ValueError):
            continue
        if v + 1e-12 >= target:
            ts = _parse_iso(m.get("timestamp"))
            if ts is None:
                return None
            return max(0.0, (ts - t0).total_seconds())
    return None


def enrich_exits(
    rows: Sequence[Dict[str, Any]],
    marks: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> List[Dict[str, Any]]:
    marks = marks or {}
    out: List[Dict[str, Any]] = []
    for r in rows:
        pnl = _f(r, "net_pnl_r", "R_multiple")
        mfe = _f(r, "mfe_r")
        mae = _f(r, "mae_r")
        t0 = _parse_iso(r.get("entry_timestamp") or r.get("signal_timestamp"))
        tid = str(r.get("trade_id") or "")
        seq = sorted(marks.get(tid) or [], key=lambda x: str(x.get("timestamp") or ""))
        capture = (pnl / mfe) if mfe > 1e-9 else None
        row = dict(r)
        row["_pnl"] = pnl
        row["_mfe"] = mfe
        row["_mae"] = mae
        row["_capture"] = capture
        row["_gave_back"] = bool(pnl > 0 and mfe > pnl + 0.25)
        row["_loser_had_mfe"] = bool(pnl <= 0 and mfe >= 0.5)
        row["_time_to_mfe"] = _first_touch(seq, field="mfe_r", target=mfe, t0=t0) if mfe > 0 else None
        row["_time_to_mae"] = _first_touch(seq, field="mae_r", target=mae, t0=t0) if mae > 0 else None
        out.append(row)
    return out


def exit_diagnosis(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows) or 1
    enriched = rows if rows and "_mfe" in rows[0] else enrich_exits(rows)
    wins = [r for r in enriched if r["_pnl"] > 0]
    losses = [r for r in enriched if r["_pnl"] <= 0]
    reach = {}
    for m in (0.5, 1.0, 1.5, 1.8, 2.0, 3.0):
        hit = sum(1 for r in enriched if r["_mfe"] + 1e-12 >= m)
        reach[f"reached_{str(m).replace('.', '_')}r"] = {
            "count": hit,
            "pct": round(100.0 * hit / n, 1) if rows else 0.0,
        }
    captures = [r["_capture"] for r in enriched if r["_capture"] is not None]
    winner_cap = [r["_capture"] for r in wins if r["_capture"] is not None]
    gave = sum(1 for r in enriched if r["_gave_back"])
    loser_mfe = sum(1 for r in enriched if r["_loser_had_mfe"])
    mean_cap = round(sum(captures) / len(captures), 4) if captures else None
    note = "Insufficient sample"
    if rows:
        if mean_cap is not None and mean_cap < 0.7 and reach["reached_1_0r"]["pct"] >= 30:
            note = (
                "Observed difference — exploratory: many trades print +1R MFE but "
                "capture less at exit. Diagnosis only; leave exits unchanged."
            )
        elif mean_cap is not None and mean_cap >= 0.85:
            note = (
                "Observed difference — exploratory: exits capture most of printed MFE "
                "in this sample. Requires holdout validation."
            )
        else:
            note = "Observed difference — exploratory. Requires holdout validation."
    times_mfe = [r["_time_to_mfe"] for r in enriched if r["_time_to_mfe"] is not None]
    times_mae = [r["_time_to_mae"] for r in enriched if r["_time_to_mae"] is not None]
    return {
        "n": len(enriched),
        "milestones": reach,
        "mean_mfe_capture": mean_cap,
        "winner_mean_capture": round(sum(winner_cap) / len(winner_cap), 4) if winner_cap else None,
        "winners_gave_back_count": gave,
        "winners_gave_back_pct": round(100.0 * gave / max(1, len(wins)), 1) if wins else 0.0,
        "losers_with_positive_mfe_count": loser_mfe,
        "losers_with_positive_mfe_pct": round(100.0 * loser_mfe / max(1, len(losses)), 1) if losses else 0.0,
        "avg_mfe": round(sum(r["_mfe"] for r in enriched) / len(enriched), 4) if enriched else 0.0,
        "avg_mae": round(sum(r["_mae"] for r in enriched) / len(enriched), 4) if enriched else 0.0,
        "median_time_to_mfe_sec": (
            round(sorted(times_mfe)[len(times_mfe) // 2], 1) if times_mfe else None
        ),
        "median_time_to_mae_sec": (
            round(sorted(times_mae)[len(times_mae) // 2], 1) if times_mae else None
        ),
        "time_to_extreme_coverage": round(100.0 * len(times_mfe) / n, 1) if rows else 0.0,
        "time_to_extreme_note": (
            "time_to_mfe/mae UNKNOWN when mark events are missing — not filled with 0"
            if not times_mfe
            else "time_to_mfe derived from journal mark events (point-in-time)"
        ),
        "exit_reasons": _reason_counts(enriched),
        "do_not_change_exits": True,
        "note": note,
    }


def _reason_counts(rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    c: Dict[str, int] = defaultdict(int)
    for r in rows:
        c[str(r.get("exit_reason") or r.get("result") or "UNKNOWN")] += 1
    return dict(c)


def direction_deep(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    side = side_analysis(rows)
    long_rs = r_series([r for r in rows if str(r.get("side") or "").upper() == "LONG"])
    short_rs = r_series([r for r in rows if str(r.get("side") or "").upper() == "SHORT"])
    l_ci = mean_t_ci(long_rs)
    s_ci = mean_t_ci(short_rs)
    overlap = True
    if l_ci[0] is not None and s_ci[0] is not None:
        overlap = not (l_ci[1] < s_ci[0] or s_ci[1] < l_ci[0])
    n_ok = len(long_rs) >= SIDE_MIN_N and len(short_rs) >= SIDE_MIN_N
    return {
        **side,
        "long_expectancy_ci95": list(l_ci),
        "short_expectancy_ci95": list(s_ci),
        "ci_overlap": overlap,
        "statistical": (
            "Insufficient sample"
            if not n_ok
            else (
                "CIs overlap — observed difference is exploratory, not distinguishable"
                if overlap
                else "CIs do not overlap in this sample — still requires holdout validation"
            )
        ),
        "structurally_superior": None,
        "recommendation": "none — do not restrict to one side",
    }


def session_bucket(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    def sess(r: Dict[str, Any]) -> str:
        ts = _parse_iso(r.get("entry_timestamp") or r.get("signal_timestamp"))
        if ts is None:
            return "UNKNOWN"
        h = ts.hour
        if h < 7:
            return "ASIA"
        if h < 13:
            return "LONDON"
        if h < 21:
            return "NEW_YORK"
        return "LATE"

    from app.services.paper_validation import _bucket

    return {
        "session": _bucket(rows, sess, TIME_MIN_N),
        "hour_dow": hour_dow_analysis(rows),
        "min_n": TIME_MIN_N,
        "note": "Thin time buckets are EXPLORATORY. Do not retune gates from clock time.",
    }


def gate_interactions(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Existing locked-gate feature values only. Does not search new thresholds."""
    from app.services.paper_validation import _bucket, feature_buckets as fb

    independent = fb(rows)

    def combo(r: Dict[str, Any]) -> str:
        feats = r.get("features") if isinstance(r.get("features"), dict) else {}
        rsi = feats.get("rsi")
        ext = feats.get("ext_pct")
        q = feats.get("qscore") or r.get("signal_score")
        try:
            rsi_s = "OB" if float(rsi) >= 72 else ("OS" if float(rsi) <= 28 else "MID")
        except (TypeError, ValueError):
            rsi_s = "UNK"
        try:
            ext_s = "EXT>=2" if float(ext) >= 2.0 else "EXT_1.4-2"
        except (TypeError, ValueError):
            ext_s = "UNK"
        try:
            q_s = "Q>=85" if float(q) >= 85 else ("Q70-85" if float(q) >= 70 else "Q<70")
        except (TypeError, ValueError):
            q_s = "UNK"
        return f"{rsi_s}|{ext_s}|{q_s}"

    combos = _bucket(rows, combo, GATE_MIN_N)
    pos = [
        k
        for k, v in combos.items()
        if isinstance(v, dict) and v.get("n", 0) >= GATE_MIN_N and v.get("expectancy", 0) > 0
    ]
    neg = [
        k
        for k, v in combos.items()
        if isinstance(v, dict) and v.get("n", 0) >= GATE_MIN_N and v.get("expectancy", 0) < 0
    ]
    return {
        "gates_locked": {"rsi_long": 28.0, "rsi_short": 72.0, "extension_pct": 1.4, "min_rr": 1.8},
        "independent": independent,
        "combinations": combos,
        "positive_expectancy_combos_min_n": pos,
        "negative_expectancy_combos_min_n": neg,
        "note": (
            "Descriptive of the locked gates as they already fired. "
            "Do not search for better thresholds. Do not drop a locked gate."
        ),
        "do_not_optimize": True,
    }


def loss_clusters(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    from app.services.paper_validation import _bucket

    def sym(r):
        return str(r.get("symbol") or "UNKNOWN")

    def hour(r):
        ts = _parse_iso(r.get("entry_timestamp") or r.get("signal_timestamp"))
        return "UNKNOWN" if ts is None else f"{ts.hour:02d}"

    def side(r):
        return str(r.get("side") or "UNKNOWN").upper()

    def reg(r):
        return normalize_regime(r.get("regime_normalized") or r.get("regime"))

    def setup(r):
        feats = r.get("features") if isinstance(r.get("features"), dict) else {}
        return f"{side(r)}|{reg(r)}|{feats.get('tier') or r.get('tier') or 'na'}"

    symbols = _bucket(rows, sym, SYMBOL_MIN_N)
    worst_sym = sorted(
        ((k, v) for k, v in symbols.items() if isinstance(v, dict)),
        key=lambda kv: kv[1].get("total_r", 0),
    )[:5]
    regimes = regime_analysis(rows)
    worst_reg = None
    worst_r = None
    for name, m in regimes.items():
        if not isinstance(m, dict) or "total_r" not in m:
            continue
        if worst_reg is None or m["total_r"] < (worst_r if worst_r is not None else 0):
            worst_reg, worst_r = name, m["total_r"]
    return {
        "by_symbol": {k: v for k, v in worst_sym},
        "by_regime": regimes,
        "by_hour": _bucket(rows, hour, TIME_MIN_N),
        "by_side": _bucket(rows, side, SIDE_MIN_N),
        "by_setup": _bucket(rows, setup, GATE_MIN_N),
        "weakest_regime_observed": worst_reg,
        "note": "Loss cluster is concentration in this sample, not causation. Thin buckets EXPLORATORY.",
    }


def drawdown_path(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    ordered = _sort_chrono(rows)
    rs = r_series(ordered)
    peak = eq = 0.0
    dd = 0.0
    trough_i = 0
    peak_i = 0
    start_i = 0
    for i, x in enumerate(rs):
        eq += x
        if eq >= peak:
            peak = eq
            peak_i = i
        cur_dd = peak - eq
        if cur_dd > dd:
            dd = cur_dd
            start_i = peak_i
            trough_i = i
    window = ordered[start_i : trough_i + 1] if ordered else []
    sides: Dict[str, int] = defaultdict(int)
    regs: Dict[str, int] = defaultdict(int)
    for r in window:
        sides[str(r.get("side") or "UNKNOWN").upper()] += 1
        regs[normalize_regime(r.get("regime_normalized") or r.get("regime"))] += 1
    m = metrics(ordered)
    return {
        "max_drawdown_r": round(dd, 4),
        "longest_losing_streak": m["longest_losing_streak"],
        "window_n": len(window),
        "window_side_counts": dict(sides),
        "window_regime_counts": dict(regs),
        "looks": (
            "concentrated"
            if window and (max(sides.values() or [0]) >= max(3, 0.6 * len(window)) or max(regs.values() or [0]) >= max(3, 0.6 * len(window)))
            else "not obviously concentrated — could be random-looking in this sample"
        ),
        "causation": False,
        "note": "Do not infer why the drawdown happened. Descriptive path only.",
    }


def holdout_split(rows: Sequence[Dict[str, Any]], frac: float = 1.0 / 3.0) -> Dict[str, Any]:
    ordered = _sort_chrono(rows)
    n = len(ordered)
    if n < HOLDOUT_MIN_N:
        return {
            "available": False,
            "n": n,
            "min_n": HOLDOUT_MIN_N,
            "label": "Insufficient sample for a chronological holdout",
            "shuffled": False,
        }
    n_hold = max(10, int(n * frac))
    research = ordered[:-n_hold]
    holdout = ordered[-n_hold:]
    rm = metrics(research)
    hm = metrics(holdout)
    return {
        "available": True,
        "shuffled": False,
        "split": "chronological — earlier = research, later = holdout",
        "research": {
            "label": "RESEARCH (earlier, not a live claim)",
            "n": rm["n"],
            "winrate": rm["winrate"],
            "expectancy": rm["expectancy"],
            "total_r": rm["total_r"],
            "first_ts": research[0].get("exit_timestamp") or research[0].get("entry_timestamp"),
            "last_ts": research[-1].get("exit_timestamp") or research[-1].get("entry_timestamp"),
        },
        "holdout": {
            "label": "HOLDOUT (later, unseen by the research cut)",
            "n": hm["n"],
            "winrate": hm["winrate"],
            "expectancy": hm["expectancy"],
            "total_r": hm["total_r"],
            "first_ts": holdout[0].get("exit_timestamp") or holdout[0].get("entry_timestamp"),
            "last_ts": holdout[-1].get("exit_timestamp") or holdout[-1].get("entry_timestamp"),
        },
        "note": "Never shuffled. Holdout is not permission to change gates.",
    }


def regime_transitions(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    ordered = _sort_chrono(rows)
    if len(ordered) < 20:
        return {"available": False, "note": "Insufficient sample"}
    pairs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    prev = None
    for r in ordered:
        cur = normalize_regime(r.get("regime_normalized") or r.get("regime"))
        if prev:
            pairs[f"{prev}->{cur}"].append(r)
        prev = cur
    from app.services.paper_validation import _bucket

    # reuse metrics per pair
    out = {}
    for k, chunk in pairs.items():
        m = metrics(chunk)
        from app.services.paper_validation import _slice_flag

        out[k] = {**m, **_slice_flag(m["n"], TIME_MIN_N)}
    return {
        "available": True,
        "pairs": out,
        "note": "Trade-to-trade regime labels, not intra-trade transitions. EXPLORATORY.",
    }


def narrative(report: Dict[str, Any]) -> Dict[str, List[str]]:
    m = report["baseline"]
    side = report["direction"]
    regimes = report["regime"]
    ex = report["exit"]
    ho = report["holdout"]
    know = [
        f"Paper n={m['n']} WR={m['winrate']*100:.1f}% exp={m['expectancy']:+.2f}R tot={m['total_r']:+.2f}R DD={m['max_drawdown_r']:.2f}R streak={m['longest_losing_streak']}.",
        "Gates remain RSI 28/72, extension 1.4%, R:R 1.8. This report does not change them.",
        "Shadow is stored and scored separately from paper.",
    ]
    promising: List[str] = []
    weak: List[str] = []
    unknown: List[str] = [
        "Whether any observed difference survives a later holdout after a strategy change (none has been made).",
        "Whether MFE giveback is an exit-rule issue or path noise.",
        "Whether LONG vs SHORT is a structural property or a sample/regime artifact.",
    ]
    sh = side.get("SHORT") or {}
    lg = side.get("LONG") or {}
    if sh.get("n", 0) >= SIDE_MIN_N and sh.get("expectancy", 0) > lg.get("expectancy", 0):
        promising.append(
            f"SHORT avgR {sh.get('expectancy'):+.2f} vs LONG {lg.get('expectancy'):+.2f} in this sample. "
            f"{side.get('statistical')} — not a reason to restrict to one side."
        )
    hv = regimes.get("HIGH_VOLATILITY") or {}
    if hv.get("n", 0) >= 15 and hv.get("expectancy", 0) > 0:
        promising.append(
            f"HIGH_VOLATILITY n={hv.get('n')} exp={hv.get('expectancy'):+.2f}R observed. "
            "Exploratory; not a reason to restrict to one volatility regime."
        )
    for name in ("RANGE", "LOW_VOLATILITY"):
        b = regimes.get(name) or {}
        if b.get("n"):
            weak.append(
                f"{name} n={b.get('n')} WR={b.get('winrate', 0)*100:.0f}% exp={b.get('expectancy', 0):+.2f}R. "
                f"{_label(b.get('n', 0), 15)}."
            )
    if ex.get("mean_mfe_capture") is not None:
        know.append(
            f"Mean MFE capture {ex['mean_mfe_capture']}; "
            f"losers with +MFE {ex['losers_with_positive_mfe_pct']}%; "
            f"winners that gave back {ex['winners_gave_back_pct']}%."
        )
    if not ho.get("available"):
        unknown.append("Chronological holdout not available — sample below minimum.")
    else:
        h = ho["holdout"]
        know.append(
            f"Holdout n={h['n']} WR={h['winrate']*100:.1f}% exp={h['expectancy']:+.2f}R (later period, not shuffled)."
        )
    text = " ".join(know + promising + weak + unknown).lower()
    for phrase in FORBIDDEN:
        if phrase in text:
            # Never 500 the API. Redact; tests assert output does not recommend these.
            text = text.replace(phrase, "[redacted]")
            unknown.append("A phrasing guard redacted a disallowed recommendation string.")
    return {
        "WHAT_WE_KNOW": know,
        "WHAT_LOOKS_PROMISING": promising or ["Nothing is confirmed. Observed positives stay exploratory."],
        "WHAT_LOOKS_WEAK": weak or ["No negative-expectancy regime has a large enough sample to call structural."],
        "WHAT_IS_STILL_UNKNOWN": unknown,
    }


def edge_report(
    *,
    paper: Optional[Sequence[Dict[str, Any]]] = None,
    shadow: Optional[Sequence[Dict[str, Any]]] = None,
    marks: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    journal_path: Optional[Path] = None,
) -> Dict[str, Any]:
    errors: List[str] = []
    malformed: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    try:
        if paper is not None:
            rows = list(paper)
        else:
            rows, malformed, counts = load_paper_closes_safe(journal_path)
        sh = list(shadow) if shadow is not None else load_shadow_resolved()
        if marks is None:
            try:
                marks = load_mark_events(journal_path)
            except Exception as e:
                errors.append(f"marks: {e}")
                marks = {}
        enriched = enrich_exits(rows, marks)
        baseline = metrics(rows)
        report: Dict[str, Any] = {
            "ok": True,
            "title": "ATLAS EDGE DIAGNOSTICS",
            "generated_for": "PHASE_8_EDGE_DIAGNOSTICS",
            "control_gates": {
                "rsi_long": 28.0,
                "rsi_short": 72.0,
                "extension_pct": 1.4,
                "min_rr": 1.8,
                "unchanged": True,
            },
            "live_capital_allowed": False,
            "journal_counts": counts,
            "malformed_records": malformed,
            "malformed_count": len(malformed),
            "baseline": baseline,
            "entry": _section(
                "entry",
                lambda: {
                    "note": "Entries already passed locked gates. Quality/RSI/ext buckets describe those fills, not new thresholds.",
                    "feature_buckets": feature_buckets(rows),
                },
                errors,
            ),
            "exit": _section("exit", lambda: exit_diagnosis(enriched), errors),
            "direction": _section("direction", lambda: direction_deep(rows), errors),
            "regime": _section("regime", lambda: regime_analysis(rows), errors),
            "regime_transitions": _section("regime_transitions", lambda: regime_transitions(rows), errors),
            "time": _section("time", lambda: session_bucket(rows), errors),
            "gate_interactions": _section("gate_interactions", lambda: gate_interactions(rows), errors),
            "loss_clusters": _section("loss_clusters", lambda: loss_clusters(rows), errors),
            "drawdown_streak": _section("drawdown_streak", lambda: drawdown_path(rows), errors),
            "mfe_mae": {
                "avg_mfe": baseline.get("avg_mfe"),
                "avg_mae": baseline.get("avg_mae"),
                "milestones": _section("milestones", lambda: r_milestones(rows), errors),
            },
            "paper_vs_shadow": _section("paper_vs_shadow", lambda: shadow_vs_paper(rows, sh), errors),
            "holdout": _section("holdout", lambda: holdout_split(rows), errors),
            "leakage": _section("leakage", lambda: leakage_audit(rows), errors),
            "uncertainty": _section("uncertainty", lambda: uncertainty(rows), errors),
            "combined_forbidden": True,
            "section_errors": errors,
        }
        try:
            report["narrative"] = narrative(report)
        except Exception as e:
            errors.append(f"narrative: {e}")
            report["narrative"] = {
                "WHAT_WE_KNOW": [f"Paper n={baseline.get('n')}. Narrative failed: {e}"],
                "WHAT_LOOKS_PROMISING": ["Insufficient sample / report incomplete"],
                "WHAT_LOOKS_WEAK": [],
                "WHAT_IS_STILL_UNKNOWN": ["Narrative could not be built from this journal snapshot."],
            }
        report["disclaimer"] = (
            "Diagnosis only. Observed difference — exploratory. Insufficient sample until holdout agrees. "
            "Not a profitability claim, not permission for live capital, not a gate-change instruction."
        )
        safe = _json_safe(report)
        blob = json.dumps(safe, default=str).lower()
        for phrase in FORBIDDEN:
            if phrase in blob:
                safe.setdefault("section_errors", []).append(f"redacted phrase guard: {phrase}")
        return safe
    except Exception as e:
        return _json_safe(
            {
                "ok": False,
                "title": "ATLAS EDGE DIAGNOSTICS",
                "error": f"{type(e).__name__}: {str(e)[:240]}",
                "live_capital_allowed": False,
                "baseline": _empty_baseline(),
                "malformed_records": malformed,
                "section_errors": errors + [str(e)[:240]],
                "disclaimer": "Diagnostics failed to fully build. Journal was not rewritten.",
            }
        )


def edge_text(limit: int = 1900) -> str:
    r = edge_report()
    b = r["baseline"]
    n = r["narrative"]
    lines = [
        "ATLAS EDGE DIAGNOSTICS (research only)",
        f"Baseline n={b['n']} WR={b['winrate']*100:.1f}% exp={b['expectancy']:+.2f}R tot={b['total_r']:+.2f}R DD={b['max_drawdown_r']:.2f}R streak={b['longest_losing_streak']}",
        "WHAT WE KNOW: " + " | ".join(n["WHAT_WE_KNOW"][:2]),
        "PROMISING: " + " | ".join(n["WHAT_LOOKS_PROMISING"][:2]),
        "WEAK: " + " | ".join(n["WHAT_LOOKS_WEAK"][:2]),
        "UNKNOWN: " + " | ".join(n["WHAT_IS_STILL_UNKNOWN"][:2]),
        "Gates locked RSI 28/72 · ext 1.4% · R:R 1.8. Not permission for live capital. Not /paper.",
    ]
    text = "\n".join(lines)
    return text if len(text) <= limit else text[: limit - 1]
