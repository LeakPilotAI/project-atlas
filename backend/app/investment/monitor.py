"""Investment data collection monitor. Not an opportunity score. Not performance."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.investment.enums import EvaluationStatus
from app.investment.provider_health import ProviderHealthBook
from app.investment.scan_store import load_observations
from app.investment.storage import OBSERVATIONS_PATH, PROVIDER_HEALTH_PATH

VALID_SET = {EvaluationStatus.VALID.value, EvaluationStatus.VALID_NO_ACTION.value}
EVAL_KEYS = [s.value for s in EvaluationStatus]


def _rec(row: dict) -> dict:
    r = row.get("research")
    return r if isinstance(r, dict) else {}


def _asset(row: dict) -> dict:
    snap = _rec(row).get("input_snapshot")
    if isinstance(snap, dict) and isinstance(snap.get("asset"), dict):
        return snap["asset"]
    return {}


def asset_type_of(row: dict) -> str:
    return str(_asset(row).get("asset_type") or row.get("asset_type") or "UNKNOWN")


def sector_of(row: dict) -> str:
    return str(_asset(row).get("sector") or row.get("sector") or "UNKNOWN")


def as_of_date_of(row: dict) -> str:
    raw = str(row.get("as_of") or row.get("timestamp") or "")
    return raw[:10] if raw else ""


def as_of_full(row: dict) -> str:
    return str(row.get("as_of") or row.get("timestamp") or "")


def is_potential(row: dict) -> bool:
    if row.get("qualified") is True:
        return True
    return str(row.get("classification") or "") in {
        "ACCUMULATION",
        "DEEP_VALUE",
        "GENERATIONAL_OPPORTUNITY",
        "WATCH",
    }


def group_quality(field_quality: dict, prefix: str) -> str:
    if prefix == "price":
        return str((field_quality or {}).get("price") or "UNKNOWN")
    if prefix == "history":
        return str((field_quality or {}).get("history") or "UNKNOWN")
    if prefix == "news":
        return str((field_quality or {}).get("news") or "MISSING")
    if prefix == "macro":
        return str((field_quality or {}).get("macro") or "MISSING")
    vals = [v for k, v in (field_quality or {}).items() if k.startswith(prefix + ".")]
    if not vals:
        return "MISSING"
    if any(v == "CONFLICTING" for v in vals):
        return "CONFLICTING"
    if any(v == "FRESH" for v in vals):
        return "FRESH"
    if any(v == "STALE" for v in vals):
        return "STALE"
    if any(v == "UNKNOWN" for v in vals) and not any(v == "MISSING" for v in vals):
        return "UNKNOWN"
    return "MISSING"


def collection_monitor(
    observations_path: Optional[Path] = None,
    *,
    provider: Optional[ProviderHealthBook] = None,
    provider_path: Optional[Path] = None,
) -> Dict[str, Any]:
    rows = load_observations(observations_path or OBSERVATIONS_PATH)
    evals = Counter(str(r.get("evaluation") or "UNKNOWN") for r in rows)
    types = Counter(asset_type_of(r) for r in rows)
    sectors = Counter(sector_of(r) for r in rows)
    days = Counter(as_of_date_of(r) or "UNKNOWN" for r in rows)
    stamps = [as_of_full(r) for r in rows if as_of_full(r)]
    stamps_sorted = sorted(stamps)
    assets = {str(r.get("symbol") or "") for r in rows if r.get("symbol")}
    valid_n = sum(evals.get(k, 0) for k in VALID_SET)
    potential = sum(1 for r in rows if is_potential(r))
    rejected = len(rows) - potential

    book = provider
    if book is None:
        p = provider_path or PROVIDER_HEALTH_PATH
        book = ProviderHealthBook.load(p) if p.exists() else ProviderHealthBook()
    ph = book.as_dict()
    req = int(ph.get("requests") or 0)
    ok = int(ph.get("successes") or 0)
    success_rate = (ok / req) if req else None
    failure_rate = ((req - ok) / req) if req else None

    return {
        "observations": len(rows),
        "unique_assets": len(assets),
        "valid_observations": valid_n,
        "valid": evals.get("VALID", 0),
        "valid_no_action": evals.get("VALID_NO_ACTION", 0),
        "insufficient_data": evals.get("INSUFFICIENT_DATA", 0),
        "provider_error": evals.get("PROVIDER_ERROR", 0),
        "rate_limited": evals.get("RATE_LIMITED", 0),
        "stale_data": evals.get("STALE_DATA", 0),
        "conflicting_data": evals.get("CONFLICTING_DATA", 0),
        "unknown": evals.get("UNKNOWN", 0),
        "evaluations": {k: evals.get(k, 0) for k in EVAL_KEYS},
        "by_asset_type": dict(types),
        "by_sector": dict(sectors),
        "by_day": dict(days),
        "session_dates": len([d for d in days if d != "UNKNOWN"]),
        "potential_opportunities": potential,
        "rejected": rejected,
        "provider_requests": req,
        "provider_successes": ok,
        "provider_success_rate": success_rate,
        "provider_failure_rate": failure_rate,
        "provider_status": ph.get("status"),
        "provider": ph,
        "oldest_observation": stamps_sorted[0] if stamps_sorted else None,
        "latest_successful_observation": stamps_sorted[-1] if stamps_sorted else None,
        "coverage_start": stamps_sorted[0][:10] if stamps_sorted else None,
        "coverage_end": stamps_sorted[-1][:10] if stamps_sorted else None,
        "note": "Collection statistics only. Not an opportunity score. Not performance.",
    }


def format_collection_monitor(mon: Optional[Dict[str, Any]] = None, **kwargs) -> str:
    m = mon or collection_monitor(**kwargs)
    sr = m.get("provider_success_rate")
    fr = m.get("provider_failure_rate")
    lines = [
        "**INVESTMENT DATA COLLECTION MONITOR**",
        "_Data quality. Not an investment score. Not performance._",
        "",
        f"Total observations: {m['observations']}",
        f"Unique assets: {m['unique_assets']}",
        f"Valid observations: {m['valid_observations']}",
        f"VALID: {m['valid']}",
        f"VALID_NO_ACTION: {m['valid_no_action']}",
        f"INSUFFICIENT_DATA: {m['insufficient_data']}",
        f"PROVIDER_ERROR: {m['provider_error']}",
        f"RATE_LIMITED: {m['rate_limited']}",
        f"STALE_DATA: {m['stale_data']}",
        f"CONFLICTING_DATA: {m['conflicting_data']}",
        f"UNKNOWN: {m['unknown']}",
        "",
        f"Potential / qualified (WATCH+): {m['potential_opportunities']}",
        f"Rejected / no-action: {m['rejected']}",
        "",
        "By asset type:",
    ]
    by_t = m.get("by_asset_type") or {}
    if not by_t:
        lines.append("(none)")
    for k, v in sorted(by_t.items()):
        lines.append(f"  {k}: {v}")
    lines += ["", "By sector:"]
    by_s = m.get("by_sector") or {}
    if not by_s:
        lines.append("(none)")
    for k, v in sorted(by_s.items()):
        lines.append(f"  {k}: {v}")
    lines += ["", "By day:"]
    by_d = m.get("by_day") or {}
    if not by_d:
        lines.append("(none)")
    for k, v in sorted(by_d.items()):
        lines.append(f"  {k}: {v}")
    lines += [
        "",
        f"Provider success rate: {sr:.0%}" if isinstance(sr, float) else "Provider success rate: n/a",
        f"Provider failure rate: {fr:.0%}" if isinstance(fr, float) else "Provider failure rate: n/a",
        f"Provider status: {m.get('provider_status')}",
        f"Oldest observation: {m.get('oldest_observation') or 'n/a'}",
        f"Latest observation: {m.get('latest_successful_observation') or 'n/a'}",
        f"Coverage: {m.get('coverage_start') or 'n/a'} – {m.get('coverage_end') or 'n/a'}",
        "",
        "Dataset size is not strategy success.",
    ]
    return "\n".join(lines)
