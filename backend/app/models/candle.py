from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Candle(Base):
    __tablename__ = "candles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    exchange: Mapped[str] = mapped_column(String(32), default="hyperliquid")
    interval: Mapped[str] = mapped_column(String(8), default="5m")  # 1m / 5m / 15m / 1h
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_candles_symbol_interval_ts", "symbol", "interval", "ts", unique=True),
    )