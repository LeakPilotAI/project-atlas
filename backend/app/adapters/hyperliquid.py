from datetime import datetime, timezone
from typing import List, Optional
import time

import httpx

from app.adapters.base import BaseExchangeAdapter, NormalizedTicker
from app.core.logging import get_logger

logger = get_logger("hyperliquid")


class HyperliquidAdapter(BaseExchangeAdapter):
    name = "hyperliquid"
    BASE_URL = "https://api.hyperliquid.xyz/info"

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        logger.info("Hyperliquid HTTP client created")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Hyperliquid HTTP client closed")

    async def get_all_tickers(self) -> List[NormalizedTicker]:
        if not self._client:
            await self.connect()

        try:
            meta_resp = await self._client.post(
                self.BASE_URL,
                json={"type": "metaAndAssetCtxs"},
            )
            meta_resp.raise_for_status()
            data = meta_resp.json()

            if not isinstance(data, list) or len(data) < 2:
                logger.warning("Unexpected Hyperliquid meta response format")
                return []

            universe = data[0].get("universe", [])
            contexts = data[1]

            tickers: List[NormalizedTicker] = []
            now = datetime.now(timezone.utc)

            for i, asset in enumerate(universe):
                if i >= len(contexts):
                    break

                ctx = contexts[i]
                symbol = asset.get("name")
                if not symbol:
                    continue

                try:
                    price = float(ctx.get("markPx") or ctx.get("midPx") or 0)
                    volume = float(ctx.get("dayNtlVlm") or 0)
                    oi = float(ctx.get("openInterest") or 0)
                    funding = (
                        float(ctx.get("funding") or 0)
                        if ctx.get("funding") is not None
                        else None
                    )

                    tickers.append(
                        NormalizedTicker(
                            symbol=symbol,
                            exchange="hyperliquid",
                            price=price,
                            volume_24h=volume,
                            open_interest=oi,
                            funding_rate=funding,
                            timestamp=now,
                            raw=ctx,
                        )
                    )
                except (TypeError, ValueError) as e:
                    logger.debug("Skipping asset", symbol=symbol, error=str(e))
                    continue

            logger.info("Fetched tickers", count=len(tickers))
            return tickers

        except Exception as e:
            logger.error("Failed to fetch tickers", error=str(e))
            return []

    async def get_candles(
        self, symbol: str, interval: str = "5m", limit: int = 100
    ) -> List[dict]:
        if not self._client:
            await self.connect()

        try:
            end_time = int(time.time() * 1000)
            interval_ms = {
                "1m": 60_000,
                "5m": 300_000,
                "15m": 900_000,
                "1h": 3_600_000,
                "4h": 14_400_000,
            }.get(interval, 300_000)

            start_time = end_time - (limit * interval_ms)

            payload = {
                "type": "candleSnapshot",
                "req": {
                    "coin": symbol,
                    "interval": interval,
                    "startTime": start_time,
                    "endTime": end_time,
                },
            }

            resp = await self._client.post(self.BASE_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, list):
                logger.warning(
                    "Unexpected candle response",
                    symbol=symbol,
                    type=type(data).__name__,
                )
                return []

            candles = []
            for c in data:
                try:
                    candles.append(
                        {
                            "open_time": int(c["t"]),
                            "open": float(c["o"]),
                            "high": float(c["h"]),
                            "low": float(c["l"]),
                            "close": float(c["c"]),
                            "volume": float(c["v"]),
                        }
                    )
                except (KeyError, TypeError, ValueError):
                    continue

            # Sort oldest → newest
            candles.sort(key=lambda x: x["open_time"])
            logger.info(
                "Fetched candles",
                symbol=symbol,
                interval=interval,
                count=len(candles),
            )
            return candles

        except Exception as e:
            logger.error("Failed to fetch candles", symbol=symbol, error=str(e))
            return []