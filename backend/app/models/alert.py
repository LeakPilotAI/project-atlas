from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, Text, Boolean, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="medium")

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Scores
    opportunity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Context
    price_at_alert: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    indicators: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Delivery
    sent_discord: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_telegram: Mapped[bool] = mapped_column(Boolean, default=False)

    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_alerts_symbol_fired", "market_symbol", "fired_at"),
        Index("ix_alerts_type", "alert_type"),
    )