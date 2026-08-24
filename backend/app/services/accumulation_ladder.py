"""Stock accumulation ladder — core plan (incl. NVDA) + auto ladders."""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Tuple

import structlog

from app.core.config import get_settings

log = structlog.get_logger(__name__)

DEFAULT_LADDERS: Dict[str, List[Tuple[float, float]]] = {
    "MSFT": [
        (485.0, 500.0),
        (465.0, 600.0),
        (440.0, 700.0),
        (410.0, 800.0),
        (380.0, 900.0),
    ],
    "GOOGL": [
        (335.0, 400.0),
        (315.0, 450.0),
        (295.0, 500.0),
        (275.0, 550.0),
        (260.0, 600.0),
    ],
    "META": [
        (580.0, 400.0),
        (550.0, 450.0),
        (520.0, 500.0),
        (480.0, 550.0),
        (450.0, 600.0),
    ],
    "ORCL": [
        (140.0, 300.0),
        (130.0, 350.0),
        (120.0, 400.0),
        (105.0, 450.0),
        (95.0, 500.0),
    ],
    "NVDA": [
        (220.0, 400.0),
        (200.0, 450.0),
        (180.0, 500.0),
        (160.0, 550.0),
        (140.0, 600.0),
    ],
}


def _parse_env_ladders(raw: str) -> Dict[str, List[Tuple[float, float]]]:
    out: Dict[str, List[Tuple[float, float]]] = {}
    if not raw or not str(raw).strip():
        return out
    for block in str(raw).split("|"):
        block = block.strip()
        if not block or ":" not in block:
            continue
        parts = block.split(":")
        sym = parts[0].strip().upper()
        if sym == "GOOG":
            sym = "GOOGL"
        rest = ":".join(parts[1:])
        levels: List[Tuple[float, float]] = []
        for ch in rest.split(","):
            ch = ch.strip()
            if ":" not in ch:
                continue
            a, b = ch.split(":", 1)
            try:
                lvl, amt = float(a.strip()), float(b.strip())
            except ValueError:
                continue
            if lvl > 0 and amt > 0:
                levels.append((lvl, amt))
        if levels:
            out[sym] = levels
    return out


class AccumulationLadderService:
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
        if not getattr(settings, "accum_enabled", True):
            log.info("Accumulation ladder disabled")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="accumulation_ladder")
        ladders = await self._merged_ladders()
        log.info(
            "Accumulation ladder started",
            symbols=list(ladders.keys()),
            levels={k: [int(x[0]) for x in v] for k, v in ladders.items()},
            scan_minutes=float(getattr(settings, "accum_scan_minutes", 15) or 15),
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
        log.info("Accumulation ladder stopped")

    def _base_ladders(self) -> Dict[str, List[Tuple[float, float]]]:
        settings = get_settings()
        env_raw = getattr(settings, "accum_ladders", None) or ""
        parsed = _parse_env_ladders(str(env_raw))
        base = dict(DEFAULT_LADDERS)
        base.update(parsed)

        symbols = list(settings.accum_symbol_list) if settings.accum_symbol_list else list(base.keys())
        out: Dict[str, List[Tuple[float, float]]] = {}
        for sym in symbols:
            key = "GOOGL" if sym == "GOOG" else sym.upper()
            levels = base.get(key)
            if not levels:
                continue
            out[key] = sorted(levels, key=lambda x: x[0], reverse=True)
        if not out:
            out = {k: sorted(v, key=lambda x: x[0], reverse=True) for k, v in DEFAULT_LADDERS.items()}
        return out

    async def _merged_ladders(self) -> Dict[str, List[Tuple[float, float]]]:
        base = self._base_ladders()
        try:
            from app.services.auto_ladder import PROTECTED, auto_ladder

            dynamic = await auto_ladder.list_all()
            for sym, levels in dynamic.items():
                if sym in PROTECTED:
                    continue
                if sym in base:
                    continue
                base[sym] = sorted(levels, key=lambda x: x[0], reverse=True)
        except Exception as e:
            log.warning("Merge auto ladders failed", error=str(e))
        return base

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
            log.warning("Accumulation redis unavailable", error=str(e))
            return None

    def _rk(self, symbol: str, level: float, kind: str) -> str:
        return f"atlas:accum:{symbol}:{int(round(level))}:{kind}"

    async def _sent(self, symbol: str, level: float, kind: str) -> bool:
        r = await self._redis_client()
        if not r:
            return False
        try:
            return bool(await r.get(self._rk(symbol, level, kind)))
        except Exception:
            return False

    async def _mark(self, symbol: str, level: float, kind: str) -> None:
        r = await self._redis_client()
        if not r:
            return
        try:
            await r.set(self._rk(symbol, level, kind), "1", ex=365 * 24 * 3600)
        except Exception as e:
            log.warning("Accumulation mark failed", symbol=symbol, error=str(e))

    async def _price(self, symbol: str) -> Optional[float]:
        try:
            import yfinance as yf

            def _fetch() -> Optional[float]:
                t = yf.Ticker(symbol)
                fi = getattr(t, "fast_info", None)
                if fi is not None:
                    for attr in ("last_price", "lastPrice", "regular_market_price"):
                        try:
                            v = getattr(fi, attr, None)
                            if v is None and isinstance(fi, dict):
                                v = fi.get(attr)
                            if v is not None and float(v) > 0:
                                return float(v)
                        except Exception:
                            continue
                hist = t.history(period="5d", interval="1d")
                if hist is not None and len(hist) > 0:
                    return float(hist["Close"].iloc[-1])
                return None

            return await asyncio.to_thread(_fetch)
        except Exception as e:
            log.warning("Accumulation price failed", symbol=symbol, error=str(e))
            return None

    async def _send(
        self,
        *,
        symbol: str,
        level: float,
        amount: float,
        price: float,
        kind: str,
        level_index: int,
        total_levels: int,
    ) -> bool:
        try:
            from app.alerts.discord import is_discord_ready, send_discord_alert
        except Exception as e:
            log.warning("Accumulation discord import failed", error=str(e))
            return False

        if not is_discord_ready():
            log.warning(
                "Discord not ready — accumulation deferred",
                symbol=symbol,
                kind=kind,
                level=level,
            )
            return False

        if await self._sent(symbol, level, kind):
            return False

        ladders = await self._merged_ladders()
        levels = ladders.get(symbol) or []
        deeper = [x for x in levels if x[0] < level]
        next_hint = ""
        if deeper:
            nxt = max(deeper, key=lambda x: x[0])
            next_hint = f"\nNext deeper level: **${nxt[0]:,.2f}** (guide ${nxt[1]:,.0f})"

        title = f"Accumulation {kind} · {symbol} L{level_index}/{total_levels}"
        desc = (
            f"**Stock ladder — research only, manual buy (Robinhood)**\n\n"
            f"Symbol: **{symbol}**\n"
            f"Event: **{kind}**\n"
            f"Level: **${level:,.2f}** (L{level_index} of {total_levels})\n"
            f"Live price: **${price:,.2f}**\n"
            f"Guide size: **${amount:,.0f}**"
            f"{next_hint}\n\n"
            f"One alert per level. After this HIT, the bot watches the next lower level automatically.\n"
            f"You place every order. Atlas does not execute."
        )
        try:
            ok = await send_discord_alert(
                symbol=symbol,
                title=title,
                description=desc,
                price=price,
                severity="HIGH" if kind == "HIT" else "MEDIUM",
                opportunity=80 if kind == "HIT" else 60,
                confidence=75,
                risk=40,
            )
        except Exception as e:
            log.warning(
                "Accumulation Discord failed",
                symbol=symbol,
                kind=kind,
                level=level,
                error=str(e),
            )
            return False

        if ok:
            await self._mark(symbol, level, kind)
            if kind == "HIT":
                await self._mark(symbol, level, "NEAR")
            log.info(
                "Accumulation alert sent",
                symbol=symbol,
                kind=kind,
                level=level,
                level_index=level_index,
                price=price,
                amount=amount,
            )
        return bool(ok)

    async def _evaluate_symbol(
        self, symbol: str, levels: List[Tuple[float, float]]
    ) -> None:
        price = await self._price(symbol)
        if price is None or price <= 0:
            return

        settings = get_settings()
        near_pct = float(getattr(settings, "accum_near_pct", 1.5) or 1.5) / 100.0
        n = len(levels)

        hits = [
            (i, lvl, amt)
            for i, (lvl, amt) in enumerate(levels, start=1)
            if price <= lvl
        ]
        if hits:
            for i, lvl, amt in hits:
                if await self._sent(symbol, lvl, "HIT"):
                    continue
                await self._send(
                    symbol=symbol,
                    level=lvl,
                    amount=amt,
                    price=price,
                    kind="HIT",
                    level_index=i,
                    total_levels=n,
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
                if await self._sent(symbol, lvl, "NEAR"):
                    continue
                if await self._sent(symbol, lvl, "HIT"):
                    continue
                await self._send(
                    symbol=symbol,
                    level=lvl,
                    amount=amt,
                    price=price,
                    kind="NEAR",
                    level_index=i,
                    total_levels=n,
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
        interval = max(
            60.0, float(getattr(settings, "accum_scan_minutes", 15) or 15) * 60.0
        )
        await self._wait_discord(45.0)
        while self._running:
            try:
                ladders = await self._merged_ladders()
                for symbol, levels in ladders.items():
                    if not self._running:
                        break
                    try:
                        await self._evaluate_symbol(symbol, levels)
                    except Exception as e:
                        log.warning(
                            "Accumulation symbol error",
                            symbol=symbol,
                            error=str(e),
                        )
                    await asyncio.sleep(0.4)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("Accumulation cycle failed", error=str(e))
            await asyncio.sleep(interval)


accumulation_ladder = AccumulationLadderService()