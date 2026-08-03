import asyncio
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from app.adapters.registry import registry
from app.analytics.anomaly import detect_anomalies
from app.analytics.indicators import calculate_basic_indicators
from app.alerts.dispatcher import dispatch_alert
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.market import Market

logger = get_logger("scanner")
settings = get_settings()


class MarketScanner:
    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        # Simple in-memory history for demo purposes (will be replaced by DB candles later)
        self._price_history: dict[str, list[float]] = {}
        self._volume_history: dict[str, list[float]] = {}

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Market scanner started", interval=settings.scan_interval_seconds)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Market scanner stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.scan_once()
            except Exception as e:
                logger.error("Scanner cycle failed", error=str(e))
            await asyncio.sleep(settings.scan_interval_seconds)

    async def scan_once(self) -> None:
        adapter = registry.get("hyperliquid")
        if not adapter:
            logger.warning("No Hyperliquid adapter available")
            return

        tickers = await adapter.get_all_tickers()
        if not tickers:
            logger.warning("No tickers received")
            return

        async with AsyncSessionLocal() as session:
            for t in tickers:
                # Upsert market
                stmt = insert(Market).values(
                    symbol=t.symbol,
                    exchange=t.exchange,
                    base_asset=t.symbol,
                    quote_asset="USDC",
                    is_active=True,
                    is_perp=True,
                    last_price=t.price,
                    volume_24h=t.volume_24h,
                    open_interest=t.open_interest,
                    last_updated=datetime.now(timezone.utc),
                ).on_conflict_do_update(
                    index_elements=["symbol"],
                    set_={
                        "last_price": t.price,
                        "volume_24h": t.volume_24h,
                        "open_interest": t.open_interest,
                        "last_updated": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    },
                )
                await session.execute(stmt)

                # Maintain simple rolling history (last 50 points)
                if t.symbol not in self._price_history:
                    self._price_history[t.symbol] = []
                    self._volume_history[t.symbol] = []

                self._price_history[t.symbol].append(t.price)
                self._volume_history[t.symbol].append(t.volume_24h or 0.0)

                # Keep only last 50
                self._price_history[t.symbol] = self._price_history[t.symbol][-50:]
                self._volume_history[t.symbol] = self._volume_history[t.symbol][-50:]

                # Calculate indicators + detect anomalies
                closes = self._price_history[t.symbol]
                volumes = self._volume_history[t.symbol]

                if len(closes) >= 5:  # need at least a few points
                    ind = calculate_basic_indicators(
                        symbol=t.symbol,
                        closes=closes,
                        volumes=volumes,
                    )
                    signals = detect_anomalies(ind)
                    for signal in signals:
                        await dispatch_alert(signal)

            await session.commit()

        logger.info(
            "Scan complete",
            markets=len(tickers),
            sample=tickers[0].symbol if tickers else None,
        )


# Global instance
scanner = MarketScanner()