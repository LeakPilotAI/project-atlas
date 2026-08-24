"""BTC generational ladder — production.

- Levels: scale-in when live BTC mid <= level.
- One HIT and one NEAR per level (Redis, survives restart).
- After L1 is marked, deeper prints auto-alert L2, L3, … (no manual reset).
- One new alert per cycle. No L63500. Manual buys only.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional, Tuple

import structlog

from app.core.config import get_settings

log = structlog.get_logger(__name__)

_DEFAULT_LEVELS: List[Tuple[float, float]] = [
    (60000.0, 300.0),
    (56000.0, 400.0),
    (52000.0, 500.0),
    (48000.0, 650.0),
    (42000.0, 700.0),
    (36000.0, 650.0),
    (30000.0, 600.0),
]


class BtcAccumulationService:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._redis = None

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        settings = get_settings()
        if not getattr(settings, "btc_accum_enabled", True):
            log.info("BTC accumulation disabled")
            return

        scan_min = float(getattr(settings, "btc_accum_scan_minutes", 15) or 15)
        if scan_min < 1:
            scan_min = 15.0
        cooldown_h = float(getattr(settings, "btc_accum_cooldown_hours", 720) or 720)
        if cooldown_h < 1:
            cooldown_h = 720.0

        self._running = True
        self._task = asyncio.create_task(self._loop(), name="btc_accumulation")
        levels = self._levels()
        log.info(
            "BTC accumulation started",
            levels=[int(x[0]) for x in levels],
            scan_minutes=scan_min,
            cooldown_hours=cooldown_h,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("BTC accumulation stopped")

    def _levels(self) -> List[Tuple[float, float]]:
        settings = get_settings()
        out: List[Tuple[float, float]] = []

        raw_list = getattr(settings, "btc_buy_level_list", None)
        if raw_list:
            for item in raw_list:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    lvl, amt = float(item[0]), float(item[1])
                    if lvl > 0 and amt > 0 and abs(lvl - 63500.0) > 1.0:
                        out.append((lvl, amt))

        if not out:
            s = getattr(settings, "btc_buy_levels", "") or ""
            for part in str(s).split(","):
                part = part.strip()
                if ":" not in part:
                    continue
                a, b = part.split(":", 1)
                try:
                    lvl, amt = float(a.strip()), float(b.strip())
                except ValueError:
                    continue
                if lvl > 0 and amt > 0 and abs(lvl - 63500.0) > 1.0:
                    out.append((lvl, amt))

        out.sort(key=lambda x: x[0], reverse=True)
        return out or list(_DEFAULT_LEVELS)

    async def _redis_client(self):
        if self._redis is not None:
            return self._redis
        try:
            from app.core.redis import get_redis_client

            self._redis = await get_redis_client()
            if self._redis is not None:
                return self._redis
        except Exception:
            pass
        try:
            import redis.asyncio as redis

            self._redis = redis.from_url(get_settings().redis_url, decode_responses=True)
            return self._redis
        except Exception as e:
            log.warning("BTC redis unavailable", error=str(e))
            return None

    def _rk(self, level: float, kind: str) -> str:
        return f"atlas:btc:lvl:{int(round(level))}:{kind}"

    async def _sent(self, level: float, kind: str) -> bool:
        r = await self._redis_client()
        if not r:
            return False
        try:
            return bool(await r.get(self._rk(level, kind)))
        except Exception:
            return False

    async def _mark(self, level: float, kind: str) -> None:
        r = await self._redis_client()
        if not r:
            return
        try:
            await r.set(self._rk(level, kind), "1", ex=365 * 24 * 3600)
        except Exception as e:
            log.warning("BTC mark failed", error=str(e))

    async def _price(self) -> Optional[float]:
        try:
            from app.adapters.registry import registry

            adapter = None
            if hasattr(registry, "get"):
                adapter = registry.get("hyperliquid")
            elif hasattr(registry, "get_adapter"):
                adapter = registry.get_adapter("hyperliquid")
            if adapter:
                if hasattr(adapter, "get_mid"):
                    m = adapter.get_mid("BTC")
                    if m:
                        return float(m)
                mids = getattr(adapter, "mids", None)
                if isinstance(mids, dict) and mids.get("BTC") is not None:
                    return float(mids["BTC"])
        except Exception as e:
            log.warning("BTC mid failed", error=str(e))

        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    "https://api.hyperliquid.xyz/info",
                    json={"type": "allMids"},
                )
                r.raise_for_status()
                data = r.json()
                if isinstance(data, dict) and "BTC" in data:
                    return float(data["BTC"])
        except Exception as e:
            log.warning("BTC HTTP mid failed", error=str(e))
        return None

    async def _send(
        self, *, level: float, amount: float, price: float, kind: str, level_index: int, total: int
    ) -> bool:
        from app.alerts.discord import is_discord_ready, send_discord_alert

        if not is_discord_ready():
            log.warning("Discord not ready — BTC deferred", level=level, kind=kind)
            return False

        if abs(level - 63500.0) <= 1.0:
            await self._mark(level, "HIT")
            await self._mark(level, "NEAR")
            return False

        if await self._sent(level, kind):
            return False

        levels = self._levels()
        deeper = [x for x in levels if x[0] < level]
        next_hint = ""
        if deeper:
            nxt = max(deeper, key=lambda x: x[0])
            next_hint = f"\nNext deeper level: **${nxt[0]:,.0f}** (guide ${nxt[1]:,.0f})"

        title = f"BTC Accumulation {kind} · L{level_index}/{total} · ${level:,.0f}"
        desc = (
            f"**BTC ladder — research only, manual buy**\n\n"
            f"Event: **{kind}**\n"
            f"Level: **${level:,.0f}** (L{level_index} of {total})\n"
            f"Live price: **${price:,.2f}**\n"
            f"Guide size: **${amount:,.0f}**\n"
            f"Keep reserve: **${get_settings().btc_emergency_reserve:,.0f}**"
            f"{next_hint}\n\n"
            f"One alert per level. After this HIT, the bot watches the next lower level automatically.\n"
            f"You place every order. Atlas does not execute."
        )
        try:
            ok = await send_discord_alert(
                symbol="BTC",
                title=title,
                description=desc,
                price=price,
                severity="HIGH" if kind == "HIT" else "MEDIUM",
                opportunity=80 if kind == "HIT" else 60,
                confidence=75,
                risk=40,
            )
        except Exception as e:
            log.warning("BTC Discord failed", kind=kind, level=level, error=str(e))
            return False

        if ok:
            await self._mark(level, kind)
            if kind == "HIT":
                await self._mark(level, "NEAR")
            log.info(
                "BTC alert sent",
                kind=kind,
                level=level,
                level_index=level_index,
                price=price,
                amount=amount,
            )
        return bool(ok)

    async def _evaluate(self, price: float) -> None:
        """Alert highest unsent HIT when price <= level; then deeper levels as price falls."""
        settings = get_settings()
        near_pct = float(getattr(settings, "btc_accum_near_pct", 1.0) or 1.0) / 100.0
        levels = self._levels()
        total = len(levels)

        # high → low so we process $60k before $56k
        hits = [(i, lvl, amt) for i, (lvl, amt) in enumerate(levels, start=1) if price <= lvl]
        if hits:
            for i, lvl, amt in hits:
                if await self._sent(lvl, "HIT"):
                    continue
                await self._send(
                    level=lvl,
                    amount=amt,
                    price=price,
                    kind="HIT",
                    level_index=i,
                    total=total,
                )
                return
            return

        nears = [
            (i, lvl, amt)
            for i, (lvl, amt) in enumerate(levels, start=1)
            if price > lvl and (price - lvl) / lvl <= near_pct
        ]
        if nears:
            for i, lvl, amt in nears:
                if await self._sent(lvl, "NEAR") or await self._sent(lvl, "HIT"):
                    continue
                await self._send(
                    level=lvl,
                    amount=amt,
                    price=price,
                    kind="NEAR",
                    level_index=i,
                    total=total,
                )
                return

    async def _wait_discord(self, timeout: float = 45.0) -> None:
        try:
            from app.alerts.discord import is_discord_ready
        except Exception:
            await asyncio.sleep(15)
            return
        elapsed = 0.0
        while elapsed < timeout and self._running:
            if is_discord_ready():
                return
            await asyncio.sleep(1.0)
            elapsed += 1.0

    async def _loop(self) -> None:
        settings = get_settings()
        scan_min = float(getattr(settings, "btc_accum_scan_minutes", 15) or 15)
        if scan_min < 1:
            scan_min = 15.0
        interval = max(60.0, scan_min * 60.0)
        await self._wait_discord(45.0)
        while self._running:
            try:
                px = await self._price()
                if px is not None:
                    await self._evaluate(px)
                else:
                    log.warning("BTC price unavailable")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("BTC cycle failed", error=str(e))
            await asyncio.sleep(interval)


btc_accumulation = BtcAccumulationService()