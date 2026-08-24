"""Hyperliquid adapter — REST info + optional WebSocket allMids."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

try:
    import websockets
except ImportError:  # pragma: no cover
    websockets = None  # type: ignore

from app.core.logging import get_logger

logger = get_logger("hyperliquid")

INFO_URL = "https://api.hyperliquid.xyz/info"
WS_URL = "wss://api.hyperliquid.xyz/ws"


@dataclass
class Ticker:
    symbol: str
    exchange: str = "hyperliquid"
    price: float = 0.0
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume_24h: float = 0.0
    open_interest: float = 0.0
    funding_rate: Optional[float] = None
    timestamp: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class HyperliquidAdapter:
    name = "hyperliquid"

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._connected = False
        self._universe_names: list[str] = []
        self._mids: dict[str, float] = {}
        self._ws_task: Optional[asyncio.Task] = None
        self._ws_running = False

    async def connect(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={"Content-Type": "application/json"},
            )
            logger.info("Hyperliquid HTTP client created")
        self._connected = True
        await self.refresh_universe()
        await self.start_mids_ws()

    async def close(self) -> None:
        self._ws_running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False

    async def _post(self, body: dict[str, Any]) -> Any:
        if not self._client:
            await self.connect()
        assert self._client is not None
        r = await self._client.post(INFO_URL, json=body)
        r.raise_for_status()
        return r.json()

    # ── Universe / allowlist validation ──────────────────────────────

    async def refresh_universe(self) -> list[str]:
        data = await self._post({"type": "meta"})
        universe = data.get("universe") if isinstance(data, dict) else None
        names: list[str] = []
        if isinstance(universe, list):
            for item in universe:
                if isinstance(item, dict) and item.get("name"):
                    names.append(str(item["name"]))
        self._universe_names = names
        logger.info("Hyperliquid universe loaded", count=len(names))
        return names

    def universe_names(self) -> list[str]:
        return list(self._universe_names)

    def validate_allowlist(self, allowlist: list[str]) -> dict[str, Any]:
        """
        Compare config allowlist to live meta names.
        Returns {matched, unknown, suggestions}.
        """
        live = {n.upper(): n for n in self._universe_names}
        matched: list[str] = []
        unknown: list[str] = []
        suggestions: dict[str, list[str]] = {}

        for raw in allowlist:
            key = raw.strip()
            if not key:
                continue
            up = key.upper()
            if up in live:
                matched.append(live[up])
                continue
            # fuzzy: substring / strip xyz suffix
            cands = [
                n
                for n in self._universe_names
                if up in n.upper() or n.upper() in up or up.replace("XYZ", "") in n.upper()
            ]
            unknown.append(key)
            if cands:
                suggestions[key] = cands[:8]
            else:
                suggestions[key] = []

        logger.info(
            "Allowlist validation",
            matched=len(matched),
            unknown=unknown,
            suggestions={k: v for k, v in suggestions.items() if v},
        )
        for u in unknown:
            logger.warning(
                "Allowlist symbol not on Hyperliquid meta",
                symbol=u,
                suggestions=suggestions.get(u, []),
            )
        return {
            "matched": matched,
            "unknown": unknown,
            "suggestions": suggestions,
            "live_count": len(self._universe_names),
        }

    # ── Tickers (metaAndAssetCtxs) ───────────────────────────────────

    async def get_all_tickers(self) -> list[Ticker]:
        data = await self._post({"type": "metaAndAssetCtxs"})
        if not isinstance(data, list) or len(data) < 2:
            logger.warning("Unexpected metaAndAssetCtxs shape")
            return []

        meta, ctxs = data[0], data[1]
        universe = meta.get("universe") if isinstance(meta, dict) else []
        if not isinstance(universe, list) or not isinstance(ctxs, list):
            return []

        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        out: list[Ticker] = []
        for i, asset in enumerate(universe):
            if i >= len(ctxs):
                break
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "")
            if not name:
                continue
            ctx = ctxs[i] if isinstance(ctxs[i], dict) else {}

            mark = ctx.get("markPx") or ctx.get("midPx") or "0"
            mid = ctx.get("midPx")
            # Prefer live WS mid when present
            ws_mid = self._mids.get(name)
            try:
                price = float(ws_mid if ws_mid is not None else mark)
            except (TypeError, ValueError):
                price = 0.0

            try:
                vol = float(ctx.get("dayNtlVlm") or 0)
            except (TypeError, ValueError):
                vol = 0.0
            try:
                oi = float(ctx.get("openInterest") or 0)
            except (TypeError, ValueError):
                oi = 0.0
            funding = None
            try:
                if ctx.get("funding") is not None:
                    funding = float(ctx["funding"])
            except (TypeError, ValueError):
                funding = None

            out.append(
                Ticker(
                    symbol=name,
                    price=price,
                    volume_24h=vol,
                    open_interest=oi,
                    funding_rate=funding,
                    timestamp=now,
                    raw=dict(ctx),
                )
            )
        logger.info("Fetched tickers", count=len(out))
        return out

    # ── Candles ──────────────────────────────────────────────────────

    async def get_candles(
        self,
        symbol: str,
        interval: str = "15m",
        lookback: int = 96,
    ) -> list[dict[str, Any]]:
        # Approximate start from interval minutes
        mins = {
            "1m": 1,
            "3m": 3,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "2h": 120,
            "4h": 240,
            "8h": 480,
            "12h": 720,
            "1d": 1440,
        }.get(interval, 15)
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - lookback * mins * 60 * 1000

        data = await self._post(
            {
                "type": "candleSnapshot",
                "req": {
                    "coin": symbol,
                    "interval": interval,
                    "startTime": start_ms,
                    "endTime": end_ms,
                },
            }
        )
        if not isinstance(data, list):
            return []

        candles: list[dict[str, Any]] = []
        for c in data:
            if not isinstance(c, dict):
                continue
            try:
                candles.append(
                    {
                        "time": int(c.get("t") or 0),
                        "open": float(c.get("o") or 0),
                        "high": float(c.get("h") or 0),
                        "low": float(c.get("l") or 0),
                        "close": float(c.get("c") or 0),
                        "volume": float(c.get("v") or 0),
                        "n": int(c.get("n") or 0),
                    }
                )
            except (TypeError, ValueError):
                continue
        return candles

    # ── Funding history ──────────────────────────────────────────────

    async def get_funding_history(
        self,
        symbol: str,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """
        POST {"type":"fundingHistory","coin":symbol,"startTime":ms}
        Returns list of {time, fundingRate, ...}.
        """
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - hours * 3600 * 1000
        try:
            data = await self._post(
                {
                    "type": "fundingHistory",
                    "coin": symbol,
                    "startTime": start_ms,
                }
            )
        except Exception as e:
            logger.warning("fundingHistory failed", symbol=symbol, error=str(e))
            return []

        if not isinstance(data, list):
            return []

        rows: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                rows.append(
                    {
                        "time": int(item.get("time") or 0),
                        "funding_rate": float(
                            item.get("fundingRate")
                            or item.get("funding_rate")
                            or item.get("funding")
                            or 0
                        ),
                        "raw": item,
                    }
                )
            except (TypeError, ValueError):
                continue
        return rows

    async def funding_bias(self, symbol: str, hours: int = 8) -> dict[str, Any]:
        """
        Aggregate recent funding for long/short lean.
        Positive cumulative → crowded long → short bias.
        Negative → crowded short → long bias.
        """
        hist = await self.get_funding_history(symbol, hours=hours)
        if not hist:
            return {
                "symbol": symbol,
                "samples": 0,
                "sum_rate": 0.0,
                "avg_rate": 0.0,
                "lean": "neutral",
                "score_delta": 0.0,
            }

        rates = [h["funding_rate"] for h in hist]
        s = sum(rates)
        avg = s / len(rates)
        lean = "neutral"
        delta = 0.0
        # Hyperliquid funding is typically small decimals per interval
        if s >= 0.0005 or avg >= 0.00005:
            lean = "short"  # longs paying → fade longs
            delta = min(12.0, 4.0 + abs(s) * 5000)
        elif s <= -0.0005 or avg <= -0.00005:
            lean = "long"
            delta = min(12.0, 4.0 + abs(s) * 5000)

        return {
            "symbol": symbol,
            "samples": len(rates),
            "sum_rate": round(s, 8),
            "avg_rate": round(avg, 8),
            "lean": lean,
            "score_delta": round(delta, 2),
        }

    # ── WebSocket allMids ────────────────────────────────────────────

    async def start_mids_ws(self) -> None:
        if websockets is None:
            logger.warning("websockets package not installed — allMids WS disabled")
            return
        if self._ws_task and not self._ws_task.done():
            return
        self._ws_running = True
        self._ws_task = asyncio.create_task(self._mids_loop())
        logger.info("Hyperliquid allMids WebSocket starting")

    async def _mids_loop(self) -> None:
        backoff = 2.0
        while self._ws_running:
            try:
                async with websockets.connect(
                    WS_URL,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=8_000_000,
                ) as ws:
                    await ws.send(
                        json.dumps(
                            {
                                "method": "subscribe",
                                "subscription": {"type": "allMids"},
                            }
                        )
                    )
                    logger.info("Subscribed to allMids")
                    backoff = 2.0
                    async for raw in ws:
                        if not self._ws_running:
                            break
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        channel = msg.get("channel")
                        data = msg.get("data")
                        if channel == "allMids" and isinstance(data, dict):
                            mids = data.get("mids") if "mids" in data else data
                            if isinstance(mids, dict):
                                for k, v in mids.items():
                                    try:
                                        self._mids[str(k)] = float(v)
                                    except (TypeError, ValueError):
                                        continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("allMids WS error — reconnecting", error=str(e))
                await asyncio.sleep(backoff)
                backoff = min(60.0, backoff * 1.5)

    def get_mid(self, symbol: str) -> Optional[float]:
        return self._mids.get(symbol)