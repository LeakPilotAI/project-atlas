"""Perp micro coach v3.1 — quality paper + shadow research hooks. Thresholds unchanged."""

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


def _trend_from_closes(closes: List[float]) -> str:
    """1h close vs SMA20. UNKNOWN = no HTF data (do not freeze paper)."""
    sma = _sma(closes, 20)
    if sma is None or sma <= 0 or not closes or len(closes) < 20:
        return "UNKNOWN"
    last = float(closes[-1])
    if last > sma * 1.002:
        return "UP"
    if last < sma * 0.998:
        return "DOWN"
    return "FLAT"


def htf_allows_side(side: str, trend: str) -> bool:
    # Chop/unknown: 5m mean-rev is allowed. Only block fading a *directional* 1h.
    if trend in ("UNKNOWN", "OFF", "FLAT"):
        return True
    if side == "LONG":
        return trend == "UP"
    if side == "SHORT":
        return trend == "DOWN"
    return False


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


def _min_score_for_tier(tier: str) -> float:
    if tier == "major":
        return 62.0
    if tier == "alt":
        return 72.0
    if tier == "meme":
        return 82.0
    return 85.0


class PerpMicroCoach:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._manage_task: Optional[asyncio.Task] = None
        self._running = False
        self._liquid: List[str] = []
        self._open: Dict[str, Dict[str, Any]] = {}
        self.last_recovery: Dict[str, Any] = {}
        self._recovered_ids: Set[str] = set()
        self._triggers_today: int = 0
        self._day_key: str = ""
        self._cooldowns: Dict[str, datetime] = {}
        self._http: Optional[httpx.AsyncClient] = None
        self._vol_map: Dict[str, float] = {}
        self._oi_map: Dict[str, float] = {}
        self.last_major_tape: Dict[str, Dict[str, Any]] = {}
        self._htf_cache: Dict[str, Tuple[float, str]] = {}

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
        try:
            from app.services.paper_journal import paper_journal

            paper_journal.reload()
            self._rehydrate_open(reason="startup")
        except Exception as e:
            log.warning("startup paper rehydrate failed", error=str(e)[:200])
        self._task = asyncio.create_task(self._loop(), name="perp_micro_coach")
        self._manage_task = asyncio.create_task(self._manage_loop(), name="perp_micro_manage")
        log.info(
            "Perp micro coach started (v3.1 live-path)",
            all_markets=bool(settings.perp_micro_all_markets),
            max_open=int(settings.effective_max_open),
            max_triggers=int(settings.perp_micro_max_triggers_per_day),
            min_oi=float(settings.perp_micro_min_oi),
            min_vol=float(settings.perp_micro_min_vol),
            min_rr=float(settings.perp_micro_min_rr),
            scalp_tp_r=float(getattr(settings, "perp_micro_scalp_tp_r", 1.0)),
            be_after_r=float(getattr(settings, "perp_micro_be_after_r", 0.3)),
            lock_after_r=float(getattr(settings, "perp_micro_lock_after_r", 0.5)),
            lock_r=float(getattr(settings, "perp_micro_lock_r", 0.2)),
            manage_seconds=float(getattr(settings, "perp_micro_manage_seconds", 8.0)),
            scalp_enabled=bool(getattr(settings, "perp_micro_scalp_enabled", True)),
            rsi_long=float(settings.perp_micro_rsi_long),
            rsi_short=float(settings.perp_micro_rsi_short),
            paper=bool(settings.perp_micro_paper_enabled),
            live_min_trades=int(settings.perp_micro_live_min_trades),
            live_min_wr=float(settings.perp_micro_live_min_winrate),
            live_min_sum_r=float(settings.perp_micro_live_min_sum_r),
        )
        if int(settings.perp_micro_max_open) == 6:
            log.warning(
                "perp_micro_max_open is 6 (old default). Set PERP_MICRO_MAX_OPEN=0 in .env for unlimited paper."
            )

    async def stop(self) -> None:
        self._running = False
        for t in (self._task, self._manage_task):
            if t:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
        self._task = None
        self._manage_task = None
        if self._http is not None:
            try:
                await self._http.aclose()
            except Exception:
                pass
            self._http = None
        try:
            from app.services.paper_journal import paper_journal

            for tid, p in list(self._open.items()):
                mark = p.get("mark")
                if mark is None:
                    continue
                try:
                    paper_journal.update_excursion(tid, float(mark), force=True)
                except Exception:
                    pass
            paper_journal.flush()
        except Exception as e:
            log.warning("shutdown paper persist failed", error=str(e)[:200])
        log.info("Perp micro coach stopped")

    @staticmethod
    def _row_from_journal(row: Dict[str, Any]) -> Dict[str, Any]:
        def _fx(*keys: str, default: float = 0.0) -> float:
            for k in keys:
                if k in row and row[k] is not None:
                    try:
                        return float(row[k])
                    except (TypeError, ValueError):
                        continue
            return default

        entry = _fx("actual_entry_price", "entry")
        stop = _fx("stop_price", "stop")
        tp1 = _fx("tp1_price", "tp1")
        tp2 = _fx("tp2_price", "tp2")
        mark = _fx("mark", default=entry)
        side = str(row.get("side") or "").upper()
        incomplete = (
            not str(row.get("symbol") or "").strip()
            or side not in ("LONG", "SHORT")
            or entry <= 0
            or stop <= 0
        )
        return {
            "symbol": str(row.get("symbol") or "").upper(),
            "side": side,
            "entry": entry,
            "stop": stop,
            "tp1": tp1,
            "tp2": tp2,
            "mark": mark if mark > 0 else entry,
            "trade_id": row.get("trade_id"),
            "tier": row.get("tier") or "alt",
            "counts_for_live": bool(row.get("counts_for_live")),
            "qscore": _fx("signal_score"),
            "mfe_r": _fx("mfe_r"),
            "mae_r": _fx("mae_r"),
            "opened_at": row.get("entry_timestamp") or row.get("opened_at"),
            "risk_price": _fx("risk_price", default=abs(entry - stop) or 1e-12),
            "lifecycle": "ERROR_REQUIRES_REVIEW" if incomplete else "RECOVERY_PENDING",
            "stale_quote": False,
            "error": "incomplete open row" if incomplete else None,
            "exit_mode": str(row.get("exit_mode") or "SCALP"),
            "scalp_tp_r": _fx("scalp_tp_r", default=0.0),
            "be_after_r": row.get("be_after_r"),
            "lock_after_r": row.get("lock_after_r"),
            "lock_r": row.get("lock_r"),
            "lock_armed": bool(row.get("lock_armed")),
            "initial_stop": _fx("initial_stop", "stop_price", "stop", default=stop),
            "working_stop": _fx("working_stop", default=stop),
            "be_armed": bool(row.get("be_armed")),
            "setup_rr": _fx("setup_rr", default=1.8),
        }

    def _rehydrate_open(self, reason: str = "cycle") -> int:
        from app.services.paper_journal import paper_journal
        if reason == "startup":
            paper_journal.reload()
        else:
            paper_journal.reconcile_from_disk()
        added = 0
        failed: List[Dict[str, Any]] = []
        review: List[Dict[str, Any]] = []
        for row in paper_journal.list_open():
            tid = row.get("trade_id")
            if not tid:
                failed.append({"reason": "missing trade_id", "row_symbol": row.get("symbol")})
                continue
            if tid in self._open:
                continue
            try:
                mapped = self._row_from_journal(row)
                if mapped.get("lifecycle") == "ERROR_REQUIRES_REVIEW":
                    review.append({"trade_id": tid, "reason": mapped.get("error") or "incomplete open row"})
                    self._open[tid] = mapped
                    self._recovered_ids.add(str(tid))
                    added += 1
                    continue
                mapped["lifecycle"] = "RECOVERY_PENDING"
                self._prepare_exit_levels(mapped)
                self._open[tid] = mapped
                self._recovered_ids.add(str(tid))
                added += 1
            except Exception as e:
                failed.append({"trade_id": tid, "reason": str(e)[:160]})
                self._open[tid] = {
                    "symbol": str(row.get("symbol") or "").upper(),
                    "side": str(row.get("side") or "").upper(),
                    "entry": 0.0,
                    "stop": 0.0,
                    "tp1": 0.0,
                    "tp2": 0.0,
                    "mark": 0.0,
                    "trade_id": tid,
                    "lifecycle": "ERROR_REQUIRES_REVIEW",
                    "stale_quote": False,
                    "error": str(e)[:160],
                    "opened_at": row.get("entry_timestamp"),
                    "mfe_r": row.get("mfe_r") or 0,
                    "mae_r": row.get("mae_r") or 0,
                }
        live_ids = {r.get("trade_id") for r in paper_journal.list_open()}
        for tid in list(self._open):
            if tid not in live_ids:
                self._open.pop(tid, None)
        jr = paper_journal.recovery_report()
        self.last_recovery = {
            "title": "ATLAS PAPER RECOVERY",
            "reason": reason,
            "persisted_open": jr["persisted_open"],
            "recovered": len(self._open),
            "added_this_pass": added,
            "already_closed": jr.get("already_closed") or 0,
            "malformed": jr["malformed"],
            "malformed_lines": jr.get("malformed_lines") or [],
            "duplicates": jr.get("duplicates") or 0,
            "failed": failed,
            "error_requires_review": review + failed,
            "management_resumed": sum(1 for p in self._open.values() if p.get("lifecycle") != "ERROR_REQUIRES_REVIEW"),
            "recovered_ids": sorted(str(x) for x in self._open),
            "note": "OPEN ≠ hung. MARKET_DATA_UNAVAILABLE ≠ CLOSED. No invented exits.",
        }
        return added

    async def list_open_papers(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for tid, p in self._open.items():
            mark = float(p.get("mark") or p.get("entry") or 0)
            entry = float(p["entry"])
            risk = abs(entry - float(p.get("initial_stop") or p.get("stop") or entry)) or 1e-12
            side = p["side"]
            ur = (mark - entry) / risk if side == "LONG" else (entry - mark) / risk
            out.append({
                "id": tid,
                "symbol": p["symbol"],
                "side": side,
                "tier": p.get("tier", "alt"),
                "entry": entry,
                "stop": p.get("working_stop") or p.get("stop"),
                "initial_stop": p.get("initial_stop") or p.get("stop"),
                "tp1": p.get("tp1"),
                "be_armed": bool(p.get("be_armed")),
                "exit_mode": p.get("exit_mode") or "SCALP",
                "mark": mark,
                "unrealized_r": round(ur, 2),
                "counts_for_live": p.get("counts_for_live", True),
                "mfe_r": p.get("mfe_r", 0),
                "mae_r": p.get("mae_r", 0),
                "stale_quote": bool(p.get("stale_quote")),
                "lifecycle": p.get("lifecycle") or "OPEN",
                "opened_at": p.get("opened_at"),
                "recovered": str(tid) in self._recovered_ids,
            })
        return out

    def lifecycle_snapshot(self) -> Dict[str, Any]:
        opens = list(self._open.values())
        missing_px = sum(1 for p in opens if p.get("stale_quote") or p.get("lifecycle") == "MARKET_DATA_UNAVAILABLE")
        review_n = sum(1 for p in opens if p.get("lifecycle") == "ERROR_REQUIRES_REVIEW")
        rec = dict(self.last_recovery or {})
        rec.update({
            "currently_open": len(opens),
            "recovered_positions": len(self._recovered_ids & {str(t) for t in self._open}),
            "orphan_candidates": missing_px,
            "positions_missing_market_data": missing_px,
            "positions_missing_state": review_n,
            "error_requires_review": review_n,
            "note": "OPEN ≠ hung. MARKET_DATA_UNAVAILABLE ≠ CLOSED. Only CLOSED counts for performance.",
        })
        return rec

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
            "message": "LIVE READY (manual only)" if ready else f"Not live-ready: {closed}/{min_n} trades, WR {wr * 100:.1f}% (need {min_wr * 100:.0f}%), sum R {sum_r:+.2f} (need ≥ {min_sum}).",
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

    async def _manage_loop(self) -> None:
        await asyncio.sleep(4)
        while self._running:
            try:
                tickers = await self._fetch_tickers()
                price_map: Dict[str, float] = {}
                for raw in tickers or []:
                    t = _to_dict(raw)
                    s = _sym(t)
                    if s:
                        px = _f(t, "price", "markPx", "midPx", "mark_px", "mid", "last")
                        if px > 0:
                            price_map[s] = px
                if price_map:
                    await self._manage_open(price_map)
                    try:
                        from app.services.v4_shadow_bridge import mirror_price_map
                        mirror_price_map(price_map)
                    except Exception:
                        pass
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("paper manage loop error", error=str(e)[:160])
            settings = get_settings()
            await asyncio.sleep(float(getattr(settings, "perp_micro_manage_seconds", 8.0) or 8.0))

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
                return data
        except Exception as e:
            log.warning("cache ticker path failed", error=str(e)[:200])
        return []

    async def _fetch_closes(self, symbol: str, n: int = 48, interval: str = "5m") -> List[float]:
        client = self._http or httpx.AsyncClient(timeout=25.0)
        owned = self._http is None
        try:
            end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            bar_ms = 5 * 60 * 1000 if interval == "5m" else 60 * 60 * 1000
            start_ms = end_ms - n * bar_ms
            r = await client.post(HL_INFO_URL, json={"type": "candleSnapshot", "req": {"coin": symbol, "interval": interval, "startTime": start_ms, "endTime": end_ms}})
            if r.status_code == 429:
                await asyncio.sleep(2.0)
                return []
            r.raise_for_status()
            rows = r.json()
            closes: List[float] = []
            for c in rows or []:
                if isinstance(c, dict):
                    closes.append(_f(c, "c", "close"))
            return [x for x in closes if x > 0]
        except Exception:
            return []
        finally:
            if owned:
                try:
                    await client.aclose()
                except Exception:
                    pass

    async def htf_trend(self, symbol: str) -> str:
        now = datetime.now(timezone.utc).timestamp()
        hit = self._htf_cache.get(symbol)
        if hit and now - float(hit[0]) < 900:
            return str(hit[1])
        closes = await self._fetch_closes(symbol, 48, interval="1h")
        trend = _trend_from_closes(closes)
        self._htf_cache[symbol] = (now, trend)
        return trend

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
        return [s for s, _, _ in ranked][:80]

    def _setup_quality(self, symbol: str, side: str, price: float, closes: List[float], rsi: float, sma20: float, ext_pct: float, hard_gates: bool = True) -> Tuple[bool, float, str]:
        settings = get_settings()
        tier = _tier(symbol, set(settings.perp_micro_majors_list))
        atr = _atr_proxy(closes, 14)
        ema21 = _ema(closes, 21)
        ema50 = _ema(closes, 50) if len(closes) >= 50 else ema21
        score = 40.0
        reasons: List[str] = []
        vol = self._vol_map.get(symbol, 0.0)
        oi = self._oi_map.get(symbol, 0.0)
        if side == "LONG":
            if rsi <= 20:
                score += 18; reasons.append("RSI deep OS")
            elif rsi <= float(settings.perp_micro_rsi_long):
                score += 10; reasons.append("RSI OS")
            elif hard_gates:
                return False, 0.0, "RSI not low enough"
        else:
            if rsi >= 80:
                score += 18; reasons.append("RSI deep OB")
            elif rsi >= float(settings.perp_micro_rsi_short):
                score += 10; reasons.append("RSI OB")
            elif hard_gates:
                return False, 0.0, "RSI not high enough"
        if ext_pct >= float(settings.perp_micro_min_extension_pct) + 0.8:
            score += 12
        elif ext_pct >= float(settings.perp_micro_min_extension_pct):
            score += 6
        elif hard_gates:
            return False, 0.0, "extension too small"
        recent = sum(closes[-5:]) / 5
        prior = sum(closes[-10:-5]) / 5
        if side == "LONG" and recent < prior * 0.995:
            score += 10
        elif side == "SHORT" and recent > prior * 1.005:
            score += 10
        else:
            score -= 8
        if ema21 and ema50:
            up = ema21 > ema50
            if side == "LONG" and not up:
                score += 8
            elif side == "SHORT" and up:
                score += 8
            elif tier != "major":
                score -= 6
        if vol >= 5_000_000:
            score += 10
        elif vol >= 1_000_000:
            score += 5
        if oi >= 5_000_000:
            score += 8
        elif oi >= 500_000:
            score += 3
        if tier == "major":
            score += 10
        elif tier == "alt":
            score += 4
        if price > 0 and (atr / price) < 0.0015 and hard_gates:
            return False, score, "ATR too tight / dead"
        return score >= _min_score_for_tier(tier), score, ", ".join(reasons) if reasons else "n/a"

    async def _cycle(self) -> None:
        from app.services.micro_heartbeat import micro_heartbeat
        self._roll_day()
        settings = get_settings()
        self._rehydrate_open(reason="cycle")
        tickers = await self._fetch_tickers()
        self._liquid = self._build_liquid(tickers) if tickers else []
        price_map: Dict[str, float] = {}
        for raw in tickers or []:
            t = _to_dict(raw)
            s = _sym(t)
            if s:
                px = _f(t, "price", "markPx", "midPx", "mark_px", "mid", "last")
                if px > 0:
                    price_map[s] = px
        await self._manage_open(price_map)
        try:
            from app.services.v4_shadow_bridge import mirror_price_map
            mirror_price_map(price_map)
        except Exception:
            pass
        max_open = int(settings.effective_max_open)
        max_day = int(settings.perp_micro_max_triggers_per_day)
        if not settings.perp_micro_paper_enabled or not self._liquid or len(self._open) >= max_open or self._triggers_today >= max_day:
            micro_heartbeat.record_scan()
            return
        open_syms = {p["symbol"] for p in self._open.values()}
        now = datetime.now(timezone.utc)
        for sym in self._liquid:
            if len(self._open) >= max_open or self._triggers_today >= max_day:
                break
            if sym in open_syms:
                continue
            cd = self._cooldowns.get(sym)
            if cd and (now - cd).total_seconds() < 1800:
                continue
            try:
                if await self._try_symbol(sym, price_map.get(sym, 0.0)):
                    self._triggers_today += 1
                    micro_heartbeat.record_trigger()
            except Exception as e:
                log.debug("symbol eval fail", symbol=sym, error=str(e))
        micro_heartbeat.record_scan()

    async def _try_symbol(self, symbol: str, price: float) -> bool:
        from app.services.paper_journal import paper_journal
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
        if ext_pct < float(settings.perp_micro_min_extension_pct) or ext_pct > float(getattr(settings, "perp_micro_max_extension_pct", 3.5)):
            return False
        side: Optional[str] = None
        if rsi <= float(settings.perp_micro_rsi_long):
            side = "LONG"
        elif rsi >= float(settings.perp_micro_rsi_short):
            side = "SHORT"
        if side is None:
            return False
        if bool(getattr(settings, "perp_micro_htf_align", True)):
            trend = await self.htf_trend(symbol)
            if not htf_allows_side(side, trend):
                return False
        ok, qscore, reason = self._setup_quality(symbol, side, price, closes, rsi, sma20, ext_pct)
        if not ok:
            return False
        tier = _tier(symbol, set(settings.perp_micro_majors_list))
        if tier in ("junk", "meme"):
            return False
        atr = _atr_proxy(closes, 14)
        min_rr = float(settings.perp_micro_min_rr)
        scalp_r = float(getattr(settings, "perp_micro_scalp_tp_r", 1.0) or 1.0)
        be_after = float(getattr(settings, "perp_micro_be_after_r", 0.3) or 0.0)
        lock_after = float(getattr(settings, "perp_micro_lock_after_r", 0.5) or 0.0)
        lock_r = float(getattr(settings, "perp_micro_lock_r", 0.2) or 0.0)
        scalp_on = bool(getattr(settings, "perp_micro_scalp_enabled", True))
        if side == "LONG":
            stop = price - 1.5 * atr
            risk = abs(price - stop)
            setup_tp = price + min_rr * risk
            tp1 = (price + scalp_r * risk) if scalp_on else setup_tp
        else:
            stop = price + 1.5 * atr
            risk = abs(price - stop)
            setup_tp = price - min_rr * risk
            tp1 = (price - scalp_r * risk) if scalp_on else setup_tp
        if risk <= 0:
            return False
        tid = await paper_journal.open_trade(
            symbol=symbol,
            side=side,
            entry=price,
            signal_price=price,
            stop=stop,
            tp1=tp1,
            tp2=setup_tp,
            risk_usd=float(settings.perp_micro_risk_usd),
            regime=f"rsi={rsi:.1f};q={qscore:.0f};{tier}",
            notes=f"ext={ext_pct:.2f}%|{reason}",
            source="perp_micro",
            strategy="rsi_extension_v1",
            signal_score=qscore,
            features={"rsi": rsi, "ext_pct": ext_pct, "atr": atr, "setup_rr": min_rr, "exit_mode": "SCALP" if scalp_on else "SETUP_18", "scalp_tp_r": scalp_r, "be_after_r": be_after, "lock_after_r": lock_after, "lock_r": lock_r},
            tier=tier,
            counts_for_live=True,
        )
        if not tid:
            return False
        self._open[tid] = {
            "symbol": symbol,
            "side": side,
            "entry": price,
            "stop": stop,
            "initial_stop": stop,
            "working_stop": stop,
            "tp1": tp1,
            "tp2": setup_tp,
            "mark": price,
            "trade_id": tid,
            "tier": tier,
            "counts_for_live": True,
            "qscore": qscore,
            "mfe_r": 0.0,
            "mae_r": 0.0,
            "exit_mode": "SCALP" if scalp_on else "SETUP_18",
            "scalp_tp_r": scalp_r,
            "be_after_r": be_after,
            "lock_after_r": lock_after,
            "lock_r": lock_r,
            "be_armed": False,
            "lock_armed": False,
            "setup_rr": min_rr,
            "risk_price": risk,
        }
        self._cooldowns[symbol] = datetime.now(timezone.utc)
        try:
            from app.services.v4_shadow_bridge import mirror_legacy_trade
            mirror_legacy_trade(
                trade_id=tid,
                symbol=symbol,
                side=side,
                price=price,
                stop=stop,
                setup_rr=min_rr,
                risk_usd=float(settings.perp_micro_risk_usd),
            )
        except Exception:
            pass
        return True

    def _prepare_exit_levels(self, p: Dict[str, Any]) -> None:
        entry = float(p.get("entry") or 0)
        side = str(p.get("side") or "").upper()
        initial_stop = float(p.get("initial_stop") or p.get("stop") or 0)
        p["initial_stop"] = initial_stop
        risk = abs(entry - initial_stop) or 1e-12
        p["risk_price"] = float(p.get("risk_price") or risk)
        if p.get("working_stop") is None:
            p["working_stop"] = initial_stop
        scalp_r = float(p.get("scalp_tp_r") or 1.0)
        if side == "LONG":
            p["tp1"] = entry + scalp_r * risk
        elif side == "SHORT":
            p["tp1"] = entry - scalp_r * risk

    async def _manage_open(self, price_map: Dict[str, float]) -> None:
        from app.services.paper_journal import paper_journal
        to_close: List[str] = []
        for tid, p in list(self._open.items()):
            try:
                if p.get("lifecycle") == "ERROR_REQUIRES_REVIEW":
                    continue
                sym = p["symbol"]
                px = price_map.get(sym)
                if px is None or px <= 0:
                    p["stale_quote"] = True
                    p["lifecycle"] = "MARKET_DATA_UNAVAILABLE"
                    continue
                mark = float(px)
                p["stale_quote"] = False
                p["lifecycle"] = "MANAGED"
                p["mark"] = mark
                paper_journal.update_excursion(tid, mark)
                jopen = paper_journal._open.get(tid, {})
                p["mfe_r"] = jopen.get("mfe_r", p.get("mfe_r", 0))
                p["mae_r"] = jopen.get("mae_r", p.get("mae_r", 0))
                self._prepare_exit_levels(p)
                side = p["side"]
                entry = float(p["entry"])
                initial_stop = float(p.get("initial_stop") or p.get("stop") or 0)
                risk = abs(entry - initial_stop) or 1e-12
                mfe = float(p.get("mfe_r") or 0)
                be_after = float(p.get("be_after_r") or 0.3)
                lock_after = float(p.get("lock_after_r") or 0.5)
                lock_r = float(p.get("lock_r") or 0.2)
                if not p.get("be_armed") and mfe >= be_after:
                    p["be_armed"] = True
                    p["working_stop"] = entry
                if mfe >= lock_after:
                    locked = entry + lock_r * risk if side == "LONG" else entry - lock_r * risk
                    p["working_stop"] = max(float(p.get("working_stop") or initial_stop), locked) if side == "LONG" else min(float(p.get("working_stop") or initial_stop), locked)
                    p["lock_armed"] = True
                working_stop = float(p.get("working_stop") or initial_stop)
                tp1 = float(p["tp1"])
                hit_stop = mark <= working_stop if side == "LONG" else mark >= working_stop
                hit_tp = mark >= tp1 if side == "LONG" else mark <= tp1
                if not hit_stop and not hit_tp:
                    continue
                if hit_stop:
                    stop_pnl = (working_stop - entry) / risk if side == "LONG" else (entry - working_stop) / risk
                    if stop_pnl >= 0.05:
                        result, exit_px, pnl_r = "LOCK", working_stop, stop_pnl
                    elif p.get("be_armed") or abs(stop_pnl) < 0.05:
                        result, exit_px, pnl_r = "BE", entry, 0.0
                    else:
                        result, exit_px, pnl_r = "STOP", initial_stop, -1.0
                else:
                    result, exit_px = "TP1", tp1
                    pnl_r = abs(tp1 - entry) / risk
                await paper_journal.close_trade(tid, exit_price=exit_px, result=result, pnl_r=pnl_r)
                p["lifecycle"] = "CLOSED"
                to_close.append(tid)
                self._cooldowns[sym] = datetime.now(timezone.utc)
            except Exception as e:
                p["lifecycle"] = "ERROR_REQUIRES_REVIEW"
                p["error"] = str(e)[:160]
        for tid in to_close:
            self._open.pop(tid, None)


perp_micro_coach = PerpMicroCoach()
