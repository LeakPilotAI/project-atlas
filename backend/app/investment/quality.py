"""Per-asset observation quality. Recurring provider/data problems. Not a score."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.investment.monitor import as_of_full, group_quality
from app.investment.scan_store import load_observations
from app.investment.storage import OBSERVATIONS_PATH

GROUPS = ("price", "fundamentals", "valuation", "history", "news", "macro")


def _mode(values: List[str]) -> str:
    if not values:
        return "UNKNOWN"
    return Counter(values).most_common(1)[0][0]


def asset_quality_breakdown(
    observations_path: Optional[Path] = None,
) -> Dict[str, Any]:
    rows = load_observations(observations_path or OBSERVATIONS_PATH)
    by_sym: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        sym = str(r.get("symbol") or "").upper()
        if sym:
            by_sym[sym].append(r)
    assets: List[Dict[str, Any]] = []
    recurring: Counter = Counter()
    for sym, items in sorted(by_sym.items()):
        latest = max(items, key=lambda x: as_of_full(x))
        fq = latest.get("field_quality") if isinstance(latest.get("field_quality"), dict) else {}
        groups = {g: group_quality(fq, g) for g in GROUPS}
        # news/macro are not collected in Phase 5 — always report MISSING unless stored
        if "news" not in fq:
            groups["news"] = "MISSING"
        if "macro" not in fq:
            groups["macro"] = "MISSING"
        for g, q in groups.items():
            if q in ("MISSING", "STALE", "CONFLICTING", "UNKNOWN"):
                recurring[f"{g}:{q}"] += 1
        assets.append(
            {
                "symbol": sym,
                "observations": len(items),
                "latest_as_of": as_of_full(latest),
                "classification": latest.get("classification"),
                "evaluation": latest.get("evaluation"),
                "groups": groups,
                "completeness": (latest.get("completeness") or {}).get("label"),
            }
        )
    return {
        "assets": assets,
        "recurring_problems": dict(recurring),
        "note": "Field quality is a diagnostic. News/macro are not collected yet (MISSING is expected).",
    }


def format_quality_breakdown(report: Optional[Dict[str, Any]] = None, **kwargs) -> str:
    r = report or asset_quality_breakdown(**kwargs)
    lines = [
        "**OBSERVATION QUALITY BREAKDOWN**",
        "_Whether a later signal would actually have evidence behind it._",
        "",
    ]
    assets = r.get("assets") or []
    if not assets:
        lines.append("(no observations yet)")
    for a in assets:
        g = a["groups"]
        lines += [
            a["symbol"],
            f"Price: {g.get('price')}",
            f"Fundamentals: {g.get('fundamentals')}",
            f"Valuation: {g.get('valuation')}",
            f"History: {g.get('history')}",
            f"News: {g.get('news')}",
            f"Macro: {g.get('macro')}",
            f"Latest evaluation: {a.get('evaluation') or 'n/a'}  completeness: {a.get('completeness') or 'n/a'}",
            "",
        ]
    rec = r.get("recurring_problems") or {}
    lines.append("Recurring problems:")
    if not rec:
        lines.append("(none)")
    else:
        for k, v in sorted(rec.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"  {k}: {v} assets")
    lines += ["", str(r.get("note") or "")]
    return "\n".join(lines)
