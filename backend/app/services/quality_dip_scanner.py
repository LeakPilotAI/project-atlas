"""Quality dip / generational discount scanner + auto-ladder hook."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog

from app.core.config import get_settings

log = structlog.get_logger(__name__)

METALS = {"GLD", "IAU", "GDX", "SLV", "SIL"}


class QualityDipScanner:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._redis = None
        self.last_scan_at: Optional[str] = None
        self.last_snapshot: List[Dict[str, Any]] = []

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        settings = get_settings()
        if not getattr(settings, "quality_dip_enabled", True):
            log.info("Quality dip scanner disabled")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="quality_dip_scanner")
        wl = settings.quality_dip_watchlist_list
        log.info(
            "Quality dip scanner started",
            adaptive=bool(settings.quality_dip_adaptive),
            watchlist=wl,
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
        log.info("Quality dip scanner stopped")

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
            log.info("Redis client created", url=get_settings().redis_url)
            return self._redis
        except Exception as e:
            log.warning("Quality dip redis unavailable", error=str(e))
            return None

    def _cd_key(self, symbol: str) -> str:
        return f"atlas:qdip:cd:{symbol.upper()}"

    def _brief_key(self) -> str:
        return "atlas:qdip:brief:last"

    async def _on_cooldown(self, symbol: str) -> bool:
        r = await self._redis_client()
        if not r:
            return False
        try:
            return bool(await r.get(self._cd_key(symbol)))
        except Exception:
            return False

    async def _mark_cooldown(self, symbol: str) -> None:
        settings = get_settings()
        hours = float(getattr(settings, "quality_dip_cooldown_hours", 12) or 12)
        r = await self._redis_client()
        if not r:
            return
        try:
            await r.set(self._cd_key(symbol), "1", ex=max(3600, int(hours * 3600)))
        except Exception as e:
            log.warning("Quality dip cooldown mark failed", symbol=symbol, error=str(e))

    def _category(self, symbol: str) -> str:
        return "metal" if symbol.upper() in METALS else "stock"

    def _thresholds(self, symbol: str, hist_vol: Optional[float] = None) -> Tuple[float, float]:
        settings = get_settings()
        cat = self._category(symbol)
        if cat == "metal":
            normal = float(settings.quality_dip_metals_threshold_pct)
            high = float(settings.quality_dip_metals_high_priority_pct)
            floor = float(settings.quality_dip_adaptive_floor_metal)
            ceil = float(settings.quality_dip_adaptive_ceiling_metal)
        else:
            normal = float(settings.quality_dip_threshold_pct)
            high = float(settings.quality_dip_high_priority_pct)
            floor = float(settings.quality_dip_adaptive_floor_stock)
            ceil = float(settings.quality_dip_adaptive_ceiling_stock)

        if settings.quality_dip_adaptive and hist_vol is not None and hist_vol > 0:
            # higher vol → slightly lower trigger (alert earlier)
            adj = min(8.0, max(-5.0, (hist_vol - 0.25) * 20.0))
            normal = max(floor, min(ceil, normal - adj * 0.3))
            high = max(floor + 2.0, min(ceil + 5.0, high - adj * 0.25))
        return normal, high

    async def _fetch_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            import yfinance as yf

            def _load() -> Optional[Dict[str, Any]]:
                t = yf.Ticker(symbol)
                hist = t.history(period="1y", interval="1d")
                if hist is None or len(hist) < 20:
                    return None
                closes = hist["Close"].astype(float)
                price = float(closes.iloc[-1])
                high_52w = float(closes.max())
                low_52w = float(closes.min())
                if price <= 0 or high_52w <= 0:
                    return None
                pct_from_high = (high_52w - price) / high_52w * 100.0

                def chg(n: int) -> Optional[float]:
                    if len(closes) <= n:
                        return None
                    prev = float(closes.iloc[-n - 1])
                    if prev <= 0:
                        return None
                    return (price - prev) / prev * 100.0

                rets = closes.pct_change().dropna()
                hist_vol = float(rets.tail(60).std() * (252 ** 0.5)) if len(rets) > 10 else None

                info_name = symbol
                try:
                    info = t.info or {}
                    info_name = info.get("shortName") or info.get("longName") or symbol
                except Exception:
                    pass

                return {
                    "symbol": symbol.upper(),
                    "name": info_name,
                    "price": price,
                    "high_52w": high_52w,
                    "low_52w": low_52w,
                    "pct_from_high": pct_from_high,
                    "chg_5d": chg(5),
                    "chg_10d": chg(10),
                    "chg_20d": chg(20),
                    "hist_vol": hist_vol,
                    "category": self._category(symbol),
                }

            return await asyncio.to_thread(_load)
        except Exception as e:
            log.warning("Quality dip fetch failed", symbol=symbol, error=str(e))
            return None

    def _review_score(self, row: Dict[str, Any], normal: float, high: float) -> float:
        pct = float(row["pct_from_high"])
        score = 0.0
        score += min(40.0, max(0.0, (pct - normal) * 1.2))
        if pct >= high:
            score += 15.0
        c5 = row.get("chg_5d")
        c10 = row.get("chg_10d")
        c20 = row.get("chg_20d")
        if c5 is not None and c5 < -3:
            score += 10.0
        if c10 is not None and c10 < -5:
            score += 8.0
        if c20 is not None and c20 < -10:
            score += 8.0
        if c5 is not None and c5 > 3:
            score -= 8.0  # bouncing — lower urgency
        low = float(row["low_52w"])
        price = float(row["price"])
        if low > 0 and (price - low) / low > 0.35:
            score -= 5.0  # still far above lows
        return max(0.0, min(100.0, score))

    def _reasons(self, row: Dict[str, Any], normal: float, high: float) -> List[str]:
        reasons: List[str] = []
        pct = float(row["pct_from_high"])
        if pct >= high:
            reasons.append(f"≥{high:.1f}% below 52-week high (high priority)")
        elif pct >= normal:
            reasons.append(f"≥{normal:.1f}% below 52-week high")
        c5 = row.get("chg_5d")
        if c5 is not None and c5 <= -float(get_settings().quality_dip_short_drop_pct):
            reasons.append(f"Sharp short drop 5d {c5:.1f}%")
        return reasons

    async def _send_alert(self, row: Dict[str, Any], normal: float, high: float, score: float) -> bool:
        try:
            from app.alerts.discord import is_discord_ready, send_discord_alert
        except Exception as e:
            log.warning("Quality dip discord import failed", error=str(e))
            return False

        if not is_discord_ready():
            return False

        symbol = row["symbol"]
        price = float(row["price"])
        pct = float(row["pct_from_high"])
        priority = "high" if pct >= high else "normal"
        reasons = self._reasons(row, normal, high)
        if not reasons:
            return False

        def fmt_chg(v: Optional[float]) -> str:
            if v is None:
                return "n/a"
            return f"{v:+.1f}%"

        title = f"{symbol} — {'Generational' if priority == 'high' else 'Quality'} Discount Zone"
        desc = (
            f"**{symbol}** — {row.get('name', symbol)}\n"
            f"Category: **{row.get('category', 'stock').upper()}** · adaptive thresholds\n"
            f"Current price: **${price:,.2f}**\n"
            f"% below 52-week high: **{pct:.1f}%**\n"
            f"Alert thresholds: {normal:.1f}% / {high:.1f}% (high)\n"
            f"52-week high: ${float(row['high_52w']):,.2f}\n"
            f"52-week low: ${float(row['low_52w']):,.2f}\n"
            f"5-day change: {fmt_chg(row.get('chg_5d'))}\n"
            f"10-day change: {fmt_chg(row.get('chg_10d'))}\n"
            f"20-day change: {fmt_chg(row.get('chg_20d'))}\n"
            f"Review score: **{score:.0f}/100**\n"
            f"Triggers:\n"
            + "\n".join(f"• {r}" for r in reasons)
            + "\n\n"
            f"**POSSIBLE QUALITY DIP / GENERATIONAL DISCOUNT – Review before buying**\n"
            f"No auto-buy. Confirm price on your broker before acting."
        )
        try:
            ok = await send_discord_alert(
                symbol=symbol,
                title=title,
                description=desc,
                price=price,
                severity="HIGH" if priority == "high" else "MEDIUM",
                opportunity=min(95, int(55 + score * 0.4)),
                confidence=70,
                risk=45,
            )
        except Exception as e:
            log.warning("Quality dip Discord failed", symbol=symbol, error=str(e))
            return False

        if ok:
            await self._mark_cooldown(symbol)
            log.info(
                "Quality dip alert sent",
                symbol=symbol,
                pct_from_high=round(pct, 1),
                review_score=round(score, 1),
            )
            # One-time auto ladder for non-core names
            try:
                from app.services.auto_ladder import auto_ladder

                await auto_ladder.maybe_create_from_dip(
                    symbol=symbol,
                    price=price,
                    name=str(row.get("name") or symbol),
                    category=str(row.get("category") or "stock"),
                    high_52w=float(row["high_52w"]),
                    low_52w=float(row["low_52w"]),
                    pct_from_high=pct,
                )
            except Exception as e:
                log.warning("Auto ladder create failed", symbol=symbol, error=str(e))
        return bool(ok)

    async def _send_briefing(self, candidates: List[Dict[str, Any]]) -> None:
        if not candidates:
            return
        r = await self._redis_client()
        if r:
            try:
                if await r.get(self._brief_key()):
                    log.info("Quality dip briefing skipped (cooldown)")
                    return
            except Exception:
                pass

        try:
            from app.alerts.discord import is_discord_ready, send_discord_alert
        except Exception:
            return
        if not is_discord_ready():
            return

        ranked = sorted(candidates, key=lambda x: x["score"], reverse=True)[:8]
        lines = []
        for i, c in enumerate(ranked, start=1):
            c5 = c["row"].get("chg_5d")
            c5s = f"{c5:+.1f}%" if c5 is not None else "n/a"
            tags = []
            if c["row"]["pct_from_high"] >= 40:
                tags.append("severe/deep drawdown")
            elif c["row"]["pct_from_high"] >= 25:
                tags.append("material drawdown")
            if c5 is not None and c5 > 3:
                tags.append("bouncing short-term")
            if c["row"].get("category") == "metal":
                tags.append("metals complex")
            tag_s = ", ".join(tags) if tags else "watch"
            lines.append(
                f"{i}. **{c['symbol']}** — score {c['score']:.0f}/100 · "
                f"{c['row']['pct_from_high']:.1f}% off high · 5d {c5s} · {tag_s}"
            )

        metals = [c["symbol"] for c in ranked if c["row"].get("category") == "metal"]
        soft = [c["symbol"] for c in ranked if c["symbol"] in {"ORCL", "INTU", "ADBE", "CRM", "NOW"}]
        approach = [
            f"• Start with **{ranked[0]['symbol']}** — highest review score.",
        ]
        if metals:
            approach.append(f"• Metals complex: {', '.join(metals)} — one theme, not separate full positions.")
        if soft:
            approach.append(f"• Software cluster: {', '.join(soft)} — compare relative strength.")

        desc = (
            f"**Quality Dip Briefing — {len(candidates)} candidates**\n"
            f"Research priority only · not buy advice · confirm live prices.\n\n"
            f"Deep-analysis priority (start here):\n"
            + "\n".join(lines)
            + "\n\nApproach\n"
            + "\n".join(approach)
            + "\n\n1. Open charts for top 3 only\n"
            "2. Verify on broker\n"
            "3. Size small if acting — discounts ≠ guarantees\n\n"
            "Atlas ranks research time. You decide capital."
        )
        try:
            ok = await send_discord_alert(
                symbol="BRIEF",
                title="Quality Dip — Batch Analysis",
                description=desc,
                price=0.0,
                severity="MEDIUM",
                opportunity=int(ranked[0]["score"]),
                confidence=70,
                risk=40,
            )
            if ok and r:
                await r.set(self._brief_key(), datetime.now(timezone.utc).isoformat(), ex=20 * 3600)
                log.info("Quality dip briefing sent", candidates=len(candidates))
        except Exception as e:
            log.warning("Quality dip briefing failed", error=str(e))

    async def _scan_once(self) -> None:
        settings = get_settings()
        symbols = settings.quality_dip_watchlist_list
        log.info("Quality dip scan starting", count=len(symbols))
        candidates: List[Dict[str, Any]] = []
        alerted = 0

        for symbol in symbols:
            if not self._running:
                break
            row = await self._fetch_symbol(symbol)
            if not row:
                continue
            normal, high = self._thresholds(symbol, row.get("hist_vol"))
            pct = float(row["pct_from_high"])
            score = self._review_score(row, normal, high)
            reasons = self._reasons(row, normal, high)
            if not reasons:
                continue

            candidates.append(
                {
                    "symbol": symbol,
                    "row": row,
                    "score": score,
                    "normal": normal,
                    "high": high,
                }
            )

            if await self._on_cooldown(symbol):
                log.info(
                    "Quality dip cooldown",
                    symbol=symbol,
                    pct_from_high=round(pct, 1),
                )
                continue

            if await self._send_alert(row, normal, high, score):
                alerted += 1
            await asyncio.sleep(0.35)

        await self._send_briefing(candidates)
        self.last_scan_at = datetime.now(timezone.utc).isoformat()
        self.last_snapshot = [
            {
                "symbol": c["symbol"],
                "score": round(float(c.get("score") or 0), 1),
                "price": (c.get("row") or {}).get("price"),
                "pct_from_high": (c.get("row") or {}).get("pct_from_high"),
                "chg_5d": (c.get("row") or {}).get("chg_5d"),
                "category": (c.get("row") or {}).get("category"),
                "high_52w": (c.get("row") or {}).get("high_52w"),
            }
            for c in sorted(candidates, key=lambda x: float(x.get("score") or 0), reverse=True)
        ]
        log.info(
            "Quality dip scan complete",
            alerted=alerted,
            candidates=len(candidates),
        )

    async def _loop(self) -> None:
        settings = get_settings()
        interval = max(
            300.0,
            float(getattr(settings, "quality_dip_scan_interval_minutes", 60) or 60) * 60.0,
        )
        await asyncio.sleep(8)
        while self._running:
            try:
                await self._scan_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("Quality dip cycle failed", error=str(e))
            await asyncio.sleep(interval)


quality_dip_scanner = QualityDipScanner()