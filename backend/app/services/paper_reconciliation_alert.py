"""Read-only alerting for PAPER reconciliation failures."""
from __future__ import annotations

import asyncio

from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from app.alerts.discord import send_discord_alert
from app.services.perp_paper_observability import reconciliation_summary

Sender = Callable[..., Awaitable[bool]]

DEFAULT_RECONCILIATION_ALERT_COOLDOWN_SECONDS = 900
_last_alert_signature: str | None = None
_last_alert_at: datetime | None = None


def _signature(rec: dict[str, Any]) -> str:
    duplicate_ids = ",".join(sorted(str(x) for x in rec.get("duplicate_fill_instances") or []))
    return f"dup={rec.get('duplicate_fill_count', 0)}|ids={duplicate_ids}|open={rec.get('journal_currently_open', 0)}"


def reset_reconciliation_alert_state() -> None:
    global _last_alert_signature, _last_alert_at
    _last_alert_signature = None
    _last_alert_at = None


async def alert_reconciliation_if_needed(
    *,
    sender: Sender = send_discord_alert,
    cooldown_seconds: float = DEFAULT_RECONCILIATION_ALERT_COOLDOWN_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    global _last_alert_signature, _last_alert_at
    rec = await asyncio.to_thread(reconciliation_summary)
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    signature = _signature(rec)
    if rec.get("reconciliation_ok"):
        reset_reconciliation_alert_state()
        return {
            "attempted": 0, "delivered": 0, "reconciliation_ok": True,
            "suppressed": False, "signature": signature, "checked_at": checked_at.isoformat(),
        }
    cooldown = max(0.0, float(cooldown_seconds))
    if _last_alert_signature == signature and _last_alert_at is not None:
        elapsed = (checked_at - _last_alert_at).total_seconds()
        if elapsed < cooldown:
            return {
                "attempted": 0, "delivered": 0, "reconciliation_ok": False,
                "suppressed": True, "suppression_reason": "cooldown",
                "signature": signature, "checked_at": checked_at.isoformat(),
                "next_alert_at": (_last_alert_at + timedelta(seconds=cooldown)).isoformat(),
            }
    description = (
        f"Duplicate fill instances: {rec.get('duplicate_fill_count', 0)}\n"
        f"Current auto-paper open trades: {rec.get('journal_currently_open', 0)}\n"
        "PAPER evidence requires operator review. No live order action was taken."
    )
    ok = bool(await sender(
        symbol="PAPER",
        title="Atlas PAPER reconciliation warning",
        description=description,
        severity="HIGH",
        opportunity=0,
        confidence=100,
        risk=100,
    ))
    if ok:
        _last_alert_signature = signature
        _last_alert_at = checked_at
    return {
        "attempted": 1, "delivered": int(ok), "reconciliation_ok": False,
        "suppressed": False, "signature": signature, "checked_at": checked_at.isoformat(),
    }
