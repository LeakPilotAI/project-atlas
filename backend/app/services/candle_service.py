from datetime import datetime, timezone
from typing import List

from sqlalchemy.dialects.postgresql import insert

from app.adapters.registry import registry
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.candle import Candle

logger = get_logger("candle_service")


async def store_candles(symbol: str, timeframe: str = "5m", limit: int = 50) -> int:
    """
    Fetch candles from Hyperliquid and upsert them into the database.
    Returns number of candles stored.
    """
    adapter = registry.get("hyperliquid")
    if not adapter:
        return 0

    raw_candles = await adapter.get_candles(symbol, interval=timeframe, limit=limit)
    if not raw_candles:
        return 0

    async with AsyncSessionLocal() as session:
        for c in raw_candles:
            open_time = datetime.fromtimestamp(c["open_time"] / 1000, tz=timezone.utc)

            stmt = insert(Candle).values(
                symbol=symbol,
                exchange="hyperliquid",
                timeframe=timeframe,
                open_time=open_time,
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=c["volume"],
            ).on_conflict_do_update(
                index_elements=["symbol", "timeframe", "open_time"],
                set_={
                    "open": c["open"],
                    "high": c["high"],
                    "low": c["low"],
                    "close": c["close"],
                    "volume": c["volume"],
                },
            )
            await session.execute(stmt)

        await session.commit()

    logger.info("Candles stored", symbol=symbol, timeframe=timeframe, count=len(raw_candles))
    return len(raw_candles)


async def get_recent_closes(symbol: str, timeframe: str = "5m", limit: int = 30) -> List[float]:
    """Helper to get recent close prices from DB."""
    from sqlalchemy import select, desc

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Candle.close)
            .where(Candle.symbol == symbol, Candle.timeframe == timeframe)
            .order_by(desc(Candle.open_time))
            .limit(limit)
        )
        closes = [row[0] for row in result.all()]
        closes.reverse()  # oldest → newest
        return closes