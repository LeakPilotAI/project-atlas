from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, Float, Integer, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin


class Market(Base, TimestampMixin):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False, default="axiom")
    base_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False, default="USDT")
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_perp: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Market metadata
    tick_size: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lot_size: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_leverage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Status
    last_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    open_interest: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_markets_exchange_symbol", "exchange", "symbol"),
        Index("ix_markets_active", "is_active"),
    )