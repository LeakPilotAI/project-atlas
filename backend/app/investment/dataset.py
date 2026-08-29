"""Dataset health. Not performance. Not alpha. Reads observations only."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from app.investment.enums import EvaluationStatus, InvestmentAlertState
from app.investment.scan_store import load_observations
from app.investment.storage import OBSERVATIONS_PATH, OUTCOMES_PATH

VALID_SET = {EvaluationStatus.VALID.value, EvaluationStatus.VALID_NO_ACTION.value}
TARGET_VALID = 500


def _sector(row: dict) -> str:
    rec = row.get("research") if isinstance(row.get("research"), dict) else {}
    snap = rec.get("input_snapshot") if isinstance(rec.get("input_snapshot"), dict) else {}
    asset = snap.get("asset") if isinstance(snap.get("asset"), dict) else {}
    return str(asset.get("sector") or row.get("sector") or "UNKNOWN")


def _month(row: dict) -> str:
    raw = str(row.get("as_of") or row.get("timestamp") or "")[:7]
    return raw or "UNKNOWN"


def dataset_stats(
    observations_path: Optional[Path] = None,
    outcomes_path: Optional[Path] = None,
) -> Dict[str, object]:
    rows = load_observations(observations_path or OBSERVATIONS_PATH)
    classes = Counter(str(r.get("classification") or "NO_ACTION") for r in rows)
    evals = Counter(str(r.get("evaluation") or "UNKNOWN") for r in rows)
    assets = {str(r.get("symbol") or "") for r in rows if r.get("symbol")}
    dates = sorted(str(r.get("as_of") or r.get("timestamp") or "")[:10] for r in rows if r.get("as_of") or r.get("timestamp"))
    valid_n = sum(evals.get(k, 0) for k in VALID_SET)
    # legacy rows with no evaluation field: treat NO_ACTION+INSUFFICIENT evidence as insufficient
    if not any(r.get("evaluation") for r in rows):
        valid_n = 0
    by_asset_cls: Dict[str, Counter] = {}
    by_sector_cls: Dict[str, Counter] = {}
    by_month_cls: Dict[str, Counter] = {}
    evidence_vals: List[str] = []
    for r in rows:
        sym = str(r.get("symbol") or "?")
        cls = str(r.get("classification") or "NO_ACTION")
        by_asset_cls.setdefault(sym, Counter())[cls] += 1
        by_sector_cls.setdefault(_sector(r), Counter())[cls] += 1
        by_month_cls.setdefault(_month(r), Counter())[cls] += 1
        rec = r.get("research") if isinstance(r.get("research"), dict) else r
        ev = rec.get("evidence_quality") if isinstance(rec, dict) else None
        if ev:
            evidence_vals.append(str(ev))
    gen_n = classes.get("GENERATIONAL_OPPORTUNITY", 0)
    gen_rate = (gen_n / len(rows)) if rows else 0.0
    last_gen = next((r.get("as_of") for r in reversed(rows) if r.get("classification") == "GENERATIONAL_OPPORTUNITY"), None)
    last_dv = next((r.get("as_of") for r in reversed(rows) if r.get("classification") == "DEEP_VALUE"), None)
    outcomes_n = 0
    op = outcomes_path or OUTCOMES_PATH
    if op.exists():
        outcomes_n = sum(1 for line in op.read_text(encoding="utf-8").splitlines() if line.strip())
    return {
        "observations": len(rows),
        "unique_assets": len(assets),
        "date_start": dates[0] if dates else None,
        "date_end": dates[-1] if dates else None,
        "valid_evaluations": valid_n,
        "insufficient_data": evals.get("INSUFFICIENT_DATA", 0),
        "provider_error": evals.get("PROVIDER_ERROR", 0),
        "rate_limited": evals.get("RATE_LIMITED", 0),
        "stale_data": evals.get("STALE_DATA", 0),
        "conflicting_data": evals.get("CONFLICTING_DATA", 0),
        "valid_no_action": evals.get("VALID_NO_ACTION", 0),
        "classifications": dict(classes),
        "evaluations": dict(evals),
        "by_asset": {k: dict(v) for k, v in by_asset_cls.items()},
        "by_sector": {k: dict(v) for k, v in by_sector_cls.items()},
        "by_month": {k: dict(v) for k, v in by_month_cls.items()},
        "generational_count": gen_n,
        "generational_rate": gen_rate,
        "last_generational": last_gen,
        "last_deep_value": last_dv,
        "evidence_counts": dict(Counter(evidence_vals)),
        "outcomes_rows": outcomes_n,
        "target_valid": TARGET_VALID,
        "target_progress": min(1.0, valid_n / TARGET_VALID) if TARGET_VALID else 0.0,
        "warning": (
            "GENERATIONAL rate is high — do not loosen thresholds to create more signals"
            if gen_rate >= 0.20 and rows
            else (
                "GENERATIONAL = 0 is expected while collecting; do not retune to force signals"
                if rows and gen_n == 0
                else ""
            )
        ),
    }


def format_dataset_report(stats: Optional[Dict[str, object]] = None, **kwargs) -> str:
    s = stats or dataset_stats(**kwargs)
    cls = s.get("classifications") or {}
    evc = s.get("evidence_counts") or {}
    rng = "n/a"
    if s.get("date_start"):
        rng = f"{s['date_start']} – {s['date_end']}"
    avg_ev = "n/a"
    if evc:
        avg_ev = ", ".join(f"{k} {v}" for k, v in sorted(evc.items()))
    lines = [
        "**ATLAS INVESTMENT DATASET**",
        "_Dataset health. Not performance. Not alpha._",
        "",
        f"Observations: {s['observations']}",
        f"Unique assets: {s['unique_assets']}",
        f"Date range: {rng}",
        f"Valid evaluations: {s['valid_evaluations']}",
        f"Valid NO_ACTION: {s['valid_no_action']}",
        f"Insufficient data: {s['insufficient_data']}",
        f"Provider error: {s['provider_error']}",
        f"Rate limited: {s['rate_limited']}",
        f"Stale data: {s['stale_data']}",
        f"Conflicting: {s['conflicting_data']}",
        "",
        "WATCH: " + str(cls.get("WATCH", 0)),
        "ACCUMULATION: " + str(cls.get("ACCUMULATION", 0)),
        "DEEP VALUE: " + str(cls.get("DEEP_VALUE", 0)),
        "GENERATIONAL: " + str(cls.get("GENERATIONAL_OPPORTUNITY", 0)),
        "THESIS BROKEN: " + str(cls.get("THESIS_BROKEN", 0)),
        "NO ACTION: " + str(cls.get("NO_ACTION", 0)),
        "",
        f"GENERATIONAL rate: {float(s.get('generational_rate') or 0):.1%}",
        f"Evidence mix: {avg_ev}",
        f"Outcome rows (separate file): {s['outcomes_rows']}",
        f"Collection target (valid): {s['valid_evaluations']} / {s['target_valid']}",
        "",
        "Do not claim the strategy works because observations exist.",
    ]
    if s.get("warning"):
        lines += ["", str(s["warning"])]
    # sector / month rates (compact)
    lines += ["", "By sector (classification counts)"]
    by_sec = s.get("by_sector") or {}
    if not by_sec:
        lines.append("(none)")
    for sec, counts in sorted(by_sec.items()):
        parts = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
        lines.append(f"{sec}: {parts}")
    return "\n".join(lines)
