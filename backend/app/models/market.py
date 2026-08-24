from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    exchange: Mapped[str] = mapped_column(String(32), default="hyperliquid", index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    open_interest: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    funding_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )