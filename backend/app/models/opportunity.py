from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    exchange: Mapped[str] = mapped_column(String(32), default="hyperliquid")
    bias: Mapped[str] = mapped_column(String(16), default="FLAT")  # LONG / SHORT / FLAT
    status: Mapped[str] = mapped_column(String(16), default="OPEN")  # OPEN / CLOSED / EXPIRED
    setup_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, default=50.0)
    entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tp1_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tp2_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    regime: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_opportunities_symbol_status", "symbol", "status"),
    )