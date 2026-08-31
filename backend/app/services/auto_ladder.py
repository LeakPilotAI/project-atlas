"""Auto-create accumulation ladders from first quality-dip alert (once per symbol)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import structlog

from app.core.config import get_settings

log = structlog.get_logger(__name__)

# Intentional core plan — never auto-overwrite
PROTECTED = {"MSFT", "GOOGL", "GOOG", "META", "ORCL", "NVDA"}


class AutoLadderService:
    def __init__(self) -> None:
        self._redis = None

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
            log.warning("Auto ladder redis unavailable", error=str(e))
            return None

    def _created_key(self, symbol: str) -> str:
        return f"atlas:auto_ladder:created:{symbol.upper()}"

    def _def_key(self, symbol: str) -> str:
        return f"atlas:auto_ladder:def:{symbol.upper()}"

    async def already_created(self, symbol: str) -> bool:
        r = await self._redis_client()
        if not r:
            return True
        try:
            return bool(await r.get(self._created_key(symbol)))
        except Exception:
            return True

    async def get_ladder(self, symbol: str) -> Optional[List[Tuple[float, float]]]:
        r = await self._redis_client()
        if not r:
            return None
        try:
            raw = await r.get(self._def_key(symbol))
            if not raw:
                return None
            data = json.loads(raw)
            out: List[Tuple[float, float]] = []
            for row in data:
                lvl = float(row["level"])
                amt = float(row["amount"])
                if lvl > 0 and amt > 0:
                    out.append((lvl, amt))
            out.sort(key=lambda x: x[0], reverse=True)
            return out or None
        except Exception as e:
            log.warning("Auto ladder read failed", symbol=symbol, error=str(e))
            return None

    async def list_all(self) -> Dict[str, List[Tuple[float, float]]]:
        r = await self._redis_client()
        if not r:
            return {}
        out: Dict[str, List[Tuple[float, float]]] = {}
        try:
            keys = await r.keys("atlas:auto_ladder:def:*")
            for key in keys:
                sym = str(key).split(":")[-1].upper()
                ladder = await self.get_ladder(sym)
                if ladder:
                    out[sym] = ladder
        except Exception as e:
            log.warning("Auto ladder list failed", error=str(e))
        return out

    def _build_levels(
        self,
        *,
        price: float,
        low_52w: Optional[float],
        category: str,
    ) -> List[Tuple[float, float]]:
        settings = get_settings()
        n = max(3, min(6, int(getattr(settings, "auto_ladder_levels", 5) or 5)))
        step = float(getattr(settings, "auto_ladder_step_pct", 5.0) or 5.0) / 100.0
        base = float(getattr(settings, "auto_ladder_base_usd", 200.0) or 200.0)
        cat = (category or "stock").lower()
        if cat in ("metal", "metals", "etf"):
            base = float(getattr(settings, "auto_ladder_base_usd_metal", 150.0) or base)

        floor = price * 0.55
        if low_52w and low_52w > 0:
            floor = max(floor, float(low_52w) * 1.02)

        levels: List[Tuple[float, float]] = []
        for i in range(n):
            if i == 0:
                lvl = price * 0.995
            else:
                lvl = price * ((1.0 - step) ** i)
            if lvl < floor:
                break
            amt = float(round(base * (1.0 + 0.12 * i), 0))
            levels.append((round(float(lvl), 2), amt))

        levels.sort(key=lambda x: x[0], reverse=True)
        return levels

    async def maybe_create_from_dip(
        self,
        *,
        symbol: str,
        price: float,
        name: str = "",
        category: str = "stock",
        high_52w: Optional[float] = None,
        low_52w: Optional[float] = None,
        pct_from_high: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        settings = get_settings()
        if not getattr(settings, "auto_ladder_enabled", True):
            return None

        sym = (symbol or "").strip().upper()
        if sym == "GOOG":
            sym = "GOOGL"
        if not sym or price is None or float(price) <= 0:
            return None
        if sym in PROTECTED:
            log.info("Auto ladder skip protected core", symbol=sym)
            return None

        if await self.already_created(sym):
            return None

        max_n = int(getattr(settings, "auto_ladder_max_symbols", 25) or 25)
        existing = await self.list_all()
        if len(existing) >= max_n and sym not in existing:
            log.warning("Auto ladder cap reached", max=max_n, symbol=sym)
            return None

        levels = self._build_levels(
            price=float(price),
            low_52w=low_52w,
            category=category or "stock",
        )
        if not levels:
            return None

        r = await self._redis_client()
        if not r:
            return None

        payload = [{"level": lvl, "amount": amt} for lvl, amt in levels]
        try:
            ok = await r.set(self._created_key(sym), "1", nx=True)
            if not ok:
                return None
            await r.set(self._def_key(sym), json.dumps(payload))
        except Exception as e:
            log.warning("Auto ladder write failed", symbol=sym, error=str(e))
            return None

        log.info(
            "Auto ladder created",
            symbol=sym,
            levels=[x[0] for x in levels],
            amounts=[x[1] for x in levels],
            price=float(price),
        )
        await self._notify_created(
            symbol=sym,
            name=name or sym,
            price=float(price),
            levels=levels,
            category=category or "stock",
            pct_from_high=pct_from_high,
        )
        return {"symbol": sym, "levels": levels}

    async def _notify_created(
        self,
        *,
        symbol: str,
        name: str,
        price: float,
        levels: List[Tuple[float, float]],
        category: str,
        pct_from_high: Optional[float],
    ) -> None:
        try:
            from app.alerts.discord import is_discord_ready, send_discord_alert
            from app.core.config import get_settings

            if not bool(get_settings().quality_dip_discord_enabled):
                return
            if not is_discord_ready():
                return
            lines = [
                f"L{i}: **${lvl:,.2f}** · guide ${amt:,.0f}"
                for i, (lvl, amt) in enumerate(levels, start=1)
            ]
            pct = f"{pct_from_high:.1f}%" if pct_from_high is not None else "n/a"
            desc = (
                f"**Auto ladder created (once)** — research only, manual buy\n\n"
                f"**{symbol}** — {name}\n"
                f"Category: {category.upper()}\n"
                f"Live: **${price:,.2f}** · off 52w high: {pct}\n\n"
                f"Scale-in plan:\n"
                + "\n".join(lines)
                + "\n\n"
                f"This symbol will **not** get another auto ladder.\n"
                f"HITs fire one level at a time as price reaches each step.\n"
                f"You place every order. Atlas does not execute."
            )
            await send_discord_alert(
                symbol=symbol,
                title=f"Auto Ladder · {symbol} · {len(levels)} levels",
                description=desc,
                price=price,
                severity="MEDIUM",
                opportunity=70,
                confidence=70,
                risk=40,
            )
        except Exception as e:
            log.warning("Auto ladder notify failed", symbol=symbol, error=str(e))


auto_ladder = AutoLadderService()