"""Read-only observability for manual-trigger auto-paper orders.

This module never places, fills, cancels, or modifies an order. It reconstructs the
resting-L1 pending book from its durable event log, exposes age/ownership health,
and creates a durable local cohort marker so post-fix evidence can be analyzed
separately from older paper history.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.services.paper_journal import JOURNAL_PATH, iter_jsonl
from app.services.paper_execution_model import execution_assumptions
from app.services.perp_setup_paper_mirror import PENDING_EVENT_PATH, SOURCE

COHORT_MARKER_PATH = Path(__file__).resolve().parents[2] / "data" / "perp_manual_auto_observability_v1.json"
COHORT_NAME = "manual_auto_observability_v1"


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _instance_id(setup: dict[str, Any]) -> str:
    key = str(setup.get("setup_key") or "")
    first = str(setup.get("first_seen_at") or "")
    epoch = str(setup.get("paper_mirror_epoch_at") or first)
    return f"{key}|{first}|{epoch}"


def _load_pending() -> tuple[dict[str, dict[str, Any]], Counter[str]]:
    pending: dict[str, dict[str, Any]] = {}
    cancel_reasons: Counter[str] = Counter()
    for row in iter_jsonl(PENDING_EVENT_PATH):
        if row.get("event") == "_malformed":
            continue
        instance = str(row.get("setup_instance_id") or "")
        if not instance:
            continue
        event = str(row.get("event") or "").lower()
        if event == "armed":
            pending[instance] = dict(row)
        elif event == "filled":
            pending.pop(instance, None)
        elif event == "cancelled":
            pending.pop(instance, None)
            cancel_reasons[str(row.get("reason") or "UNKNOWN")] += 1
    return pending, cancel_reasons


def pending_health(setups: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    pending, cancel_reasons = _load_pending()
    now = _now_dt()
    current = {_instance_id(s): s for s in setups if _instance_id(s)}
    buckets = {"lt_15m": 0, "m15_60": 0, "h1_6": 0, "h6_24": 0, "gt_24h": 0, "unknown": 0}
    details: list[dict[str, Any]] = []
    oldest_age: float | None = None
    currently_backed = 0

    for instance, row in pending.items():
        armed_at = _parse_dt(row.get("timestamp"))
        age = max(0.0, (now - armed_at).total_seconds()) if armed_at else None
        if age is None:
            buckets["unknown"] += 1
        elif age < 900:
            buckets["lt_15m"] += 1
        elif age < 3600:
            buckets["m15_60"] += 1
        elif age < 21600:
            buckets["h1_6"] += 1
        elif age < 86400:
            buckets["h6_24"] += 1
        else:
            buckets["gt_24h"] += 1
        if age is not None and (oldest_age is None or age > oldest_age):
            oldest_age = age
        setup = current.get(instance)
        if setup is not None:
            currently_backed += 1
        details.append({
            "setup_instance_id": instance,
            "symbol": str(row.get("symbol") or "").upper(),
            "side": str(row.get("side") or "").upper(),
            "tier": row.get("tier"),
            "limit_price": row.get("limit_price"),
            "armed_at": row.get("timestamp"),
            "age_sec": None if age is None else round(age, 1),
            "age_hours": None if age is None else round(age / 3600.0, 2),
            "present_in_current_snapshot": setup is not None,
            "current_state": None if setup is None else setup.get("state"),
            "current_discovery_stale": None if setup is None else bool(setup.get("discovery_stale")),
        })

    details.sort(key=lambda x: (x.get("age_sec") is None, -(x.get("age_sec") or 0)))
    detached = len(pending) - currently_backed
    return {
        "pending_count": len(pending),
        "currently_backed": currently_backed,
        "not_in_current_snapshot": detached,
        "oldest_pending_age_sec": None if oldest_age is None else round(oldest_age, 1),
        "oldest_pending_age_hours": None if oldest_age is None else round(oldest_age / 3600.0, 2),
        "age_buckets": buckets,
        "review_recommended": bool(buckets["gt_24h"] or buckets["unknown"]),
        "cancel_reason_counts": dict(cancel_reasons),
        "oldest_pending": details[:10],
        "note": "Observability only. Pending resting-L1 orders are not cancelled by this health report.",
    }


def _ensure_cohort_marker(path: Path = COHORT_MARKER_PATH) -> dict[str, Any]:
    if path.exists():
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(row, dict) and row.get("started_at"):
                return row
        except Exception:
            pass
    row = {
        "cohort": COHORT_NAME,
        "started_at": _now_dt().isoformat(),
        "source": SOURCE,
        "note": "First runtime observation after paper ownership/observability cleanup. Entry-time scoped; older trades remain archived.",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


def cohort_summary(path: Path = COHORT_MARKER_PATH) -> dict[str, Any]:
    marker = _ensure_cohort_marker(path)
    cutoff = _parse_dt(marker.get("started_at"))
    cohort_ids: set[str] = set()
    open_ids: set[str] = set()
    closed_ids: set[str] = set()
    if cutoff is not None:
        for row in iter_jsonl(JOURNAL_PATH):
            tid = str(row.get("trade_id") or "")
            if not tid:
                continue
            event = str(row.get("event") or "").lower()
            if event == "open" and str(row.get("source") or "") == SOURCE:
                entry_at = _parse_dt(row.get("entry_timestamp") or row.get("signal_timestamp") or row.get("timestamp"))
                if entry_at is not None and entry_at >= cutoff:
                    cohort_ids.add(tid)
                    open_ids.add(tid)
            elif event == "close" and tid in cohort_ids:
                closed_ids.add(tid)
                open_ids.discard(tid)
    return {
        **marker,
        "opened": len(cohort_ids),
        "closed": len(closed_ids),
        "open": len(open_ids),
        "entry_time_scoped": True,
        "live_capital_allowed": False,
    }


def build_paper_observability(setups: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    return {
        "pending_health": pending_health(setups),
        "clean_cohort": cohort_summary(),
        "reconciliation": reconciliation_summary(),
        "execution_model": execution_assumptions(),
        "execution": "PAPER_ONLY",
        "real_order_actions": False,
    }


def reconciliation_summary() -> dict[str, Any]:
    opens: dict[str, dict[str, Any]] = {}
    closes: set[str] = set()
    fills: Counter[str] = Counter()
    for row in iter_jsonl(JOURNAL_PATH):
        if row.get("event") == "_malformed":
            continue
        tid = str(row.get("trade_id") or "")
        if not tid:
            continue
        ev = str(row.get("event") or "").lower()
        if ev == "open" and str(row.get("source") or "") == SOURCE:
            opens[tid] = row
        elif ev == "close":
            closes.add(tid)
    for row in iter_jsonl(PENDING_EVENT_PATH):
        if row.get("event") == "_malformed":
            continue
        if str(row.get("event") or "").lower() == "filled":
            fills[str(row.get("setup_instance_id") or "")] += 1
    duplicate_fill_instances = sorted(k for k,v in fills.items() if k and v > 1)
    orphan_open_ids = sorted(tid for tid in opens if tid not in closes)
    return {
        "journal_open_events": len(opens),
        "journal_closed_events": sum(1 for tid in opens if tid in closes),
        "journal_currently_open": len(orphan_open_ids),
        "duplicate_fill_instances": duplicate_fill_instances,
        "duplicate_fill_count": len(duplicate_fill_instances),
        "reconciliation_ok": len(duplicate_fill_instances) == 0,
        "execution": "PAPER_ONLY",
        "live_capital_allowed": False,
    }
