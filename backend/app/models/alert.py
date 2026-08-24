from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market_symbol: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    opportunity: Mapped[int] = mapped_column(Integer, default=50)
    confidence: Mapped[int] = mapped_column(Integer, default=50)
    risk: Mapped[int] = mapped_column(Integer, default=50)
    source: Mapped[str] = mapped_column(String(32), default="scanner")
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (
        Index("ix_alerts_symbol_fired", "market_symbol", "fired_at"),
    )