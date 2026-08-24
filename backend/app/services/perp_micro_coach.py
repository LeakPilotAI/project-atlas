"""Perp micro coach v3.1 — quality paper, strict live-path, rate-limit safe."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
import structlog

from app.core.config import get_settings

log = structlog.get_logger(__name__)

HL_INFO_URL = "https://api.hyperliquid.xyz/info"

MEME_BLOCK: Set[str] = {
    "FARTCOIN", "WIF", "PURR", "CASHCAT", "MYRO", "POPCAT", "MEW", "PNUT",
    "GOAT", "MOODENG", "GIGA", "SPX", "TREMP", "BOME", "SLERF", "MICHI",
    "MELANIA", "TRUMP", "MAGA", "DOGE2", "SHIB", "PEPE", "kPEPE", "BRETT",
    "NEIRO", "MOG", "TURBO", "FLOKI", "kFLOKI", "BONK", "WEN", "MEME",
    "BANANA", "ANIME", "NOT", "TNSR", "SOPH", "WCT", "RSR", "XPL",
}

LIVE_ALT_ALLOW: Set[str] = {
    "AAVE", "UNI", "MKR", "CRV", "LDO", "COMP", "SNX", "PENDLE",
    "NEAR", "APT", "ARB", "OP", "SUI", "SEI", "TIA", "INJ",
    "LINK", "DOT", "ATOM", "AVAX", "ADA", "LTC", "BCH", "XRP",
    "DOGE", "HYPE", "BNB",
}


def _rsi(closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    gains: List[float] = []
    losses: List[float] = []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    gains = gains[-period:]
    losses = losses[-period:]
    avg_g = sum(gains) / period
    avg_l = sum(losses) / period
    if avg_l <= 1e-12:
        return 100.0
    rs = avg_g / avg_l
    return 100.0 - (100.0 / (1.0 + rs))


def _sma(xs: List[float], n: int) -> Optional[float]:
    if len(xs) < n:
        return None
    return sum(xs[-n:]) / n


def _ema(xs: List[float], n: int) -> Optional[float]:
    if len(xs) < n:
        return None
    k = 2.0 / (n + 1)
    e = sum(xs[:n]) / n
    for x in xs[n:]:
        e = x * k + e * (1 - k)
    return e


def _atr_proxy(closes: List[float], n: int = 14) -> float:
    if len(closes) < n + 1:
        return abs(closes[-1] * 0.008) if closes else 0.0
    window = closes[-(n + 1) :]
    ranges = [abs(window[i] - window[i - 1]) for i in range(1, len(window))]
    return (sum(ranges) / len(ranges)) if ranges else abs(closes[-1] * 0.008)


def _f(d: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return default


def _sym(d: Dict[str, Any]) -> str:
    return str(d.get("symbol") or d.get("coin") or d.get("name") or "").upper()


def _to_dict(item: Any) -> Dict[str, Any]:
    if item is None:
        return {}
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        try:
            return dict(item.model_dump())
        except Exception:
            pass
    if hasattr(item, "dict"):
        try:
            return dict(item.dict())
        except Exception:
            pass
    if hasattr(item, "__dict__"):
        d = {k: v for k, v in vars(item).items() if not k.startswith("_")}
        if d:
            return d
    out: Dict[str, Any] = {}
    for k in (
        "symbol", "coin", "name", "price", "markPx", "midPx", "mark_px", "mid",
        "last", "volume_24h", "dayNtlVlm", "day_ntl_vlm", "volume24h", "vol24h",
        "volume", "open_interest", "openInterest", "open_interest_usd", "oi",
        "funding_rate", "funding",
    ):
        if hasattr(item, k):
            try:
                out[k] = getattr(item, k)
            except Exception:
                pass
    return out


def _tier(symbol: str, majors: Set[str]) -> str:
    if symbol in majors:
        return "major"
    if symbol in MEME_BLOCK:
        return "meme"
    if symbol in LIVE_ALT_ALLOW:
        return "alt"
    return "junk"


class PerpMicroCoach:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._liquid: List[str] = []
        self._open: Dict[str, Dict[str, Any]] = {}
        self._triggers_today: int = 0
        self._day_key: str = ""
        self._cooldowns: Dict[str, datetime] = {}
        self._http: Optional[httpx.AsyncClient] = None
        self._vol_map: Dict[str, float] = {}
        self._oi_map: Dict[str, float] = {}

    @property
    def running(self) -> bool:
        return self._running

    @property
    def liquid_count(self) -> int:
        return len(self._liquid)

    async def start(self) -> None:
        get_settings.cache_clear()
        settings = get_settings()
        if not bool(settings.perp_micro_enabled):
            log.info("Perp micro coach disabled")
            return
        if self._task and not self._task.done():
            return
        self._http = httpx.AsyncClient(timeout=25.0)
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="perp_micro_coach")
        log.info(
            "Perp micro coach started (v3.1 live-path)",
            all_markets=bool(settings.perp_micro_all_markets),
            max_open=int(settings.perp_micro_max_open),
            max_triggers=int(settings.perp_micro_max_triggers_per_day),
            min_oi=float(settings.perp_micro_min_oi),
            min_vol=float(settings.perp_micro_min_vol),
            min_rr=float(settings.perp_micro_min_rr),
            rsi_long=float(settings.perp_micro_rsi_long),
            rsi_short=float(settings.perp_micro_rsi_short),
            paper=bool(settings.perp_micro_paper_enabled),
            live_min_trades=int(settings.perp_micro_live_min_trades),
            live_min_wr=float(settings.perp_micro_live_min_winrate),
            live_min_sum_r=float(settings.perp_micro_live_min_sum_r),
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
        if self._http is not None:
            try:
                await self._http.aclose()
            except Exception:
                pass
            self._http = None
        log.info("Perp micro coach stopped")

    async def list_open_papers(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for tid, p in self._open.items():
            mark = float(p.get("mark") or p.get("entry") or 0)
            entry = float(p["entry"])
            stop = float(p.get("stop") or entry)
            risk = abs(entry - stop) or 1e-12
            side = p["side"]
            ur = (mark - entry) / risk if side == "LONG" else (entry - mark) / risk
            out.append(
                {
                    "id": tid,
                    "symbol": p["symbol"],
                    "side": side,
                    "tier": p.get("tier", "alt"),
                    "entry": entry,
                    "stop": p.get("stop"),
                    "tp1": p.get("tp1"),
                    "mark": mark,
                    "unrealized_r": round(ur, 2),
                    "counts_for_live": p.get("counts_for_live", True),
                }
            )
        return out

    async def paper_stats(self) -> Dict[str, Any]:
        from app.services.paper_journal import paper_journal

        base = await paper_journal.stats()
        base["live_readiness"] = await self.live_readiness()
        return base

    async def live_readiness(self) -> Dict[str, Any]:
        settings = get_settings()
        from app.services.paper_journal import paper_journal

        stats = await paper_journal.stats()
        wins = int(stats.get("wins") or stats.get("w") or 0)
        losses = int(stats.get("losses") or stats.get("l") or 0)
        closed = wins + losses
        sum_r = float(stats.get("sum_r") or stats.get("sum_R") or 0.0)
        wr = (wins / closed) if closed else 0.0
        min_n = int(settings.perp_micro_live_min_trades)
        min_wr = float(settings.perp_micro_live_min_winrate)
        min_sum = float(settings.perp_micro_live_min_sum_r)
        ready = closed >= min_n and wr >= min_wr and sum_r >= min_sum
        return {
            "ready": ready,
            "closed": closed,
            "wins": wins,
            "losses": losses,
            "winrate": round(wr, 4),
            "sum_r": round(sum_r, 2),
            "need_trades": max(0, min_n - closed),
            "need_winrate": min_wr,
            "need_sum_r": min_sum,
            "message": (
                "LIVE READY (manual only)"
                if ready
                else (
                    f"Not live-ready: {closed}/{min_n} trades, "
                    f"WR {wr * 100:.1f}% (need {min_wr * 100:.0f}%), "
                    f"sum R {sum_r:+.2f} (need ≥ {min_sum})."
                )
            ),
        }

    async def _loop(self) -> None:
        await asyncio.sleep(8)
        while self._running:
            try:
                await self._cycle()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("Perp micro cycle error", error=str(e), exc_info=True)
                await asyncio.sleep(20)
            settings = get_settings()
            await asyncio.sleep(float(settings.perp_micro_scan_seconds or 90))

    def _roll_day(self) -> None:
        key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if key != self._day_key:
            self._day_key = key
            self._triggers_today = 0

    async def _fetch_tickers(self) -> List[Any]:
        try:
            from app.adapters.hyperliquid_cache import get_tickers_cached

            data = await get_tickers_cached()
            if data:
                log.info(
                    "Micro coach tickers via cache",
                    count=len(data),
                    first_type=type(data[0]).__name__,
                )
                return data
        except Exception as e:
            log.warning("cache ticker path failed", error=str(e)[:200])
        return await self._fetch_tickers_direct_hl()

    async def _fetch_tickers_direct_hl(self) -> List[Dict[str, Any]]:
        try:
            from app.adapters.hyperliquid_cache import get_tickers_cached

            return await get_tickers_cached(force=True)
        except Exception:
            return []

    async def _fetch_closes(self, symbol: str, n: int = 48) -> List[float]:
        client = self._http or httpx.AsyncClient(timeout=25.0)
        owned = self._http is None
        try:
            end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            start_ms = end_ms - n * 5 * 60 * 1000
            r = await client.post(
                HL_INFO_URL,
                json={
                    "type": "candleSnapshot",
                    "req": {
                        "coin": symbol,
                        "interval": "5m",
                        "startTime": start_ms,
                        "endTime": end_ms,
                    },
                },
            )
            if r.status_code == 429:
                log.warning("candle 429", symbol=symbol)
                await asyncio.sleep(2.0)
                return []
            r.raise_for_status()
            rows = r.json()
            closes: List[float] = []
            for c in rows or []:
                if isinstance(c, dict):
                    closes.append(_f(c, "c", "close"))
            return [x for x in closes if x > 0]
        except Exception as e:
            log.debug("candle fail", symbol=symbol, error=str(e)[:120])
            return []
        finally:
            if owned:
                try:
                    await client.aclose()
                except Exception:
                    pass

    def _build_liquid(self, tickers: List[Any]) -> List[str]:
        settings = get_settings()
        min_vol = float(settings.perp_micro_min_vol)
        min_oi = float(settings.perp_micro_min_oi)
        majors = set(settings.perp_micro_majors_list)
        ranked: List[Tuple[str, float, str]] = []
        self._vol_map.clear()
        self._oi_map.clear()

        for raw in tickers:
            t = _to_dict(raw)
            if not t:
                continue
            sym = _sym(t)
            if not sym:
                continue
            vol = _f(t, "volume_24h", "dayNtlVlm", "day_ntl_vlm", "volume24h", "vol24h", "volume")
            oi = _f(t, "open_interest", "openInterest", "open_interest_usd", "oi")
            px = _f(t, "price", "markPx", "midPx", "mark_px", "mid", "last")
            if 0 < oi < min_oi and px > 0 and oi * px >= min_oi * 0.2:
                oi = oi * px
            self._vol_map[sym] = vol
            self._oi_map[sym] = oi
            if vol < min_vol or oi < min_oi:
                continue
            tier = _tier(sym, majors)
            if settings.perp_micro_prefer_majors and tier == "meme" and vol < min_vol * 4:
                continue
            if tier == "junk" and vol < min_vol * 5:
                continue
            ranked.append((sym, vol, tier))

        tier_rank = {"major": 0, "alt": 1, "meme": 2, "junk": 3}
        ranked.sort(key=lambda x: (tier_rank.get(x[2], 9), -x[1]))
        symbols = [s for s, _, _ in ranked]
        if not symbols:
            soft: List[Tuple[str, float]] = []
            for raw in tickers:
                t = _to_dict(raw)
                sym = _sym(t)
                vol = _f(t, "volume_24h", "dayNtlVlm", "volume24h", "volume")
                if sym and vol >= max(50_000.0, min_vol * 0.05):
                    soft.append((sym, vol))
            soft.sort(key=lambda x: -x[1])
            symbols = [s for s, _ in soft][:60]
            log.warning("Liquid set soft fallback", soft_count=len(symbols))
        return symbols[:80]

    def _setup_quality(
        self,
        symbol: str,
        side: str,
        price: float,
        closes: List[float],
        rsi: float,
        sma20: float,
        ext_pct: float,
    ) -> Tuple[bool, float, str]:
        settings = get_settings()
        majors = set(settings.perp_micro_majors_list)
        tier = _tier(symbol, majors)
        atr = _atr_proxy(closes, 14)
        ema21 = _ema(closes, 21)
        ema50 = _ema(closes, 50) if len(closes) >= 50 else ema21

        score = 40.0
        reasons: List[str] = []
        vol = self._vol_map.get(symbol, 0.0)
        oi = self._oi_map.get(symbol, 0.0)

        if side == "LONG":
            if rsi <= 20:
                score += 18
                reasons.append("RSI deep OS")
            elif rsi <= float(settings.perp_micro_rsi_long):
                score += 10
                reasons.append("RSI OS")
            else:
                return False, 0.0, "RSI not low enough"
        else:
            if rsi >= 80:
                score += 18
                reasons.append("RSI deep OB")
            elif rsi >= float(settings.perp_micro_rsi_short):
                score += 10
                reasons.append("RSI OB")
            else:
                return False, 0.0, "RSI not high enough"

        if ext_pct >= float(settings.perp_micro_min_extension_pct) + 0.8:
            score += 12
            reasons.append("strong ext")
        elif ext_pct >= float(settings.perp_micro_min_extension_pct):
            score += 6
            reasons.append("ext ok")
        else:
            return False, 0.0, "extension too small"

        recent = sum(closes[-5:]) / 5
        prior = sum(closes[-10:-5]) / 5
        if side == "LONG" and recent < prior * 0.995:
            score += 10
            reasons.append("dump structure")
        elif side == "SHORT" and recent > prior * 1.005:
            score += 10
            reasons.append("rip structure")
        else:
            score -= 8
            reasons.append("weak structure")

        if ema21 and ema50:
            up = ema21 > ema50
            if side == "LONG" and not up:
                score += 8
                reasons.append("against short EMA stack")
            elif side == "SHORT" and up:
                score += 8
                reasons.append("against long EMA stack")
            elif tier == "major":
                score += 2
            else:
                score -= 6
                reasons.append("with-trend exhaustion only")

        if vol >= 5_000_000:
            score += 10
            reasons.append("high vol")
        elif vol >= 1_000_000:
            score += 5
        if oi >= 5_000_000:
            score += 8
            reasons.append("high OI")
        elif oi >= 500_000:
            score += 3

        if tier == "major":
            score += 10
            min_score = 62.0
        elif tier == "alt":
            score += 4
            min_score = 72.0
            if vol < 500_000 or oi < 200_000:
                return False, score, "alt liquidity too low"
        elif tier == "meme":
            min_score = 82.0
        else:
            min_score = 85.0
            if vol < 1_000_000:
                return False, score, "junk / thin tape"

        if price > 0 and (atr / price) < 0.0015:
            return False, score, "ATR too tight / dead"
        if price > 0 and (atr / price) > 0.06 and tier != "major":
            score -= 10
            reasons.append("wild ATR")

        ok = score >= min_score
        return ok, score, ", ".join(reasons) if reasons else "n/a"

    async def _cycle(self) -> None:
        from app.services.micro_heartbeat import micro_heartbeat

        self._roll_day()
        settings = get_settings()
        tickers = await self._fetch_tickers()
        log.info("Micro coach tickers", count=len(tickers))

        if tickers:
            self._liquid = self._build_liquid(tickers)
            log.info("Liquid tradable set", count=len(self._liquid), sample=self._liquid[:8])
        else:
            log.warning("Micro coach got 0 tickers")

        price_map: Dict[str, float] = {}
        for raw in tickers or []:
            t = _to_dict(raw)
            s = _sym(t)
            if s:
                price_map[s] = _f(t, "price", "markPx", "midPx", "mark_px", "mid", "last")

        await self._manage_open(price_map)

        max_open = int(settings.perp_micro_max_open)
        max_day = int(settings.perp_micro_max_triggers_per_day)

        if not settings.perp_micro_paper_enabled or not self._liquid:
            micro_heartbeat.record_scan()
            return
        if len(self._open) >= max_open:
            micro_heartbeat.record_scan()
            return
        if self._triggers_today >= max_day:
            micro_heartbeat.record_scan()
            return

        evaluated = 0
        for sym in self._liquid:
            if len(self._open) >= max_open or self._triggers_today >= max_day:
                break
            if sym in {p["symbol"] for p in self._open.values()}:
                continue
            cd = self._cooldowns.get(sym)
            if cd and (datetime.now(timezone.utc) - cd).total_seconds() < 5400:
                continue
            try:
                evaluated += 1
                if await self._try_symbol(sym, price_map.get(sym, 0.0)):
                    self._triggers_today += 1
                    micro_heartbeat.record_trigger()
            except Exception as e:
                log.debug("symbol eval fail", symbol=sym, error=str(e))
            if evaluated % 5 == 0:
                await asyncio.sleep(0.4)

        log.info(
            "Micro coach cycle done",
            liquid=len(self._liquid),
            evaluated=evaluated,
            open=len(self._open),
            triggers_today=self._triggers_today,
            max_open=max_open,
            max_day=max_day,
        )
        micro_heartbeat.record_scan()

    async def _try_symbol(self, symbol: str, price: float) -> bool:
        settings = get_settings()
        if price <= 0:
            return False
        closes = await self._fetch_closes(symbol, 48)
        if len(closes) < 25:
            return False
        closes[-1] = price

        rsi = _rsi(closes, 14)
        sma20 = _sma(closes, 20)
        if rsi is None or sma20 is None or sma20 <= 0:
            return False

        ext_pct = abs(price - sma20) / sma20 * 100.0
        if ext_pct < float(settings.perp_micro_min_extension_pct):
            return False

        side: Optional[str] = None
        if rsi <= float(settings.perp_micro_rsi_long):
            side = "LONG"
        elif rsi >= float(settings.perp_micro_rsi_short):
            side = "SHORT"
        if side is None:
            return False

        ok, qscore, reason = self._setup_quality(symbol, side, price, closes, rsi, sma20, ext_pct)
        if not ok:
            return False

        atr = _atr_proxy(closes, 14)
        if side == "LONG":
            stop = price - 1.5 * atr
            tp1 = price + 2.5 * atr
            tp2 = price + 4.0 * atr
        else:
            stop = price + 1.5 * atr
            tp1 = price - 2.5 * atr
            tp2 = price - 4.0 * atr

        risk = abs(price - stop)
        if risk <= 0:
            return False
        rr = abs(tp1 - price) / risk
        if rr < float(settings.perp_micro_min_rr):
            return False

        majors = set(settings.perp_micro_majors_list)
        tier = _tier(symbol, majors)
        counts_for_live = tier in ("major", "alt")

        from app.alerts.discord import is_discord_ready, send_discord_alert
        from app.services.paper_journal import paper_journal

        tid = await paper_journal.open_trade(
            symbol=symbol,
            side=side,
            entry=price,
            stop=stop,
            tp1=tp1,
            tp2=tp2,
            risk_usd=float(settings.perp_micro_risk_usd),
            regime=f"rsi={rsi:.1f};q={qscore:.0f};{tier}",
            notes=f"ext={ext_pct:.2f}%|{reason}|live={counts_for_live}",
            source="perp_micro",
        )
        self._open[tid] = {
            "symbol": symbol,
            "side": side,
            "entry": price,
            "stop": stop,
            "tp1": tp1,
            "tp2": tp2,
            "mark": price,
            "trade_id": tid,
            "tier": tier,
            "counts_for_live": counts_for_live,
            "qscore": qscore,
        }
        self._cooldowns[symbol] = datetime.now(timezone.utc)

        if is_discord_ready():
            live_tag = "live-stat" if counts_for_live else "experimental"
            await send_discord_alert(
                symbol=symbol,
                title=f"Paper TRIGGER · {symbol} · {side}",
                description=(
                    f"**{symbol} · {side}** (paper · {tier} · **{live_tag}**)\n"
                    f"Entry `{price}` · Stop `{stop:.6g}` · TP1 `{tp1:.6g}`\n"
                    f"RSI `{rsi:.1f}` · ext `{ext_pct:.2f}%` · R:R `{rr:.1f}` · Q `{qscore:.0f}`\n"
                    f"_{reason}_\n_Simulation only. No live execution._"
                ),
                price=price,
                severity="MEDIUM",
                opportunity=min(95, int(qscore)),
                confidence=min(90, int(50 + qscore / 3)),
                risk=45 if tier == "major" else (50 if tier == "alt" else 60),
            )
        log.info(
            "Paper TRIGGER",
            symbol=symbol,
            side=side,
            entry=price,
            trade_id=tid,
            tier=tier,
            qscore=qscore,
            counts_for_live=counts_for_live,
        )
        return True

    async def _manage_open(self, price_map: Dict[str, float]) -> None:
        from app.alerts.discord import is_discord_ready, send_discord_alert
        from app.services.paper_journal import paper_journal

        to_close: List[str] = []
        for tid, p in list(self._open.items()):
            sym = p["symbol"]
            mark = price_map.get(sym) or float(p.get("mark") or p["entry"])
            p["mark"] = mark
            side, entry = p["side"], float(p["entry"])
            stop, tp1 = float(p["stop"]), float(p["tp1"])
            risk = abs(entry - stop) or 1e-12
            hit_stop = mark <= stop if side == "LONG" else mark >= stop
            hit_tp = mark >= tp1 if side == "LONG" else mark <= tp1
            if not hit_stop and not hit_tp:
                continue
            if hit_stop:
                result, exit_px, pnl_r = "STOP", stop, -1.0
            else:
                result, exit_px = "TP1", tp1
                pnl_r = abs(tp1 - entry) / risk
            await paper_journal.close_trade(tid, exit_price=exit_px, result=result, pnl_r=pnl_r)
            to_close.append(tid)
            self._cooldowns[sym] = datetime.now(timezone.utc)
            if is_discord_ready():
                live_tag = "live-stat" if p.get("counts_for_live") else "experimental"
                await send_discord_alert(
                    symbol=sym,
                    title=f"Paper {result} · {sym} · {side}",
                    description=(
                        f"**{sym}** {side} closed **{result}**\n"
                        f"Entry `{entry}` → Exit `{exit_px:.6g}` · **{pnl_r:+.2f}R**\n"
                        f"Tier `{p.get('tier', '?')}` · **{live_tag}**\n_Paper only._"
                    ),
                    price=exit_px,
                    severity="LOW" if result == "TP1" else "MEDIUM",
                    opportunity=60,
                    confidence=60,
                    risk=40,
                )
            log.info("Paper CLOSE", trade_id=tid, symbol=sym, result=result, pnl_r=pnl_r)
        for tid in to_close:
            self._open.pop(tid, None)


perp_micro_coach = PerpMicroCoach()