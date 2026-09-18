"""Read-only alerting for PAPER reconciliation failures."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from app.alerts.discord import send_discord_alert
from app.services.perp_paper_observability import reconciliation_summary

Sender = Callable[..., Awaitable[bool]]


async def alert_reconciliation_if_needed(*, sender: Sender = send_discord_alert) -> dict[str, Any]:
    rec = reconciliation_summary()
    if rec.get("reconciliation_ok"):
        return {"attempted": 0, "delivered": 0, "reconciliation_ok": True}
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
    return {"attempted": 1, "delivered": int(ok), "reconciliation_ok": False}
