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
        log.info(
            "Perp micro coach started (v3.1 live-path)",
            all_markets=bool(settings.perp_micro_all_markets),
            max_open=int(settings.effective_max_open),
            max_triggers=int(settings.perp_micro_max_triggers_per_day),
            min_oi=float(settings.perp_micro_min_oi),
            min_vol=float(settings.perp_micro_min_vol),
            min_rr=float(settings.perp_micro_min_rr),
            scalp_tp_r=float(getattr(settings, "perp_micro_scalp_tp_r", 1.0)),
            be_after_r=float(getattr(settings, "perp_micro_be_after_r", 0.5)),
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
            "initial_stop": _fx("initial_stop", "stop_price", "stop", default=stop),
            "working_stop": _fx("working_stop", default=stop),
            "be_armed": bool(row.get("be_armed")),
            "setup_rr": _fx("setup_rr", default=1.8),
        }

    def _rehydrate_open(self, reason: str = "cycle") -> int:
        """Journal is source of truth across restarts. Coach memory is not."""
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
            "management_resumed": sum(
                1 for p in self._open.values() if p.get("lifecycle") != "ERROR_REQUIRES_REVIEW"
            ),
            "recovered_ids": sorted(str(x) for x in self._open),
            "note": "OPEN ≠ hung. MARKET_DATA_UNAVAILABLE ≠ CLOSED. No invented exits.",
        }
        if added or failed or review or reason == "startup":
            log.info(
                "Rehydrated paper opens from journal",
                added=added,
                open=len(self._open),
                reason=reason,
                failed=len(failed),
                review=len(review),
            )
        return added

    async def list_open_papers(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for tid, p in self._open.items():
            mark = float(p.get("mark") or p.get("entry") or 0)
            entry = float(p["entry"])
            stop = float(p.get("working_stop") or p.get("initial_stop") or p.get("stop") or entry)
            risk = abs(entry - float(p.get("initial_stop") or p.get("stop") or entry)) or 1e-12
            side = p["side"]
            ur = (mark - entry) / risk if side == "LONG" else (entry - mark) / risk
            out.append(
                {
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
                }
            )
        return out

    def lifecycle_snapshot(self) -> Dict[str, Any]:
        from datetime import datetime, timezone as _tz

        now = datetime.now(_tz.utc)
        opens = list(self._open.values())
        ages = []
        oldest = None
        oldest_age = -1.0
        missing_px = 0
        for p in opens:
            ts = p.get("opened_at")
            age = None
            if ts:
                try:
                    t0 = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    age = (now - t0).total_seconds()
                    ages.append(age)
                    if age > oldest_age:
                        oldest_age = age
                        oldest = p.get("symbol")
                except Exception:
                    pass
            if p.get("stale_quote") or p.get("lifecycle") == "MARKET_DATA_UNAVAILABLE":
                missing_px += 1
        review_n = sum(1 for p in opens if p.get("lifecycle") == "ERROR_REQUIRES_REVIEW")
        rec = dict(self.last_recovery or {})
        rec.update(
            {
                "currently_open": len(opens),
                "recovered_positions": len(self._recovered_ids & {str(t) for t in self._open}),
                "orphan_candidates": missing_px,
                "positions_missing_market_data": missing_px,
                "positions_missing_state": review_n,
                "error_requires_review": review_n,
                "avg_age_sec": round(sum(ages) / len(ages), 1) if ages else None,
                "oldest_open_symbol": oldest,
                "oldest_open_age_sec": round(oldest_age, 1) if oldest_age >= 0 else None,
                "failed_recovery": rec.get("failed") or [],
                "note": "OPEN ≠ hung. MARKET_DATA_UNAVAILABLE ≠ CLOSED. Only CLOSED counts for performance.",
            }
        )
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
        pinned: List[str] = []
        seen = set(self._vol_map.keys()) | set(symbols)
        for m in settings.perp_micro_majors_list:
            if m in seen and m not in pinned:
                pinned.append(m)
        rest = [s for s in symbols if s not in pinned]
        return (pinned + rest)[:80]

    def _setup_quality(
        self,
        symbol: str,
        side: str,
        price: float,
        closes: List[float],
        rsi: float,
        sma20: float,
        ext_pct: float,
        hard_gates: bool = True,
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
                if hard_gates:
                    return False, 0.0, "RSI not low enough"
                reasons.append("RSI not OS")
        else:
            if rsi >= 80:
                score += 18
                reasons.append("RSI deep OB")
            elif rsi >= float(settings.perp_micro_rsi_short):
                score += 10
                reasons.append("RSI OB")
            else:
                if hard_gates:
                    return False, 0.0, "RSI not high enough"
                reasons.append("RSI not OB")

        if ext_pct >= float(settings.perp_micro_min_extension_pct) + 0.8:
            score += 12
            reasons.append("strong ext")
        elif ext_pct >= float(settings.perp_micro_min_extension_pct):
            score += 6
            reasons.append("ext ok")
        else:
            if hard_gates:
                return False, 0.0, "extension too small"
            reasons.append("extension too small")

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
                if hard_gates:
                    return False, score, "alt liquidity too low"
                reasons.append("alt liquidity too low")
        elif tier == "meme":
            min_score = 82.0
        else:
            min_score = 85.0
            if vol < 1_000_000:
                if hard_gates:
                    return False, score, "junk / thin tape"
                reasons.append("junk / thin tape")

        if price > 0 and (atr / price) < 0.0015:
            if hard_gates:
                return False, score, "ATR too tight / dead"
            reasons.append("ATR too tight / dead")
            score -= 8
        if price > 0 and (atr / price) > 0.06 and tier != "major":
            score -= 10
            reasons.append("wild ATR")

        ok = score >= min_score
        return ok, score, ", ".join(reasons) if reasons else "n/a"

    async def _cycle(self) -> None:
        from app.services.micro_heartbeat import micro_heartbeat

        self._roll_day()
        settings = get_settings()
        self._rehydrate_open(reason="cycle")
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
                px = _f(t, "price", "markPx", "midPx", "mark_px", "mid", "last")
                if px > 0:
                    price_map[s] = px

        await self._manage_open(price_map)

        # Shadow research (never affects paper)
        try:
            from app.services.shadow_research import shadow_research

            shadow_research.update_prices(price_map)
        except Exception as e:
            log.debug("shadow update failed", error=str(e)[:120])

        max_open = int(settings.effective_max_open)
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
        open_syms = {p["symbol"] for p in self._open.values()}
        now = datetime.now(timezone.utc)
        for sym in self._liquid:
            if len(self._open) >= max_open or self._triggers_today >= max_day:
                break
            if sym in open_syms:
                try:
                    from app.services.paper_pipeline import paper_pipeline

                    paper_pipeline.inc("skip_already_open")
                except Exception:
                    pass
                continue
            cd = self._cooldowns.get(sym)
            if cd and (now - cd).total_seconds() < 5400:
                try:
                    from app.services.paper_pipeline import paper_pipeline

                    paper_pipeline.inc("skip_cooldown")
                except Exception:
                    pass
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
        from app.services.paper_journal import paper_journal
        from app.services.paper_pipeline import paper_pipeline
        from app.services.shadow_research import shadow_research

        settings = get_settings()
        if price <= 0:
            paper_pipeline.inc_reject("NO_PRICE")
            return False
        closes = await self._fetch_closes(symbol, 48)
        if len(closes) < 25:
            paper_pipeline.inc("candle_fail")
            return False
        closes[-1] = price
        paper_pipeline.inc("candle_success")
        paper_pipeline.last_candle_ok_at = datetime.now(timezone.utc).isoformat()

        rsi = _rsi(closes, 14)
        sma20 = _sma(closes, 20)
        if rsi is None or sma20 is None or sma20 <= 0:
            paper_pipeline.inc("candle_fail")
            return False

        ext_pct = abs(price - sma20) / sma20 * 100.0
        majors = set(settings.perp_micro_majors_list)
        if symbol in majors:
            side_hint = (
                "LONG"
                if rsi <= float(settings.perp_micro_rsi_long)
                else ("SHORT" if rsi >= float(settings.perp_micro_rsi_short) else None)
            )
            blocked = None
            if ext_pct < float(settings.perp_micro_min_extension_pct):
                blocked = "extension"
            elif side_hint is None:
                blocked = "rsi"
            self.last_major_tape[symbol] = {
                "symbol": symbol,
                "price": price,
                "rsi": round(float(rsi), 2),
                "ext_pct": round(float(ext_pct), 3),
                "side": side_hint,
                "blocked": blocked,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        if ext_pct < float(settings.perp_micro_min_extension_pct):
            paper_pipeline.inc_reject("EXTENSION_TOO_SMALL")
            shadow_research.record_evaluation(
                symbol=symbol,
                side=None,
                mark_price=price,
                score=0.0,
                required_score=62.0,
                qualified=False,
                failed_gates=["extension_too_small"],
                features={"ext_pct": ext_pct, "sma20": sma20, "rsi": rsi},
                regime=f"rsi={rsi:.1f}",
                notes="pre-side filter",
            )
            return False
        paper_pipeline.inc("extension_pass")

        side: Optional[str] = None
        if rsi <= float(settings.perp_micro_rsi_long):
            side = "LONG"
        elif rsi >= float(settings.perp_micro_rsi_short):
            side = "SHORT"
        if side is None:
            paper_pipeline.inc_reject("RSI_NOT_EXTREME")
            shadow_research.record_evaluation(
                symbol=symbol,
                side=None,
                mark_price=price,
                score=float(rsi),
                required_score=float(settings.perp_micro_rsi_long),
                qualified=False,
                failed_gates=["rsi_not_extreme"],
                features={"rsi": rsi, "ext_pct": ext_pct, "sma20": sma20},
                regime=f"rsi={rsi:.1f}",
            )
            return False
        paper_pipeline.inc("rsi_extreme")
        paper_pipeline.inc("long_candidates" if side == "LONG" else "short_candidates")

        ok, qscore, reason = self._setup_quality(
            symbol, side, price, closes, rsi, sma20, ext_pct
        )
        majors = set(settings.perp_micro_majors_list)
        tier = _tier(symbol, majors)
        min_score = _min_score_for_tier(tier)
        atr = _atr_proxy(closes, 14)
        paper_pipeline.inc("quality_evaluated")

        if not ok:
            failed: List[str] = []
            if qscore < min_score:
                failed.append("score_threshold")
                paper_pipeline.inc("rejected_score")
            if "RSI" in reason:
                failed.append("rsi_gate")
            if "extension" in reason.lower() or "ext" in reason.lower():
                failed.append("extension")
            if any(x in reason.lower() for x in ("liquidity", "thin", "junk")):
                failed.append("liquidity")
                paper_pipeline.inc("rejected_liquidity")
            if "ATR" in reason or "atr" in reason:
                failed.append("risk_atr")
                paper_pipeline.inc("rejected_atr")
            if "structure" in reason.lower():
                failed.append("structure")
            if not failed:
                failed.append("quality")
            paper_pipeline.inc_reject(failed[0].upper() if failed else "QUALITY")

            await paper_journal.log_candidate(
                symbol=symbol,
                side=side,
                taken=False,
                signal_price=price,
                score=qscore,
                regime=f"rsi={rsi:.1f}",
                features={"rsi": rsi, "ext_pct": ext_pct, "sma20": sma20},
                reject_reason=reason,
                strategy="rsi_extension_v1",
            )
            shadow_research.record_evaluation(
                symbol=symbol,
                side=side,
                mark_price=price,
                score=qscore,
                required_score=min_score,
                qualified=False,
                failed_gates=failed,
                features={
                    "rsi": rsi,
                    "ext_pct": ext_pct,
                    "sma20": sma20,
                    "atr": atr,
                    "vol": self._vol_map.get(symbol),
                    "oi": self._oi_map.get(symbol),
                    "tier": tier,
                    "reason": reason,
                },
                regime=f"rsi={rsi:.1f};{tier}",
                stop=(price - 1.5 * atr) if side == "LONG" else (price + 1.5 * atr),
                tp1=(price + 1.8 * 1.5 * atr) if side == "LONG" else (price - 1.8 * 1.5 * atr),
                tp2=(price + 3.0 * 1.5 * atr) if side == "LONG" else (price - 3.0 * 1.5 * atr),
                notes=reason,
            )
            return False
        paper_pipeline.inc("quality_pass")

        min_rr = float(settings.perp_micro_min_rr)
        scalp_r = float(getattr(settings, "perp_micro_scalp_tp_r", 1.0) or 1.0)
        be_after = float(getattr(settings, "perp_micro_be_after_r", 0.5) or 0.0)
        scalp_on = bool(getattr(settings, "perp_micro_scalp_enabled", True))
        if side == "LONG":
            stop = price - 1.5 * atr
            risk = abs(price - stop)
            setup_tp = price + min_rr * risk
            tp1 = (price + scalp_r * risk) if scalp_on else setup_tp
            tp2 = setup_tp
        else:
            stop = price + 1.5 * atr
            risk = abs(price - stop)
            setup_tp = price - min_rr * risk
            tp1 = (price - scalp_r * risk) if scalp_on else setup_tp
            tp2 = setup_tp

        if risk <= 0:
            paper_pipeline.inc_reject("ZERO_RISK")
            return False
        rr = abs(setup_tp - price) / risk
        if rr < min_rr:
            paper_pipeline.inc("rejected_rr")
            paper_pipeline.inc_reject("RISK_REWARD")
            await paper_journal.log_candidate(
                symbol=symbol,
                side=side,
                taken=False,
                signal_price=price,
                score=qscore,
                regime=f"rsi={rsi:.1f}",
                features={"rsi": rsi, "ext_pct": ext_pct, "rr": rr},
                reject_reason=f"R:R {rr:.2f} < min",
                strategy="rsi_extension_v1",
            )
            shadow_research.record_evaluation(
                symbol=symbol,
                side=side,
                mark_price=price,
                score=qscore,
                required_score=min_score,
                qualified=False,
                failed_gates=["risk_reward"],
                features={
                    "rsi": rsi,
                    "ext_pct": ext_pct,
                    "rr": rr,
                    "atr": atr,
                    "tier": tier,
                },
                regime=f"rsi={rsi:.1f};{tier}",
                stop=stop,
                tp1=tp1,
                tp2=tp2,
                notes=f"R:R {rr:.2f}",
            )
            return False
        paper_pipeline.inc("rr_pass")
        paper_pipeline.inc("qualified")
        paper_pipeline.last_qualified_at = datetime.now(timezone.utc).isoformat()
        paper_pipeline.inc("paper_open_attempted")

        counts_for_live = tier in ("major", "alt")

        tid = await paper_journal.open_trade(
            symbol=symbol,
            side=side,
            entry=price,
            signal_price=price,
            stop=stop,
            tp1=tp1,
            tp2=tp2,
            risk_usd=float(settings.perp_micro_risk_usd),
            regime=f"rsi={rsi:.1f};q={qscore:.0f};{tier}",
            notes=f"ext={ext_pct:.2f}%|{reason}|live={counts_for_live}",
            source="perp_micro",
            strategy="rsi_extension_v1",
            signal_score=qscore,
            features={
                "rsi": rsi,
                "ext_pct": ext_pct,
                "sma20": sma20,
                "atr": atr,
                "vol": self._vol_map.get(symbol),
                "oi": self._oi_map.get(symbol),
                "rr": rr,
                "setup_rr": min_rr,
                "exit_mode": "SCALP" if scalp_on else "SETUP_18",
                "scalp_tp_r": scalp_r,
                "be_after_r": be_after,
            },
            tier=tier,
            counts_for_live=counts_for_live,
        )
        if not tid:
            paper_pipeline.inc("paper_open_failed")
            return False
        paper_pipeline.inc("paper_open_succeeded")
        paper_pipeline.last_paper_open_at = datetime.now(timezone.utc).isoformat()
        await paper_journal.log_candidate(
            symbol=symbol,
            side=side,
            taken=True,
            signal_price=price,
            score=qscore,
            regime=f"rsi={rsi:.1f}",
            features={"rsi": rsi, "ext_pct": ext_pct},
            strategy="rsi_extension_v1",
        )
        shadow_research.record_evaluation(
            symbol=symbol,
            side=side,
            mark_price=price,
            score=qscore,
            required_score=min_score,
            qualified=True,
            failed_gates=[],
            features={
                "rsi": rsi,
                "ext_pct": ext_pct,
                "sma20": sma20,
                "atr": atr,
                "vol": self._vol_map.get(symbol),
                "oi": self._oi_map.get(symbol),
                "tier": tier,
            },
            regime=f"rsi={rsi:.1f};{tier}",
            stop=stop,
            tp1=setup_tp,
            tp2=tp2,
            notes="QUALIFIED paper path",
        )

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
            "counts_for_live": counts_for_live,
            "qscore": qscore,
            "mfe_r": 0.0,
            "mae_r": 0.0,
            "exit_mode": "SCALP" if scalp_on else "SETUP_18",
            "scalp_tp_r": scalp_r,
            "be_after_r": be_after,
            "be_armed": False,
            "setup_rr": min_rr,
            "risk_price": risk,
        }
        self._cooldowns[symbol] = datetime.now(timezone.utc)

        from app.alerts.discord import is_discord_ready, send_discord_alert

        if is_discord_ready():
            paper_pipeline.inc("discord_trigger_attempted")
            live_tag = "live-stat" if counts_for_live else "experimental"
            dm_ok = await send_discord_alert(
                symbol=symbol,
                title=f"Paper TRIGGER · {symbol} · {side}",
                description=(
                    f"**{symbol} · {side}** (paper · {tier} · **{live_tag}**)\n"
                    f"Entry `{price}` · Stop `{stop:.6g}` · Scalp TP `{tp1:.6g}` (1.0R)\n"
                    f"RSI `{rsi:.1f}` · ext `{ext_pct:.2f}%` · setup R:R `{rr:.1f}` · Q `{qscore:.0f}`\n"
                    f"Manage: bank 1.0R · BE after +0.5R MFE. Entry gates unchanged.\n"
                    f"_{reason}_\n_Paper only. No live execution._"
                ),
                price=price,
                severity="MEDIUM",
                opportunity=min(95, int(qscore)),
                confidence=min(90, int(50 + qscore / 3)),
                risk=45 if tier == "major" else (50 if tier == "alt" else 60),
            )
            if dm_ok:
                paper_pipeline.inc("discord_trigger_delivered")
                paper_pipeline.last_discord_alert_at = datetime.now(timezone.utc).isoformat()
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

    def _prepare_exit_levels(self, p: Dict[str, Any]) -> None:
        """Entry filters stay 1.8R geometry. Paper management may scalp."""
        from app.core.config import get_settings

        settings = get_settings()
        entry = float(p.get("entry") or 0)
        side = str(p.get("side") or "").upper()
        initial_stop = float(p.get("initial_stop") or p.get("stop") or 0)
        p["initial_stop"] = initial_stop
        risk = abs(entry - initial_stop) or 1e-12
        p["risk_price"] = float(p.get("risk_price") or risk)
        mode = str(p.get("exit_mode") or "").upper()
        if not mode:
            mode = "SCALP" if bool(getattr(settings, "perp_micro_scalp_enabled", True)) else "SETUP_18"
        p["exit_mode"] = "SETUP_18" if mode in ("SETUP_18", "SETUP18", "LEGACY") else "SCALP"
        if p.get("working_stop") is None:
            p["working_stop"] = initial_stop
        if p["exit_mode"] == "SETUP_18":
            return
        scalp_r = float(p.get("scalp_tp_r") or 0) or float(getattr(settings, "perp_micro_scalp_tp_r", 1.0) or 1.0)
        p["scalp_tp_r"] = scalp_r
        if p.get("be_after_r") is None:
            p["be_after_r"] = float(getattr(settings, "perp_micro_be_after_r", 0.5) or 0.0)
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
                    mark = float(p.get("mark") or p.get("entry") or 0)
                    p["stale_quote"] = True
                    p["lifecycle"] = "MARKET_DATA_UNAVAILABLE"
                    log.warning("Open paper missing live quote", symbol=sym, trade_id=tid, mark=mark)
                    p["mark"] = mark
                    continue
                mark = float(px)
                p["stale_quote"] = False
                p["lifecycle"] = "MANAGED"
                p["mark"] = mark
                paper_journal.update_excursion(tid, mark)
                jopen = paper_journal._open.get(tid, {})
                p["mfe_r"] = jopen.get("mfe_r", p.get("mfe_r", 0))
                p["mae_r"] = jopen.get("mae_r", p.get("mae_r", 0))
                if jopen.get("be_armed"):
                    p["be_armed"] = True
                if jopen.get("working_stop") is not None:
                    p["working_stop"] = jopen.get("working_stop")

                self._prepare_exit_levels(p)
                side, entry = p["side"], float(p["entry"])
                initial_stop = float(p.get("initial_stop") or p.get("stop") or 0)
                risk = abs(entry - initial_stop) or 1e-12
                mfe = float(p.get("mfe_r") or 0)
                be_after = p.get("be_after_r")
                if be_after is None:
                    be_after = 99.0 if p.get("exit_mode") == "SETUP_18" else 0.5
                be_after = float(be_after)
                if (
                    p.get("exit_mode") == "SCALP"
                    and not p.get("be_armed")
                    and be_after > 0
                    and mfe + 1e-12 >= be_after
                ):
                    p["be_armed"] = True
                    p["working_stop"] = entry
                    try:
                        paper_journal.note_be_armed(tid, entry)
                    except Exception:
                        pass

                working_stop = float(p.get("working_stop") or initial_stop)
                p["stop"] = working_stop
                tp1 = float(p["tp1"])
                hit_stop = mark <= working_stop if side == "LONG" else mark >= working_stop
                hit_tp = mark >= tp1 if side == "LONG" else mark <= tp1
                if not hit_stop and not hit_tp:
                    continue
                p["lifecycle"] = "EXIT_TRIGGERED"
                if hit_stop:
                    be = bool(p.get("be_armed")) and abs(working_stop - entry) <= max(1e-12, abs(entry) * 1e-9)
                    if be:
                        result, exit_px, pnl_r = "BE", entry, 0.0
                    else:
                        result, exit_px, pnl_r = "STOP", initial_stop, -1.0
                else:
                    result, exit_px = "TP1", tp1
                    pnl_r = abs(tp1 - entry) / risk
                jmem = paper_journal._open.get(tid)
                if jmem is not None:
                    jmem["exit_mode"] = p.get("exit_mode")
                    jmem["be_armed"] = bool(p.get("be_armed"))
                    jmem["working_stop"] = p.get("working_stop")
                close_row = await paper_journal.close_trade(
                    tid, exit_price=exit_px, result=result, pnl_r=pnl_r
                )
                p["lifecycle"] = "CLOSED"
                to_close.append(tid)
                self._cooldowns[sym] = datetime.now(timezone.utc)
                mfe = close_row.get("mfe_r", 0)
                mae = close_row.get("mae_r", 0)
                try:
                    from app.alerts.discord import is_discord_ready, send_discord_alert

                    if is_discord_ready():
                        live_tag = "live-stat" if p.get("counts_for_live") else "experimental"
                        await send_discord_alert(
                            symbol=sym,
                            title=f"Paper {result} · {sym} · {side}",
                            description=(
                                f"**{sym}** {side} closed **{result}**\n"
                                f"Entry `{entry}` → Exit `{exit_px:.6g}` · **{pnl_r:+.2f}R**\n"
                                f"MFE `{mfe:+.2f}R` · MAE `{mae:+.2f}R`\n"
                                f"Tier `{p.get('tier', '?')}` · **{live_tag}**\n_Paper only._"
                            ),
                            price=exit_px,
                            severity="LOW" if result == "TP1" else "MEDIUM",
                            opportunity=60,
                            confidence=60,
                            risk=40,
                        )
                except Exception as e:
                    log.warning("paper close discord failed; trade already persisted", error=str(e)[:160])
                log.info(
                    "Paper CLOSE",
                    trade_id=tid,
                    symbol=sym,
                    result=result,
                    pnl_r=pnl_r,
                    mfe_r=mfe,
                    mae_r=mae,
                )
            except Exception as e:
                p["lifecycle"] = "ERROR_REQUIRES_REVIEW"
                p["error"] = str(e)[:160]
                log.warning("open paper manage failed; left OPEN for review", trade_id=tid, error=str(e)[:160])
        for tid in to_close:
            self._open.pop(tid, None)


perp_micro_coach = PerpMicroCoach()