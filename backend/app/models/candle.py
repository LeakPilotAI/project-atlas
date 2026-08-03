from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Candle(Base):
    __tablename__ = "candles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False, default="hyperliquid")
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)  # 1m, 5m, 15m, 1h
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_candles_symbol_tf_time", "symbol", "timeframe", "open_time", unique=True),
        Index("ix_candles_open_time", "open_time"),
    )