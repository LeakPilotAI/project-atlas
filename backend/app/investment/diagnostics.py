"""Investment data-health text. Research-only. Not /paper. Not performance."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.investment.dataset import dataset_stats, format_dataset_report
from app.investment.enums import DataQuality, EvaluationStatus
from app.investment.provider_health import ProviderHealthBook, get_provider_health
from app.investment.scan_models import ScanObservation, ScanReport
from app.investment.storage import LAST_CYCLE_PATH, ensure_dirs
from app.investment.universe import load_universe

GROUP_KEYS = ("price", "fundamentals", "valuation", "history")


def _group_status(obs_list: List[ScanObservation], group: str) -> str:
    if not obs_list:
        return "MISSING"
    flags = []
    for o in obs_list:
        if group == "history":
            q = (o.field_quality or {}).get("history") or (o.data_source_status or {}).get("history") or "UNKNOWN"
            flags.append(str(q))
            continue
        if group == "price":
            flags.append((o.field_quality or {}).get("price") or DataQuality.MISSING.value)
            continue
        prefix = f"{group}."
        vals = [v for k, v in (o.field_quality or {}).items() if k.startswith(prefix)]
        if not vals:
            flags.append((o.data_source_status or {}).get(group) or DataQuality.MISSING.value)
        else:
            if any(v == "CONFLICTING" for v in vals):
                flags.append("CONFLICTING")
            elif any(v in ("FRESH",) for v in vals):
                flags.append("FRESH")
            elif any(v == "STALE" for v in vals):
                flags.append("STALE")
            else:
                flags.append("MISSING")
    # roll up
    if any(f in ("ERROR", "PROVIDER_ERROR") for f in flags):
        return "ERROR"
    if any("RATE" in str(f) for f in flags):
        return "ERROR"
    n = len(flags)
    missing = sum(1 for f in flags if f in ("MISSING", "UNKNOWN", "CACHED") and f != "FRESH")
    # prefer explicit qualities
    if any(f == "CONFLICTING" for f in flags):
        return "CONFLICTING"
    fresh = sum(1 for f in flags if f == "FRESH")
    stale = sum(1 for f in flags if f == "STALE")
    miss = sum(1 for f in flags if f in ("MISSING", "UNKNOWN"))
    if miss == n:
        return "MISSING"
    if stale and not fresh:
        return "STALE"
    if fresh:
        return "FRESH"
    return "MISSING"


def _eval_counts(obs_list: List[ScanObservation]) -> Dict[str, int]:
    out: Dict[str, int] = {s.value: 0 for s in EvaluationStatus}
    for o in obs_list:
        key = o.evaluation or EvaluationStatus.UNKNOWN.value
        out[key] = out.get(key, 0) + 1
    return out


def coverage_pct(obs_list: List[ScanObservation], group: str) -> float:
    if not obs_list:
        return 0.0
    ok = 0
    for o in obs_list:
        if group == "price":
            q = (o.field_quality or {}).get("price")
            if q in ("FRESH", "STALE"):
                ok += 1
        elif group == "history":
            st = (o.data_source_status or {}).get("history")
            if st in ("FETCHED", "CACHED"):
                ok += 1
        else:
            vals = [v for k, v in (o.field_quality or {}).items() if k.startswith(group + ".")]
            if any(v in ("FRESH", "STALE") for v in vals):
                ok += 1
    return 100.0 * ok / len(obs_list)


def format_data_health(report: ScanReport) -> str:
    obs = report.observations
    ev = _eval_counts(obs)
    valid = ev.get("VALID", 0) + ev.get("VALID_NO_ACTION", 0)
    insuff = ev.get("INSUFFICIENT_DATA", 0)
    rate = sum(1 for o in obs if o.evaluation == EvaluationStatus.RATE_LIMITED.value)
    prov = ev.get("PROVIDER_ERROR", 0)
    lines = [
        "**INVESTMENT DATA HEALTH**",
        f"Universe: {report.universe}",
        f"Symbols attempted: {report.evaluated + report.failed}",
        f"Price: {_group_status(obs, 'price')}",
        f"Fundamentals: {_group_status(obs, 'fundamentals')}",
        f"Valuation: {_group_status(obs, 'valuation')}",
        f"Historical data: {_group_status(obs, 'history')}",
        f"Complete evaluations: {valid}",
        f"Insufficient-data evaluations: {insuff}",
        f"Provider errors: {prov}",
        f"Rate limits: {rate}",
        f"Observations written: {report.evaluated}",
        f"Alerts generated: {report.alerts_emitted}",
        "",
        "NO_ACTION from genuine evidence is VALID_NO_ACTION.",
        "NO_ACTION from missing Yahoo fields is INSUFFICIENT_DATA / PROVIDER_ERROR.",
        "They are not the same.",
    ]
    for o in obs[:20]:
        rec = o.research
        cls = o.classification
        evs = o.evaluation or "UNKNOWN"
        reason = o.evaluation_reason or o.blocking_reason or ""
        comp = (o.completeness or {}).get("label") or ""
        lines += [
            "",
            o.symbol,
            f"Classification: {cls}",
            f"Evaluation: {evs}",
            f"Reason: {reason}",
        ]
        if rec is not None:
            lines.append(
                f"Evidence: {rec.evidence_quality.value}  Required fields: {comp or 'n/a'}"
            )
    return "\n".join(lines)


def format_scanner_health(
    *,
    running: bool,
    last: Optional[dict] = None,
    provider: Optional[ProviderHealthBook] = None,
) -> str:
    last = last or load_last_cycle() or {}
    provider = provider or get_provider_health()
    ph = provider.as_dict() if hasattr(provider, "as_dict") else {}
    obs = last.get("observations") or last.get("evaluated") or 0
    lines = [
        "**ATLAS INVESTMENT HEALTH**",
        f"Scanner: {'RUNNING' if running else 'STOPPED'}",
        f"Universe: {last.get('universe', 'n/a')}",
        f"Last cycle: {last.get('finished_at') or last.get('started_at') or 'n/a'}",
        f"Last successful cycle: {last.get('last_successful') or last.get('finished_at') or 'n/a'}",
        f"Provider: {ph.get('status', 'UNKNOWN')}",
        f"Price coverage: {last.get('price_coverage', 'n/a')}"
        + ("%" if isinstance(last.get("price_coverage"), (int, float)) else ""),
        f"Fundamental coverage: {last.get('fund_coverage', 'n/a')}"
        + ("%" if isinstance(last.get("fund_coverage"), (int, float)) else ""),
        f"Valuation coverage: {last.get('val_coverage', 'n/a')}"
        + ("%" if isinstance(last.get("val_coverage"), (int, float)) else ""),
        f"Valid evaluations: {last.get('valid_evaluations', 'n/a')}",
        f"Insufficient: {last.get('insufficient_data', 'n/a')}",
        f"Observations: {obs}",
        f"Last GENERATIONAL: {last.get('last_generational') or 'none'}",
        f"Last DEEP VALUE: {last.get('last_deep_value') or 'none'}",
        "No real orders: YES",
        "Trading engine: ISOLATED",
        "",
        f"Yahoo requests: {ph.get('requests', 0)}  successes: {ph.get('successes', 0)}",
        f"401: {ph.get('http_401', 0)}  429: {ph.get('http_429', 0)}  timeouts: {ph.get('timeouts', 0)}",
        f"empty: {ph.get('empty', 0)}  missing ticker: {ph.get('missing_ticker', 0)}  other: {ph.get('other', 0)}",
    ]
    return "\n".join(lines)


def cycle_summary(report: ScanReport) -> dict:
    ev = _eval_counts(report.observations)
    ds = dataset_stats()
    return {
        "scan_id": report.scan_id,
        "started_at": report.started_at.isoformat() if report.started_at else None,
        "finished_at": report.finished_at.isoformat() if report.finished_at else None,
        "last_successful": report.finished_at.isoformat() if report.finished_at and not report.error else None,
        "session": report.session,
        "universe": report.universe,
        "evaluated": report.evaluated,
        "failed": report.failed,
        "alerts_emitted": report.alerts_emitted,
        "observations": report.evaluated,
        "valid_evaluations": ev.get("VALID", 0) + ev.get("VALID_NO_ACTION", 0),
        "insufficient_data": ev.get("INSUFFICIENT_DATA", 0),
        "provider_error": ev.get("PROVIDER_ERROR", 0),
        "rate_limited": ev.get("RATE_LIMITED", 0),
        "price_coverage": round(coverage_pct(report.observations, "price"), 1),
        "fund_coverage": round(coverage_pct(report.observations, "fundamentals"), 1),
        "val_coverage": round(coverage_pct(report.observations, "valuation"), 1),
        "last_generational": ds.get("last_generational"),
        "last_deep_value": ds.get("last_deep_value"),
        "evaluation_counts": ev,
        "classification_counts": dict(report.counts),
    }


def save_last_cycle(summary: dict, path: Optional[Path] = None) -> None:
    ensure_dirs()
    p = path or LAST_CYCLE_PATH
    p.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")


def load_last_cycle(path: Optional[Path] = None) -> Optional[dict]:
    p = path or LAST_CYCLE_PATH
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def format_full_health(*, running: bool = False) -> str:
    parts = [
        format_scanner_health(running=running),
        "",
        format_dataset_report(),
    ]
    last = load_last_cycle()
    if last:
        # rebuild a tiny data-health block from last cycle counts
        parts += [
            "",
            "**LAST CYCLE DATA HEALTH**",
            f"Universe: {last.get('universe')}",
            f"Symbols attempted: {(last.get('evaluated') or 0) + (last.get('failed') or 0)}",
            f"Valid evaluations: {last.get('valid_evaluations')}",
            f"Insufficient-data evaluations: {last.get('insufficient_data')}",
            f"Provider errors: {last.get('provider_error')}",
            f"Rate limits: {last.get('rate_limited')}",
            f"Observations written: {last.get('observations')}",
            f"Alerts generated: {last.get('alerts_emitted')}",
        ]
    return "\n".join(parts)
