"""Retry-safe delivery for durable Quality Dips V3 research events."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from app.alerts.discord import send_discord_alert
from app.investment.quality_dips_v3_state import QualityDipsV3StateStore, quality_dips_v3_state_store

Sender = Callable[..., Awaitable[bool]]


async def deliver_v3_events(
    events: list[dict[str, Any]],
    *,
    store: QualityDipsV3StateStore = quality_dips_v3_state_store,
    sender: Sender = send_discord_alert,
) -> dict[str, int]:
    attempted = delivered = failed = skipped = 0
    for event in events:
        key = str(event.get("key") or "")
        if not key:
            skipped += 1
            continue
        existing = store.get_event(key) or {}
        delivery = dict(existing.get("delivery") or {})
        if bool(delivery.get("delivered")):
            skipped += 1
            continue

        attempted += 1
        symbol = str(event.get("symbol") or "").upper()
        message = str(event.get("message") or "")
        try:
            ok = bool(await sender(
                symbol=symbol,
                title=f"Atlas Quality Dips V3 · {event.get('event_type')}",
                description=message,
                severity="HIGH" if event.get("event_type") == "ENTRY_LEVEL_REACHED" else "MEDIUM",
                opportunity=80,
                confidence=75,
                risk=35,
            ))
        except Exception:
            ok = False

        store.mark_delivery(key, delivered=ok)
        if ok:
            delivered += 1
        else:
            failed += 1
    store.save()
    return {"attempted": attempted, "delivered": delivered, "failed": failed, "skipped": skipped}
