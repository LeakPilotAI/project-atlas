"""Quality-dip view and durable accumulation-level alert monitor.

The investment engine remains the source of truth. Real brokerage execution is
always manual. A lightweight quote monitor watches frozen accumulation ladders and
DMs one alert per L1/L2/L3/L4 hit for each accumulation cycle.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from app.core.config import get_settings
from app.investment.storage import DATA_DIR, OPPORTUNITIES_PATH, PLANS_PATH, ensure_dirs

log = structlog.get_logger(__name__)

ALERT_COOLDOWN_PATH = DATA_DIR / "quality_dip_alerts.json"
LADDER_MONITOR_INTERVAL_SEC = 60.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except Exception:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except Exception:
        return []
    return out


class QualityDipScanner:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._ladder_task: Optional[asyncio.Task] = None
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
        self._ladder_task = asyncio.create_task(self._ladder_loop(), name="quality_dip_ladder_monitor")
        log.info("Quality dip consumer started (investment engine is source of truth)")

    async def stop(self) -> None:
        self._running = False
        for task in (self._task, self._ladder_task):
            if task:
                task.cancel()
        for task in (self._task, self._ladder_task):
            if task:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._task = None
        self._ladder_task = None
        log.info("Quality dip consumer stopped")

    def _research_gate(self, row: Dict[str, Any]) -> Dict[str, Any]:
        from app.investment.buy_prep import from_tape_row
        from app.investment.high_conviction import from_quality_tape

        prep = from_tape_row(row)
        return from_quality_tape(row, prep)

    def _should_notify(self, row: Dict[str, Any], hours: float) -> bool:
        gate = self._research_gate(row)
        if not bool(gate.get("high_conviction")):
            return False
        sym = str(row.get("symbol") or "").upper()
        if not sym:
            return False
        prev = self._cooldowns.get(sym) or {}
        if str(prev.get("action") or "") == "A+_QUALITY_DIP":
            last = _parse(prev.get("last_at"))
            if last and _now() - last < timedelta(hours=max(1.0, hours)):
                return False
        return True

    async def _emit(self, row: Dict[str, Any]) -> None:
        from app.investment.buy_prep import format_quality_dip_alert, from_tape_row
        from app.investment.high_conviction import from_quality_tape
        from app.investment.notify import deliver_investment_alert

        prep = from_tape_row(row)
        gate = from_quality_tape(row, prep)
        text = format_quality_dip_alert(row, prep)
        runway = gate.get("recovery_runway_pct")
        runway_line = "UNKNOWN" if runway is None else f"{float(runway):.1f}%"
        text = (
            "A+ QUALITY DIP RESEARCH CANDIDATE\n"
            f"Recovery runway to prior high: {runway_line}\n"
            "25% is a screening hurdle, not a promised return.\n\n"
            + text
        )
        ok = await deliver_investment_alert(
            text,
            symbol=str(row.get("symbol") or ""),
            priority="HIGH",
            title=f"ATLAS A+ QUALITY DIP · {row.get('symbol')}",
        )
        now = _now().isoformat()
        self._cooldowns[str(row.get("symbol") or "").upper()] = {
            "action": "A+_QUALITY_DIP",
            "last_at": now,
            "delivered": bool(ok),
        }
        self._save_cooldowns()
        self.last_alerts = ([{
            "symbol": row.get("symbol"),
            "action": "A+_QUALITY_DIP",
            "at": now,
            "delivered": bool(ok),
            "recovery_runway_pct": runway,
        }] + self.last_alerts)[:20]
        log.info("A+ quality dip research alert", symbol=row.get("symbol"), recovery_runway_pct=runway, delivered=bool(ok))

    async def _accumulation_board(self) -> list[dict[str, Any]]:
        """Build a fresh quote-aware board, fetching only current ACCUMULATE names."""
        from app.investment.board import build_quality_dips_board
        from app.investment.quality_dip_quotes import apply_quote_overlay, quality_dip_quote_service

        research = _load_jsonl(OPPORTUNITIES_PATH)
        plans = _load_jsonl(PLANS_PATH)
        base = build_quality_dips_board(research, plans, limit=100)
        symbols = [r.get("symbol") for r in base if str(r.get("stance") or "").upper() == "ACCUMULATE"]
        if not symbols:
            return base
        quotes = await quality_dip_quote_service.get_many(symbols)
        return build_quality_dips_board(apply_quote_overlay(research, quotes), plans, limit=100)

    async def _emit_ladder_hit(self, hit: Any) -> bool:
        from app.investment.notify import deliver_investment_alert

        text = "\n".join([
            f"ACCUMULATION DIP LEVEL HIT · {hit.level}",
            f"{hit.symbol}",
            "",
            f"Frozen {hit.level} research limit: ${hit.level_price:,.2f}",
            f"Latest supported quote: ${hit.market_price:,.2f}",
            f"Accumulation-cycle anchor: ${hit.anchor_price:,.2f}",
            f"Depth from anchor: {hit.pct_below_anchor:.1f}%",
            f"Quote session: {hit.quote_session}",
            f"Quote timestamp: {hit.quote_timestamp or 'UNKNOWN'}",
            "",
            "MANUAL ACTION:",
            f"Review {hit.symbol} in Robinhood now. Atlas detected the price reaching/crossing this frozen dip level.",
            "This alert does not place a brokerage order and is not a guarantee the dip will reverse.",
            "The next lower level remains armed if the accumulation thesis stays active.",
        ])
        return await deliver_investment_alert(
            text,
            symbol=hit.symbol,
            priority="HIGH" if hit.level in {"L3", "L4"} else "NORMAL",
            title=f"ATLAS ACCUMULATION · {hit.symbol} · {hit.level} HIT",
        )

    async def _ladder_once(self) -> None:
        from app.investment.accumulation_ladder import accumulation_ladder_store

        board = await self._accumulation_board()
        hits = accumulation_ladder_store.sync(board)
        settings = get_settings()
        discord_enabled = bool(getattr(settings, "quality_dip_discord_enabled", False))
        for hit in hits:
            delivered = False
            if discord_enabled:
                try:
                    delivered = await self._emit_ladder_hit(hit)
                except Exception as exc:
                    log.warning("accumulation ladder DM failed", symbol=hit.symbol, level=hit.level, error=str(exc)[:160])
            event = {
                "symbol": hit.symbol,
                "action": "ACCUMULATION_LEVEL_HIT",
                "level": hit.level,
                "level_price": hit.level_price,
                "market_price": hit.market_price,
                "cycle_id": hit.cycle_id,
                "at": _now().isoformat(),
                "delivered": delivered,
            }
            self.last_alerts = ([event] + self.last_alerts)[:20]
            log.info("accumulation ladder level hit", **event)

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

    async def _ladder_loop(self) -> None:
        await asyncio.sleep(12)
        while self._running:
            try:
                await self._ladder_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("accumulation ladder monitor failed", error=str(exc)[:200])
            await asyncio.sleep(LADDER_MONITOR_INTERVAL_SEC)

    async def _loop(self) -> None:
        settings = get_settings()
        interval = max(180.0, float(getattr(settings, "quality_dip_scan_interval_minutes", 15) or 15) * 60.0)
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
