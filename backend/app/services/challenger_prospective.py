"""Forward-only persistence for Atlas V6 challengers.

Membership is frozen from the PAPER open event using only information present at
entry. Historical closes cannot enter the cohort. The append-only membership log
is research state only and cannot alter production strategy or execution.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from app.services.challenger_lab import LAB_VERSION, _extension, _quality, _regime
from app.services.paper_journal import JOURNAL_PATH, iter_jsonl
from app.services.paper_validation import metrics, uncertainty

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MARKER_PATH = DATA_DIR / "v6_challenger_prospective_marker.json"
MEMBERSHIP_PATH = DATA_DIR / "v6_challenger_membership.jsonl"
COHORT_NAME = "v6_forward_only"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _append(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass


def ensure_marker(path: Path = MARKER_PATH, *, now: Optional[datetime] = None) -> Dict[str, Any]:
    if path.exists():
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(row, dict) and row.get("started_at") and row.get("cohort") == COHORT_NAME:
                return row
        except Exception:
            pass
    started = (now or _now()).astimezone(timezone.utc).isoformat()
    row = {
        "cohort": COHORT_NAME,
        "version": LAB_VERSION,
        "started_at": started,
        "membership_basis": "PAPER open event; pre-entry fields only",
        "forward_only": True,
        "live_capital_allowed": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


def classify_open(row: Dict[str, Any]) -> list[str]:
    """Predeclared V6 membership from the immutable open snapshot only."""
    trend = _regime(row) in {"TREND_UP", "TREND_DOWN"}
    ext = _extension(row)
    quality = _quality(row)
    ext3 = ext is not None and ext >= 3.0
    q85 = quality is not None and quality >= 85.0
    out: list[str] = []
    if trend:
        out.append("trend_regime")
    if ext3:
        out.append("extension_3pct")
    if q85:
        out.append("quality_85")
    if trend and ext3 and q85:
        out.append("trend_extension_quality")
    return out


def _existing_memberships(path: Path) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in iter_jsonl(path):
        if row.get("event") == "membership" and row.get("trade_id"):
            out[str(row["trade_id"])] = row
    return out


def sync_memberships(
    *, journal_path: Path = JOURNAL_PATH,
    marker_path: Path = MARKER_PATH,
    membership_path: Path = MEMBERSHIP_PATH,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    marker = ensure_marker(marker_path, now=now)
    cutoff = _parse(marker.get("started_at"))
    existing = _existing_memberships(membership_path)
    added = 0
    skipped_pre_cutoff = 0
    for row in iter_jsonl(journal_path):
        if row.get("event") != "open" or str(row.get("trade_type") or "PAPER").upper() != "PAPER":
            continue
        tid = str(row.get("trade_id") or "")
        if not tid or tid in existing:
            continue
        entry_at = _parse(row.get("entry_timestamp") or row.get("signal_timestamp") or row.get("timestamp"))
        if cutoff is None or entry_at is None or entry_at < cutoff:
            skipped_pre_cutoff += 1
            continue
        membership = {
            "event": "membership",
            "cohort": COHORT_NAME,
            "version": LAB_VERSION,
            "trade_id": tid,
            "entry_timestamp": entry_at.isoformat(),
            "recorded_at": (now or _now()).astimezone(timezone.utc).isoformat(),
            "symbol": row.get("symbol"),
            "side": row.get("side"),
            "source": row.get("source"),
            "strategy": row.get("strategy"),
            "challengers": classify_open(row),
            "pre_entry_snapshot": {
                "regime": _regime(row),
                "extension_pct": _extension(row),
                "quality": _quality(row),
                "tier": row.get("tier"),
            },
        }
        _append(membership_path, membership)
        existing[tid] = membership
        added += 1
    return {"marker": marker, "memberships": existing, "added": added, "skipped_pre_cutoff": skipped_pre_cutoff}


def prospective_report(
    *, journal_path: Path = JOURNAL_PATH,
    marker_path: Path = MARKER_PATH,
    membership_path: Path = MEMBERSHIP_PATH,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    state = sync_memberships(
        journal_path=journal_path, marker_path=marker_path, membership_path=membership_path, now=now
    )
    memberships = state["memberships"]
    closes: Dict[str, Dict[str, Any]] = {}
    for row in iter_jsonl(journal_path):
        if row.get("event") == "close" and str(row.get("trade_id") or "") in memberships:
            closes[str(row["trade_id"])] = row

    names = ("trend_regime", "extension_3pct", "quality_85", "trend_extension_quality")
    challengers: Dict[str, Any] = {}
    for name in names:
        member_ids = {tid for tid, m in memberships.items() if name in (m.get("challengers") or [])}
        closed = [closes[tid] for tid in member_ids if tid in closes]
        m = metrics(closed)
        challengers[name] = {
            "opened": len(member_ids),
            "closed": len(closed),
            "open": len(member_ids) - len(closed),
            "metrics": m,
            "uncertainty": uncertainty(closed),
            "prospective_validated": False,
            "promoted": False,
        }

    all_ids = set(memberships)
    all_closed = [closes[tid] for tid in all_ids if tid in closes]
    return {
        "ok": True,
        "title": "ATLAS V6 PROSPECTIVE CHALLENGER COHORT",
        "mode": "FORWARD_ONLY_RESEARCH",
        "marker": state["marker"],
        "membership_count": len(memberships),
        "closed_count": len(all_closed),
        "open_count": len(memberships) - len(all_closed),
        "added_this_sync": state["added"],
        "baseline": {**metrics(all_closed), "uncertainty": uncertainty(all_closed)},
        "challengers": challengers,
        "retrospective_rows_count_as_prospective": False,
        "production_strategy_modified": False,
        "automatic_promotion": False,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
        "note": "Membership is frozen at PAPER open from pre-entry fields and survives restart in an append-only log.",
    }
