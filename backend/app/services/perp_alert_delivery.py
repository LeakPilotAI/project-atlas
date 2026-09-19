from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional

from app.alerts.discord import send_discord_alert
from app.core.logging import get_logger

log = get_logger("perp_alert_delivery")

Sender = Callable[..., Awaitable[bool]]
Acknowledger = Callable[[str], bool]


def _fmt_price(value: Any) -> str:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if x >= 1000:
        return f"${x:,.2f}"
    if x >= 1:
        return f"${x:,.4f}"
    return f"${x:.8f}"


def build_perp_alert(setup: Dict[str, Any]) -> Dict[str, Any]:
    symbol = str(setup.get("symbol") or "").upper()
    side = str(setup.get("side") or "").upper()
    tier = str(setup.get("tier") or "WATCH").upper()
    state = str(setup.get("state") or "WAIT").upper()
    levels = setup.get("levels") or {}
    score = float(setup.get("score") or 0.0)
    reason = str(setup.get("alert_reason") or "qualified actionable setup")
    next_action = str(setup.get("next_action") or "Review the manual levels before acting.")

    if not symbol or side not in {"LONG", "SHORT"}:
        raise ValueError("invalid manual perp alert candidate")

    description = (
        f"**{tier} · {state} · score {score:.1f}/100**\n"
        f"Mark: `{_fmt_price(setup.get('price') or setup.get('mark'))}`\n"
        f"L1 `{_fmt_price(levels.get('l1'))}` · L2 `{_fmt_price(levels.get('l2'))}` · "
        f"L3 `{_fmt_price(levels.get('l3'))}`\n"
        f"Stop `{_fmt_price(levels.get('stop'))}`\n"
        f"TP1 `{_fmt_price(levels.get('tp1'))}` · TP2 `{_fmt_price(levels.get('tp2'))}`\n"
        f"Action: {next_action}\n"
        f"Reason: {reason}\n\n"
        "_Hyperliquid only · manual execution · no order was placed._"
    )
    return {
        "symbol": symbol,
        "title": f"Atlas Perp · {tier} {symbol} {side}",
        "description": description,
        "price": float(setup.get("price") or setup.get("mark") or 0.0),
        "severity": "HIGH" if tier == "PRIME" else "MEDIUM",
        "opportunity": max(0, min(100, int(round(score)))),
        "confidence": max(0, min(100, int(round(score)))),
        "risk": 50,
    }


async def deliver_alert_candidates(
    candidates: Iterable[Dict[str, Any]],
    *,
    acknowledge: Acknowledger,
    sender: Sender = send_discord_alert,
) -> Dict[str, int]:
    """Deliver eligible manual-perp alerts without losing failed sends."""
    attempted = delivered = acknowledged = failed = 0
    for setup in list(candidates):
        if not bool(setup.get("alert_eligible")):
            continue
        key = str(setup.get("setup_key") or "")
        if not key:
            continue
        attempted += 1
        try:
            payload = build_perp_alert(setup)
            ok = bool(await sender(**payload))
        except Exception as exc:
            log.warning("Manual perp Discord delivery failed", setup_key=key, error=str(exc)[:160])
            ok = False
        if not ok:
            failed += 1
            continue
        delivered += 1
        try:
            if acknowledge(key):
                acknowledged += 1
        except Exception as exc:
            log.warning("Manual perp alert acknowledgement failed", setup_key=key, error=str(exc)[:160])
    return {
        "attempted": attempted,
        "delivered": delivered,
        "acknowledged": acknowledged,
        "failed": failed,
    }


class PerpAlertDeliveryService:
    """Poll manual-perp lifecycle for Discord alerts and the isolated paper mirror."""

    def __init__(self, *, interval_seconds: float = 10.0) -> None:
        self.interval_seconds = max(5.0, float(interval_seconds))
        self.running = False
        self.last_result: Dict[str, int] = {"attempted": 0, "delivered": 0, "acknowledged": 0, "failed": 0}
        self.last_paper_result: Dict[str, int] = {"opened": 0, "closed": 0, "marked": 0, "skipped": 0}
        self.last_reconciliation_result: Dict[str, Any] = {"attempted": 0, "delivered": 0, "reconciliation_ok": True}
        self.last_error: Optional[str] = None
        self.last_step_timings_ms: Dict[str, float] = {}
        self.last_cycle_elapsed_ms: float = 0.0
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._loop(), name="perp_alert_delivery")
        log.info("Manual perp Discord delivery + paper mirror started")

    async def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("Manual perp Discord delivery + paper mirror stopped")

    async def deliver_once(self, *, sender: Sender = send_discord_alert) -> Dict[str, int]:
        from app.services.perp_manual_service import perp_manual_service

        snapshot = perp_manual_service.snapshot()
        candidates = list(snapshot.get("alert_candidates") or [])
        result = await deliver_alert_candidates(
            candidates,
            acknowledge=perp_manual_service.acknowledge_alert,
            sender=sender,
        )
        self.last_result = result
        self.last_error = None
        return result

    async def paper_once(self) -> Dict[str, int]:
        from app.services.perp_manual_service import perp_manual_service
        from app.services.perp_setup_paper_mirror import perp_setup_paper_mirror

        snapshot = perp_manual_service.snapshot()
        setups = list(snapshot.get("setups") or [])
        price_map = {
            str(row.get("symbol") or "").upper(): float(row.get("price") or 0.0)
            for row in list(snapshot.get("markets") or [])
            if row.get("symbol") and float(row.get("price") or 0.0) > 0
        }
        result = await perp_setup_paper_mirror.sync(setups, price_map)
        self.last_paper_result = result
        return result

    def reconciliation_status(self) -> Dict[str, Any]:
        return {
            "running": bool(self.running),
            "last_result": dict(self.last_reconciliation_result),
            "last_error": self.last_error,
            "execution": "PAPER_ONLY",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "last_step_timings_ms": dict(self.last_step_timings_ms),
            "last_cycle_elapsed_ms": round(float(self.last_cycle_elapsed_ms), 3),
        }

    async def _loop(self) -> None:
        await asyncio.sleep(5)
        while self.running:
            cycle_started = time.perf_counter()
            step_started = time.perf_counter()
            try:
                await self.paper_once()
            except Exception as exc:
                log.warning("Manual perp paper mirror pass failed", error=f"{type(exc).__name__}: {str(exc)[:180]}")
            finally:
                self.last_step_timings_ms["paper_once"] = round((time.perf_counter() - step_started) * 1000.0, 3)
            step_started = time.perf_counter()
            try:
                await self.deliver_once()
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {str(exc)[:180]}"
                log.warning("Manual perp Discord delivery pass failed", error=self.last_error)
            finally:
                self.last_step_timings_ms["deliver_once"] = round((time.perf_counter() - step_started) * 1000.0, 3)
            step_started = time.perf_counter()
            try:
                from app.services.paper_reconciliation_alert import alert_reconciliation_if_needed
                self.last_reconciliation_result = await alert_reconciliation_if_needed()
            except Exception as exc:
                log.warning("PAPER reconciliation alert pass failed", error=f"{type(exc).__name__}: {str(exc)[:180]}")
            finally:
                self.last_step_timings_ms["reconciliation"] = round((time.perf_counter() - step_started) * 1000.0, 3)
                self.last_cycle_elapsed_ms = round((time.perf_counter() - cycle_started) * 1000.0, 3)
            await asyncio.sleep(self.interval_seconds)


perp_alert_delivery_service = PerpAlertDeliveryService()
