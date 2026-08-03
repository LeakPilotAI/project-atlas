from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin


class Opportunity(Base, TimestampMixin):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), default="hyperliquid")

    # Original anomaly
    initial_alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    initial_severity: Mapped[str] = mapped_column(String(16), nullable=False)
    initial_price: Mapped[float] = mapped_column(Float, nullable=False)
    initial_message: Mapped[str] = mapped_column(Text, nullable=False)

    # Lifecycle
    status: Mapped[str] = mapped_column(String(32), default="monitoring")
    # monitoring | long_signal | short_signal | neutral | expired | invalidated

    recommendation: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # LONG | SHORT | NONE
    recommendation_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recommendation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Tracking window
    monitored_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Context
    indicators_at_detection: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    final_indicators: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)