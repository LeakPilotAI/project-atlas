"""Axiom perpetual market adapter.

Axiom's perpetuals product is powered by Hyperliquid. This adapter expands Atlas market
coverage beyond the native Hyperliquid perp dex to HIP-3 builder-deployed dexes (where
stock/index/commodity perps live), while preserving venue-aligned mark prices.

Manual/research use only. No order submission lives here.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import httpx

from app.adapters.hyperliquid import Ticker
from app.core.logging import get_logger

log = get_logger("axiom_perps")
INFO_URL = "https://api.hyperliquid.xyz/info"


class AxiomPerpAdapter:
    """Read-only market-data adapter for the perp markets Axiom can surface."""

    name = "axiom_perps"

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._connected = False
        self._universe_names: list[str] = []
        self._dex_names: list[str] = [""]

    async def connect(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={"Content-Type": "application/json"},
            )
        self._connected = True
        await self.refresh_universe()
        log.info("Axiom perp market adapter connected", markets=len(self._universe_names), dexes=len(self._dex_names))

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._connected = False

    async def _post(self, body: dict[str, Any]) -> Any:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={"Content-Type": "application/json"},
            )
        response = await self._client.post(INFO_URL, json=body)
        response.raise_for_status()
        return response.json()

    async def _perp_dex_names(self) -> list[str]:
        names = [""]
        try:
            payload = await self._post({"type": "perpDexs"})
        except Exception as exc:
            log.warning("HIP-3 dex discovery failed; native perps remain available", error=str(exc)[:160])
            return names
        if isinstance(payload, list):
            for row in payload:
                if isinstance(row, dict) and row.get("name"):
                    name = str(row["name"]).strip()
                    if name and name not in names:
                        names.append(name)
        return names

    @staticmethod
    def _qualified_name(dex: str, raw_name: str) -> str:
        name = str(raw_name or "").strip()
        if not dex or ":" in name:
            return name
        return f"{dex}:{name}"

    async def refresh_universe(self) -> list[str]:
        dexes = await self._perp_dex_names()
        names: list[str] = []
        healthy_dexes: list[str] = []
        for dex in dexes:
            try:
                meta = await self._post({"type": "meta", "dex": dex})
            except Exception as exc:
                log.debug("Perp dex meta skipped", dex=dex or "native", error=str(exc)[:120])
                continue
            universe = meta.get("universe") if isinstance(meta, dict) else None
            if not isinstance(universe, list):
                continue
            healthy_dexes.append(dex)
            for row in universe:
                if isinstance(row, dict) and row.get("name"):
                    q = self._qualified_name(dex, str(row["name"]))
                    if q and q not in names:
                        names.append(q)
        self._dex_names = healthy_dexes or [""]
        self._universe_names = names
        return list(names)

    def universe_names(self) -> list[str]:
        return list(self._universe_names)

    async def get_all_tickers(self) -> list[Ticker]:
        if not self._dex_names:
            await self.refresh_universe()
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        out: list[Ticker] = []
        for dex in list(self._dex_names):
            try:
                payload = await self._post({"type": "metaAndAssetCtxs", "dex": dex})
            except Exception as exc:
                log.debug("Perp dex ticker snapshot skipped", dex=dex or "native", error=str(exc)[:120])
                continue
            if not isinstance(payload, list) or len(payload) < 2:
                continue
            meta, ctxs = payload[0], payload[1]
            universe = meta.get("universe") if isinstance(meta, dict) else []
            if not isinstance(universe, list) or not isinstance(ctxs, list):
                continue
            for idx, asset in enumerate(universe):
                if idx >= len(ctxs) or not isinstance(asset, dict):
                    break
                raw_name = str(asset.get("name") or "")
                if not raw_name:
                    continue
                symbol = self._qualified_name(dex, raw_name)
                ctx = ctxs[idx] if isinstance(ctxs[idx], dict) else {}
                try:
                    price = float(ctx.get("markPx") or ctx.get("midPx") or 0.0)
                except (TypeError, ValueError):
                    price = 0.0
                try:
                    volume = float(ctx.get("dayNtlVlm") or 0.0)
                except (TypeError, ValueError):
                    volume = 0.0
                try:
                    oi = float(ctx.get("openInterest") or 0.0)
                except (TypeError, ValueError):
                    oi = 0.0
                funding = None
                try:
                    if ctx.get("funding") is not None:
                        funding = float(ctx["funding"])
                except (TypeError, ValueError):
                    funding = None
                out.append(Ticker(symbol=symbol, exchange="axiom_perps", price=price, volume_24h=volume, open_interest=oi, funding_rate=funding, timestamp=now, raw={"dex": dex or "native", **ctx}))
        return out

    async def get_candles(self, symbol: str, interval: str = "15m", lookback: int = 96) -> list[dict[str, Any]]:
        mins = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120, "4h": 240, "8h": 480, "12h": 720, "1d": 1440}.get(interval, 15)
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - lookback * mins * 60 * 1000
        payload = await self._post({"type": "candleSnapshot", "req": {"coin": symbol, "interval": interval, "startTime": start_ms, "endTime": end_ms}})
        if not isinstance(payload, list):
            return []
        candles: list[dict[str, Any]] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            try:
                candles.append({"time": int(row.get("t") or 0), "open": float(row.get("o") or 0), "high": float(row.get("h") or 0), "low": float(row.get("l") or 0), "close": float(row.get("c") or 0), "volume": float(row.get("v") or 0), "n": int(row.get("n") or 0)})
            except (TypeError, ValueError):
                continue
        return candles
