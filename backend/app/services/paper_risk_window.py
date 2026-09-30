"""Bounded PAPER loss window used by auto-mirror risk controls.

The durable PAPER journal remains the research source of truth.  This helper only
computes the realized UTC-day loss window used to decide whether *new* simulated
positions may be opened.  Historical/session PnL is never deleted or rewritten.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.paper_journal import JOURNAL_PATH, iter_jsonl


def utc_day_risk_snapshot(path: Path = JOURNAL_PATH, *, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    day = current.date()
    net_r = 0.0
    closed = 0

    if path.exists():
        for row in iter_jsonl(path):
            if row.get("event") != "close":
                continue
            if str(row.get("trade_type") or "PAPER").upper() == "TEST":
                continue
            result = str(row.get("result") or "").upper()
            if bool(row.get("session_roll")) or result in {"SESSION_ROLL", "INTERRUPTED"}:
                continue
            raw = row.get("exit_timestamp") or row.get("timestamp")
            if not raw:
                continue
            try:
                ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                ts = ts.astimezone(timezone.utc)
            except Exception:
                continue
            if ts.date() != day:
                continue
            try:
                value = float(row.get("net_pnl_r") if row.get("net_pnl_r") is not None else row.get("R_multiple") or 0.0)
            except (TypeError, ValueError):
                continue
            net_r += value
            closed += 1

    return {
        "net_r": round(net_r, 4),
        "closed": closed,
        "window": "UTC_DAY",
        "window_date": day.isoformat(),
        "source": "PAPER_JOURNAL_REALIZED_CLOSES",
    }
