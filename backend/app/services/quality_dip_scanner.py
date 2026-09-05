"""Quality-dip view. Thin consumer of the investment engine. No second Yahoo loop."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog

from app.core.config import get_settings
from app.investment.storage import DATA_DIR, ensure_dirs

log = structlog.get_logger(__name__)

ALERT_COOLDOWN_PATH = DATA_DIR / "quality_dip_alerts.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


class QualityDipScanner:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.last_scan_at: Optional[str] = None
        self.last_snapshot: List[Dict[str, Any]] = []
        self.last_alerts: List[Dict[str, Any]] = []
        self._cooldowns: Dict[str, Dict[str, Any]] = {}
        self._load_cooldowns()

    @property
    def running(self) -> bool:
        return self._running

    def _load_cooldowns(self) -> None:
        self._cooldowns = {}
        if not ALERT_COOLDOWN_PATH.exists():
            return
        try:
            data = json.loads(ALERT_COOLDOWN_PATH.read_text(encoding="utf-8"))
        except Exception:
            return
        rows = data.get("symbols") if isinstance(data, dict) else data
        if not isinstance(rows, dict):
            return
        self._cooldowns = rows

    def _save_cooldowns(self) -> None:
        ensure_dirs()
        ALERT_COOLDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
        ALERT_COOLDOWN_PATH.write_text(
            json.dumps({"symbols": self._cooldowns}, indent=2),
            encoding="utf-8",
        )

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        settings = get_settings()
        if not getattr(settings, "quality_dip_enabled", True):
            log.info("Quality dip consumer disabled")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="quality_dip_consumer")
        log.info("Quality dip consumer started (investment engine is source of truth)")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("Quality dip consumer stopped")

    def _should_notify(self, row: Dict[str, Any], hours: float) -> bool:
        if not row.get("notify"):
            return False
        sym = str(row.get("symbol") or "").upper()
        if not sym:
            return False
        prev = self._cooldowns.get(sym) or {}
        if str(prev.get("action") or "") == str(row.get("action") or ""):
            last = _parse(prev.get("last_at"))
            if last and _now() - last < timedelta(hours=max(1.0, hours)):
                return False
        return True

    async def _emit(self, row: Dict[str, Any]) -> None:
        from app.investment.buy_prep import format_quality_dip_alert, from_tape_row
        from app.investment.notify import deliver_investment_alert

        prep = from_tape_row(row)
        text = format_quality_dip_alert(row, prep)
        ok = await deliver_investment_alert(
            text,
            symbol=str(row.get("symbol") or ""),
            priority=str(prep.get("priority") or "NORMAL"),
            title=f"ATLAS QUALITY DIP — {prep.get('action')} · {row.get('symbol')}",
        )
        now = _now().isoformat()
        self._cooldowns[str(row.get("symbol") or "").upper()] = {
            "action": row.get("action"),
            "last_at": now,
            "delivered": bool(ok),
        }
        self._save_cooldowns()
        self.last_alerts = ([{"symbol": row.get("symbol"), "action": row.get("action"), "at": now, "delivered": bool(ok)}] + self.last_alerts)[:20]
        log.info(
            "quality dip alert",
            symbol=row.get("symbol"),
            action=row.get("action"),
            delivered=bool(ok),
        )

    async def _consume(self) -> None:
        from app.investment.scan import investment_scanner
        from app.investment.storage import bootstrap_universe_if_missing
        from app.investment.tape import as_quality_dip_rows

        bootstrap_universe_if_missing()
        if not getattr(investment_scanner, "running", False):
            try:
                await investment_scanner.run_once()
            except Exception as e:
                log.warning("investment run_once from quality-dip consumer failed", error=str(e)[:200])
        rows = as_quality_dip_rows()
        self.last_snapshot = rows
        self.last_scan_at = _now().isoformat()
        settings = get_settings()
        if not bool(getattr(settings, "quality_dip_discord_enabled", False)):
            return
        hours = float(getattr(settings, "quality_dip_cooldown_hours", 12) or 12)
        for row in rows:
            if not self._should_notify(row, hours):
                continue
            try:
                await self._emit(row)
            except Exception as e:
                log.warning("quality dip notify failed", symbol=row.get("symbol"), error=str(e)[:160])

    async def _loop(self) -> None:
        settings = get_settings()
        interval = max(
            180.0,
            float(getattr(settings, "quality_dip_scan_interval_minutes", 15) or 15) * 60.0,
        )
        await asyncio.sleep(8)
        while self._running:
            try:
                await self._consume()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("Quality dip consume failed", error=str(e))
            await asyncio.sleep(interval)


quality_dip_scanner = QualityDipScanner()
